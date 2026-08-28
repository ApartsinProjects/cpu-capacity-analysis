"""Sizing-accuracy baselines on Bitbrains.

Per (VM, hour-of-day) bin, split the CPU time series into train (all samples
except the last 6 days) and test (last 6 days). Fit four sizing methods on
train and evaluate on test.

Methods:
  1. lognorm_ctop:    C_top = exp(mu + k * sigma) of log-normal fit on train
  2. empirical_p998:  99.8th percentile of train samples
  3. gauss_meanksd:   mean(train) + k * std(train)
  4. rolling_max:     max(train)

Target confidence: 0.998 (k = 3 for the Gaussian rule).

Metrics per method, aggregated across bins:
  - coverage: fraction of test samples <= predicted C_top
  - mean_ceiling: mean of predicted C_top across bins
  - relative_cost: mean of (C_top - test_p99) / test_p99, positive means the
    method reserves more headroom than the actual 99th percentile of test.
"""
import glob, os, random, sys, json
import numpy as np, pandas as pd
from scipy import stats

random.seed(42)
K = 3
TARGET_CONF = 0.998
MIN_TRAIN_BIN = 60
MIN_TEST_BIN = 12
CPU_FLOOR = 0.05

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
    mask = np.isfinite(cpu) & (cpu >= CPU_FLOOR) & (cpu <= 100)
    return ts[mask], hours[mask], days[mask], cpu[mask]


def methods(train):
    out = {}
    # log-normal
    try:
        s, loc, scale = stats.lognorm.fit(train, floc=0)
        mu = np.log(scale); sigma = s
        out["lognorm_ctop"] = float(np.exp(mu + K * sigma))
    except Exception:
        out["lognorm_ctop"] = float("nan")
    # empirical percentile
    out["empirical_p998"] = float(np.quantile(train, TARGET_CONF))
    # Gaussian
    out["gauss_meanksd"] = float(train.mean() + K * train.std())
    # rolling max
    out["rolling_max"] = float(train.max())
    return out


def process(files, split_days=6):
    rows = []
    for i, fp in enumerate(files):
        r = read_vm(fp)
        if r is None: continue
        ts, hours, days, cpu = r
        if len(cpu) < 200: continue
        day_max = days.max()
        train_mask = days <= (day_max - split_days)
        test_mask  = days >  (day_max - split_days)
        train_all, test_all = cpu[train_mask], cpu[test_mask]
        train_h, test_h = hours[train_mask], hours[test_mask]
        for h in range(24):
            tr = train_all[train_h == h]
            te = test_all[test_h == h]
            if len(tr) < MIN_TRAIN_BIN or len(te) < MIN_TEST_BIN: continue
            ctops = methods(tr)
            test_p99 = float(np.quantile(te, 0.99))
            row = {
                "vm": os.path.relpath(fp).replace("\\", "/"),
                "hour": h,
                "n_train": len(tr), "n_test": len(te),
                "test_p99": test_p99, "test_max": float(te.max()),
            }
            for m, ct in ctops.items():
                row[f"ctop_{m}"] = ct
                row[f"cov_{m}"] = float(np.mean(te <= ct)) if np.isfinite(ct) else np.nan
            rows.append(row)
        if (i + 1) % 25 == 0:
            print(f"  {i+1} files, {len(rows)} bins", file=sys.stderr)
    return pd.DataFrame(rows)


def summarize(df, methods_list):
    out = {}
    for m in methods_list:
        cov = df[f"cov_{m}"]
        ct  = df[f"ctop_{m}"]
        rel = (ct - df["test_p99"]) / df["test_p99"].replace(0, np.nan)
        out[m] = {
            "mean_coverage":     float(cov.mean()),
            "median_coverage":   float(cov.median()),
            "share_at_target":   float((cov >= TARGET_CONF).mean()),
            "mean_ceiling_pct":  float(ct.mean()),
            "median_ceiling_pct":float(ct.median()),
            "median_rel_cost":   float(rel.median()),
        }
    return out


ROOT_FS  = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8"
ROOT_RND = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8"
METHODS = ["lognorm_ctop", "empirical_p998", "gauss_meanksd", "rolling_max"]

results = {}
for label, root in [("fastStorage", ROOT_FS), ("rnd", ROOT_RND)]:
    all_files = sorted(glob.glob(os.path.join(root, "*.csv")))
    sample = random.sample(all_files, min(300, len(all_files)))
    print(f"### {label}: {len(sample)} files", file=sys.stderr)
    df = process(sample)
    df.to_csv(f"sizing_{label}.csv", index=False)
    results[label] = summarize(df, METHODS)
    print(f"### {label} bins: {len(df)}", file=sys.stderr)

with open("sizing_summary.json", "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))
