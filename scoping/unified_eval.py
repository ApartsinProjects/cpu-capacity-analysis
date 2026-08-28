"""Unified sizing evaluation panel.

One script, one VM sample per trace, one bin filter, all six sizing methods
co-computed per (VM, hour-of-day) bin on the same held-out split. Emits a
single per-bin CSV per trace that feeds Section 7 (Table 4), Section 8
(SLA simulation), and cluster-bootstrap confidence intervals.

Methods:
  1. lognorm_ctop     exp(mu + 3*sigma) of log-normal fit on train samples
  2. empirical_p998   99.8th empirical percentile of train samples
  3. gauss_meanksd    mean(train) + 3 * std(train)
  4. rolling_max      max(train)
  5. ml_gbm_p998      sklearn GradientBoostingRegressor(loss=quantile, alpha=0.998)
                       features are 7-day rolling mean/std/max/p99 at same hour
  6. ewmq_p998        exponentially-weighted moving 99.8-percentile

All methods use the same train (all samples except last 6 days) and test
(last 6 days) split, the same MIN_TRAIN_BIN (60) and MIN_TEST_BIN (12).
"""
import glob, os, random, sys, json, warnings
import numpy as np, pandas as pd
from scipy import stats
from sklearn.ensemble import GradientBoostingRegressor
warnings.filterwarnings("ignore")

random.seed(42)
np.random.seed(42)

K = 3
TARGET_CONF = 0.998
MIN_TRAIN_BIN = 60
MIN_TEST_BIN = 12
CPU_FLOOR = 0.05
TEST_DAYS = 6
N_SAMPLE_PER_TRACE = 250

METHODS = ["lognorm_ctop", "empirical_p998", "gauss_meanksd",
           "rolling_max", "ml_gbm_p998", "ewmq_p998"]

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
    return ts[m], hours[m], days[m], cpu[m]

def compute_ceilings(train, per_day_stats_train, days_train):
    """Compute ceilings under all six methods on the training data for one bin.

    train: 1D CPU% samples in the training window at this (VM, hour)
    per_day_stats_train: DataFrame with columns day, mean, std, max, p99
                         for days in the training window at this hour
    days_train: array of day indices matching train samples
    Returns dict method -> ceiling.
    """
    out = {}
    # log-normal ceiling
    try:
        s, _, sc = stats.lognorm.fit(train, floc=0)
        mu = np.log(sc); sigma = s
        out["lognorm_ctop"] = float(np.exp(mu + K * sigma))
    except Exception:
        out["lognorm_ctop"] = float("nan")
    # empirical percentile
    out["empirical_p998"] = float(np.quantile(train, TARGET_CONF))
    # Gaussian
    out["gauss_meanksd"] = float(train.mean() + K * train.std())
    # rolling max
    out["rolling_max"] = float(train.max())
    # EWMQ: exponentially-weighted mean of per-day p99
    if len(per_day_stats_train) >= 3:
        past = per_day_stats_train["p99"].values
        w = 0.5 ** np.arange(len(past))[::-1]
        out["ewmq_p998"] = float(np.sum(w * past) / np.sum(w))
    else:
        out["ewmq_p998"] = float("nan")
    # ML GBM
    if len(per_day_stats_train) >= 8:
        X_tr, y_tr = [], []
        for _, row in per_day_stats_train.iterrows():
            d = row["day"]
            # rolling 7-day features up to (but not including) d
            window = per_day_stats_train[
                (per_day_stats_train["day"] < d) &
                (per_day_stats_train["day"] >= d - 7)
            ]
            if len(window) < 3: continue
            feats = np.array([window["mean"].mean(), window["std"].mean(),
                              window["max"].mean(), window["p99"].mean()])
            samples = train[days_train == d]
            for s in samples:
                X_tr.append(feats); y_tr.append(s)
        if len(y_tr) >= 100:
            X_tr = np.array(X_tr); y_tr = np.array(y_tr)
            try:
                model = GradientBoostingRegressor(loss="quantile", alpha=TARGET_CONF,
                                                  n_estimators=40, max_depth=3, random_state=42)
                model.fit(X_tr, y_tr)
                # Features for the test window: last-7-days rolling stats at
                # the end of the training window
                last_day_train = per_day_stats_train["day"].max()
                window = per_day_stats_train[per_day_stats_train["day"] >= last_day_train - 6]
                feats = np.array([window["mean"].mean(), window["std"].mean(),
                                  window["max"].mean(), window["p99"].mean()])
                out["ml_gbm_p998"] = float(model.predict(feats.reshape(1, -1))[0])
            except Exception:
                out["ml_gbm_p998"] = float("nan")
        else:
            out["ml_gbm_p998"] = float("nan")
    else:
        out["ml_gbm_p998"] = float("nan")
    return out

def process_vm(hours, days, cpu, vm_id):
    if len(cpu) == 0: return []
    day_max = days.max(); day_min = days.min()
    if day_max - day_min < 8 + TEST_DAYS: return []
    train_cutoff = day_max - TEST_DAYS
    rows = []
    for h in range(24):
        m_h = hours == h
        c_h = cpu[m_h]; d_h = days[m_h]
        if len(c_h) < 30: continue
        # Split
        train_mask = d_h <= train_cutoff
        test_mask  = d_h >  train_cutoff
        tr = c_h[train_mask]; te = c_h[test_mask]
        tr_days = d_h[train_mask]
        if len(tr) < MIN_TRAIN_BIN or len(te) < MIN_TEST_BIN: continue
        # per-day stats for the training window at this hour
        per_day = []
        for d in range(day_min, train_cutoff + 1):
            dm = (d_h == d) & train_mask
            xs = c_h[dm]
            if len(xs) < 3: continue
            per_day.append({"day": d, "mean": xs.mean(), "std": xs.std(),
                            "max": xs.max(), "p99": np.quantile(xs, 0.99)})
        pd_df = pd.DataFrame(per_day)
        ceils = compute_ceilings(tr, pd_df, tr_days)
        row = {"vm": vm_id, "hour": h, "n_train": int(len(tr)), "n_test": int(len(te)),
               "test_p99": float(np.quantile(te, 0.99)), "test_max": float(te.max())}
        for m, ct in ceils.items():
            row[f"ctop_{m}"] = ct
            row[f"cov_{m}"] = float(np.mean(te <= ct)) if np.isfinite(ct) else np.nan
        rows.append(row)
    return rows

def process(files):
    all_rows = []
    for i, fp in enumerate(files):
        r = read_vm(fp)
        if r is None: continue
        _, hours, days, cpu = r
        vm_id = os.path.relpath(fp).replace("\\", "/")
        all_rows.extend(process_vm(hours, days, cpu, vm_id))
        if (i + 1) % 25 == 0:
            print(f"  {i+1} files, {len(all_rows)} bins", file=sys.stderr)
    return pd.DataFrame(all_rows)

ROOT_FS  = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8"
ROOT_RND = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8"

for label, root in [("fastStorage", ROOT_FS), ("rnd", ROOT_RND)]:
    files = sorted(glob.glob(os.path.join(root, "*.csv")))
    sample = random.sample(files, min(N_SAMPLE_PER_TRACE, len(files)))
    print(f"### {label}: {len(sample)} files", file=sys.stderr)
    df = process(sample)
    df.to_csv(f"unified_{label}.csv", index=False)
    n_bins = len(df)
    n_vms = df["vm"].nunique() if n_bins else 0
    summary = {"n_vms": int(n_vms), "n_bins": int(n_bins)}
    for m in METHODS:
        cov = df[f"cov_{m}"]
        ct  = df[f"ctop_{m}"]
        rel = (ct - df["test_p99"]) / df["test_p99"].replace(0, np.nan)
        summary[m] = {
            "mean_coverage":     float(cov.mean()),
            "share_at_target":   float((cov >= TARGET_CONF).mean()),
            "median_ceiling_pct":float(ct.median()),
            "median_rel_cost":   float(rel.median()),
            "n_valid":           int(ct.notna().sum()),
        }
    with open(f"unified_{label}_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
