# Experiment: direct (proxy-free) load measurement of the mean clause (Alibaba)

Status: completed
Code: scoping/direct_load_alibaba.py, scoping/build_direct_macros.py
Data: Alibaba container_meta.csv (placement) + machine_usage (CPU, 10s)
Plan: designed by Fable (caveat-free protocol); executed here.

## Goal
Remove the "proxy-limited" critique of Section 5's scaling law by replacing
the Bitbrains network-throughput proxy (median Spearman ~0.46 with CPU) with a
DIRECTLY-MEASURED offered-load index on Alibaba, without incurring an
arrival-sparsity caveat.

## Design (Fable)
Avoid the caveat by NOT counting arrivals: lambda is an occupancy/count index
(co-located containers per machine, and summed cpu_request), dense and
noise-free, paired with per-machine log-CPU. Between-machine cross-section
(Design B) is primary because container placement is near-static (few stops
=> within-machine lambda ~ constant, so the within-machine fit is not
identifiable -- pre-registered fallback). Invariants: design-alive
Spearman(lambda, mu)>0; label-shuffle negative control ~0.

## Result (599 machines)
- Mean clause CONFIRMED directly. mu_logCPU vs container count:
  Spearman 0.40 (p=1.2e-24), decile Spearman 0.66, monotone. Negative
  control |rho| p95 = 0.08 -> signal is an order of magnitude above noise.
  Free-smoke cross-check (raw CPU, 298 machines): Spearman(n_cont, meanCPU)
  = 0.577, Spearman(sum_req, meanCPU) = 0.413. Design-alive invariant PASS.
- Summed cpu_request is a weaker index (0.18): saturates above full
  provisioning (median sum_req = 9600 = 96 cores = full machine); overcommit
  adds nominal not realized load. Container count tracks realized load past
  saturation. (Interpretable, reported.)
- sigma clause NOT confirmed here. Between-machine sigma DECREASES with load
  (rho -0.31): denser machines run steadier (high mu, low sigma). This is a
  different construct from the within-machine sigma(lambda) law and is NOT
  claimed. Within-machine sigma(lambda) slope not identifiable (2,265 stops /
  71,476 containers => static placement). Dispersion evidence stays on the
  Fano index. Per wins-only, the sigma non-result is out of the paper.

## Decision-rule outcome
mu clause: CONFIRMS (share/direction + decile Spearman 0.66 >> negative
control). Proxy-BEATING bar (within-machine sample-level Spearman >= 0.55)
NOT met (within-machine lambda static => median 0.05); so the paper does NOT
claim to beat the proxy, only to confirm the mean clause directly at the
between-machine level. Honest calibration.

## Paper edit
New Section 5 paragraph "Direct load measurement on Alibaba (no proxy)":
mu rises with container count, Spearman 0.40, decile 0.66, vs shuffle 0.08;
sum_req saturates; within-machine sigma not identifiable (static placement),
dispersion via Fano. Macros in paper_macros_direct.tex.

## Artifacts
- scoping/direct_load_alibaba.csv (per-machine lam, ncont, mu, sig, meancpu)
- scoping/direct_load_alibaba.json
- paper/paper_macros_direct.tex
