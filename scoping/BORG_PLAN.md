# Plan: Testing the σ(λ) mechanism on Google Borg data

## Why Borg

The paper's Section 6 mechanism-consistent salvage says the σ ∝ 1/√λ term
dominates only when each measurement window aggregates a small number of
transactions. On Bitbrains that condition fails (5-minute windows average
thousands of events per bin). Testing the mechanism directly needs paired
arrival-rate and CPU data at a resolution finer than one minute on the same
machine. No dataset in the public traces we already have supplies that;
Google Borg does.

## The dataset

**Google Cluster Data 2019** (Verma et al., publicly released 2020) covers
eight Borg cells over 30 days in May 2019, roughly 12,000 machines per cell
and about 100 million jobs. Two tables are needed together for this test:

- `instance_events`: one row per instance start / update / end, with
  microsecond-resolution timestamps. Gives arrival rate `λ(t)` at any
  aggregation window.
- `instance_usage`: 5-minute-window CPU and memory averages per instance.

Access: BigQuery Public Datasets
(`google.com:google-cluster-data`). Pricing is on-demand, $6.25 per TB
scanned (US region). No storage cost to us since we query the public copy.

**Google Cluster Data 2011** is a fallback: smaller (12,500 machines, one
month), fully described in Reiss et al. SoCC 2012, downloadable as ~40 GB
compressed CSVs. Task-events at second-level plus 5-minute task-usage.
Old but well-understood.

## Design

**Cohort.** Fix one cell (say cell `a`). Pick machines with sustained load
across the 30 days (median CPU > 10%, no long idle stretches). Sample 200
machines, verify the sample is representative.

**Per-machine per-hour-of-day bin:**
1. From `instance_events`, count arrivals per 30-second sub-window inside
   the bin. This yields the observed arrival count `n_j` per 30-second
   window `j` at that hour, across ~30 days.
2. From `instance_usage`, get CPU% per 5-minute window. Average five
   consecutive `n_j`'s to align with each CPU sample, giving paired
   `(N_5min, C_5min)` observations.
3. Fit the mechanism per bin: μ_logC on N_5min (linear), σ_logC on N_5min
   (both Form A `γ/√λ + δ` and Form B `√(α²λ + σ_ε²)`).

**Two decisive tests.**
1. **Direction test at coarse resolution.** Repeat the fit at 5-minute
   window granularity (matches Bitbrains). Does σ(λ) increase, as Bitbrains
   shows and Form B expects, or decrease, as Form A predicts?
2. **CLT-regime test at fine resolution.** Repeat the fit at 30-second
   window granularity, using single 30-second CPU samples reconstructed
   from finer trace metadata where available. If the mechanism is right,
   the σ(λ) slope should be steeper (larger α̂ from Form B) at 30 s than
   at 5 min, because per-window event counts are smaller and the CLT term
   is relatively larger.

**Cross-check.** Correlate the per-machine α̂ from Form B with the machine's
job-type composition. If α̂ is stable within one job class (e.g., single-
service latency-critical) and variable across classes, the mechanism holds
per-workload and the population aggregate hides real structure.

## Cost estimate

**BigQuery.** The 2019 dataset is 2.4 TB compressed. A 200-machine, 30-day
extract of `instance_events` + `instance_usage` filtered by cell and machine
list is roughly 50 GB scanned, `0.05 × $6.25 = $0.31` per query. Expect
20-30 queries for exploration, feature engineering, and cohort selection:
**~$10 total** at conservative pricing.

**Storage.** Extract lands as ~5-10 GB parquet in a scratch GCS bucket or
locally. Free at that size.

**Compute.** All fits happen locally (laptop-scale, ~2-3 minutes total for
200 machines × 24 bins × 2 window sizes). Cloud compute not required.

**My execution time.** BigQuery schema exploration (30 min), SQL query
authoring and iteration (1 h), data pull (~5 min per query, backgrounded),
per-machine fit script analogous to `scoping/fit.py` (1 h), diagnostic and
paper text (1 h). Total ~3-4 sessions of my time.

**Alternative if BigQuery access is friction.** The 2011 trace is bulk-
downloadable (~40 GB compressed) with no cloud dependency. Same design
except at 2011 hardware / workload scale. Cost: $0, plus one overnight
download.

## Deliverables

1. `scoping/borg_extract.sql` — the BigQuery queries, with row and byte
   counts per query documented in the header.
2. `scoping/borg_fit.py` — per-machine per-bin fit at both window sizes,
   Form A and Form B both fitted.
3. `scoping/borg_summary.json` — aggregate results (share of machines with
   γ̂ > 0, sign flip from 5-min to 30-s, α̂ agreement between μ and σ
   fits).
4. Section 6 revision (or a new short section) reporting either:
   - **The mechanism replicates on paired arrival + CPU data** (Form B fits
     well, α̂ from σ fit within 30% of α̂ from μ fit, CLT-regime test
     shows steeper slope at 30 s), or
   - **The mechanism does not replicate even with paired data** (Form B
     also fails, or the sign flip doesn't happen), which would be an
     equally important negative result that would motivate revising the
     multiplicative-overhead argument itself.

## Prerequisites

- A Google Cloud project with BigQuery enabled.
- Authenticate `gcloud auth application-default login`.
- Confirm access to the `google.com:google-cluster-data` public dataset.

## Risk register

- **BigQuery quota.** On-demand queries have a per-project TB/day cap;
  20-30 queries at 50 GB each is well under.
- **Instance-usage sparsity.** Not every instance reports every 5-minute
  window. Filter by minimum sample count per bin (60, matching current
  Bitbrains threshold).
- **Sub-minute CPU is not natively in the 2019 trace.** The 30-second
  test may need to be reframed as "coarser than 5 min" (e.g., 15-minute
  aggregation) if sub-5-minute CPU is unavailable. In that case the CLT-
  regime test compares 5-min vs 15-min vs 60-min rather than 30-sec vs
  5-min, which weakens but does not defeat the test.
