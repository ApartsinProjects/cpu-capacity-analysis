"""Scoping experiment: per-VM-per-hour distribution fit on Bitbrains fastStorage.

For a random subset of VMs, bin CPU% by hour-of-day and fit four candidate
distributions (log-normal, normal, gamma, Weibull). Report per-bin winner by
AIC and per-bin KS-test acceptance rate.
"""
import glob, os, json, random, sys, math, datetime as dt
import numpy as np
import pandas as pd
from scipy import stats

random.seed(42)

DATA = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8"
files = sorted(glob.glob(os.path.join(DATA, "*.csv")))
N_VMS = 300
sample_files = random.sample(files, N_VMS)

MIN_N = 60          # bin must have at least 60 samples (5h of data)
CPU_FLOOR = 0.05    # CPU% floor to keep log defined and avoid degenerate zeros

CANDIDATES = ["lognorm", "norm", "gamma", "weibull_min"]

def fit_and_score(x):
    """Return dict of {dist: (aic, ks_pvalue)} for each candidate."""
    n = len(x)
    out = {}
    for name in CANDIDATES:
        dist = getattr(stats, name)
        try:
            if name == "lognorm":
                params = dist.fit(x, floc=0)
            elif name in ("gamma", "weibull_min"):
                params = dist.fit(x, floc=0)
            else:
                params = dist.fit(x)
            k = len(params) - (1 if name in ("lognorm", "gamma", "weibull_min") else 0)
            logL = np.sum(dist.logpdf(x, *params))
            if not np.isfinite(logL):
                out[name] = (np.inf, 0.0)
                continue
            aic = 2 * k - 2 * logL
            ks_stat, ks_p = stats.kstest(x, name, args=params)
            out[name] = (aic, ks_p)
        except Exception:
            out[name] = (np.inf, 0.0)
    return out


bin_records = []
per_vm_count = 0
for fp in sample_files:
    try:
        df = pd.read_csv(fp, sep=";\t| ;\t|\t| ;", engine="python", skipinitialspace=True)
    except Exception:
        try:
            df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
        except Exception:
            continue
    # Normalize column names
    df.columns = [c.strip() for c in df.columns]
    if "CPU usage [%]" not in df.columns or "Timestamp [ms]" not in df.columns:
        continue
    ts = df["Timestamp [ms]"].astype(float).values
    # Timestamps are seconds (10-digit values) per inspection
    hours = (np.floor(ts / 3600).astype(int)) % 24
    cpu = df["CPU usage [%]"].astype(float).values
    mask = np.isfinite(cpu) & (cpu >= CPU_FLOOR) & (cpu <= 100)
    cpu = cpu[mask]; hours = hours[mask]
    if len(cpu) < MIN_N:
        continue
    per_vm_count += 1
    vm_id = os.path.splitext(os.path.basename(fp))[0]
    for h in range(24):
        x = cpu[hours == h]
        if len(x) < MIN_N:
            continue
        scores = fit_and_score(x)
        best = min(scores, key=lambda k: scores[k][0])
        bin_records.append({
            "vm": vm_id, "hour": h, "n": len(x),
            "mean": float(np.mean(x)), "std": float(np.std(x)),
            **{f"aic_{k}": scores[k][0] for k in CANDIDATES},
            **{f"ksp_{k}": scores[k][1] for k in CANDIDATES},
            "best_aic": best,
        })
    if per_vm_count % 25 == 0:
        print(f"processed {per_vm_count} VMs, {len(bin_records)} bins", file=sys.stderr)

print(f"TOTAL: {per_vm_count} VMs, {len(bin_records)} bins", file=sys.stderr)

results = pd.DataFrame(bin_records)
results.to_csv("bitbrains_fit_results.csv", index=False)

# --- Summary ---
n_bins = len(results)
summary = {}
summary["n_vms_used"] = per_vm_count
summary["n_bins"] = n_bins
summary["min_samples_per_bin"] = MIN_N

# best-by-AIC winner share
winners = results["best_aic"].value_counts(normalize=True).to_dict()
summary["best_aic_share"] = {k: round(v, 4) for k, v in winners.items()}

# median AIC per family
summary["median_aic"] = {c: round(float(results[f"aic_{c}"].replace([np.inf,-np.inf], np.nan).median()), 3) for c in CANDIDATES}

# KS-not-rejected at alpha=0.05
summary["ks_not_rejected_at_0.05"] = {c: round(float((results[f"ksp_{c}"] >= 0.05).mean()), 4) for c in CANDIDATES}
summary["ks_not_rejected_at_0.01"] = {c: round(float((results[f"ksp_{c}"] >= 0.01).mean()), 4) for c in CANDIDATES}

# Pairwise: log-normal AIC minus alternative AIC (negative means log-normal wins)
for c in ["norm", "gamma", "weibull_min"]:
    d = results[f"aic_lognorm"] - results[f"aic_{c}"]
    d = d.replace([np.inf,-np.inf], np.nan).dropna()
    summary[f"aic_lognorm_minus_{c}"] = {
        "median": round(float(d.median()), 3),
        "share_lognorm_wins": round(float((d < 0).mean()), 4),
        "share_lognorm_wins_by_>=_2": round(float((d <= -2).mean()), 4),
    }

with open("bitbrains_summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print(json.dumps(summary, indent=2))
