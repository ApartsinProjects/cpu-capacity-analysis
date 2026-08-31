# Backlog (re-ranked 2026-08-31)

## Done this cycle
- [x] Fresh Fable adversarial review of current draft.
- [x] Alibaba sizing panel + SLA (third trace, 10s) -> Table tab:sizing-ali,
      resolution-crossover framing. (exp 2026-08-31_alibaba_sizing_sla)
- [x] Fix integrity overclaims A1-A4, A10: CI language -> paired-sign-test
      language, disclose ties, define rolling_max, fix method counts.
- [x] Cohort-flow table (tab:cohorts); define sigma-direction (106) vs
      mechanism-agreement (98) cohorts; reconcile "105 of 106".
- [x] Stale captions (Table 1, pairwise), "three independent" -> "three".

## P0 done (cycle 2)
- [x] Macro-ize Section 5/6/8 mechanism + paired-test numbers via
      build_mech_macros.py -> paper_macros_mech.tex. (Form C, dispersion,
      composite proxy, all sign-test counts.) A few diagnostic literals remain
      hardcoded (skew 0.33/1.68, 65/35 decomposition, "85-90%", 44.9/9.5 KB/s,
      "~0.46", "~0.27") -- lower staleness risk; macro-ize in a later pass if
      the sigma_rootcause summary is regenerated to JSON.
- [x] De-circularize sigma-direction cohort (B3): full panel 78%/89%,
      proxy-selected 77%/92% (vs R^2-selected 96%/100%). Direction survives.

## P1
- [ ] Add Alibaba to the pairwise-AIC (tab:pairwise) and AD/CvM (tab:advcm)
      tables, or note explicitly they are Bitbrains-only (A8/A9).
- [ ] Anchor / cite the "original industrial study" or drop the replication
      framing (Section 8 / verdict item 4).
- [ ] Related-work expansion: Crovella-Bestavros, Harchol-Balter, AutoScale,
      Autopilot, Quasar already cited; add explicit positioning vs Autopilot's
      running-percentile ceiling (closest deployed competitor).
- [ ] Paper length now 14 pages; tighten toward venue norm if needed.

## P2 (method-improvement ideas; smoke before scale)
- [ ] Direct-dispersion Section 5 on Alibaba: replace network proxy with real
      container-arrival counts as lambda; refit mu/sigma clauses -> converts
      Section 5 from proxy-limited to directly-measured on one trace, could
      substantiate/kill the 9x ratio without waiting for Borg (Fable secondary).
- [ ] Best-AIC-family ceiling (adaptive parametric): per bin size to the
      99.8% quantile of the AIC-best family among {lognorm,gamma,Weibull}.
      NOTE: prior reasoning suggests this will NOT beat rolling_max on Alibaba
      (gamma/Weibull are lighter-tailed -> lower ceiling -> less coverage);
      likely a dead end for the coverage race but worth a cheap smoke as a
      "best parametric" upper bound. Low priority.
- [ ] Calibrated SLA variant (Fable B7): report a variant where availability
      is not the coverage=uptime identity, to show the ranking is not an
      artifact of the SLA-catastrophe regime (79-87% net for the winner).

## Rejected / parked
- Borg/BigQuery paired arrival+CPU experiment (BORG_PLAN.md): high value for
  the mechanism claim but needs GCP billing + ~$10; parked pending user go.
