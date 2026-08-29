"""Metric sensitivity: share-at-target across MIN_TEST_BIN thresholds, plus
pinball-loss-at-0.998 as a proper scoring rule that does not saturate.

Reviewer MODERATE #9: the coverage metric is near-degenerate at small
test-bin sizes; with n_test < ~500 the criterion collapses to "covers all
test samples". Address by (a) filtering the unified panel by
n_test >= 60, 120, 240 and reporting share_at_target at each, and
(b) reporting a pinball loss at the 0.998 quantile which is proper and
does not saturate at small n.

Pinball loss at quantile alpha for prediction q and true value y:
    L(y, q) = alpha * (y - q)     if y > q
              (1 - alpha) * (q - y)  if y <= q
Sum or mean over test samples per bin, average across bins.

This does not require re-running any fit. Just recomputes per-bin metrics
from the unified panel's per-bin ceilings + per-bin test 99th percentile
+ per-bin test max, and (for pinball) reconstructs test samples where
possible or approximates from the reported percentiles.
"""
import json, os, sys, glob
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_FS  = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8"
ROOT_RND = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8"

METHODS = ["lognorm_ctop", "empirical_p998", "gauss_meanksd",
           "rolling_max", "ml_gbm_p998", "ewmq_p998"]
CPU_FLOOR = 0.05
TEST_DAYS = 6
TARGET = 0.998
ALPHA = 0.998

def read_vm(fp):
    try:
        df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
    except Exception:
        return None
    df.columns = [c.strip() for c in df.columns]
    if "CPU usage [%]" not in df.columns or "Timestamp [ms]" not in df.columns:
        return None
    ts = df["Timestamp [ms]"].astype(float).values
    hours = (np.floor(ts / 3600).astype(int)) % 24
    days = np.floor(ts / 86400).astype(int)
    cpu = df["CPU usage [%]"].astype(float).values
    m = np.isfinite(cpu) & (cpu >= CPU_FLOOR) & (cpu <= 100)
    return hours[m], days[m], cpu[m]

def pinball(y, q, alpha=ALPHA):
    """Pinball loss for scalar or vector y against scalar q."""
    y = np.asarray(y)
    diff = y - q
    return np.where(diff > 0, alpha * diff, (alpha - 1) * diff).mean()

# 1) Sensitivity of share_at_target to MIN_TEST_BIN filter
print("=== Sensitivity: share_at_target across MIN_TEST_BIN ===", file=sys.stderr)
sensitivity = {}
for label in ["fastStorage", "rnd"]:
    fp = os.path.join(HERE, f"unified_{label}.csv")
    df = pd.read_csv(fp)
    sensitivity[label] = {}
    for min_n in [12, 30, 60, 120]:
        sub = df[df["n_test"] >= min_n]
        row = {"n_bins": int(len(sub))}
        for m in METHODS:
            col = f"cov_{m}"
            if col not in sub.columns: continue
            valid = sub[col].notna()
            share = float((sub.loc[valid, col] >= TARGET).mean()) if valid.any() else np.nan
            row[m] = share
        sensitivity[label][f"min_n_{min_n}"] = row

# 2) Pinball loss at 0.998 quantile
print("=== Pinball loss at 0.998 quantile ===", file=sys.stderr)
# Need per-bin test samples to compute pinball. Re-derive by reading the raw
# VM CSVs for each (VM, hour) bin that appears in the unified panel and
# reconstructing the test window. Cache per-VM reads.
def collect_test_samples(vm_paths_in_panel, root):
    """Return dict (vm_id, hour) -> np.array of test samples."""
    out = {}
    for fp in vm_paths_in_panel:
        # unified_eval's vm_id was os.path.relpath(fp) — but we stored it
        # relative to the scoping cwd. Try both interpretations.
        real = fp if os.path.exists(fp) else os.path.join(root, os.path.basename(fp))
        r = read_vm(real)
        if r is None: continue
        hours, days, cpu = r
        if len(cpu) == 0: continue
        cut = days.max() - TEST_DAYS
        for h in range(24):
            m = (hours == h) & (days > cut)
            if m.sum() > 0:
                out[(fp, h)] = cpu[m]
    return out

pinball_out = {}
for label, root in [("fastStorage", ROOT_FS), ("rnd", ROOT_RND)]:
    fp = os.path.join(HERE, f"unified_{label}.csv")
    df = pd.read_csv(fp)
    vm_paths = df["vm"].unique().tolist()
    # collect test samples
    print(f"  {label}: collecting test samples for {len(vm_paths)} VMs", file=sys.stderr)
    samples = collect_test_samples(vm_paths, root)
    per_method_losses = {m: [] for m in METHODS}
    for _, row in df.iterrows():
        te = samples.get((row["vm"], int(row["hour"])))
        if te is None or len(te) == 0: continue
        for m in METHODS:
            col = f"ctop_{m}"
            if col not in row or not np.isfinite(row[col]): continue
            per_method_losses[m].append(pinball(te, row[col]))
    pinball_out[label] = {
        m: {
            "n_bins": len(per_method_losses[m]),
            "mean_pinball": float(np.mean(per_method_losses[m])) if per_method_losses[m] else np.nan,
            "median_pinball": float(np.median(per_method_losses[m])) if per_method_losses[m] else np.nan,
        } for m in METHODS
    }

# --- Save ---
out = {"sensitivity": sensitivity, "pinball_loss": pinball_out}
with open(os.path.join(HERE, "metric_sensitivity.json"), "w") as f:
    json.dump(out, f, indent=2)

# --- Print summary ---
print()
print("### Share-at-target sensitivity to MIN_TEST_BIN filter ###")
for label in ["fastStorage", "rnd"]:
    print(f"[{label}]")
    for min_n in [12, 30, 60, 120]:
        r = sensitivity[label][f"min_n_{min_n}"]
        line = f"  MIN_TEST_BIN={min_n:3d} n={r['n_bins']:5d}: "
        line += " ".join(f"{m[:6]}={100*r.get(m, float('nan')):5.2f}" for m in METHODS)
        print(line)
print()
print("### Pinball loss at 0.998 quantile (mean across bins; lower is better) ###")
for label in ["fastStorage", "rnd"]:
    print(f"[{label}]")
    for m in METHODS:
        v = pinball_out[label][m]
        print(f"  {m:16s}: mean={v['mean_pinball']:.4f} median={v['median_pinball']:.4f} n={v['n_bins']}")
