"""Parameter-scaling fit on Bitbrains.

For every (VM, hour-of-day) bin retained by the per-bin log-normal fit
(see scoping/fit.py, scoping/fit_rnd.py), we recompute mu, sigma of
log(CPU) and a load-index proxy `lam` from network-received throughput
(mean KB/s in the bin). We then fit per VM:

    mu(lam)    = alpha * lam + beta
    sigma(lam) = gamma / sqrt(lam) + delta

by ordinary least squares, and report the distribution of R^2 across VMs.
Caveat: Bitbrains has no transaction-count column; network throughput is a
proxy assumed monotone in request rate for typical VM workloads.
"""
import glob, os, random, sys, json
import numpy as np, pandas as pd

random.seed(42)
MIN_N = 60
CPU_FLOOR = 0.05
MIN_BINS_PER_VM = 6

def read_vm(fp):
    try:
        df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
    except Exception:
        return None
    df.columns = [c.strip() for c in df.columns]
    need = ["CPU usage [%]", "Timestamp [ms]", "Network received throughput [KB/s]"]
    if not all(c in df.columns for c in need): return None
    ts = df["Timestamp [ms]"].astype(float).values
    hours = (np.floor(ts / 3600).astype(int)) % 24
    cpu = df["CPU usage [%]"].astype(float).values
    net = df["Network received throughput [KB/s]"].astype(float).values
    mask = np.isfinite(cpu) & np.isfinite(net) & (cpu >= CPU_FLOOR) & (cpu <= 100) & (net >= 0)
    return hours[mask], cpu[mask], net[mask]


def ols_r2(x, y):
    if len(x) < 3 or np.std(x) == 0: return np.nan, np.nan, np.nan
    A = np.vstack([x, np.ones_like(x)]).T
    (a, b), *_ = np.linalg.lstsq(A, y, rcond=None)
    ypred = A @ np.array([a, b])
    ss_res = float(np.sum((y - ypred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return float(a), float(b), float(r2)


def process(files):
    per_vm = []
    for i, fp in enumerate(files):
        r = read_vm(fp)
        if r is None: continue
        hours, cpu, net = r
        triples = []
        for h in range(24):
            m = hours == h
            if m.sum() < MIN_N: continue
            c = cpu[m]; n = net[m]
            mu = float(np.mean(np.log(c)))
            sigma = float(np.std(np.log(c)))
            lam = float(np.mean(n))
            triples.append((lam, mu, sigma))
        if len(triples) < MIN_BINS_PER_VM: continue
        arr = np.array(triples)
        lam = arr[:, 0]; mu = arr[:, 1]; sig = arr[:, 2]
        # mu(lam) = alpha*lam + beta
        a1, b1, r2_mu = ols_r2(lam, mu)
        # sigma(lam) = gamma / sqrt(lam) + delta, i.e. sigma = gamma * (1/sqrt(lam)) + delta
        ok = lam > 0
        if ok.sum() < 3:
            r2_sig = np.nan; g = d = np.nan
        else:
            x = 1.0 / np.sqrt(lam[ok])
            g, d, r2_sig = ols_r2(x, sig[ok])
        per_vm.append({
            "vm": os.path.relpath(fp).replace("\\", "/"),
            "n_bins": len(triples),
            "alpha": a1, "beta": b1, "r2_mu": r2_mu,
            "gamma": g, "delta": d, "r2_sigma": r2_sig,
            "lam_min": float(lam.min()), "lam_max": float(lam.max()),
        })
        if (i + 1) % 25 == 0:
            print(f"  {i+1} files, {len(per_vm)} VMs kept", file=sys.stderr)
    return pd.DataFrame(per_vm)


def summarize(df):
    return {
        "n_vms": int(len(df)),
        "mu_r2":    {"median": float(df["r2_mu"].median()),    "share_ge_0.5": float((df["r2_mu"] >= 0.5).mean()),    "share_ge_0.8": float((df["r2_mu"] >= 0.8).mean())},
        "sigma_r2": {"median": float(df["r2_sigma"].median()), "share_ge_0.5": float((df["r2_sigma"] >= 0.5).mean()), "share_ge_0.8": float((df["r2_sigma"] >= 0.8).mean())},
        "alpha_median": float(df["alpha"].median()),
        "gamma_median": float(df["gamma"].median()),
    }


ROOT_FS  = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8"
ROOT_RND = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8"

results = {}
for label, root in [("fastStorage", ROOT_FS), ("rnd", ROOT_RND)]:
    files = sorted(glob.glob(os.path.join(root, "*.csv")))
    sample = random.sample(files, min(300, len(files)))
    print(f"### {label}: {len(sample)} files", file=sys.stderr)
    df = process(sample)
    df.to_csv(f"scaling_{label}.csv", index=False)
    results[label] = summarize(df)

with open("scaling_summary.json", "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))
