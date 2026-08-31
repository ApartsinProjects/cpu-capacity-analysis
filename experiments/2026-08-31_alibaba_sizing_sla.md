# Experiment: Alibaba sizing panel + SLA revenue (third trace, 10s resolution)

Status: completed
Code: scoping/unified_eval_alibaba.py, scoping/alibaba_panel_stats.py
Data: Alibaba cluster-trace-v2018 machine_usage (first 300 machines, 8 days, ~10s)
Seed: 42 (deterministic first-N-machine acceptance); bootstrap B=2000, RNG(42)

## Hypothesis
Extending the unified sizing panel + SLA simulation from the two 5-minute
Bitbrains traces to the 10-second Alibaba trace either (a) confirms the
log-normal ceiling's coverage-per-headroom + revenue win across resolutions
(bulletproofs the claim) or (b) shows rolling_max overtaking at fine
resolution (scopes the claim). Reviewer-requested "cheapest large
credibility gain"; also refutes the share-at-target saturation concern
because 10s bins are large.

## Setup
- Same six-method compute_ceilings as unified_eval.py (construct-matched).
- Hold out last 2 of 8 days; MIN_TRAIN 60, MIN_TEST 12, CPU floor 0.05.
- ml_gbm_p998 n/a (needs >=8 training days; 8-day trace supplies 6 train).
- Panel: 291 machines, 6961 bins, median test-bin = 718 samples.

## Headline numbers (95% cluster-bootstrap CI over machines)

Share-at-target (%):
- rolling_max     76.63 [74.67, 78.42]   ceiling 77.0
- lognorm_ctop    69.40 [67.12, 71.55]   ceiling 74.2
- empirical_p998  59.01 [56.63, 61.30]   ceiling 71.9
- gauss_meanksd   42.41 [40.18, 44.59]   ceiling 64.4
- ewmq_p998        9.78 [ 8.58, 11.05]   ceiling 56.5

SLA net revenue, AWS/Azure (%):
- rolling_max     73.16 [69.14, 77.11]
- lognorm_ctop    69.16 [65.05, 73.13]
- empirical_p998  68.95 [64.79, 72.78]
- gauss_meanksd   60.72 [56.75, 64.69]
- ewmq_p998       18.67 [15.05, 22.76]

Paired per-VM sign test (AWS net revenue), lognorm vs baseline:
- vs empirical_p998: 37 win / 20 loss / 233 tie, p=0.033 (lognorm cheaper)
- vs gauss_meanksd:  129 / 0 / 161, p<1e-38 (lognorm cheaper)
- vs ewmq_p998:      221 / 1 / 68,  p<1e-64 (lognorm cheaper)
- vs rolling_max:    3 / 52 / 235,  p=1.5e-12 (lognorm DEARER; rolling_max wins)

## Conclusion
Outcome (b): resolution-dependent crossover, characterized. The log-normal
ceiling is the best FIXED-CONFIDENCE sizing rule on all three traces
(beats empirical, Gaussian, EWMQ on Alibaba revenue), but the unbounded
rolling maximum overtakes the whole panel at 10s resolution. Root cause
(verified, not a bug): log-normal is well-calibrated on Alibaba (mean
coverage 0.976, near the 99.8% target); with ~718-sample test bins,
share-at-target and the SLA tiers reward rolling_max, whose train-max over
dense sampling converges to a near-exact high quantile. No parametric
99.8% quantile can beat an empirical max at capturing observed worst-case
under dense sampling. rolling_max's cost: no confidence target, headroom
unbounded in sample size.

Paper framing: reported honestly as Table tab:sizing-ali + a
resolution-crossover paragraph; the coverage-per-headroom Pareto + revenue
win is scoped to 5-minute production resolution (Bitbrains); the crossover
is presented as a sampling-density property, which is a novel characterisation
rather than a hidden loss.

## Artifacts
- scoping/unified_alibaba.csv (per-bin, 6961 rows)
- scoping/alibaba_panel_stats.json
- paper/paper_macros_alibaba.tex (generated)
- Table tab:sizing-ali in paper/paper.tex
