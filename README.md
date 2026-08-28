# From CPU Load to Revenue: A Probabilistic Capacity Model

A probabilistic method that predicts CPU utilization on a transaction-processing
system from offered load, and turns that prediction into hardware sizing
decisions under revenue and SLA-penalty constraints. This repository holds the
short technical report and the source materials it draws on.

## The report

- **Read online (GitHub Pages):** <https://apartsinprojects.github.io/cpu-capacity-analysis/>
- **Printable PDF:** [assets/cpu-capacity-report.pdf](assets/cpu-capacity-report.pdf)
- **Source HTML:** [cpu-capacity-report.html](cpu-capacity-report.html)
- Mirror on claude.ai:
  <https://claude.ai/code/artifact/bf37f8f8-b3a1-429f-8345-ee2540f03edd>

## Source materials

- **`XL_LN.pptx`** — analysis deck: Poisson arrivals, log-normal CPU model,
  parameter learning.
- **`dashboard.pptx`** — controlled load experiment at 70%, 100%, and 120% of
  nominal load; observed CPU on application and database tiers; comparison of
  the normal/linear and log-normal candidate models.
- **`Capacity Analysis and Trends (CAT)_sasha.pptx`** — production-scale
  validation on 26 rating/balance servers over 30 days: log-normal CPU per
  hourly bin, `C_top = exp(avg + 3*std of log CPU)` covers CPU at 99.8%
  probability.
- **`DecisionSupportTool.pptx`** — decision-support model that combines the
  capacity distribution with a revenue-share / fines policy to compute
  expected revenue per server.
- **`CAT.pdf`** — one-page writeup of the deployment outcomes.

## Workbooks

- **`ROI.xlsx`** — worked example of the decision-support model
  (20 servers, ~$70M annual revenue, tiered fines) with an hour-by-hour table
  and the CPU failure curve.
- **`RoiNew_v4.xlsx`** — quarterly sizing plan across two server generations
  with growth forecasts, availability projections, and purchase schedule.
- **`Summary1.xlsx`** — fitted log-normal and normal/linear parameters
  behind Figure 2; hour-by-hour soak-test time series behind Figure 1.
- **`Book1.xlsx`** — per-hour-of-day bins for a representative server
  showing how `mu(log CPU)` and `sigma(log CPU)` scale with load
  (behind Figure 4).
- **`Res.xlsx`, `Res (1).xlsx`** — per-server pivots and multi-year event
  trends used for long-horizon forecasts.
- **`analysis.zip`** — raw per-5-second CPU measurements for two server
  generations (source data behind the fits).

## Assets

- **`assets/cpu-capacity-report.pdf`** — printable PDF of the report.
- **`assets/report-previews/`** — rendered screenshots of the report.
- **`assets/slide-renders/`** — PNG renders of every source-deck slide, useful
  for browsing the raw material without opening PowerPoint.
