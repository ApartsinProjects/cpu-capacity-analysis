# Editorial Pass Report: paper.tex (2026-08-29)

Scope: full-prose editorial pass on `E:\Projects\Submitted\Amdocs\paper\paper.tex`. No number, table row, figure, equation, macro, or section heading was changed. Approximately 20 distinct prose edits.

## 1. Structural changes

- **Abstract rewritten** from ~370 words to ~230 with a clean arc: motivation, question, method, data, fit result, scaling result, sizing and revenue result, release. The scaling detail (Spearman CIs per trace, fitted c values, Form C equation) was cut from the abstract; every retained number and macro is unchanged. The `Section~\ref` inside the abstract was removed.
- **Section 6 (Parameter Scaling)**: Form A and Form B are now named once, at the point where the two functional forms are introduced, and referred to by name afterward; the "Per-VM mechanism consistency" paragraph no longer re-states both formulas. The Form C paragraph now ends with the figure pointer instead of interleaving future work and the figure sentence; the future-work pointer (BORG_PLAN) appears once in Form C and is referenced back from the Interpretation paragraph rather than restated in full.
- **Section 7 (Sizing Accuracy)**: removed a duplicated "Table 5 reports the pooled results" sentence (it appeared both at the end of the metrics paragraph and at the start of the panel paragraph). Deleted the "Interpretation" paragraph, which repeated the results paragraph nearly verbatim; its one non-redundant clause ("at a competitive median predicted ceiling") was folded into the results paragraph, which now hands off explicitly to Section 8.
- Introduction subsections ("dollar problem", "Who this is for", Contributions) kept in their existing order; the order motivates, targets, then enumerates, which works.

## 2. Stale content removed

- **Sec. 1, dollar-problem paragraph**: "quantified against five practitioner baselines" while Table 5 has four baselines; changed to four.
- **Sec. 1, Contributions**: "against five baselines on held-out data" followed by a list of four; changed to four. Also dropped "the corrected standard-deviation form" (draft-history wording) to "the standard-deviation form".
- **Sec. 1, Who this is for**: "ships the whole pipeline as a two-file reference implementation"; Section 10 describes a Docker image and GitHub repo, not two files. Rewritten to point at what Section 10 actually says.
- **Sec. 5, Method**: duplicate sentence "Every bin with at least 60 samples is retained" (already stated in the preceding sentence).
- **Sec. 6**: "the aggregate is a mixed picture that deserves splitting" and "Following the project convention of inspecting failing points" (internal-process language and non-wins framing) removed; "the (incorrect) form from an earlier draft of this paper" and the sign-flip relitigation ("that sign flip is consistent between the paper's original (incorrect) derivation...") removed; Form A is now a named reference form without draft archaeology. Paragraph heading "increases with load, at both meaning and magnitude" simplified.
- **Sec. 7**: "we fit four sizing methods" followed by five bullets; changed to five. "all six ceilings co-computed per bin" while Table 5 lists five methods; replaced with "every ceiling co-computed per bin" to avoid asserting a count that the table does not show (see item 4).
- **Sec. 8**: "the four sizing methods from Section 7" while Table 6 lists five; changed to five. "\texttt{rolling\_max}" cited as a covering method though it appears in no table (evidently a removed baseline); the sentence now makes the same step-function argument without naming it. "four physics-based and data-driven baselines" simplified to "four baselines" (none of the four is physics-based).
- **Acknowledgements**: "traces used in Section 5" broadened to "traces used in this paper" (they underpin Sections 5 through 8).

## 3. Style tightening (representative)

- Before: "Sound sizing therefore rests on one quantity, stated precisely: given a transaction rate, what is the probability that CPU utilization stays below..." After: "Sound sizing rests on one quantity: given a transaction rate, the probability that CPU utilization stays below...".
- Before: "which is expected KS behaviour with fitted parameters and hundreds to thousands of samples; all four families are rejected at similar rates, so KS is not discriminating..." After: split into two sentences; "so KS does not discriminate on this data".
- Before: "we present it as evidence that the load-proportional demand fluctuation ... admits a fitted parametric form, not as a confirmation of the arrival-only mechanism" (defensive framing). After: "Form C establishes that the load-proportional demand fluctuation ... admits a fitted parametric form; separating it from the arrival-only mechanism requires paired arrival and CPU data at sub-minute resolution".
- Before: "methods that cover more often (lognorm_ctop, rolling_max) keep more revenue even when they carry a higher predicted ceiling ... over the range where either method operates." After: "a method that covers more often keeps more revenue even when it carries a higher predicted ceiling ... over the range where these methods operate."
- Fixed two mid-word line-break hyphens that would typeset as "CPU- utilization" and "demand- fluctuation" (also "arrival- rate"). Replaced the double hyphen in "Kolmogorov--Smirnov" per the no-double-hyphen rule.

## 4. Noticed but NOT fixed (needs your review; would touch numbers)

- **"all six ceilings co-computed per bin" (Sec. 7)**: Table 5 shows five methods. If the unified-panel script really co-computes six (e.g. including the removed rolling_max), the honest count is six but the sixth is unreported; if it computes five, the old text was wrong. I sidestepped the count in prose; confirm against the panel script and, if you want a count, put the true one.
- **Sec. 7 old Interpretation paragraph claimed non-overlapping CIs "on both share-at-target and mean coverage"**: no "mean coverage" column exists in Table 5. I dropped the mean-coverage clause when deleting the paragraph; if a mean-coverage comparison exists in an artifact, it could be reinstated with its source.
- **Table 7 caption** says log-normal's AWS/fastStorage CI is non-overlapping with every other method; I left the caption untouched (table territory) but did not verify it against the CI macros.
- **Abstract previously said "roughly 500 VMs"** for Rnd while Table 1 says 500; the rewritten abstract says 500. If the raw trace count is genuinely approximate, restore "roughly".
