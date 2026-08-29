"""Composite load-index proxy on Bitbrains: combine
network-received + disk-read + disk-write + memory-delta into a single
load-rate proxy per bin. Compare Spearman(proxy, CPU) against the
single-signal network proxy currently used by scaling_fit.py.
"""
import os, glob, random, sys, json
import numpy as np, pandas as pd
from scipy.stats import spearmanr

random.seed(42)
ROOT = {
    "fastStorage": r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8",
    "rnd":         r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8",
}
N_SAMPLE = 200
CPU_FLOOR = 0.05

def read_vm(fp):
    try:
        df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
    except Exception: return None
    df.columns = [c.strip() for c in df.columns]
    need = ["CPU usage [%]", "Timestamp [ms]", "Network received throughput [KB/s]",
            "Disk read throughput [KB/s]", "Disk write throughput [KB/s]",
            "Memory usage [KB]"]
    if not all(c in df.columns for c in need): return None
    ts = df["Timestamp [ms]"].astype(float).values
    order = np.argsort(ts)
    df = df.iloc[order].reset_index(drop=True)
    ts = df["Timestamp [ms]"].astype(float).values
    cpu = df["CPU usage [%]"].astype(float).values
    net = df["Network received throughput [KB/s]"].astype(float).values
    dr  = df["Disk read throughput [KB/s]"].astype(float).values
    dw  = df["Disk write throughput [KB/s]"].astype(float).values
    mem = df["Memory usage [KB]"].astype(float).values
    # memory delta (positive part) as proxy for new allocations
    mem_delta = np.diff(mem, prepend=mem[0])
    mem_delta_pos = np.maximum(mem_delta, 0)
    mask = (np.isfinite(cpu) & np.isfinite(net) & np.isfinite(dr) &
            np.isfinite(dw) & np.isfinite(mem_delta_pos) &
            (cpu >= CPU_FLOOR) & (cpu <= 100))
    return {"cpu": cpu[mask], "net": net[mask], "disk_r": dr[mask],
            "disk_w": dw[mask], "mem_delta": mem_delta_pos[mask]}

def zscore(x):
    s = np.std(x)
    return (x - np.mean(x)) / s if s > 1e-9 else x - np.mean(x)

per_vm_rows = []
for label, root in ROOT.items():
    files = sorted(glob.glob(os.path.join(root, "*.csv")))
    sample = random.sample(files, min(N_SAMPLE, len(files)))
    print(f"### {label}: {len(sample)} files", file=sys.stderr)
    for i, fp in enumerate(sample):
        r = read_vm(fp)
        if r is None or len(r["cpu"]) < 60: continue
        # Spearman for each single signal
        rho_net,  _ = spearmanr(r["cpu"], r["net"])
        rho_dr,   _ = spearmanr(r["cpu"], r["disk_r"])
        rho_dw,   _ = spearmanr(r["cpu"], r["disk_w"])
        rho_md,   _ = spearmanr(r["cpu"], r["mem_delta"])
        # Composite: equal-weight sum of z-scored signals
        composite = zscore(r["net"]) + zscore(r["disk_r"]) + zscore(r["disk_w"]) + zscore(r["mem_delta"])
        rho_comp, _ = spearmanr(r["cpu"], composite)
        # Composite excluding weak signals: net + disk_r + disk_w
        composite_v2 = zscore(r["net"]) + zscore(r["disk_r"]) + zscore(r["disk_w"])
        rho_comp2, _ = spearmanr(r["cpu"], composite_v2)
        per_vm_rows.append({"trace": label, "vm": os.path.basename(fp),
                             "n": len(r["cpu"]),
                             "rho_net": float(rho_net),
                             "rho_disk_read": float(rho_dr),
                             "rho_disk_write": float(rho_dw),
                             "rho_mem_delta": float(rho_md),
                             "rho_composite_all": float(rho_comp),
                             "rho_composite_net_disk": float(rho_comp2)})
    print(f"  processed {sum(1 for r in per_vm_rows if r['trace']==label)} VMs", file=sys.stderr)

df = pd.DataFrame(per_vm_rows).dropna()
df.to_csv("E:/Projects/Submitted/Amdocs/scoping/composite_proxy.csv", index=False)

summary = {}
for label in ["fastStorage", "rnd"]:
    sub = df[df["trace"] == label]
    summary[label] = {
        "n_vms": int(len(sub)),
        "median_rho_net": float(sub["rho_net"].median()),
        "median_rho_disk_read": float(sub["rho_disk_read"].median()),
        "median_rho_disk_write": float(sub["rho_disk_write"].median()),
        "median_rho_mem_delta": float(sub["rho_mem_delta"].median()),
        "median_rho_composite_all": float(sub["rho_composite_all"].median()),
        "median_rho_composite_net_disk": float(sub["rho_composite_net_disk"].median()),
    }
with open("E:/Projects/Submitted/Amdocs/scoping/composite_proxy_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
