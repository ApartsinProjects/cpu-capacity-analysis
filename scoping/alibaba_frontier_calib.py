"""#1 matched-coverage frontier + #2 calibration/reliability, on Alibaba
(10s) and Bitbrains fastStorage (5min).

#1: sweep K in the log-normal ceiling exp(mu+K sigma) and m in m*trainmax;
    at the coverage the rolling maximum achieves, find the K that matches it
    and compare reserved headroom. Answers: at EQUAL safety, does the
    parametric ceiling reserve less capacity than the empirical maximum,
    even at 10s resolution (where the fixed-k=3 comparison lost)?

#2: for nominal target quantiles q, build each parametric ceiling at q
    (lognorm exp(mu+z_q sigma); gauss mean+z_q std; empirical train-quantile),
    and measure realized held-out coverage. A calibrated model lands on the
    diagonal (realized ~ nominal); a sizing-safe model sits on/above it.
"""
import os, glob, sys, json, tarfile
import numpy as np, pandas as pd
from scipy import stats
from collections import defaultdict

CPU_FLOOR = 0.05
MIN_TRAIN_BIN = 60
MIN_TEST_BIN = 12
TARGET = 0.998
KS = np.round(np.linspace(1.0, 5.0, 41), 3)
MS = np.round(np.linspace(0.6, 2.2, 33), 3)
QGRID = [0.90, 0.95, 0.99, 0.998, 0.999]
ZQ = {q: float(stats.norm.ppf(q)) for q in QGRID}

ALI_TAR = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/alibaba/machine_usage.tar.gz"
FS_ROOT = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8"

def make_bin(tr, te):
    if len(tr) < MIN_TRAIN_BIN or len(te) < MIN_TEST_BIN: return None
    try:
        s, _, sc = stats.lognorm.fit(tr, floc=0)
        mu = np.log(sc); sigma = s
    except Exception:
        return None
    # compact train sample for arbitrary-quantile (empirical-frontier) sweeps
    etr = np.sort(tr.astype(np.float32))
    if len(etr) > 600:
        etr = etr[np.linspace(0, len(etr)-1, 600).astype(int)]
    return {"mu": float(mu), "sigma": float(sigma),
            "tmean": float(tr.mean()), "tstd": float(tr.std()),
            "trainmax": float(tr.max()), "etrain": etr,
            "eq": {q: float(np.quantile(tr, q)) for q in QGRID},
            "test": te.astype(np.float32), "test_p99": float(np.quantile(te, 0.99))}

def collect_alibaba(n_machines=250, test_days=2, downsample=2):
    per = defaultdict(lambda: ([], []))
    seen = defaultdict(int)
    acc = set(); row = 0
    with tarfile.open(ALI_TAR, "r:gz") as tf:
        for member in [m for m in tf.getmembers() if m.name.endswith(".csv")]:
            f = tf.extractfile(member)
            for line in f:
                row += 1
                if row % 60_000_000 == 0: print(f"  ali row {row:,}", file=sys.stderr)
                p = line.decode("utf-8", "ignore").rstrip("\n").split(",")
                if len(p) < 3: continue
                mid = p[0]
                if mid not in acc:
                    if len(acc) < n_machines: acc.add(mid)
                    else: continue
                seen[mid] += 1
                if seen[mid] % downsample: continue     # thin the 10s series
                try: ts = int(p[1]); cpu = float(p[2])
                except: continue
                if not (CPU_FLOOR <= cpu <= 100): continue
                tl, cl = per[mid]; tl.append(ts); cl.append(np.float32(cpu))
    bins = []
    for mid in list(per.keys()):
        tl, cl = per.pop(mid)
        ts = np.asarray(tl, dtype=np.int32); cpu = np.asarray(cl, dtype=np.float32)
        hours = (ts // 3600) % 24; days = ts // 86400
        if days.max() - days.min() < 4: continue
        cut = days.max() - test_days
        for h in range(24):
            mh = hours == h
            c = cpu[mh]; d = days[mh]
            if len(c) < 30: continue
            b = make_bin(c[d <= cut], c[d > cut])
            if b: b["vm"] = mid; bins.append(b)
    return bins

def collect_fs(n_files=250, test_days=6):
    import random; random.seed(42)
    files = sorted(glob.glob(os.path.join(FS_ROOT, "*.csv")))
    files = random.sample(files, min(n_files, len(files)))
    bins = []
    for fp in files:
        try:
            df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
        except Exception: continue
        df.columns = [c.strip() for c in df.columns]
        if "CPU usage [%]" not in df.columns: continue
        ts = df["Timestamp [ms]"].astype(float).values
        hours = (np.floor(ts/3600).astype(int)) % 24; days = np.floor(ts/86400).astype(int)
        cpu = df["CPU usage [%]"].astype(float).values
        m = np.isfinite(cpu) & (cpu >= CPU_FLOOR) & (cpu <= 100)
        hours, days, cpu = hours[m], days[m], cpu[m]
        if len(cpu) == 0 or days.max()-days.min() < 8+test_days: continue
        cut = days.max() - test_days
        for h in range(24):
            mh = hours == h; c = cpu[mh]; d = days[mh]
            if len(c) < 30: continue
            b = make_bin(c[d <= cut], c[d > cut])
            if b: b["vm"] = fp; bins.append(b)
    return bins

def frontier(bins):
    rows = []
    def med_headroom(bins, ceil):
        hr = [(c-b["test_p99"])/b["test_p99"] for b, c in zip(bins, ceil) if b["test_p99"]>0]
        return float(np.median(hr))
    def add(method, param, ceil):
        cov = np.array([(b["test"] <= c).mean() for b, c in zip(bins, ceil)])
        rows.append({"method":method,"param":float(param),
                     "share_at_target":float((cov>=TARGET).mean()),
                     "mean_coverage":float(cov.mean()),
                     "median_headroom":med_headroom(bins, ceil),
                     "median_ceiling":float(np.median(ceil))})
    QLEVELS = np.round(1 - np.geomspace(0.20, 0.0005, 40), 5)  # 0.80 .. 0.9995
    for K in KS:
        add("lognorm", K, np.array([np.exp(b["mu"]+K*b["sigma"]) for b in bins]))
        add("gauss",   K, np.array([b["tmean"]+K*b["tstd"] for b in bins]))
    for m in MS:
        add("rolling_max", m, np.array([m*b["trainmax"] for b in bins]))
    for q in QLEVELS:
        add("empirical", q, np.array([float(np.quantile(b["etrain"], q)) for b in bins]))
    return pd.DataFrame(rows)

def matched_coverage(fr):
    """At the rolling_max operating point m=1 (its share), find the lognorm K
    whose share matches, and compare MEDIAN ceiling and median headroom
    (robust to near-floor test_p99 outliers)."""
    ln = fr[fr.method=="lognorm"].sort_values("param")
    rm = fr[fr.method=="rolling_max"].sort_values("param")
    rm1 = rm.iloc[(rm.param-1.0).abs().argmin()]
    target_share = rm1["share_at_target"]
    i = int((ln["share_at_target"]-target_share).abs().argmin())
    lnm = ln.iloc[i]
    ceil_ratio = float(lnm["median_ceiling"]/rm1["median_ceiling"]) if rm1["median_ceiling"] else float("nan")
    return {"rm_share_at_m1":float(rm1["share_at_target"]),
            "rm_median_ceiling_at_m1":float(rm1["median_ceiling"]),
            "rm_median_headroom_at_m1":float(rm1["median_headroom"]),
            "ln_matched_K":float(lnm["param"]),
            "ln_matched_share":float(lnm["share_at_target"]),
            "ln_matched_median_ceiling":float(lnm["median_ceiling"]),
            "ln_matched_median_headroom":float(lnm["median_headroom"]),
            "ceiling_ratio_ln_over_rm":ceil_ratio,
            "ceiling_saving_pct":float(100*(1-ceil_ratio))}

def calibration(bins):
    out = {}
    for q in QGRID:
        z = ZQ[q]
        for name, ceilfn in [("lognorm", lambda b: np.exp(b["mu"]+z*b["sigma"])),
                             ("gauss",   lambda b: b["tmean"]+z*b["tstd"]),
                             ("empirical", lambda b: b["eq"][q])]:
            covs = np.array([(b["test"] <= ceilfn(b)).mean() for b in bins])
            out.setdefault(name, []).append({"nominal":q,
                "realized_mean_cov":float(covs.mean()),
                "share_at_nominal":float((covs>=q).mean()),
                "median_headroom":float(np.median([(ceilfn(b)-b["test_p99"])/b["test_p99"]
                                                   if b["test_p99"]>0 else np.nan for b in bins]))})
    return out

def pinball(y, q, alpha=0.998):
    d = y - q
    return float(np.mean(np.where(d > 0, alpha * d, (alpha - 1) * d)))

def metrics(bins):
    """Per-method proper-scoring (pinball@0.998) + intuitive excess-capacity
    ratio (ceiling / realized 0.998 quantile of the test window). The excess
    ratio is 1.0 for a perfectly-tight ceiling; >1 wastes capacity; <1
    under-covers. Reported as median over bins, with coverage."""
    defs = {"lognorm": lambda b: np.exp(b["mu"] + 3*b["sigma"]),
            "gauss":   lambda b: b["tmean"] + 3*b["tstd"],
            "empirical": lambda b: b["eq"][0.998],
            "rolling_max": lambda b: b["trainmax"]}
    out = {}
    for name, fn in defs.items():
        pins, exc, cov = [], [], []
        for b in bins:
            c = fn(b)
            q998 = float(np.quantile(b["test"], 0.998))
            pins.append(pinball(b["test"], c))
            if q998 > 0: exc.append(c / q998)
            cov.append(float((b["test"] <= c).mean()))
        out[name] = {"median_pinball": float(np.median(pins)),
                     "mean_pinball": float(np.mean(pins)),
                     "median_excess_ratio": float(np.median(exc)),
                     "mean_coverage": float(np.mean(cov)),
                     "share_at_target": float(np.mean(np.array(cov) >= TARGET))}
    return out

def run(label, bins):
    print(f"### {label}: {len(bins)} bins, {len({b['vm'] for b in bins})} units", file=sys.stderr)
    fr = frontier(bins)
    fr.to_csv(f"frontier_{label}.csv", index=False)
    mc = matched_coverage(fr)
    cal = calibration(bins)
    met = metrics(bins)
    pd.DataFrame(sum(([{**r,"method":k} for r in v] for k,v in cal.items()), [])).to_csv(f"calib_{label}.csv", index=False)
    return {"n_bins":len(bins), "n_units":len({b['vm'] for b in bins}),
            "matched_coverage":mc, "calibration":cal, "metrics":met}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "alibaba"
    bins = collect_alibaba() if which == "alibaba" else collect_fs()
    res = run(which, bins)
    del bins
    with open(f"frontier_calib_{which}.json", "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))
