# Strong-Accept Verdict on the Revised Manuscript

Reviewer verdict for Performance Evaluation (Elsevier), second round.

## 1. Verdict

NOT YET STRONG ACCEPT.

## 2. Why

The revision genuinely improved: the GBM confidence intervals are now internally consistent (60.41 in [56.70, 63.88] on fastStorage, 49.36 in [45.67, 52.94] on Rnd), the false CI-separation sentences were replaced with claims that survive checking against the macros, a third trace from a second provider was added (Alibaba cluster-trace-v2018, 298 machines, 7,145 bins, log-normal best in 63.64%), the SLA section now carries an explicit "Scope of the simulation" paragraph labeling it a stylized cost model, and a metric-sensitivity paragraph (min-bin 30, pinball loss) answers the saturation objection. The three-trace, 19,624-bin distributional result (\CombinedLogNormShareVmw = 66.71%, CI [64.61, 68.76]) is now the paper's most defensible claim and would anchor a solid accept. But the single most serious defect from the first round persists in aggravated form: the rolling-max baseline is still absent from Table tab:sizing and Table tab:sla even though paper_macros.tex still carries its complete results (\UFsRMShare = 81.44 [78.47, 84.04], \URnRMShare = 76.04 [73.00, 78.73], and all six SlaFsRM/SlaRnRM revenue cells). On Rnd, rolling max beats the log-normal ceiling (76.04 vs \URnLNShare = 73.64) and its revenue is within 2.2 points under AWS (\SlaRnRMAWSNet = 77.10 vs \SlaRnLNAWSNet = 79.30). The revision responded to my first-round finding by deleting the two textual mentions of rolling_max rather than restoring the rows, so the abstract's "highest share-at-target coverage on both traces" and the sizing section's headline remain contradicted by the authors' own computed numbers, now with the contradicting evidence hidden more thoroughly than before. A paper whose comparison table omits the baseline that beats it on one of two traces cannot be a strong accept regardless of the quality of everything around it, and the hedge "against every baseline it does not tie with" does not cure a comparison the baseline was removed from.

## 3. The gap to strong accept

### Incremental improvements the current framing needs

1. Restore rolling_max to Table tab:sizing, Table tab:sla, the paired sign tests, and the metric-sensitivity checks. Rewrite the abstract, Section 6, and Section 7 conclusions to state where log-normal wins, ties, and loses. This is non-negotiable; the macros prove the numbers exist.
2. Cohort-flow accounting. The pipeline goes 1,250/500 advertised, 300 sampled, 286/291 fitted, 260/258 in scaling, 210/221 in the panel, 106 in the marquee cohort. The seed-42 sampling statement helps, but the "well-fitting well-proxied" thresholds behind "105 of 106" are still undefined anywhere in the paper. One table: stage, filter, threshold, VMs remaining, plus the sigma-direction share on the unfiltered scaling population.
3. Extend Alibaba beyond the fit. The new trace appears only in Section 5; the sizing panel and SLA simulation remain Bitbrains-only, so the strongest new evidence does not touch the weakest claims. Running the unified panel on Alibaba (10-second resolution, so test bins are large and the saturation concern vanishes) would be the cheapest large credibility gain available.
4. Cite or drop the anchor. Section 7 still says "the original industrial study" with no citation; either identify it or remove the replication framing.
5. Small fixes: Table 1 caption says "Public Bitbrains traces" while listing Alibaba; "three independent public traces" overstates independence of two same-archive Bitbrains traces; the source header still says "Draft. Target venues: SoCC / Middleware / HotCloud / IEEE TCC".

### Structural pivots

The evidence supports two pivots, and one fits far better than the other.

Pivot A (recommended): reframe the sizing contribution from "highest coverage" to coverage-per-headroom. The macros show log-normal is not the coverage winner; it is the Pareto winner. On fastStorage it matches rolling max on coverage (82.73 vs 81.44, overlapping CIs) at a 20% lower median ceiling (3.21 vs 4.00 CPU%); on Rnd it concedes 2.4 coverage points while pricing 30% less headroom (3.16 vs 4.50). Rolling max buys coverage by being wide; the log-normal ceiling buys nearly the same coverage from two fitted parameters. That claim is true on every number in the macro file, it is the claim a capacity planner actually cares about, it makes rolling_max's presence in the tables an asset instead of a threat, and it requires zero new computation. The revenue section then arbitrates the trade honestly: under step-shaped credits the parametric ceiling still nets more revenue than rolling max on both traces (\SlaFsLNAWSNet 86.81 vs \SlaFsRMAWSNet 82.43; 79.30 vs 77.10 on Rnd), which is a legitimate, CI-checkable win the current framing forfeits by hiding the comparison.

Pivot B (viable but weaker): drop the sizing evaluation to an application sketch and lead with the empirical distribution result, now three traces, two providers, two resolutions, 19,624 bins, with the sigma-increases-with-load finding and its variance decomposition (65% within-day, 35% between-day) as the second contribution. This is publishable at Performance Evaluation and fully honest, but it discards the paper's most differentiated material and leaves the mechanism story ending on Form B being AICc-preferred over pinned Form C on 55% vs 37% of VMs, a minority result for the proposed extension.

Pivot A preserves everything, needs only rewriting plus the restored rows, and converts the paper's integrity liability into its central claim.

## 4. The single highest-impact action

Restore the rolling_max rows to Tables tab:sizing and tab:sla, add it to the paired sign tests, and rewrite the headline claim as the coverage-per-headroom Pareto result (near-equal coverage at 20 to 30 percent lower ceiling, and higher net revenue than rolling max under all three SLA schedules on both traces). This one change removes the disqualifying suppression, turns the strongest baseline into the foil that makes the method look good for the right reason, and is executable from numbers already sitting in paper_macros.tex.
