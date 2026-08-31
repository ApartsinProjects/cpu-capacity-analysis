# Project Log: Log-Normal CPU Capacity Model paper

Chronological record of the autonomous revision cycles. Newest first.

## Current standing (2026-08-31)

Paper draft target: *Performance Evaluation* (Elsevier). Core empirical result
(log-normal best-fitting family in 66.7% of 19,624 VM-hour bins across 3 traces /
2 providers) is solid and macro-backed. Decision-layer sections (sizing, SLA) were
Bitbrains-only. This session extends them to Alibaba and repairs integrity defects.

## Cycle 2 (2026-08-31): macro-ize hardcoded numbers + de-circularize sigma cohort

**Macro-ization (reviewer B5).** New scoping/build_mech_macros.py reads the
committed summary artifacts (formC_summary.json, composite_proxy_summary.json,
alibaba_fano_summary.json, sla_paired_summary.json) and emits
paper/paper_macros_mech.tex. Replaced ~20 previously-hardcoded literals in
Sections 5/6/8 with macros: Form C R^2 (0.71/0.75/0.79), AICc split (now
correctly per-trace 63/31 fs, 55/36 rnd -- the paper's hardcoded "37%" was a
rounding slip of 36%), median c (0.019/0.025), partial Spearman (0.49/0.72),
composite-proxy Spearmans, dispersion index (5.7/4.2), and all fastStorage +
Rnd paired-sign-test counts. Now a rebuild regenerates these from source.
Gotcha fixed: LaTeX \newcommand names cannot contain digits (\FormCFsR2B,
\Disp5min failed); renamed to letters-only (\FormCFsRB, \DispFivemin).

**De-circularize sigma-direction cohort (reviewer B3).** The "105 of 106"
near-unanimity was computed on a cohort selected by sigma-fit R^2 (the
DEPENDENT variable) -- circular. Recomputed the direction share (gamma_A<0,
i.e. sigma rises with lambda) on the FULL proxy panel and on a cohort selected
by PROXY quality (rho_cpu_net, the INDEPENDENT variable), from diag_proxy.csv:
  - Full panel:        78% fastStorage, 89% Rnd (n=120 each)
  - Above-median proxy: 77% / 92%
  - R^2-resolvable:     96% / 100% (the old circular cohort)
The direction survives strongly without conditioning on fit quality; the
near-unanimity was a selection artifact. Abstract + Section 5 now lead with
the full-panel/proxy-selected shares and note the resolvable-cohort figure as
secondary. Paper rebuilds clean at 14 pages, 0 undefined macros.

## Cycle 1 (2026-08-31): fresh Fable adversarial review + Alibaba decision-layer extension

**Fable review (adversarial, fresh eyes on current draft).** Independently ranked
"run sizing+SLA on Alibaba" as the #1 highest-impact experiment (matching the prior
PE strong-accept verdict). Also mined integrity-critical defects, all verified
against paper_macros.tex:

- **A1 (FATAL).** Abstract/intro/§8 caption/§8 body claim a "CI-separated revenue
  lead over every baseline on fastStorage AWS, including rolling maximum." But
  LN AWS CI [83.83, 89.57] overlaps RM CI [78.93, 85.50] on [83.83, 85.50]. The
  paired sign test (p<1e-3) is legitimate and different; "CI-separated" is false.
- **A2.** "Both [LN and RM] dominate the remaining three baselines with
  non-overlapping CIs" — RM CIlo 78.47 overlaps gauss CIhi 78.65 on fastStorage.
- **A3.** "each has a CI-separated lead over empirical percentile on Rnd" — LN Rnd
  CIlo 69.85 overlaps empirical CIhi 72.71; only rolling_max clears it (by 0.29).
- **A4.** rolling_max is used in every headline comparison but never DEFINED; method
  list says "five" while the table shows six. Section 7 says "five" too.
- **A5.** Abstract "105 of 106 VMs" cohort vs macro refit cohorts 51+47=98 — needs
  reconciling/defining.
- **A6/B5.** Section 5 mechanism numbers + all paired-sign-test counts are hardcoded,
  not macro-backed, contradicting the reproducibility claim.
- **A7/A8/A12.** Table 1 caption "Public Bitbrains traces" lists Alibaba; pairwise
  AIC + AD/CvM tables omit Alibaba silently; AWS and Azure SLA schedules are
  identical (10/25/100) so "three schedules" is really two.
- **B8.** Gamma wins 23.9% of Alibaba bins vs 3.4% Weibull — family ranking
  reshuffles by resolution; needs a sentence.

**Alibaba sizing panel (new experiment, exp 2026-08-31_alibaba_sizing).** Wrote
scoping/unified_eval_alibaba.py: identical six-method compute_ceilings, hold out
last 2 of 8 days, CPU floor 0.05, first 300 machines. Smoke (40 machines, 888 bins)
PASSED sanity: lognorm_ctop share-at-target 0.771 (HIGHEST, above rolling_max 0.691),
coverage 0.974, ceiling 73.9%. ml_gbm n/a (8-day trace < 8 train days needed).
Notable regime difference: on Alibaba the log-normal ceiling sits ABOVE rolling_max
(higher coverage AND higher headroom), unlike Bitbrains (same coverage, less
headroom). So the coverage-per-headroom "less headroom" claim is Bitbrains-specific;
the share-at-target win generalizes and is stronger on Alibaba. Full 300-machine run
in progress.

**Key findings so far.**
- Log-normal sizing ceiling leads on share-at-target on a third trace at 10s
  resolution (saturation concern refuted: large test bins).
- Integrity overclaims A1-A4 must be corrected before any submission; they are
  wins-only overclaims contradicted by the paper's own macros.

**Next.**
1. Finish Alibaba full panel; sanity-gate; run SLA sim + bootstrap CIs on Alibaba.
2. Fix overclaims A1-A4, A10 (CI language -> paired-test language + disclose ties).
3. Macroize Alibaba sizing/SLA; add to tables; extend build script.
4. De-circularize scaling cohort framing (B3); align Form C abstract with AICc (B4).
5. Stale captions/counts (A7, A8, A12); gamma sentence (B8).
