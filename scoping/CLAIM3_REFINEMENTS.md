# Claim 3 refinements: can "lognorm ties rolling_max" become a win?

Status: brainstorm plus pre-computed diagnostics, 2026-08-29. All numbers below were computed
this session directly from `unified_fastStorage.csv` (4908 bins, 210 VMs) and `unified_rnd.csv`
(5173 bins, 221 VMs); nothing is projected.

## Pre-computed evidence (changes the priors)

Before ranking refinements, four cheap paired analyses were run on the existing CSVs. They shift
the picture in both directions:

1. **McNemar on per-bin hit/miss (weak point 2).** fastStorage: lognorm-only hits 438 vs
   rolling_max-only hits 427, exact binomial p = 0.73, a true tie. **Rnd: 531 vs 661,
   p = 1.8e-4, rolling_max is significantly better per bin.** The Rnd "slight win" in the paper
   is a statistically solid win for rolling_max once paired.
2. **Per-bin Pareto domination (weak point 5).** rolling_max strictly dominates lognorm
   (ceiling <= and coverage >=, one strict) in 51.1% of fastStorage bins and 42.3% of Rnd bins;
   lognorm dominates in 26.8% on both. Among bins where both methods hit the target, lognorm has
   the lower ceiling only 33.1% (fastStorage) and 36.8% (Rnd) of the time, and the median
   per-bin ceiling ratio lognorm/rolling_max is 1.086 and 1.032. The paper's "lognorm picks
   lower median ceilings" (3.21 vs 4.00) is a marginal-median composition effect; bin-by-bin,
   lognorm is the more expensive method. Relative headroom over test_p99 confirms this: median
   61.7% vs 19.9% (fastStorage), 32.0% vs 12.5% (Rnd).
3. **Continuous uncovered mass.** Mean uncovered demand fraction (1 - coverage):
   fastStorage lognorm 0.0138 vs rolling_max 0.0208; VM-clustered bootstrap on the paired
   difference gives [-0.0157, -0.0002], excluding zero, a genuine lognorm win on the continuous
   metric. Rnd: 0.02334 vs 0.02335, difference CI [-0.0054, 0.0051], exact tie.
4. **Miss severity.** When the ceiling is exceeded, lognorm's median overshoot of test_max is
   worse (0.40 vs 0.11 fastStorage), because the two methods miss on different bins.

Net reading: at the current operating points, rolling_max is cheaper per bin and matches or
beats lognorm on thresholded coverage. Lognorm's defensible edge is on continuous uncovered
mass (fastStorage only) and on being a tunable one-parameter family. Any honest strengthening
of Claim 3 must therefore run through matched cost.

## Refinements, ranked by (impact if positive, cost)

### R1. Matched-cost coverage frontier (K-sweep) [execute this session]

One line: sweep the lognorm quantile parameter K in exp(mu + K sigma) and a multiplier m on
max(train), recompute per-bin coverage from the raw traces, and compare coverage at equal mean
relative headroom.

- **Spec.** New script `scoping/frontier_claim3.py`. Reuses `read_vm`, the bin construction,
  and the train/test split from `unified_eval.py` verbatim (same VM sample, same bin filter,
  same TEST_DAYS). For each (VM, hour) bin, fit lognorm once (mu, sigma from train), store
  max(train), store test samples. For K in linspace(1.0, 4.5, 36) and m in linspace(0.7, 2.0,
  27), compute ceiling and coverage per bin, aggregate share-at-target (cov >= 0.998), mean
  uncovered mass, and mean relative headroom over test_p99. Output one CSV of
  (method, param, share, uncovered_mass, mean_headroom, median_headroom) per trace, plus a
  VM-clustered bootstrap CI on the share difference at the cost-matched point: the K* whose
  mean headroom equals rolling_max's m = 1 headroom.
- **Success.** At rolling_max's own cost point, lognorm's frontier delivers higher
  share-at-target with a CI excluding zero on at least one trace and no loss on the other.
  Claim 3 becomes "at matched cost, the log-normal family dominates rolling max," a strictly
  stronger and cleaner statement.
- **Failure.** rolling_max's point lies on or above the lognorm frontier on both traces. Then
  the paper must say lognorm is not better than rolling_max at any common cost; the per-bin
  Pareto counts above (51% vs 27% domination) make this outcome a live possibility, and the
  result must be reported either way.
- **Cost.** Script writing plus one local run over 431 traces: about 20-30 minutes of agent
  execution, local CPU only, $0.

### R2. Continuous uncovered-mass comparison (already computed, promote to paper-grade)

One line: replace or complement share-at-target with mean uncovered demand mass, paired per bin.

- **Spec.** Extend `unified_eval.py` reporting (or a sibling `uncovered_mass.py`) to emit mean
  (1 - cov) per method with VM-clustered bootstrap CIs from the existing CSVs only.
- **Success.** Already observed: lognorm significantly better on fastStorage
  (diff CI [-0.0157, -0.0002]), tie on Rnd. Supports "lognorm never worse, sometimes better on
  uncovered mass" but only alongside R1, because lognorm buys this with 3x headroom.
- **Failure.** Not applicable as a standalone claim; if R1 fails, this metric alone cannot
  carry Claim 3, since the cost asymmetry would remain unaddressed.
- **Cost.** 5 minutes of agent execution, $0.

### R3. Formal McNemar and per-VM win-rate table

One line: report the paired per-bin test and per-VM win rates instead of overlapping marginal CIs.

- **Spec.** From the CSVs: McNemar exact test per trace; per-VM share comparison
  (fastStorage: lognorm wins 91 VMs, rolling_max 75, tie 44; Rnd: 95 vs 94 vs 32) with a sign
  test.
- **Success.** fastStorage per-VM sign test favoring lognorm would add one supporting cell.
- **Failure (already realized on Rnd).** The Rnd McNemar (p = 1.8e-4 for rolling_max) refutes
  a raw-coverage win there. If adopted, the paper must state rolling_max wins raw per-bin
  coverage on Rnd. This refinement is a truth-forcing device, not a strengthener.
- **Cost.** Done this session, $0.

### R4. Per-bin Pareto census

One line: count bins where each method strictly dominates the other on (ceiling, coverage).

- **Spec.** Two comparisons per bin from the CSVs; report domination shares and the both-hit
  cheaper-method share.
- **Success.** Would require lognorm domination share to exceed rolling_max's.
- **Failure (already realized).** rolling_max dominates in 51.1% / 42.3% of bins vs 26.8% for
  lognorm on both traces. At the fixed K = 3 operating point, rolling_max Pareto-dominates
  more often on both panels. This must be flagged: absent an R1 rescue at matched cost, this
  census refutes Claim 3 as a superiority claim and the paper should present lognorm as the
  tunable-family option, not the winner.
- **Cost.** Done this session, $0.

## Recommendation

Execute **R1** now. It is the only analysis that can convert the tie into a win, its failure
mode is informative rather than wasted, and every other refinement's verdict is conditional on
it. R2 and R3 become paper-ready for free once R1's verdict is known.

## Python skeleton for R1

```python
"""frontier_claim3.py: matched-cost coverage frontier, lognorm K-sweep vs rolling_max m-sweep."""
import numpy as np, pandas as pd
from scipy import stats
from unified_eval import read_vm, TEST_DAYS  # reuse split and bin logic constants

KS = np.linspace(1.0, 4.5, 36)
MS = np.linspace(0.7, 2.0, 27)
MIN_TRAIN, MIN_TEST, TARGET = 30, 24, 0.998   # mirror unified_eval bin filter exactly

def collect_bins(files):
    bins = []  # (vm, hour, mu, sigma, trainmax, test_samples, test_p99)
    for fp in files:
        _, hours, days, cpu = read_vm(fp)
        cut = days.max() - TEST_DAYS
        for h in range(24):
            m = hours == h
            tr = cpu[m & (days <= cut)]; te = cpu[m & (days > cut)]
            if len(tr) < MIN_TRAIN or len(te) < MIN_TEST:  # same filter as unified_eval
                continue
            try:
                s, _, sc = stats.lognorm.fit(tr, floc=0)
            except Exception:
                continue
            bins.append((fp, h, np.log(sc), s, tr.max(), te, np.quantile(te, 0.99)))
    return bins

def frontier(bins):
    rows = []
    for K in KS:
        cov = np.array([ (te <= np.exp(mu + K * sg)).mean() for _,_,mu,sg,_,te,_ in bins])
        hr  = np.array([ (np.exp(mu + K * sg) - p99) / p99 for _,_,mu,sg,_,_,p99 in bins])
        rows.append(("lognorm", K, (cov >= TARGET).mean(), (1 - cov).mean(), hr.mean()))
    for m in MS:
        cov = np.array([ (te <= m * tmax).mean() for _,_,_,_,tmax,te,_ in bins])
        hr  = np.array([ (m * tmax - p99) / p99 for _,_,_,_,tmax,_,p99 in bins])
        rows.append(("rolling_max", m, (cov >= TARGET).mean(), (1 - cov).mean(), hr.mean()))
    return pd.DataFrame(rows, columns=["method","param","share","unc_mass","mean_headroom"])

# main: run per trace family, interpolate lognorm share at rolling_max m=1 headroom,
# then VM-clustered bootstrap the share difference at that matched cost point.
# Invariants to assert before reporting: share is monotone nondecreasing in K and m;
# K=3 and m=1 rows reproduce the unified CSV numbers exactly (same bins, same split).
```

The two invariants in the skeleton are the acceptance gate: if K = 3 and m = 1 do not
reproduce the published 82.73% / 81.44% / 73.64% / 76.04% shares, the frontier used different
bins and its verdict is void.
