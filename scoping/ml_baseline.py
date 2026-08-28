"""ML baseline for the sizing comparison: quantile gradient-boosted regression.

Per (VM, hour-of-day) bin we treat each day's samples as one observation
window. Features (7-day rolling): mean, std, max, and p99 of CPU in the
prior 7 days at that same hour-of-day. Target: sample of CPU in the current
day at that hour. We fit sklearn's GradientBoostingRegressor with quantile
loss at 0.998 on the train set (all days except last 6), and predict the
99.8th-percentile ceiling for the test window.

Cheaper alternative baseline for comparison: exponentially-weighted moving
99.8-percentile (EWMQ) — no model dependency, standard in industry.
"""
import glob, os, random, sys, json, warnings
import numpy as np, pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
warnings.filterwarnings("ignore")

random.seed(42)
CPU_FLOOR = 0.05
MIN_TRAIN_DAYS = 8
TEST_DAYS = 6

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

def rolling_features(daily_stats, current_day):
    """From per-day stats table, compute 7-day rolling features up to but not including current_day."""
    window = daily_stats[(daily_stats["day"] < current_day) & (daily_stats["day"] >= current_day - 7)]
    if len(window) < 3:
        return None
    return np.array([window["mean"].mean(), window["std"].mean(), window["max"].mean(), window["p99"].mean()])

def process_vm(hours, days, cpu):
    """Return per-(vm, hour) predictions on the test window."""
    if len(cpu) == 0: return None
    day_max = days.max(); day_min = days.min()
    n_days = day_max - day_min + 1
    if n_days < MIN_TRAIN_DAYS + TEST_DAYS: return None
    train_cutoff = day_max - TEST_DAYS
    rows = []
    for h in range(24):
        mask = hours == h
        c_h = cpu[mask]; d_h = days[mask]
        if len(c_h) < 30: continue
        # Per-day stats at this hour
        per_day = []
        for d in range(day_min, day_max + 1):
            dm = d_h == d
            if dm.sum() < 3: continue
            per_day.append({"day": d, "mean": c_h[dm].mean(), "std": c_h[dm].std(),
                            "max": c_h[dm].max(), "p99": np.quantile(c_h[dm], 0.99)})
        if len(per_day) < MIN_TRAIN_DAYS + 3: continue
        pd_df = pd.DataFrame(per_day)
        # Build (feature, sample) pairs for training
        X_tr, y_tr = [], []
        for _, row in pd_df.iterrows():
            d = row["day"]
            if d > train_cutoff: continue
            feats = rolling_features(pd_df, d)
            if feats is None: continue
            samples = c_h[d_h == d]
            for s in samples:
                X_tr.append(feats); y_tr.append(s)
        if len(y_tr) < 100: continue
        X_tr = np.array(X_tr); y_tr = np.array(y_tr)
        try:
            model = GradientBoostingRegressor(loss="quantile", alpha=0.998,
                                              n_estimators=40, max_depth=3, random_state=42)
            model.fit(X_tr, y_tr)
        except Exception:
            continue
        # Predict on test: use train-window-derived features to predict test window ceiling
        test_feats = rolling_features(pd_df, day_max - TEST_DAYS + 1)
        if test_feats is None: continue
        pred = float(model.predict(test_feats.reshape(1, -1))[0])
        # Also EWMQ baseline: exponentially weighted mean of past p99s
        past = pd_df[pd_df["day"] <= train_cutoff]["p99"].values
        if len(past) < 3: continue
        w = 0.5 ** np.arange(len(past))[::-1]
        ewmq = float(np.sum(w * past) / np.sum(w))
        # Test samples
        test_mask = (hours == h) & (days > train_cutoff)
        te = cpu[test_mask]
        if len(te) < 6: continue
        rows.append({"hour": h, "n_test": int(len(te)),
                     "ml_gbm_p998": pred, "cov_ml_gbm_p998": float(np.mean(te <= pred)),
                     "ewmq_p998": ewmq, "cov_ewmq_p998": float(np.mean(te <= ewmq)),
                     "test_p99": float(np.quantile(te, 0.99))})
    return pd.DataFrame(rows) if rows else None

def process(files):
    all_rows = []
    for i, fp in enumerate(files):
        r = read_vm(fp)
        if r is None: continue
        _, hours, days, cpu = r
        out = process_vm(hours, days, cpu)
        if out is None or len(out) == 0: continue
        out["vm"] = os.path.relpath(fp).replace("\\", "/")
        all_rows.append(out)
        if (i + 1) % 20 == 0:
            print(f"  {i+1} files, {sum(len(x) for x in all_rows)} bins", file=sys.stderr)
    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()

def summarize(df):
    out = {}
    for method in ["ml_gbm_p998", "ewmq_p998"]:
        cov = df[f"cov_{method}"]
        ct = df[method]
        rel = (ct - df["test_p99"]) / df["test_p99"].replace(0, np.nan)
        out[method] = {
            "n_bins": int(len(df)),
            "mean_coverage": float(cov.mean()),
            "share_at_target": float((cov >= 0.998).mean()),
            "median_ceiling_pct": float(ct.median()),
            "median_rel_cost": float(rel.median()),
        }
    return out

ROOT_FS  = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8"
ROOT_RND = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8"

results = {}
for label, root in [("fastStorage", ROOT_FS), ("rnd", ROOT_RND)]:
    files = sorted(glob.glob(os.path.join(root, "*.csv")))
    sample = random.sample(files, min(200, len(files)))  # ML is heavier, use 200
    print(f"### {label}: {len(sample)} files", file=sys.stderr)
    df = process(sample)
    df.to_csv(f"ml_{label}.csv", index=False)
    results[label] = summarize(df) if len(df) else {}
    print(f"### {label}: {len(df)} bins done", file=sys.stderr)

with open("ml_summary.json", "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))
