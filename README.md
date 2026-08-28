# CPU Capacity Analysis

Source material and short technical report for a probabilistic method that
predicts CPU utilization on a transaction-processing system from offered load,
and turns that prediction into capacity sizing under revenue/penalty
constraints.

## Contents

- **`cpu-capacity-report.html`** — the short report (open in a browser).
- **`XL_LN.pptx`** — original analysis deck: Poisson arrivals, log-normal
  CPU model, parameter learning.
- **`dashboard.pptx`** — controlled load experiment at 70%, 100%, and 120% of
  nominal load; observed CPU on application and database tiers; comparison of
  the normal/linear and log-normal candidate models.
- **`Capacity Analysis and Trends (CAT)_sasha.pptx`** — production-scale
  validation on 26 rating/balance servers over 30 days: log-normal CPU per
  hourly bin, C_top = exp(avg + 3·std of log CPU) covers CPU at 99.8%
  probability.
- **`DecisionSupportTool.pptx`** — decision-support model that combines the
  capacity distribution with a revenue-share / fines policy to compute
  expected revenue per server.
- **`CAT.pdf`** — one-page writeup of the deployment outcomes.
- **`ROI.xlsx`, `RoiNew_v4.xlsx`** — worked ROI and quarterly sizing plans
  built on the decision-support model.
- **`Summary1.xlsx`, `Book1.xlsx`, `Res.xlsx`, `Res (1).xlsx`** — fitted
  parameters, per-hour CPU/event bins, soak-test time series, and multi-year
  transaction trends.
- **`analysis.zip`** — raw per-5-second CPU measurements for two server
  generations.

## Published report

The rendered report is also published as an artifact at
<https://claude.ai/code/artifact/bf37f8f8-b3a1-429f-8345-ee2540f03edd>.
