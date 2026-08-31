"""Unified sizing evaluation panel -- Alibaba cluster-trace-v2018.

Extends the Bitbrains unified panel (scoping/unified_eval.py) to a third
trace from a second provider. Same six sizing methods, same compute_ceilings
logic, same metrics, co-computed per (machine, hour-of-day) bin on the same
held-out split, so the Alibaba column is apples-to-apples with fastStorage
and Rnd.

Difference from unified_eval.py: the Alibaba machine_usage trace is 8 days at
~10 s resolution (vs Bitbrains's 30 days at 5 min). We hold out the last
TEST_DAYS=2 days as test and train on the first ~6. Because the resolution
is 30x finer, each retained (machine, hour) test bin has hundreds of samples,
so the share-at-target metric does not saturate the way it can at Bitbrains's
12-sample test bins -- which is precisely the reviewer-requested robustness
gain. ml_gbm_p998 needs >=8 days of training history for its 7-day rolling
features and is therefore n/a on the 8-day trace; the other five methods are
co-computed as on Bitbrains.

Output schema is identical to unified_{fastStorage,rnd}.csv so the same
bootstrap_cis.py and SLA logic consume it unchanged.
"""
import tarfile, os, sys, json, warnings
import numpy as np, pandas as pd
from scipy import stats
from sklearn.ensemble import GradientBoostingRegressor
warnings.filterwarnings("ignore")

np.random.seed(42)

K = 3
TARGET_CONF = 0.998
MIN_TRAIN_BIN = 60
MIN_TEST_BIN = 12
CPU_FLOOR = 0.05            # matches unified_eval.py sizing-panel filter
TEST_DAYS = 2              # last 2 of 8 days held out
MIN_SPAN_DAYS = 4
N_MACHINES = int(os.environ.get("ALI_N_MACHINES", "300"))
MAX_ROWS = int(os.environ.get("ALI_MAX_ROWS", "0"))   # 0 = scan all
TAR = os.environ.get("ALI_TAR",
    r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/alibaba/machine_usage.tar.gz")

METHODS = ["lognorm_ctop", "empirical_p998", "gauss_meanksd",
           "rolling_max", "ml_gbm_p998", "ewmq_p998"]

# ---- compute_ceilings: copied verbatim from unified_eval.py ----
def compute_ceilings(train, per_day_stats_train, days_train):
    out = {}
    try:
        s, _, sc = stats.lognorm.fit(train, floc=0)
        mu = np.log(sc); sigma = s
        out["lognorm_ctop"] = float(np.exp(mu + K * sigma))
    except Exception:
        out["lognorm_ctop"] = float("nan")
    out["empirical_p998"] = float(np.quantile(train, TARGET_CONF))
    out["gauss_meanksd"] = float(train.mean() + K * train.std())
    out["rolling_max"] = float(train.max())
    if len(per_day_stats_train) >= 3:
        past = per_day_stats_train["p99"].values
        w = 0.5 ** np.arange(len(past))[::-1]
        out["ewmq_p998"] = float(np.sum(w * past) / np.sum(w))
    else:
        out["ewmq_p998"] = float("nan")
    if len(per_day_stats_train) >= 8:
        X_tr, y_tr = [], []
        for _, row in per_day_stats_train.iterrows():
            d = row["day"]
            window = per_day_stats_train[
                (per_day_stats_train["day"] < d) &
                (per_day_stats_train["day"] >= d - 7)
            ]
            if len(window) < 3: continue
            feats = np.array([window["mean"].mean(), window["std"].mean(),
                              window["max"].mean(), window["p99"].mean()])
            samples = train[days_train == d]
            for sv in samples:
                X_tr.append(feats); y_tr.append(sv)
        if len(y_tr) >= 100:
            X_tr = np.array(X_tr); y_tr = np.array(y_tr)
            try:
                model = GradientBoostingRegressor(loss="quantile", alpha=TARGET_CONF,
                                                  n_estimators=40, max_depth=3, random_state=42)
                model.fit(X_tr, y_tr)
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
    if day_max - day_min < MIN_SPAN_DAYS: return []
    train_cutoff = day_max - TEST_DAYS
    rows = []
    for h in range(24):
        m_h = hours == h
        c_h = cpu[m_h]; d_h = days[m_h]
        if len(c_h) < 30: continue
        train_mask = d_h <= train_cutoff
        test_mask  = d_h >  train_cutoff
        tr = c_h[train_mask]; te = c_h[test_mask]
        tr_days = d_h[train_mask]
        if len(tr) < MIN_TRAIN_BIN or len(te) < MIN_TEST_BIN: continue
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

def stream_machines():
    """Collect ts/cpu series for the first N_MACHINES distinct machine ids."""
    from collections import defaultdict
    series = defaultdict(lambda: ([], []))  # m_id -> (ts_list, cpu_list)
    accepted = set()
    row_count = 0
    with tarfile.open(TAR, "r:gz") as tf:
        members = [m for m in tf.getmembers() if m.name.endswith(".csv")]
        for member in members:
            f = tf.extractfile(member)
            for line in f:
                row_count += 1
                if MAX_ROWS and row_count > MAX_ROWS: break
                if row_count % 20_000_000 == 0:
                    print(f"  row {row_count:,}, {len(accepted)} machines", file=sys.stderr)
                p = line.decode("utf-8", "ignore").rstrip("\n").split(",")
                if len(p) < 3: continue
                try:
                    mid = p[0]; ts = int(p[1]); cpu = float(p[2])
                except (ValueError, IndexError):
                    continue
                if mid not in accepted:
                    if len(accepted) < N_MACHINES:
                        accepted.add(mid)
                    else:
                        continue
                if not (CPU_FLOOR <= cpu <= 100): continue
                tl, cl = series[mid]
                tl.append(ts); cl.append(cpu)
            if MAX_ROWS and row_count > MAX_ROWS: break
    print(f"scanned {row_count:,} rows; {len(series)} machines collected", file=sys.stderr)
    return series

def main():
    series = stream_machines()
    all_rows = []
    for i, (mid, (tl, cl)) in enumerate(series.items()):
        ts = np.asarray(tl, dtype=float)
        cpu = np.asarray(cl, dtype=float)
        hours = (np.floor(ts / 3600).astype(int)) % 24
        days = np.floor(ts / 86400).astype(int)
        all_rows.extend(process_vm(hours, days, cpu, mid))
        if (i + 1) % 50 == 0:
            print(f"  {i+1} machines processed, {len(all_rows)} bins", file=sys.stderr)
    df = pd.DataFrame(all_rows)
    df.to_csv("unified_alibaba.csv", index=False)
    n_bins = len(df); n_vms = df["vm"].nunique() if n_bins else 0
    summary = {"n_vms": int(n_vms), "n_bins": int(n_bins)}
    for m in METHODS:
        if f"cov_{m}" not in df.columns:
            summary[m] = {"n_valid": 0}; continue
        cov = df[f"cov_{m}"]; ct = df[f"ctop_{m}"]
        rel = (ct - df["test_p99"]) / df["test_p99"].replace(0, np.nan)
        summary[m] = {
            "mean_coverage":      float(cov.mean()),
            "share_at_target":    float((cov >= TARGET_CONF).mean()),
            "median_ceiling_pct": float(ct.median()),
            "median_rel_cost":    float(rel.median()),
            "n_valid":            int(ct.notna().sum()),
        }
    with open("unified_alibaba_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
