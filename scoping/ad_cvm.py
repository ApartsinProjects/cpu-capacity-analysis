"""Anderson-Darling and Cramer-von Mises tests per bin, four families.

Reuses the same random sample as fit.py / fit_rnd.py. For every retained
(VM, hour-of-day) bin, refits the four candidate distributions and computes
A-D and CvM statistics against the fitted CDFs. Reports median statistic per
family and share-of-bins where log-normal has the smallest statistic.
"""
import glob, os, random, sys, json
import numpy as np, pandas as pd
from scipy import stats

random.seed(42)
MIN_N = 60
CPU_FLOOR = 0.05
CANDIDATES = ["lognorm", "norm", "gamma", "weibull_min"]

def ad_statistic(x_sorted, cdf_vals):
    """Anderson-Darling statistic for a fully specified fitted CDF."""
    n = len(x_sorted)
    u = np.clip(cdf_vals, 1e-12, 1 - 1e-12)
    i = np.arange(1, n + 1)
    s = np.sum((2 * i - 1) * (np.log(u) + np.log(1 - u[::-1])))
    return -n - s / n

def fit_and_stats(x):
    x_sorted = np.sort(x)
    out = {}
    for name in CANDIDATES:
        dist = getattr(stats, name)
        try:
            if name in ("lognorm", "gamma", "weibull_min"):
                params = dist.fit(x, floc=0)
            else:
                params = dist.fit(x)
            cdf_vals = dist.cdf(x_sorted, *params)
            if not np.all(np.isfinite(cdf_vals)):
                out[name] = {"ks": np.nan, "cvm": np.nan, "ad": np.nan}
                continue
            ks_stat = stats.kstest(x, name, args=params).statistic
            cvm = stats.cramervonmises(x, name, args=params).statistic
            ad = ad_statistic(x_sorted, cdf_vals)
            out[name] = {"ks": float(ks_stat), "cvm": float(cvm), "ad": float(ad)}
        except Exception:
            out[name] = {"ks": np.nan, "cvm": np.nan, "ad": np.nan}
    return out

def process(files):
    rows = []
    for i, fp in enumerate(files):
        try:
            df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
        except Exception: continue
        df.columns = [c.strip() for c in df.columns]
        if "CPU usage [%]" not in df.columns or "Timestamp [ms]" not in df.columns: continue
        ts = df["Timestamp [ms]"].astype(float).values
        hours = (np.floor(ts / 3600).astype(int)) % 24
        cpu = df["CPU usage [%]"].astype(float).values
        mask = np.isfinite(cpu) & (cpu >= CPU_FLOOR) & (cpu <= 100)
        cpu = cpu[mask]; hours = hours[mask]
        if len(cpu) < MIN_N: continue
        vm = os.path.relpath(fp).replace("\\", "/")
        for h in range(24):
            x = cpu[hours == h]
            if len(x) < MIN_N: continue
            s = fit_and_stats(x)
            row = {"vm": vm, "hour": h, "n": len(x)}
            for k, v in s.items():
                for stat_name, val in v.items():
                    row[f"{stat_name}_{k}"] = val
            rows.append(row)
        if (i + 1) % 25 == 0:
            print(f"  {i+1} files, {len(rows)} bins", file=sys.stderr)
    return pd.DataFrame(rows)

def summarize(df):
    out = {}
    for stat_name in ["ks", "cvm", "ad"]:
        family_medians = {}
        for c in CANDIDATES:
            col = df[f"{stat_name}_{c}"].replace([np.inf, -np.inf], np.nan)
            family_medians[c] = float(col.median())
        out[f"{stat_name}_median"] = {k: round(v, 4) for k, v in family_medians.items()}
        # share of bins where log-normal has smallest statistic
        cols = [df[f"{stat_name}_{c}"] for c in CANDIDATES]
        stacked = pd.concat(cols, axis=1).values  # rows x 4
        winners = np.nanargmin(stacked, axis=1)
        ln_idx = CANDIDATES.index("lognorm")
        out[f"{stat_name}_share_lognorm_best"] = round(float(np.mean(winners == ln_idx)), 4)
    return out

ROOT_FS  = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8"
ROOT_RND = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8"

results = {}
for label, root in [("fastStorage", ROOT_FS), ("rnd", ROOT_RND)]:
    files = sorted(glob.glob(os.path.join(root, "*.csv")))
    sample = random.sample(files, min(300, len(files)))
    print(f"### {label}: {len(sample)} files", file=sys.stderr)
    df = process(sample)
    df.to_csv(f"ad_cvm_{label}.csv", index=False)
    results[label] = summarize(df)
    results[label]["n_bins"] = int(len(df))

with open("ad_cvm_summary.json", "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))
