"""VM-clustered bootstrap confidence intervals on every headline number.

All four claim families in one script, ~2 minutes total on a laptop with
B = 2000 resamples using precomputed per-VM aggregates.
"""
import json, os, sys, numpy as np, pandas as pd
from scipy.stats import spearmanr

B = 2000
RNG = np.random.default_rng(42)
HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = ["lognorm", "norm", "gamma", "weibull_min"]
METHODS = ["lognorm_ctop", "empirical_p998", "gauss_meanksd",
           "rolling_max", "ml_gbm_p998", "ewmq_p998"]

def boot_of_scalar_from_vm_stats(per_vm_values, agg_fn=np.mean):
    """per_vm_values: array of one number per VM. agg_fn maps sample to scalar."""
    arr = np.asarray(per_vm_values, dtype=float)
    n = len(arr)
    boot = np.empty(B)
    for b in range(B):
        idx = RNG.integers(0, n, size=n)
        boot[b] = agg_fn(arr[idx])
    boot = boot[np.isfinite(boot)]
    return {"point": float(agg_fn(arr)),
            "ci_low": float(np.percentile(boot, 2.5)),
            "ci_hi":  float(np.percentile(boot, 97.5))}

def boot_of_paired(a, b_arr, agg_fn):
    """Paired bootstrap of a function of two aligned arrays."""
    n = len(a); boot = np.empty(B)
    for i in range(B):
        idx = RNG.integers(0, n, size=n)
        try:
            boot[i] = agg_fn(a[idx], b_arr[idx])
        except Exception:
            boot[i] = np.nan
    boot = boot[np.isfinite(boot)]
    return {"point": float(agg_fn(a, b_arr)),
            "ci_low": float(np.percentile(boot, 2.5)),
            "ci_hi":  float(np.percentile(boot, 97.5))}

def per_vm_share(df, mask_col):
    """Per-VM: share of rows where mask_col is True."""
    return df.groupby("vm")[mask_col].mean()

results = {}

# ---------- Claim 1: log-normal winner share ----------
print("Claim 1", file=sys.stderr)
c1 = {}
for label, fp in [("fastStorage", "bitbrains_fit_results.csv"),
                   ("rnd", "rnd_fit_results.csv")]:
    df = pd.read_csv(os.path.join(HERE, fp))
    for fam in CANDIDATES:
        df[f"is_{fam}"] = (df["best_aic"] == fam)
        per_vm = per_vm_share(df, f"is_{fam}")
        c1[f"{label}_{fam}"] = boot_of_scalar_from_vm_stats(per_vm.values)

# combined: unique VM key across datasets
df_fs = pd.read_csv(os.path.join(HERE, "bitbrains_fit_results.csv"))
df_rd = pd.read_csv(os.path.join(HERE, "rnd_fit_results.csv"))
df_fs["vm"] = "fs::" + df_fs["vm"].astype(str)
df_rd["vm"] = "rn::" + df_rd["vm"].astype(str)
combined = pd.concat([df_fs, df_rd], ignore_index=True)
for fam in CANDIDATES:
    combined[f"is_{fam}"] = (combined["best_aic"] == fam)
    per_vm = per_vm_share(combined, f"is_{fam}")
    c1[f"combined_{fam}"] = boot_of_scalar_from_vm_stats(per_vm.values)
results["claim1_winner_share"] = c1

# ---------- Claim 2: Spearman + 9x ratio ----------
print("Claim 2", file=sys.stderr)
c2 = {}
for label in ["fastStorage", "rnd"]:
    df = pd.read_csv(os.path.join(HERE, f"refit_ab_{label}.csv"))
    ok = (df["r2_mu"] >= 0.5) & (df["r2B"] >= 0.3) & (df["alpha_mu"] > 0) & (df["alpha_sig"] > 0)
    coh = df[ok].reset_index(drop=True)
    a_mu = coh["alpha_mu"].values
    a_sg = coh["alpha_sig"].values
    def _sp(x, y): return float(spearmanr(x, y).statistic)
    def _rt(x, y): return float(np.median(y / x))
    c2[f"{label}_spearman"] = boot_of_paired(a_mu, a_sg, _sp)
    c2[f"{label}_median_ratio"] = boot_of_paired(a_mu, a_sg, _rt)
    c2[f"{label}_cohort_n"] = int(len(coh))
results["claim2_scaling_mechanism"] = c2

# ---------- Claim 3: share-at-target per method (from unified panel) ----------
print("Claim 3", file=sys.stderr)
c3 = {}
for label in ["fastStorage", "rnd"]:
    fp = os.path.join(HERE, f"unified_{label}.csv")
    if not os.path.exists(fp):
        c3[label] = None; continue
    df = pd.read_csv(fp)
    per_method = {}
    for m in METHODS:
        col = f"cov_{m}"
        if col not in df.columns: continue
        df_m = df[df[col].notna()].copy()
        df_m["at_target"] = df_m[col] >= 0.998
        per_vm = per_vm_share(df_m, "at_target")
        per_method[m] = boot_of_scalar_from_vm_stats(per_vm.values)
    c3[label] = per_method
results["claim3_share_at_target"] = c3

# ---------- Claim 4: SLA net revenue per method per provider ----------
print("Claim 4", file=sys.stderr)
def credit(a, provider):
    if a >= 0.9999: return 0.0
    if a >= 0.99:   return 0.10
    if a >= 0.95:   return 0.25
    return 1.00 if provider != "GCP" else 0.50

c4 = {}
for label in ["fastStorage", "rnd"]:
    fp = os.path.join(HERE, f"unified_{label}.csv")
    if not os.path.exists(fp):
        c4[label] = None; continue
    df = pd.read_csv(fp)
    per_provider = {}
    for prov in ["AWS", "GCP", "Azure"]:
        per_method = {}
        for m in METHODS:
            col = f"cov_{m}"
            if col not in df.columns: continue
            # per-VM availability (weighted mean by n_test)
            def _wm(g, col=col):
                mask = g[col].notna()
                if mask.sum() == 0: return np.nan
                return (g.loc[mask, col] * g.loc[mask, "n_test"]).sum() / g.loc[mask, "n_test"].sum()
            per_vm_A = df.groupby("vm").apply(_wm).dropna()
            per_vm_net = per_vm_A.apply(lambda a, prov=prov: 1 - credit(a, prov))
            per_method[m] = boot_of_scalar_from_vm_stats(per_vm_net.values)
        per_provider[prov] = per_method
    c4[label] = per_provider
results["claim4_sla_net_revenue"] = c4

with open(os.path.join(HERE, "bootstrap_cis.json"), "w") as f:
    json.dump(results, f, indent=2)
print("bootstrap_cis.json written")
