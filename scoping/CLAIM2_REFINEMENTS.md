# Claim 2 Refinements: Making the Scaling-Consistency Claim Attack-Proof

Scope: Claim 2 of `paper/paper.tex` (Section 7): sigma_log C rises with lambda on 105/106 well-fitting VMs, bootstrap Spearman(alpha_mu, alpha_sig) = 0.82 [0.67, 0.91] (fastStorage) and 0.94 [0.85, 0.98] (rnd), median alpha_sig/alpha_mu near 9 on both traces, excess attributed to load-proportional demand fluctuation (65 percent sub-hour, 35 percent day-to-day per `SIGMA_ROOTCAUSE.md`). Inputs: `scoping/refit_ab_fastStorage.csv`, `scoping/refit_ab_rnd.csv`, raw Bitbrains CSVs under the scratchpad. Refinements are ranked by impact-per-cost; all cost figures are agent execution minutes on local CPU, zero cloud dollars unless flagged.

## Ranked refinements

### R1. Fit Form C, the mechanism-consistent extension, with alpha pinned to the mu fit

**One line.** Turn the demand-fluctuation attribution from narrative into a fitted model: sigma(lambda) = sqrt(alpha^2 lambda + c^2 lambda^2 + sigma_eps^2), where c^2 lambda^2 is the load-proportional demand-fluctuation variance.

**Operational spec.** New script `scoping/refit_form_c.py`, reusing `read_vm` and `per_vm_triples` from `refit_form_ab.py` verbatim (same CPU floor 0.05, MIN_N 60, MIN_BINS 6, same 300-file seed-42 sample, so the cohort matches the published numbers exactly). Per VM, fit three sigma models on the 24 hour-of-day bins: Form B (free alpha), Form C free (alpha, c, sigma_eps all fitted, bounded nonnegative), and Form C pinned (alpha fixed to that VM's alpha_mu from the mu regression, only c and sigma_eps fitted). Form C nests Form B at c = 0, so compare with AICc (n as small as 6 bins makes the small-sample correction mandatory) and an extra-sum-of-squares F test, not raw R^2. Report on the existing cohort (r2_mu >= 0.5, r2B >= 0.3, both alphas positive; n = 51 + 47): median R^2 of each form, fraction of VMs where AICc prefers C over B, median fitted c, and the ratio alpha_Cfree/alpha_mu.

**Success criterion (supports the claim).** Form C pinned, which spends zero free parameters on alpha, reaches R^2 comparable to free Form B (median within ~0.05) on a majority of the cohort, and AICc prefers C over B on at least half. This would show the 9x excess is exactly what a c-lambda term absorbs, the alpha recovered from the mean is simultaneously consistent with the dispersion, and the attribution paragraph becomes a fitted, falsifiable model. The prediction sharpener: the fitted c^2/(alpha^2 + c^2 lambda) share at each VM's median lambda should reproduce the roughly 65 percent within-day burst share from `rc_vm_summary.csv` in rank order.

**Failure criterion (refutes; would force revision).** If pinning alpha to alpha_mu collapses R^2 (median near 0 or negative) while free Form C simply re-inflates alpha by ~9x with c near 0, the demand-fluctuation term does not rescue mechanism consistency; the paper would then have to state that the multiplicative-overhead alpha explains the mean but not the dispersion, and the 9x ratio would stand as an unresolved discrepancy rather than an explained excess. This outcome must be reported, not filtered.

**Cost.** 30-45 agent minutes, local CPU only.

### R2. Partial Spearman controlling for per-VM load scale

**One line.** Test whether the 0.82/0.94 correlation survives once the shared 1/lambda units of both alphas are controlled for.

**Operational spec.** Extend the same script (the CSVs already carry lam_min, lam_max). On each cohort: (a) partial Spearman of log alpha_mu vs log alpha_sig controlling for log median lambda (use lam_max or the geometric mean of lam_min, lam_max as the scale proxy); (b) the dimensionless version, Spearman of alpha_mu * (lam_max - lam_min) vs alpha_sig * (lam_max - lam_min) is degenerate by construction, so instead correlate the residuals of each log alpha regressed on log lambda-scale. Cluster-bootstrap VMs for the CI, matching `bootstrap_cis.py`.

**Success criterion.** Partial rho >= 0.5 with a bootstrap CI excluding 0 on both traces: the consistency is per-VM physics, not units. One added sentence in Section 7.

**Failure criterion (refutes).** Partial rho collapsing to near 0 means the headline Spearman is a units artifact (any two coefficients with 1/lambda dimensions across VMs spanning 4 decades of lambda would correlate); the mechanism-consistency sentence would have to be weakened to the direction claim alone. Explicitly a refutation path.

**Cost.** 10-15 agent minutes.

### R3. Autopsy of the one decreasing VM

**One line.** Name the 1-in-106 exception and determine whether it is a counter-instance or a fitting artifact.

**Operational spec.** From `rc_vm_summary.csv` (or recompute the tercile comparison in `sigma_rootcause.py`), identify the VM whose high-lambda tercile sigma is below its low-lambda tercile. Pull its raw CSV, plot sigma and both variance components against lambda, and run two robustness probes: (a) day-level cluster bootstrap of the tercile difference (does the decrease survive resampling days?); (b) sensitivity to the bin filter (MIN_N 60 vs 120) and to dropping its single highest-lambda bin.

**Success criterion.** The decrease is inside the bootstrap noise or vanishes under either probe: the paper gains one sentence ("the single exception is a low-range VM whose decrease is within resampling noise") satisfying the inspect-the-failing-point convention.

**Failure criterion (refutes, mildly).** A robust, well-measured decreasing VM is a genuine counter-instance; the claim wording moves from near-universality to "105 of 106, with one characterized exception" and the exception's workload profile gets a diagnostic sentence. This weakens rhetoric, not the mechanism, unless the VM turns out typical of a subpopulation, which the probe would reveal.

**Cost.** 10-15 agent minutes.

### R4. Day-demeaned sigma refit tying Form C's c to the burst decomposition

**One line.** Recompute sigma on day-demeaned log C and refit Form C, checking that the fitted c shrinks by the between-day share (about 35 percent of the variance increase).

**Operational spec.** Same pipeline as R1, but subtract each calendar-day-hour mean from log C before computing per-bin sigma (the day index construction already exists in `sigma_rootcause.py`). Compare fitted c^2 (raw) vs c^2 (demeaned) per VM; the mechanism predicts the demeaned c^2 retains roughly the within-day share of the load-proportional variance.

**Success criterion.** Median c^2_demeaned / c^2_raw in a band consistent with the 65 percent within-day share (say 0.5 to 0.8), tying the fitted extension quantitatively to the decomposition and closing weak point 4 completely.

**Failure criterion.** A ratio near 0 or above 1 breaks the link between the fitted c and the decomposition story; the two analyses would then be measuring different things and the attribution paragraph would need to choose one.

**Cost.** 30-40 agent minutes; run only after R1 succeeds.

### R5. Cross-trace replication on Azure Public Dataset

**One line.** Rerun the mu/sigma/Form C pipeline on a non-Bitbrains trace to remove the single-source caveat.

**Operational spec.** Azure Public Dataset V2 (VM CPU readings, 5-minute cadence) is the closest structural match; the network-throughput proxy for lambda is absent there, so lambda must be proxied by a demand covariate available in the trace (deployment size or the VM's own mean CPU in a held-out window), which changes the construct and must be stated. Alternative: the Borg plan already scoped in `BORG_PLAN.md` (BigQuery dollars, days of wall-clock).

**Success/failure.** Directional replication (sigma rising with the load proxy on a large majority of well-fitting VMs) supports generality; a flat or falling profile on another platform bounds the claim to Bitbrains-like workloads and the paper's scope sentence changes.

**Cost.** 60-120 agent minutes plus a multi-GB download whose wall-clock is external; or BigQuery dollars for Borg. Future work, not this session.

## The one to execute this session

**R1 plus R2 in one script** (they read the same rows; R2 adds ~15 lines). R1 attacks the two central weak points at once: the 9x ratio gets a mechanism-consistent model that either absorbs it or demonstrably fails to, and the attribution acquires a goodness-of-fit number. R2 rides along and either certifies or kills the Spearman headline. Total: about 40 minutes of agent execution, $0.

```python
"""refit_form_c.py: Form C sigma fits + partial Spearman units control.
Reuses cohort construction from refit_form_ab.py (seed 42, same filters)."""
import glob, os, random, json
import numpy as np, pandas as pd
from scipy.optimize import curve_fit
from scipy.stats import spearmanr, f as fdist

# refit_form_ab.py executes its pipeline at import time; copy read_vm and
# per_vm_triples verbatim into this file (or refactor them behind a
# __main__ guard first) rather than importing the module.
from refit_ab_shared import read_vm, per_vm_triples  # same preprocessing, same cohort

random.seed(42)
ROOT = {"fastStorage": r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8",
        "rnd":         r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8"}

def fit_curve(f, lam, sig, p0, bounds):
    popt, _ = curve_fit(f, lam, sig, p0=p0, bounds=bounds, maxfev=5000)
    pred = f(lam, *popt)
    ss_res = float(np.sum((sig - pred) ** 2))
    ss_tot = float(np.sum((sig - sig.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    n, k = len(lam), len(popt)
    aicc = n * np.log(ss_res / n + 1e-300) + 2 * k + (2 * k * (k + 1)) / max(n - k - 1, 1)
    return popt, r2, ss_res, aicc

fB  = lambda l, a, s:    np.sqrt(np.maximum(a*a*l + s*s, 1e-12))
fC  = lambda l, a, c, s: np.sqrt(np.maximum(a*a*l + c*c*l*l + s*s, 1e-12))

results = {}
for label, root in ROOT.items():
    prior = pd.read_csv(f"refit_ab_{label}.csv")           # published cohort + alpha_mu
    coh = prior[(prior.r2_mu >= 0.5) & (prior.r2B >= 0.3) &
                (prior.alpha_mu > 0) & (prior.alpha_sig > 0)]
    rows = []
    for _, pr in coh.iterrows():
        fp = os.path.join(root, os.path.basename(pr["vm"]))
        hours, cpu, net = read_vm(fp)
        t = per_vm_triples(hours, cpu, net); lam, sig = t[:, 0], t[:, 2]
        try:
            (aB, sB), r2B, ssB, aiccB = fit_curve(fB, lam, sig, [0.01, np.median(sig)], ([0,0],[np.inf]*2))
            (aC, cC, sC), r2C, ssC, aiccC = fit_curve(fC, lam, sig, [aB, 1e-3, sB], ([0,0,0],[np.inf]*3))
            # Form C with alpha PINNED to the mu-fit alpha: zero free params spent on alpha
            am = pr["alpha_mu"]
            fCp = lambda l, c, s: fC(l, am, c, s)
            (cP, sP), r2P, ssP, _ = fit_curve(fCp, lam, sig, [1e-3, np.median(sig)], ([0,0],[np.inf]*2))
            n = len(lam)
            F = ((ssB - ssC) / 1) / (ssC / max(n - 3, 1))   # nested B (c=0) vs C
            pF = 1 - fdist.cdf(F, 1, max(n - 3, 1))
            rows.append(dict(vm=pr["vm"], n=n, alpha_mu=am,
                             r2B=r2B, r2C=r2C, r2P=r2P, c_free=cC, c_pin=cP,
                             ratio_free=aC/am, aicc_pref_C=bool(aiccC < aiccB), pF=pF,
                             lam_med=float(np.median(lam)), lam_lo=lam.min(), lam_hi=lam.max()))
        except Exception:
            continue
    df = pd.DataFrame(rows); df.to_csv(f"refit_c_{label}.csv", index=False)
    # ---- R2: partial Spearman of log alphas controlling for log load scale ----
    x, y = np.log(coh.alpha_mu.values), np.log(coh.alpha_sig.values)
    z = np.log(np.sqrt(coh.lam_min.values * coh.lam_max.values))  # geometric-mean lambda
    def resid(v):  # rank residuals of v on z
        r = pd.Series(v).rank().values; rz = pd.Series(z).rank().values
        b = np.polyfit(rz, r, 1); return r - np.polyval(b, rz)
    rho_partial = float(spearmanr(resid(x), resid(y)).statistic)
    boot = [spearmanr(*(lambda i: (resid(x[i]), resid(y[i])))(
            np.random.randint(0, len(x), len(x)))).statistic for _ in range(2000)]
    results[label] = dict(
        cohort_n=len(df),
        median_r2B=float(df.r2B.median()), median_r2C=float(df.r2C.median()),
        median_r2_pinned=float(df.r2P.median()),
        frac_aicc_prefers_C=float(df.aicc_pref_C.mean()),
        frac_F_sig=float((df.pF < 0.05).mean()),
        median_ratio_free=float(df.ratio_free.median()),
        rho_raw=float(spearmanr(x, y).statistic),
        rho_partial=rho_partial,
        rho_partial_ci=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))])
with open("refit_c_summary.json", "w") as f: json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))
```

Invariants to check before believing the output (verification discipline): r2C >= r2B on every VM (nesting; a violation is a convergence bug), c_free = 0 must reproduce Form B numbers exactly, and the pinned fit's R^2 can never exceed the free Form C R^2. Any suspiciously good pinned fit on a VM with r2_mu < 0.6 gets its raw sigma(lambda) plotted and eyeballed before the aggregate is quoted.
