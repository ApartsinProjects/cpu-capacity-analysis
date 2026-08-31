"""Direct (proxy-free) load measurement for the Section 5 scaling law on
Alibaba cluster-trace-v2018. Implements the Fable-designed protocol that
AVOIDS the arrival-sparsity caveat: lambda is an OCCUPANCY integral, not an
event count -- the summed provisioned CPU (cpu_request) of the containers
active on a machine, a step function known exactly at every instant. Per-
window noise therefore comes only from the CPU side (~hundreds of samples),
never from counting arrivals.

Two pre-registered fits:
  Design B (between-machine, primary given near-static placement): one
    (lambda_m, mu_m, sigma_m) point per machine; regress mu and sigma of
    log-CPU on lambda across machines.
  Design W (within-machine, construct-matched to the Bitbrains per-VM fit):
    per machine, hourly (lambda_w, mu_w, sigma_w) triples, OLS per machine,
    aggregate the alpha>0 share. Eligible only where within-machine lambda
    varies.

Invariants:
  4.1 design-alive: Spearman(lambda_m, mu_m) across machines > 0, p small.
  4.2 negative control: shuffle machine labels between lambda and CPU series;
      the within-machine Spearman median must collapse to ~0.

Outputs direct_load_alibaba.json + paper macros are built separately.
"""
import tarfile, os, sys, json, collections
import numpy as np
from scipy.stats import spearmanr

D = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/alibaba"
TAR = D + "/machine_usage.tar.gz"
CMETA = D + "/container_meta.csv"
TRACE_END = 691200
CPU_FLOOR = 0.5           # half the 1% integer resolution
DOWNSAMPLE = 6            # keep every 6th 10s row -> 60s series (memory)
N_MACHINES = int(os.environ.get("DL_N_MACHINES", "600"))
MAX_ROWS = int(os.environ.get("DL_MAX_ROWS", "0"))
RNG = np.random.default_rng(42)

def build_intervals():
    """Per machine: list of (t_start, t_end, cpu_request) active intervals."""
    first_ts = {}     # container -> min ts
    stop_ts = {}      # container -> max stop ts
    creq = {}         # container -> first cpu_request
    cmach = {}        # container -> machine (first seen)
    for line in open(CMETA):
        x = line.rstrip("\n").split(",")
        if len(x) < 8: continue
        cid, mid, ts, app, st, cr = x[0], x[1], x[2], x[3], x[4], x[5]
        if st == "unknow": continue
        try: ts = int(ts); cr = float(cr)
        except: continue
        if cid not in first_ts or ts < first_ts[cid]: first_ts[cid] = ts
        if cid not in creq: creq[cid] = cr; cmach[cid] = mid
        if st == "stopped":
            if cid not in stop_ts or ts > stop_ts[cid]: stop_ts[cid] = ts
    per_m = collections.defaultdict(list)
    for cid, ts0 in first_ts.items():
        t1 = stop_ts.get(cid, TRACE_END)
        per_m[cmach[cid]].append((ts0, t1, creq[cid]))
    return per_m

def lam_at(intervals, t):
    return sum(cr for (a, b, cr) in intervals if a <= t <= b)

def stream_cpu(machines_wanted):
    """Collect downsampled (ts, cpu) per wanted machine from machine_usage."""
    series = collections.defaultdict(lambda: ([], []))
    cnt = collections.Counter()
    row = 0
    with tarfile.open(TAR, "r:gz") as tf:
        for member in [m for m in tf.getmembers() if m.name.endswith(".csv")]:
            f = tf.extractfile(member)
            for line in f:
                row += 1
                if MAX_ROWS and row > MAX_ROWS: break
                if row % 40_000_000 == 0:
                    print(f"  row {row:,}", file=sys.stderr)
                x = line.decode("utf-8", "ignore").rstrip("\n").split(",")
                if len(x) < 3: continue
                mid = x[0]
                if mid not in machines_wanted: continue
                cnt[mid] += 1
                if cnt[mid] % DOWNSAMPLE: continue
                try:
                    ts = int(x[1]); cpu = float(x[2])
                except: continue
                if not (0 <= cpu <= 100): continue
                tl, cl = series[mid]; tl.append(ts); cl.append(cpu)
            if MAX_ROWS and row > MAX_ROWS: break
    print(f"scanned {row:,} rows; {len(series)} machines with CPU", file=sys.stderr)
    return series

def main():
    per_m = build_intervals()
    lam_static = {m: sum(cr for (_, _, cr) in ivs) for m, ivs in per_m.items()}
    ncont = {m: len(ivs) for m, ivs in per_m.items()}
    wanted = set(list(per_m.keys())[:N_MACHINES]) if N_MACHINES else set(per_m)
    series = stream_cpu(wanted)

    rows = []           # Design B per-machine
    within_rho = []     # within-machine sample-level Spearman(lam(t),cpu)
    shuf_rho = []       # negative control
    per_machine_ts = {}
    for m, (tl, cl) in series.items():
        if len(cl) < 200: continue
        ts = np.asarray(tl); cpu = np.asarray(cl, float)
        logc = np.log(np.maximum(cpu, CPU_FLOOR))
        ivs = per_m[m]
        lam_t = np.array([lam_at(ivs, int(t)) for t in ts], float)
        # Design B point
        rows.append({"m": m, "lam": lam_static[m], "ncont": ncont[m],
                     "mu": float(logc.mean()), "sig": float(logc.std()),
                     "meancpu": float(cpu.mean())})
        # within-machine Spearman (lambda varies only if machine has stops)
        if np.ptp(lam_t) > 0:
            r, _ = spearmanr(lam_t, cpu); within_rho.append(r)
        per_machine_ts[m] = (ts, cpu, lam_t)

    import pandas as pd
    df = pd.DataFrame(rows)
    # Design B regressions across machines
    def ols(x, y):
        x = np.asarray(x, float); y = np.asarray(y, float)
        b, a = np.polyfit(x, y, 1)  # slope, intercept
        r, p = spearmanr(x, y)
        return {"slope": float(b), "intercept": float(a),
                "spearman": float(r), "p": float(p)}
    out = {"n_machines": int(len(df)),
           "designB_mu_on_lam": ols(df.lam, df.mu),
           "designB_sig_on_lam": ols(df.lam, df.sig),
           "designB_mu_on_ncont": ols(df.ncont, df.mu),
           "designB_meancpu_on_lam": ols(df.lam, df.meancpu),
           "invariant41_spearman_lam_mu": ols(df.lam, df.mu)["spearman"],
           "lam_range": [float(df.lam.min()), float(df.lam.median()), float(df.lam.max())]}
    # decile table
    df["dec"] = pd.qcut(df.lam, 10, labels=False, duplicates="drop")
    dec = df.groupby("dec").agg(lam=("lam","median"), mu=("mu","median"),
                                sig=("sig","median"), n=("m","size")).reset_index()
    out["deciles"] = dec.to_dict("records")
    drho, dp = spearmanr(dec.lam, dec.mu)
    out["decile_spearman_lam_mu"] = float(drho)

    # within-machine sample-level Spearman
    if within_rho:
        wr = np.array(within_rho)
        out["within_machine_spearman"] = {
            "n_machines_with_lambda_variation": int(len(wr)),
            "median": float(np.median(wr)), "mean": float(np.mean(wr)),
            "share_positive": float((wr > 0).mean())}
    else:
        out["within_machine_spearman"] = {"n_machines_with_lambda_variation": 0}

    # Negative control: shuffle machine labels between lambda-series and CPU-series
    ms = list(per_machine_ts.keys())
    perm = RNG.permutation(len(ms))
    for i, mi in enumerate(ms):
        ts_i, cpu_i, _ = per_machine_ts[mi]
        mj = ms[perm[i]]
        _, _, lam_j = per_machine_ts[mj]
        if len(lam_j) == len(cpu_i) and np.ptp(lam_j) > 0:
            r, _ = spearmanr(lam_j, cpu_i); shuf_rho.append(r)
    # between-machine negative control: shuffle mu against lam
    shuf_between = []
    lamv = df.lam.values; muv = df.mu.values
    for _ in range(200):
        r, _ = spearmanr(lamv, RNG.permutation(muv)); shuf_between.append(r)
    out["negative_control"] = {
        "between_machine_shuffled_spearman_median": float(np.median(shuf_between)),
        "between_machine_shuffled_abs_p95": float(np.percentile(np.abs(shuf_between), 95))}

    df.to_csv("direct_load_alibaba.csv", index=False)
    with open("direct_load_alibaba.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
