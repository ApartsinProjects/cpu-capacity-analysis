"""Shared preprocessing helpers extracted from refit_form_ab.py."""
import os, numpy as np, pandas as pd

CPU_FLOOR = 0.05
MIN_N = 60

def read_vm(fp):
    try:
        df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
    except Exception:
        return None
    df.columns = [c.strip() for c in df.columns]
    need = ["CPU usage [%]", "Timestamp [ms]", "Network received throughput [KB/s]"]
    if not all(c in df.columns for c in need):
        return None
    ts = df["Timestamp [ms]"].astype(float).values
    hours = (np.floor(ts / 3600).astype(int)) % 24
    cpu = df["CPU usage [%]"].astype(float).values
    net = df["Network received throughput [KB/s]"].astype(float).values
    m = np.isfinite(cpu) & np.isfinite(net) & (cpu >= CPU_FLOOR) & (cpu <= 100) & (net >= 0)
    return hours[m], cpu[m], net[m]

def per_vm_triples(hours, cpu, net):
    triples = []
    for h in range(24):
        m = hours == h
        if m.sum() < MIN_N: continue
        c = cpu[m]; n = net[m]
        triples.append((float(np.mean(n)), float(np.mean(np.log(c))), float(np.std(np.log(c)))))
    return np.array(triples)
