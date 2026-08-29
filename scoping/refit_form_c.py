"""Form C sigma fit + partial-Spearman units control (Claim 2 R1+R2)."""
import os, json, sys
import numpy as np, pandas as pd
from scipy.optimize import curve_fit
from scipy.stats import spearmanr
from refit_ab_shared import read_vm, per_vm_triples

ROOT = {"fastStorage": r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8",
        "rnd":         r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8"}

fB = lambda l, a, s:    np.sqrt(np.maximum(a*a*l + s*s, 1e-12))
fC = lambda l, a, c, s: np.sqrt(np.maximum(a*a*l + c*c*l*l + s*s, 1e-12))

def fit_generic(f, lam, sig, p0, bounds):
    try:
        popt, _ = curve_fit(f, lam, sig, p0=p0, bounds=bounds, maxfev=5000)
        pred = f(lam, *popt)
        ss_res = float(np.sum((sig - pred) ** 2))
        ss_tot = float(np.sum((sig - sig.mean()) ** 2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
        n, k = len(lam), len(popt)
        aicc = n * np.log(ss_res / n + 1e-300) + 2 * k + (2 * k * (k + 1)) / max(n - k - 1, 1)
        return popt, float(r2), float(ss_res), float(aicc)
    except Exception:
        return None, np.nan, np.nan, np.nan

results = {}
for label, root in ROOT.items():
    prior = pd.read_csv(f"E:/Projects/Submitted/Amdocs/scoping/refit_ab_{label}.csv")
    coh = prior[(prior.r2_mu >= 0.5) & (prior.r2B >= 0.3) &
                (prior.alpha_mu > 0) & (prior.alpha_sig > 0)].reset_index(drop=True)
    rows = []
    for _, pr in coh.iterrows():
        fp = os.path.join(root, os.path.basename(pr["vm"]))
        r = read_vm(fp)
        if r is None: continue
        hours, cpu, net = r
        t = per_vm_triples(hours, cpu, net)
        if len(t) < 4: continue
        lam, sig = t[:, 0], t[:, 2]
        if lam.min() <= 0: continue
        med_sig = float(np.median(sig))
        # Form B
        pB, r2B, ssB, aiccB = fit_generic(fB, lam, sig, [0.01, med_sig], ([0,0],[np.inf,np.inf]))
        # Form C free
        p0C = [pB[0], 1e-3, pB[1]] if pB is not None else [0.01, 1e-3, med_sig]
        pC, r2C, ssC, aiccC = fit_generic(fC, lam, sig, p0C, ([0,0,0],[np.inf]*3))
        # Form C with alpha pinned to alpha_mu
        am = float(pr["alpha_mu"])
        fCp = lambda l, c, s, am=am: fC(l, am, c, s)
        pP, r2P, ssP, aiccP = fit_generic(fCp, lam, sig, [1e-3, med_sig], ([0,0],[np.inf,np.inf]))
        rows.append({
            "vm": pr["vm"], "n_bins": int(len(t)), "alpha_mu": am,
            "r2B": r2B, "r2C": r2C, "r2P": r2P,
            "aiccB": aiccB, "aiccC": aiccC, "aiccP": aiccP,
            "alpha_B": float(pB[0]) if pB is not None else np.nan,
            "alpha_C": float(pC[0]) if pC is not None else np.nan,
            "c_C":     float(pC[1]) if pC is not None else np.nan,
            "c_P":     float(pP[0]) if pP is not None else np.nan,
            "lam_min": float(lam.min()), "lam_max": float(lam.max()),
            "lam_gmean": float(np.exp(np.log(lam[lam > 0]).mean())),
        })
    df = pd.DataFrame(rows)
    df.to_csv(f"E:/Projects/Submitted/Amdocs/scoping/formC_{label}.csv", index=False)

    # Pre-registered invariants
    valid = df.dropna(subset=["r2B","r2C","r2P"])
    nest_ok = float((valid["r2C"] >= valid["r2B"] - 1e-6).mean())
    pin_ok  = float((valid["r2P"] <= valid["r2C"] + 1e-6).mean())
    # AICc-preferred model
    def best_by_aicc(r):
        aicc = {"B": r["aiccB"], "C": r["aiccC"], "P": r["aiccP"]}
        return min(aicc, key=lambda k: aicc[k] if np.isfinite(aicc[k]) else np.inf)
    valid = valid.copy()
    valid["best"] = valid.apply(best_by_aicc, axis=1)
    best_counts = valid["best"].value_counts(normalize=True).to_dict()

    # R2: partial Spearman controlling for log geometric-mean lambda
    la = np.log(coh["alpha_mu"].values.astype(float) + 1e-12)
    ls = np.log(coh["alpha_sig"].values.astype(float) + 1e-12)
    lm = np.log(np.maximum(coh["lam_max"].values.astype(float), 1e-6))
    # residualize both by rank-fitting on lm
    def resid_rank(y, x):
        ry, rx = pd.Series(y).rank().values, pd.Series(x).rank().values
        A = np.vstack([rx, np.ones_like(rx)]).T
        b, *_ = np.linalg.lstsq(A, ry, rcond=None)
        return ry - A @ b
    r_a = resid_rank(la, lm); r_s = resid_rank(ls, lm)
    rho_full, _ = spearmanr(la, ls)
    rho_partial, _ = spearmanr(r_a, r_s)

    results[label] = {
        "n_vms": int(len(df)),
        "nesting_invariant_share": nest_ok,   # expect ~1.0
        "pinning_invariant_share": pin_ok,    # expect ~1.0 (pinned R2 <= free R2)
        "best_aicc_share": best_counts,
        "r2_medians": {"B": float(valid["r2B"].median()),
                        "C": float(valid["r2C"].median()),
                        "P": float(valid["r2P"].median())},
        "spearman_full": float(rho_full),
        "spearman_partial_ctrl_lam": float(rho_partial),
        "c_median_free": float(valid["c_C"].median()) if len(valid) else np.nan,
        "c_median_pinned": float(valid["c_P"].median()) if len(valid) else np.nan,
    }
    print(f"[{label}] {json.dumps(results[label], indent=2)}", file=sys.stderr)

with open("E:/Projects/Submitted/Amdocs/scoping/formC_summary.json", "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))
