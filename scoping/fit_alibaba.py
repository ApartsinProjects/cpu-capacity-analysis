"""Fit per-(machine, hour-of-day) log-normal / normal / gamma / Weibull on
Alibaba cluster-trace-v2018 machine_usage.

Schema (per Alibaba docs, machine_usage.csv):
  machine_id, time_stamp, cpu_util_percent, mem_util_percent, mem_gps,
  mkpi, net_in, net_out, disk_io_percent
Sampling: approximately every 10 seconds.
"""
import tarfile, os, random, sys, json, csv, gzip
import numpy as np, pandas as pd
from scipy import stats
from collections import defaultdict

random.seed(42)
CPU_FLOOR = 5.0   # Alibaba stores CPU% as 0-100 float, keep floor tighter
MIN_N = 60
CANDIDATES = ["lognorm", "norm", "gamma", "weibull_min"]

def fit_and_score(x):
    out = {}
    for name in CANDIDATES:
        dist = getattr(stats, name)
        try:
            params = dist.fit(x, floc=0) if name in ("lognorm","gamma","weibull_min") else dist.fit(x)
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

TAR = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/alibaba/machine_usage.tar.gz"
N_TARGET_MACHINES = 300

# Stream through the tar's machine_usage.csv (its inner file inside the tar)
print(f"opening {TAR}", file=sys.stderr)
per_machine = defaultdict(lambda: defaultdict(list))
accepted = set()
row_count = 0

with tarfile.open(TAR, "r:gz") as tf:
    members = [m for m in tf.getmembers() if m.name.endswith(".csv")]
    print(f"csv members: {[m.name for m in members]}", file=sys.stderr)
    for member in members:
        with tf.extractfile(member) as f:
            for line in f:
                row_count += 1
                if row_count % 20_000_000 == 0:
                    print(f"  row {row_count:,}, {len(accepted)} machines accepted", file=sys.stderr)
                parts = line.decode("utf-8", errors="ignore").rstrip("\n").split(",")
                if len(parts) < 3: continue
                try:
                    m_id = parts[0]
                    ts = int(parts[1])
                    cpu = float(parts[2])
                except (ValueError, IndexError):
                    continue
                if m_id not in accepted:
                    if len(accepted) < N_TARGET_MACHINES:
                        accepted.add(m_id)
                    else:
                        continue
                if not (CPU_FLOOR <= cpu <= 100): continue
                h = int((ts // 3600) % 24)
                per_machine[m_id][h].append(cpu)

print(f"total rows scanned: {row_count:,}; accepted machines: {len(accepted)}", file=sys.stderr)

# Fit
rows = []
per_m_count = 0
for m_id, hours_dict in per_machine.items():
    total = sum(len(v) for v in hours_dict.values())
    if total < MIN_N: continue
    per_m_count += 1
    for h in range(24):
        x = np.asarray(hours_dict.get(h, []))
        if len(x) < MIN_N: continue
        scores = fit_and_score(x)
        best = min(scores, key=lambda k: scores[k][0])
        rows.append({
            "vm": m_id, "hour": h, "n": len(x),
            "mean": float(np.mean(x)), "std": float(np.std(x)),
            **{f"aic_{k}": scores[k][0] for k in CANDIDATES},
            **{f"ksp_{k}": scores[k][1] for k in CANDIDATES},
            "best_aic": best,
        })
    if per_m_count % 50 == 0:
        print(f"  processed {per_m_count} machines, {len(rows)} bins", file=sys.stderr)

print(f"TOTAL: {per_m_count} machines, {len(rows)} bins", file=sys.stderr)

df = pd.DataFrame(rows)
df.to_csv("alibaba_fit_results.csv", index=False)

summary = {"n_vms_used": int(df["vm"].nunique()) if len(df) else 0,
           "n_bins": int(len(df)),
           "min_samples_per_bin": MIN_N}
if len(df):
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
with open("alibaba_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
