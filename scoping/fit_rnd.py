"""Same fit as scoping/fit.py, run against Bitbrains Rnd (3 months, 500 VMs/month)."""
import glob, os, json, random, sys, numpy as np, pandas as pd
from scipy import stats

random.seed(42)
ROOT = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd"
MONTHS = ["2013-7", "2013-8", "2013-9"]
files = []
for m in MONTHS:
    files += sorted(glob.glob(os.path.join(ROOT, m, "*.csv")))

# Sample same size as fastStorage run for comparability
N_TARGET = 300
sample_files = random.sample(files, N_TARGET)

MIN_N = 60
CPU_FLOOR = 0.05
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


bin_records = []
per_vm_count = 0
for fp in sample_files:
    try:
        df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
    except Exception:
        continue
    df.columns = [c.strip() for c in df.columns]
    if "CPU usage [%]" not in df.columns or "Timestamp [ms]" not in df.columns:
        continue
    ts = df["Timestamp [ms]"].astype(float).values
    hours = (np.floor(ts / 3600).astype(int)) % 24
    cpu = df["CPU usage [%]"].astype(float).values
    mask = np.isfinite(cpu) & (cpu >= CPU_FLOOR) & (cpu <= 100)
    cpu = cpu[mask]; hours = hours[mask]
    if len(cpu) < MIN_N:
        continue
    per_vm_count += 1
    vm_id = os.path.relpath(fp, ROOT).replace("\\", "/").replace(".csv", "")
    for h in range(24):
        x = cpu[hours == h]
        if len(x) < MIN_N: continue
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
results.to_csv("rnd_fit_results.csv", index=False)

summary = {}
summary["n_vms_used"] = per_vm_count
summary["n_bins"] = len(results)
summary["best_aic_share"] = {k: round(v, 4) for k, v in results["best_aic"].value_counts(normalize=True).to_dict().items()}
summary["median_aic"] = {c: round(float(results[f"aic_{c}"].replace([np.inf,-np.inf], np.nan).median()), 3) for c in CANDIDATES}
summary["ks_not_rejected_at_0.05"] = {c: round(float((results[f"ksp_{c}"] >= 0.05).mean()), 4) for c in CANDIDATES}
for c in ["norm", "gamma", "weibull_min"]:
    d = results[f"aic_lognorm"] - results[f"aic_{c}"]
    d = d.replace([np.inf,-np.inf], np.nan).dropna()
    summary[f"aic_lognorm_minus_{c}"] = {
        "median": round(float(d.median()), 3),
        "share_lognorm_wins": round(float((d < 0).mean()), 4),
        "share_lognorm_wins_by_>=_2": round(float((d <= -2).mean()), 4),
    }

with open("rnd_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
