# Claim 4 Refinements: SLA Net-Revenue Win

Claim 4 currently rests on unpaired mean-over-VMs net revenue with percentile bootstrap CIs: a clean lognorm vs rolling_max separation on fastStorage AWS (86.81 vs 82.43, non-overlapping) and an overlap on Rnd AWS (79.30 vs 77.10). All refinements below run off `scoping/unified_fastStorage.csv` and `scoping/unified_rnd.csv`, which carry per-(vm, hour-of-day) coverage and bin counts for all six methods; no new simulation is needed.

Refinements are ranked by (impact if positive, cost).

## R1. Paired per-VM credit comparison (top pick)

**One line.** Replace the unpaired mean comparison with a paired per-VM analysis: for each VM compute credit under lognorm and under rolling_max on the same availability panel, then bootstrap the paired difference and report win/tie/loss shares.

**Operational spec.** New script `scoping/sla_paired.py`. Reproduce `per_vm_availability` from `sla_sim.py` on both unified CSVs, apply the three credit schedules per VM per method, form `d_i = credit_baseline(VM_i) - credit_lognorm(VM_i)` for each baseline in {rolling_max, empirical_p998, gauss_meanksd, ml_gbm_p998, ewmq_p998}, and report per (trace, provider, baseline): mean(d) with a 10k-resample paired percentile bootstrap CI, share of VMs with d>0 (lognorm strictly cheaper), d=0 (same SLA tier), d<0, and an exact sign test on the nonzero differences. Because the step function makes most paired differences exactly zero (both methods land in the same tier), the sign test on ties-removed differences is the correct primary test.

**Why it has power the current analysis lacks.** The unpaired CIs on Rnd overlap because between-VM variance dominates. Per-VM availabilities of lognorm and rolling_max on the same VM are highly correlated; pairing removes that variance. The current summary already hints at the direction: on Rnd, lognorm has share_ge_9999 = 29.5% vs rolling_max 11.2%, while their share_ge_99 and share_ge_95 are close, so the paired signal concentrates at the top tier.

**Success criterion.** On Rnd AWS, the paired bootstrap CI on mean(d) excludes zero in lognorm's favor (or the sign test gives p < 0.05 with wins > losses), and the same holds on fastStorage and under GCP and Azure. Claim 4 upgrades from "wins one cell, ties one" to "paired per-VM advantage on both traces under all three schedules."

**Failure criterion (refutation-capable, flagged).** If on Rnd the paired losses match or exceed wins, or the paired CI covers zero on both AWS and Azure, the paper must scope the claim to "log-normal wins on fastStorage; on Rnd it is statistically indistinguishable from rolling_max," and the tie is real rather than a power artifact.

**Cost.** 15-25 min of agent execution, local CPU only, ~$0.

## R2. Step-boundary sensitivity sweep

**One line.** Test whether the fastStorage win and the Rnd tie survive perturbation of the SLA tier thresholds and replacement of the hard steps by a piecewise-linear credit curve.

**Operational spec.** Script `scoping/sla_sensitivity.py`. Two axes on the same per-VM availability panel: (a) shift each threshold pair (0.9999, 0.99, 0.95) multiplicatively over a grid, for example the 99% tier swept over {98.5, 98.75, 99.0, 99.25, 99.5}% with the others fixed, recomputing mean net revenue per method per grid point; (b) replace the step function by linear interpolation of credit between tier midpoints (credit rises continuously from 0 at 99.99% to 1.0 at 90%), which is the graceful-degradation Ps(C) surrogate from weak point 3. Output: a table of lognorm minus rolling_max revenue gap across the grid and under the smooth curve, with paired bootstrap CIs at each point.

**Success criterion.** The lognorm advantage keeps its sign at every grid point and under the smooth curve, on both traces. Claim 4 can then state the win is not an artifact of where the public thresholds happen to sit.

**Failure criterion (refutation-capable, flagged).** If the sign flips at plausible thresholds, or the smooth curve erases the fastStorage gap, the paper must state that the advantage is specific to the published step schedules.

**Cost.** 20-30 min of agent execution, ~$0.

## R3. Block-bootstrap monthly extrapolation

**One line.** Quantify how a 6-day availability estimate propagates to the monthly SLA horizon by block-resampling test days into synthetic 30-day months.

**Operational spec.** Requires per-day (not per-hour-of-day-bin) coverage, so it re-reads the per-VM traces referenced in the unified CSVs' `vm` column paths; if those scratchpad traces are gone, it degrades to resampling hour-of-day bins with replacement 5x to synthesize month-length weight, which tests estimator variance but not day-to-day dependence. For each VM, resample 30 days (or 5x the bins), compute monthly availability, apply the AWS schedule, repeat 2k times, and compare the distribution of monthly credit between lognorm and rolling_max.

**Success criterion.** The ranking and the fastStorage gap are stable in the synthetic-month distribution; the paper can state the 6-day-to-month mapping was tested.

**Failure criterion (refutation-capable, flagged).** If monthly-horizon credit distributions of the two methods overlap heavily on fastStorage, the headline win is a short-window artifact and the claim must be scoped to the evaluated window.

**Cost.** 30-45 min of agent execution if traces must be re-read; ~$0. Blocked if the scratchpad trace files were cleaned; check first.

## R4. Dollar-denominated worked example

**One line.** Convert the net-revenue-ratio gap into dollars per month for a concrete instance and fleet.

**Operational spec.** No new statistics. Take a public on-demand price (verify current AWS m5.xlarge on-demand pricing with the `web-researcher` skill before quoting), multiply the fastStorage AWS gap (86.81 - 82.43 = 4.38 points of billed revenue) by price x 730 h x 254 VMs, and report per-VM and fleet monthly dollars. Also report the cross-schedule spread from `sla_summary.json` (weak point 5): the largest lognorm-vs-rolling_max mean-credit gap by provider, noting GCP's 0.50 floor compresses all gaps (fastStorage GCP gap is 3.19 points vs AWS 4.38).

**Success criterion.** Always succeeds; purely presentational. Strengthens the claim's legibility, not its validity.

**Failure criterion.** None; cannot refute.

**Cost.** 10 min of agent execution plus one web lookup, ~$0.

## Recommendation for this session

Execute **R1**. Highest impact (it can convert the Rnd tie into a win, which is the single weakest cell in Claim 4), lowest cost, zero new data. R2 is the natural follow-up because R1's paired machinery is 90% of R2's code.

### Python skeleton for R1

```python
"""sla_paired.py: paired per-VM SLA credit comparison, lognorm vs baselines."""
import json
import numpy as np
import pandas as pd

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
            row[f"A_{m}"] = (np.sum(covs[valid] * ns[valid]) / ns[valid].sum()
                             if valid.any() else np.nan)
        rows.append(row)
    return pd.DataFrame(rows)

def sign_test_p(wins, losses):
    """Two-sided exact binomial sign test, ties removed."""
    from scipy.stats import binomtest
    n = wins + losses
    return binomtest(wins, n, 0.5).pvalue if n > 0 else 1.0

results = {}
for trace, path in [("fastStorage", "unified_fastStorage.csv"),
                    ("rnd", "unified_rnd.csv")]:
    vm_df = per_vm_availability(pd.read_csv(f"E:/Projects/Submitted/Amdocs/scoping/{path}"))
    results[trace] = {}
    for prov, floor in SCHEDULES.items():
        c_ln = vm_df["A_lognorm_ctop"].apply(lambda a: credit(a, floor)).values
        results[trace][prov] = {}
        for base in BASELINES:
            mask = np.isfinite(vm_df[f"A_{base}"].values) & np.isfinite(vm_df["A_lognorm_ctop"].values)
            c_b = vm_df.loc[mask, f"A_{base}"].apply(lambda a: credit(a, floor)).values
            d = c_b - c_ln[mask]                      # >0: lognorm cheaper on this VM
            # Sanity invariant: identical availabilities must give d == 0 everywhere.
            idx = np.arange(len(d))
            boot = np.array([d[RNG.choice(idx, len(d))].mean() for _ in range(B)])
            wins, losses = int((d > 0).sum()), int((d < 0).sum())
            results[trace][prov][base] = {
                "n": int(len(d)),
                "mean_diff": float(d.mean()),
                "ci_low": float(np.percentile(boot, 2.5)),
                "ci_hi": float(np.percentile(boot, 97.5)),
                "wins": wins, "ties": int((d == 0).sum()), "losses": losses,
                "sign_test_p": float(sign_test_p(wins, losses)),
            }

with open("E:/Projects/Submitted/Amdocs/scoping/sla_paired.json", "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps(results["rnd"]["AWS"]["rolling_max"], indent=2))  # the tie cell
```

Verification before any number reaches the paper: confirm `n` matches `n_vms` from `sla_summary.json` (254 / 258 for the four core methods), confirm the unpaired means reproduce Table `tab:sla`, and inspect the VMs contributing d < 0 individually before accepting the aggregate.
