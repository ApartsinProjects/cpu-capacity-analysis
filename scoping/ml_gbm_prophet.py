"""Additional ML baseline: gradient-boosted quantile regression with a
richer feature set (hour-of-day, day-of-week, lag-1/lag-7-day p99,
rolling-window aggregates), evaluated at alpha=0.998 on the unified panel.

This is a stronger baseline than the existing ml_gbm_p998 in unified_eval.py,
which used only 4 aggregate features. Adds seasonal + short-lag features
that a Prophet or LSTM forecaster would use. Kept intentionally lightweight
(no PyTorch dependency) but reflects the same class of data-driven
tail-percentile forecasters reviewers ask for.
"""
import glob, os, random, sys, json, warnings
import numpy as np, pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
warnings.filterwarnings("ignore")

random.seed(42); np.random.seed(42)

CPU_FLOOR = 0.05
TARGET = 0.998
MIN_TRAIN, MIN_TEST = 60, 12
TEST_DAYS = 6

def read_vm(fp):
    try: df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
    except Exception: return None
    df.columns = [c.strip() for c in df.columns]
    if "CPU usage [%]" not in df.columns or "Timestamp [ms]" not in df.columns: return None
    ts = df["Timestamp [ms]"].astype(float).values
    hours = (np.floor(ts / 3600).astype(int)) % 24
    days = np.floor(ts / 86400).astype(int)
    dow = (days % 7).astype(int)
    cpu = df["CPU usage [%]"].astype(float).values
    m = np.isfinite(cpu) & (cpu >= CPU_FLOOR) & (cpu <= 100)
    return ts[m], hours[m], days[m], dow[m], cpu[m]

def build_features(hours, days, dow, cpu, target_day, target_hour):
    """Rich features: hour, day-of-week, lag-7-day same-hour p99, rolling stats."""
    m_h = (hours == target_hour) & (days < target_day)
    if m_h.sum() < 3: return None
    c_h = cpu[m_h]; d_h = days[m_h]
    # per-day stats at this hour
    per_day = pd.DataFrame({"day": d_h, "cpu": c_h}).groupby("day")["cpu"].agg([
        "mean","std","max",lambda x: np.quantile(x, 0.99)]).reset_index()
    per_day.columns = ["day","mean","std","max","p99"]
    if len(per_day) < 3: return None
    # lag-1 day same-hour p99
    lag1 = per_day.iloc[-1]["p99"] if len(per_day) >= 1 else np.nan
    # lag-7 day same-hour p99
    lag7 = per_day.iloc[-7]["p99"] if len(per_day) >= 7 else per_day.iloc[0]["p99"]
    # rolling 7-day aggregates
    recent = per_day.tail(7)
    return np.array([
        target_hour, target_dow, lag1, lag7,
        float(recent["mean"].mean()), float(recent["std"].mean()),
        float(recent["max"].mean()), float(recent["p99"].mean()),
    ])

target_dow = 0  # placeholder; used inside build_features

def eval_vm(fp):
    r = read_vm(fp)
    if r is None: return []
    ts, hours, days, dow, cpu = r
    if len(cpu) == 0: return []
    day_max = days.max(); day_min = days.min()
    if day_max - day_min < 8 + TEST_DAYS: return []
    train_cutoff = day_max - TEST_DAYS
    rows = []
    for h in range(24):
        m_h = hours == h
        c_h = cpu[m_h]; d_h = days[m_h]; dw_h = dow[m_h]
        if len(c_h) < 30: continue
        train_mask = d_h <= train_cutoff
        test_mask = d_h > train_cutoff
        tr, te = c_h[train_mask], c_h[test_mask]
        tr_days, tr_dow = d_h[train_mask], dw_h[train_mask]
        if len(tr) < MIN_TRAIN or len(te) < MIN_TEST: continue
        # Build training set: for each training day, features → sample values
        X_tr, y_tr = [], []
        for d in np.unique(tr_days):
            global target_dow
            target_dow = int(dw_h[d_h == d][0])
            feats = build_features(hours, days, dow, cpu, d, h)
            if feats is None: continue
            samples = c_h[d_h == d]
            for s in samples:
                X_tr.append(feats); y_tr.append(s)
        if len(y_tr) < 100: continue
        X_tr, y_tr = np.array(X_tr), np.array(y_tr)
        try:
            model = GradientBoostingRegressor(loss="quantile", alpha=TARGET,
                                              n_estimators=80, max_depth=4,
                                              learning_rate=0.1, random_state=42)
            model.fit(X_tr, y_tr)
        except Exception: continue
        # Predict for the test-window using the day just before test start
        target_dow = int(dow[days == train_cutoff][0]) if (days == train_cutoff).any() else 0
        test_feats = build_features(hours, days, dow, cpu, train_cutoff + 1, h)
        if test_feats is None: continue
        pred = float(model.predict(test_feats.reshape(1, -1))[0])
        rows.append({"vm": os.path.basename(fp), "hour": h,
                     "n_test": int(len(te)),
                     "ctop_ml_rich": pred,
                     "cov_ml_rich": float(np.mean(te <= pred)),
                     "test_p99": float(np.quantile(te, 0.99))})
    return rows

ROOTS = {
    "fastStorage": r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8",
    "rnd":         r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8",
}
summary = {}
for label, root in ROOTS.items():
    files = sorted(glob.glob(os.path.join(root, "*.csv")))
    sample = random.sample(files, min(250, len(files)))
    print(f"### {label}: {len(sample)} files", file=sys.stderr)
    rows = []
    for i, fp in enumerate(sample):
        rows.extend(eval_vm(fp))
        if (i + 1) % 50 == 0:
            print(f"  {i+1} files, {len(rows)} bins", file=sys.stderr)
    df = pd.DataFrame(rows)
    if len(df):
        df.to_csv(f"E:/Projects/Submitted/Amdocs/scoping/ml_rich_{label}.csv", index=False)
        summary[label] = {
            "n_bins": int(len(df)),
            "mean_coverage": float(df["cov_ml_rich"].mean()),
            "share_at_target": float((df["cov_ml_rich"] >= TARGET).mean()),
            "median_ceiling": float(df["ctop_ml_rich"].median()),
        }
    print(f"### {label} done: {len(df)} bins, share@target={summary.get(label,{}).get('share_at_target', 0)*100:.2f}%", file=sys.stderr)

with open("E:/Projects/Submitted/Amdocs/scoping/ml_rich_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
