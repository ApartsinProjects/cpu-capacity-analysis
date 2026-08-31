"""Anderson-Darling / Cramer-von Mises / KS per bin on Alibaba, four families.

Same preprocessing as fit_alibaba.py (first 300 machines, CPU floor 5.0,
MIN_N 60, hour-of-day bins) so the Alibaba AD/CvM column matches the Alibaba
AIC winner-share bins exactly. Mirrors ad_cvm.py's statistic definitions.
"""
import tarfile, os, sys, json
import numpy as np, pandas as pd
from scipy import stats
from collections import defaultdict

CPU_FLOOR = 5.0
MIN_N = 60
N_TARGET = 300
CANDIDATES = ["lognorm", "norm", "gamma", "weibull_min"]
TAR = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/alibaba/machine_usage.tar.gz"

def ad_statistic(x_sorted, cdf_vals):
    n = len(x_sorted)
    u = np.clip(cdf_vals, 1e-12, 1 - 1e-12)
    i = np.arange(1, n + 1)
    s = np.sum((2 * i - 1) * (np.log(u) + np.log(1 - u[::-1])))
    return -n - s / n

def fit_and_stats(x):
    x_sorted = np.sort(x); out = {}
    for name in CANDIDATES:
        dist = getattr(stats, name)
        try:
            params = dist.fit(x, floc=0) if name in ("lognorm","gamma","weibull_min") else dist.fit(x)
            cdf_vals = dist.cdf(x_sorted, *params)
            if not np.all(np.isfinite(cdf_vals)):
                out[name] = {"ks": np.nan, "cvm": np.nan, "ad": np.nan}; continue
            ks = stats.kstest(x, name, args=params).statistic
            cvm = stats.cramervonmises(x, name, args=params).statistic
            ad = ad_statistic(x_sorted, cdf_vals)
            out[name] = {"ks": float(ks), "cvm": float(cvm), "ad": float(ad)}
        except Exception:
            out[name] = {"ks": np.nan, "cvm": np.nan, "ad": np.nan}
    return out

per_machine = defaultdict(lambda: defaultdict(list)); accepted = set(); row_count = 0
with tarfile.open(TAR, "r:gz") as tf:
    for member in [m for m in tf.getmembers() if m.name.endswith(".csv")]:
        f = tf.extractfile(member)
        for line in f:
            row_count += 1
            if row_count % 40_000_000 == 0:
                print(f"  row {row_count:,}", file=sys.stderr)
            p = line.decode("utf-8","ignore").rstrip("\n").split(",")
            if len(p) < 3: continue
            try:
                m_id = p[0]; ts = int(p[1]); cpu = float(p[2])
            except (ValueError, IndexError): continue
            if m_id not in accepted:
                if len(accepted) < N_TARGET: accepted.add(m_id)
                else: continue
            if not (CPU_FLOOR <= cpu <= 100): continue
            per_machine[m_id][int((ts // 3600) % 24)].append(cpu)

rows = []
for m_id, hd in per_machine.items():
    if sum(len(v) for v in hd.values()) < MIN_N: continue
    for h in range(24):
        x = np.asarray(hd.get(h, []))
        if len(x) < MIN_N: continue
        s = fit_and_stats(x)
        row = {"vm": m_id, "hour": h, "n": len(x)}
        for k, v in s.items():
            for sn, val in v.items(): row[f"{sn}_{k}"] = val
        rows.append(row)
df = pd.DataFrame(rows)
df.to_csv("ad_cvm_alibaba.csv", index=False)

out = {"n_bins": int(len(df))}
for sn in ["ks", "cvm", "ad"]:
    out[f"{sn}_median"] = {c: round(float(df[f"{sn}_{c}"].replace([np.inf,-np.inf],np.nan).median()), 4) for c in CANDIDATES}
    stacked = pd.concat([df[f"{sn}_{c}"] for c in CANDIDATES], axis=1).values
    winners = np.nanargmin(stacked, axis=1)
    out[f"{sn}_share_lognorm_best"] = round(float(np.mean(winners == CANDIDATES.index("lognorm"))), 4)
with open("ad_cvm_alibaba_summary.json", "w") as f:
    json.dump(out, f, indent=2)
print(json.dumps(out, indent=2))
