"""SLA-aware revenue simulation.

Uses per-(VM, hour-of-day) sizing results (from sizing_eval.py) to compute
per-VM availability under each of four sizing methods, then applies three
public cloud SLA schedules to obtain service-credit fractions per method
per provider. Reports mean credit and mean net-revenue-ratio per method
per provider across VMs.

Availability per VM per method:
    A = sum(cov_method[b] * n_test[b]) / sum(n_test[b])
    across all retained hour-of-day bins b for that VM.

SLA schedules (monthly uptime -> service credit fraction):
    AWS EC2:    >= 0.9999 -> 0 ; >= 0.99 -> 0.10 ; >= 0.95 -> 0.25 ; else 1.00
    GCP CE:     >= 0.9999 -> 0 ; >= 0.99 -> 0.10 ; >= 0.95 -> 0.25 ; else 0.50
    Azure VM:   >= 0.9999 -> 0 ; >= 0.99 -> 0.10 ; >= 0.95 -> 0.25 ; else 1.00
"""
import os, json
import numpy as np, pandas as pd

METHODS = ["lognorm_ctop", "empirical_p998", "gauss_meanksd", "rolling_max"]

def credit_aws(a):
    if a >= 0.9999: return 0.0
    if a >= 0.99:   return 0.10
    if a >= 0.95:   return 0.25
    return 1.00

def credit_gcp(a):
    if a >= 0.9999: return 0.0
    if a >= 0.99:   return 0.10
    if a >= 0.95:   return 0.25
    return 0.50

def credit_azure(a):
    if a >= 0.9999: return 0.0
    if a >= 0.99:   return 0.10
    if a >= 0.95:   return 0.25
    return 1.00

SCHEDULES = {"AWS": credit_aws, "GCP": credit_gcp, "Azure": credit_azure}

def per_vm_availability(df):
    """One row per (vm, method) with A."""
    rows = []
    for (vm,), g in df.groupby(["vm"]):
        n_tot = g["n_test"].sum()
        if n_tot == 0: continue
        row = {"vm": vm, "n_test": int(n_tot)}
        for m in METHODS:
            covs = g[f"cov_{m}"].values
            ns = g["n_test"].values
            valid = np.isfinite(covs)
            if not valid.any():
                row[f"A_{m}"] = np.nan
                continue
            row[f"A_{m}"] = float(np.sum(covs[valid] * ns[valid]) / np.sum(ns[valid]))
        rows.append(row)
    return pd.DataFrame(rows)

def summarize(vm_df):
    out = {}
    for m in METHODS:
        col = vm_df[f"A_{m}"]
        method_out = {
            "n_vms": int(col.notna().sum()),
            "mean_availability": float(col.mean()),
            "median_availability": float(col.median()),
            "share_ge_9999": float((col >= 0.9999).mean()),
            "share_ge_99":   float((col >= 0.99).mean()),
            "share_ge_95":   float((col >= 0.95).mean()),
        }
        for prov, fn in SCHEDULES.items():
            credits = col.dropna().apply(fn)
            method_out[f"mean_credit_{prov}"] = float(credits.mean())
            method_out[f"mean_net_revenue_ratio_{prov}"] = float(1 - credits.mean())
        out[m] = method_out
    return out

results = {}
for label in ["fastStorage", "rnd"]:
    fp = f"sizing_{label}.csv"
    if not os.path.exists(fp):
        print(f"skip {label}: {fp} not found"); continue
    df = pd.read_csv(fp)
    vm_df = per_vm_availability(df)
    vm_df.to_csv(f"sla_{label}.csv", index=False)
    results[label] = summarize(vm_df)

with open("sla_summary.json", "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))
