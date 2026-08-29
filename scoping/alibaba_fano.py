"""Fano-factor test on Alibaba container_meta: directly measures the
empirical dispersion index Var(n)/E(n) for container arrivals per machine
per fixed window. If Var(n)/E(n) is close to 1, arrivals are Poisson-like;
if it is on the order of 81, batching alone explains the ~9x alpha ratio
observed in Section 7 for Bitbrains.
"""
import os, json, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CM_PATH = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/alibaba/container_meta.csv"

# Load and filter to unique first-appearance events per container
print("loading container_meta ...", file=sys.stderr)
df = pd.read_csv(CM_PATH, header=None,
                 names=["container","machine","ts","app","status","cpu_req","cpu_lim","mem"])
df = df.sort_values("ts").drop_duplicates("container", keep="first")
print(f"unique containers: {len(df):,} on {df['machine'].nunique()} machines", file=sys.stderr)

results = {}
for window_sec, label in [(300, "5min"), (900, "15min"), (3600, "1hour")]:
    df["_bucket"] = df["ts"] // window_sec
    # arrivals per (machine, bucket)
    counts = df.groupby(["machine", "_bucket"]).size()
    # Per machine, compute dispersion across its buckets
    per_machine = counts.groupby(level=0).agg(["mean", "var", "count"])
    per_machine = per_machine[per_machine["count"] >= 8]  # need enough buckets to estimate var
    per_machine["disp"] = per_machine["var"] / per_machine["mean"]
    per_machine = per_machine.replace([np.inf, -np.inf], np.nan).dropna(subset=["disp"])
    # summary
    high_load = per_machine[per_machine["mean"] >= 2.0]  # machines with meaningful arrival rate
    results[label] = {
        "window_sec": window_sec,
        "n_machines_total": int(len(per_machine)),
        "n_machines_high_load": int(len(high_load)),
        "median_disp_all": float(per_machine["disp"].median()),
        "median_disp_high_load": float(high_load["disp"].median()) if len(high_load) else np.nan,
        "p25_disp_high_load": float(high_load["disp"].quantile(0.25)) if len(high_load) else np.nan,
        "p75_disp_high_load": float(high_load["disp"].quantile(0.75)) if len(high_load) else np.nan,
        "share_disp_ge_2": float((per_machine["disp"] >= 2).mean()),
        "share_disp_ge_10": float((per_machine["disp"] >= 10).mean()),
        "share_disp_ge_50": float((per_machine["disp"] >= 50).mean()),
    }
    print(f"[{label}] n={len(per_machine)} machines, median dispersion={results[label]['median_disp_all']:.2f}, "
          f"high-load median={results[label]['median_disp_high_load']:.2f}, "
          f"share>=10: {100*results[label]['share_disp_ge_10']:.1f}%", file=sys.stderr)

# Save
with open(os.path.join(HERE, "alibaba_fano_summary.json"), "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))

# Reference: 9x observed alpha_sigma / alpha_mu ratio implies dispersion index
# ~= 81. If median empirical dispersion is >> 1 (say >= 10), batching is a
# plausible driver. If it hovers near 1, the excess must come from another
# source (Cox process, correlation, cost heterogeneity).
