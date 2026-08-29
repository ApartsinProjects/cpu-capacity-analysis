"""Fit log-normal / normal / gamma / Weibull per (VM, hour-of-day) bin on
Azure Public Dataset v2 vm_cpu_readings. Same pipeline as fit.py / fit_rnd.py.

Schema (per Azure v2 docs):
  timestamp (5-min-quantized seconds), vm_id (hash), min_cpu, max_cpu, avg_cpu
No header row in the CSV files. We read the avg_cpu column.
"""
import gzip, os, random, sys, json, csv
import numpy as np, pandas as pd
from scipy import stats
from collections import defaultdict

random.seed(42)
CPU_FLOOR = 0.05
MIN_N = 60
CANDIDATES = ["lognorm", "norm", "gamma", "weibull_min"]

def fit_and_score(x):
    out = {}
    for name in CANDIDATES:
        dist = getattr(stats, name)
        try:
            if name in ("lognorm", "gamma", "weibull_min"):
                params = dist.fit(x, floc=0)
                k = 2
            else:
                params = dist.fit(x)
                k = 2
            logL = np.sum(dist.logpdf(x, *params))
            if not np.isfinite(logL):
                out[name] = (np.inf, 0.0); continue
            aic = 2 * k - 2 * logL
            ks_stat, ks_p = stats.kstest(x, name, args=params)
            out[name] = (aic, ks_p)
        except Exception:
            out[name] = (np.inf, 0.0)
    return out

def stream_azure_readings(path, n_target_vms):
    """Stream the gzip CSV; return dict vm_id -> {hour: [cpu samples]}.

    Sample N_TARGET_VMS distinct VMs (by hash of the first vm_id we see);
    keep only their samples to bound memory.
    """
    print(f"streaming {path}", file=sys.stderr)
    seen_vms = {}
    accepted = set()
    per_vm = defaultdict(lambda: defaultdict(list))
    row_count = 0
    with gzip.open(path, "rt") as f:
        reader = csv.reader(f)
        for row in reader:
            row_count += 1
            if row_count % 5_000_000 == 0:
                print(f"  row {row_count:,}, {len(accepted)} VMs accepted", file=sys.stderr)
            if len(row) < 5: continue
            try:
                ts = float(row[0]); vm = row[1]
                # avg_cpu in column 4 per Azure v2 docs
                cpu = float(row[4])
            except (ValueError, IndexError):
                continue
            if vm not in seen_vms:
                seen_vms[vm] = len(seen_vms)
                if len(accepted) < n_target_vms:
                    accepted.add(vm)
            if vm not in accepted: continue
            if not (CPU_FLOOR <= cpu <= 100): continue
            h = int((ts // 3600) % 24)
            per_vm[vm][h].append(cpu)
    print(f"total rows scanned: {row_count:,}; accepted VMs: {len(accepted)}", file=sys.stderr)
    return per_vm

def process(per_vm):
    rows = []
    per_vm_count = 0
    for vm_id, hours_dict in per_vm.items():
        # Need at least MIN_N samples in some hour bin
        total = sum(len(v) for v in hours_dict.values())
        if total < MIN_N: continue
        per_vm_count += 1
        for h in range(24):
            x = np.asarray(hours_dict.get(h, []))
            if len(x) < MIN_N: continue
            scores = fit_and_score(x)
            best = min(scores, key=lambda k: scores[k][0])
            rows.append({
                "vm": vm_id, "hour": h, "n": len(x),
                "mean": float(np.mean(x)), "std": float(np.std(x)),
                **{f"aic_{k}": scores[k][0] for k in CANDIDATES},
                **{f"ksp_{k}": scores[k][1] for k in CANDIDATES},
                "best_aic": best,
            })
        if per_vm_count % 100 == 0:
            print(f"  processed {per_vm_count} VMs, {len(rows)} bins", file=sys.stderr)
    print(f"TOTAL: {per_vm_count} VMs, {len(rows)} bins", file=sys.stderr)
    return pd.DataFrame(rows)

PATH = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/azure/azure_v2_file1.csv.gz"
N_TARGET_VMS = 400

per_vm = stream_azure_readings(PATH, N_TARGET_VMS)
df = process(per_vm)
df.to_csv("azure_fit_results.csv", index=False)

# summary
summary = {"n_vms_used": int(df["vm"].nunique()),
           "n_bins": int(len(df)),
           "min_samples_per_bin": MIN_N}
winners = df["best_aic"].value_counts(normalize=True).to_dict()
summary["best_aic_share"] = {k: round(v, 4) for k, v in winners.items()}
summary["median_aic"] = {c: round(float(df[f"aic_{c}"].replace([np.inf,-np.inf], np.nan).median()), 3) for c in CANDIDATES}
summary["ks_not_rejected_at_0.05"] = {c: round(float((df[f"ksp_{c}"] >= 0.05).mean()), 4) for c in CANDIDATES}
for c in ["norm", "gamma", "weibull_min"]:
    d = (df[f"aic_lognorm"] - df[f"aic_{c}"]).replace([np.inf,-np.inf], np.nan).dropna()
    summary[f"aic_lognorm_minus_{c}"] = {
        "median": round(float(d.median()), 3),
        "share_lognorm_wins": round(float((d < 0).mean()), 4),
        "share_lognorm_wins_by_>=_2": round(float((d <= -2).mean()), 4),
    }
with open("azure_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
