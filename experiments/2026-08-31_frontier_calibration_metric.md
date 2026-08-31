# Experiment: clearer efficiency metric + calibration + frontier figures

Status: completed
Code: scoping/alibaba_frontier_calib.py, build_frontier_calib_macros.py,
      plot_frontier.py, plot_calibration.py
Data: Bitbrains fastStorage (5min, raw) + Alibaba (10s, tar). Rnd raw n/a.

## Motivation
User asked for a clearer metric showing log-normal's advantage, and better
figures. share-at-target saturates and is operating-point dependent; at fixed
k=3 log-normal over-provisions (excess 1.53x on fastStorage) and does NOT win
pinball (gauss tighter). Manufacturing a single-number win would be dishonest.

## Metric found: capacity to reach a target coverage (efficient frontier)
Sweep each method's parameter; plot median reserved capacity vs realized
coverage. The lower curve is more efficient. This is fair (all methods at
matched coverage) and non-gameable.

Capacity (median ceiling, CPU%) to reach 98% realized coverage:
- fastStorage (5min): lognorm 2.88, gauss 3.04, empirical 3.92, rolling_max 4.20
  -> lognorm reserves 26% less than empirical, 31% less than rolling_max.
- Alibaba (10s):      lognorm 81.6, gauss 80.0, empirical 74.0, rolling_max 75.0
  -> lognorm ~9-10% MORE (boundary; no advantage at dense sampling).

## Two mechanisms (fastStorage)
1. rolling_max wasteful at every coverage level.
2. empirical percentile SATURATES at the training max (cannot place a ceiling
   above the largest observed sample) -> its frontier turns up near 0.98,
   while the parametric ceiling EXTRAPOLATES the tail from 2 params. This is
   the concrete advantage of fitting a distribution over reading a percentile.

## Calibration (#2)
Realized vs nominal coverage. Log-normal best/tied-best on both traces
(fastStorage 98.5% at nominal 99.8%, Alibaba 97.4% ties empirical, beats gauss
96.0%). Under-coverage from train->test drift (larger on Alibaba's 2-day test).

## Bug caught
matched_coverage first used MEAN relative headroom -> corrupted by near-floor
test_p99 outliers (absurd 36x). Fixed to median ceiling. (frontier_claim3.py
in the repo has the same mean-headroom pattern; the paper's Pareto claim uses
median ceiling so is unaffected, but noted.)

## Honest framing
The efficiency advantage is real and LARGE at production (5-min) / sparse-tail
resolution and narrows to parity at dense (10s) sampling -- consistent with the
resolution crossover. Presented as fig:frontier (headline) + fig:calibration,
scoped honestly.

## Artifacts
frontier_{fastStorage,alibaba}.csv, calib_{...}.csv, frontier_calib_{...}.json,
paper/fig_frontier.pdf, paper/fig_calibration.pdf, paper_macros_frontcal.tex.
