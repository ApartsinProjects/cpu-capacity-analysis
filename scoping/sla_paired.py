"""Paired per-VM SLA credit comparison, lognorm vs each baseline."""
import json, numpy as np, pandas as pd
from scipy.stats import binomtest

RNG = np.random.default_rng(0)
B = 10_000
METHODS = ["lognorm_ctop", "empirical_p998", "gauss_meanksd",
           "rolling_max", "ml_gbm_p998", "ewmq_p998"]
BASELINES = [m for m in METHODS if m != "lognorm_ctop"]

def credit(a, floor):
    if a >= 0.9999: return 0.0
    if a >= 0.99:   return 0.10
    if a >= 0.95:   return 0.25
    return floor

SCHEDULES = {"AWS": 1.00, "GCP": 0.50, "Azure": 1.00}

def per_vm_availability(df):
    rows = []
    for vm, g in df.groupby("vm"):
        ns = g["n_test"].values
        if ns.sum() == 0: continue
        row = {"vm": vm}
        for m in METHODS:
            covs = g[f"cov_{m}"].values
            valid = np.isfinite(covs)
            row[f"A_{m}"] = (float(np.sum(covs[valid] * ns[valid]) / ns[valid].sum())
                             if valid.any() else np.nan)
        rows.append(row)
    return pd.DataFrame(rows)

results = {}
for trace, path in [("fastStorage", "unified_fastStorage.csv"),
                    ("rnd", "unified_rnd.csv")]:
    vm_df = per_vm_availability(pd.read_csv(f"E:/Projects/Submitted/Amdocs/scoping/{path}"))
    results[trace] = {"n_vms": int(len(vm_df))}
    for prov, floor in SCHEDULES.items():
        c_ln = np.array([credit(a, floor) for a in vm_df["A_lognorm_ctop"].values])
        prov_out = {}
        for base in BASELINES:
            A_b = vm_df[f"A_{base}"].values
            A_ln = vm_df["A_lognorm_ctop"].values
            mask = np.isfinite(A_b) & np.isfinite(A_ln)
            if mask.sum() == 0:
                prov_out[base] = None; continue
            c_b = np.array([credit(a, floor) for a in A_b[mask]])
            c_l = c_ln[mask]
            d = c_b - c_l   # positive: lognorm has smaller credit (better)
            wins = int((d > 0).sum())        # lognorm cheaper than baseline
            losses = int((d < 0).sum())      # baseline cheaper than lognorm
            ties = int((d == 0).sum())
            # Sign test on non-ties
            sign_p = float(binomtest(wins, wins + losses, 0.5).pvalue) if wins + losses > 0 else 1.0
            # Bootstrap mean diff (paired)
            idx = np.arange(len(d))
            boot = np.array([d[RNG.choice(idx, size=len(d), replace=True)].mean() for _ in range(B)])
            prov_out[base] = {
                "n": int(len(d)),
                "wins_lognorm_cheaper": wins,
                "ties": ties,
                "losses": losses,
                "mean_diff_c_base_minus_c_lognorm": float(d.mean()),
                "mean_diff_ci_low": float(np.percentile(boot, 2.5)),
                "mean_diff_ci_hi": float(np.percentile(boot, 97.5)),
                "sign_test_p_two_sided": sign_p,
                "significant_at_0.05": bool(sign_p < 0.05),
            }
        results[trace][prov] = prov_out

with open("E:/Projects/Submitted/Amdocs/scoping/sla_paired_summary.json", "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))
