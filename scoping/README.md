# Scoping experiment: log-normal CPU fit on a public trace

This folder holds a scoping experiment that tests one of the main claims in the
report, "CPU utilization at a given load is log-normal", on data outside the
original 2011 study. The purpose is to establish whether the claim survives
independent replication before writing a full paper around it.

## Dataset

**Bitbrains GWA-T-12 fastStorage.** 1,250 virtual machines from a Dutch managed
hosting provider (Bitbrains IT Services), sampled every 5 minutes over about
30 days. Publicly hosted by the AtLarge research group at TU Delft:
<https://atlarge-research.com/gwa-t-12/>. Column used: `CPU usage [%]`.
Acknowledgement to Bitbrains IT Services Inc. is included per the trace's
usage terms.

## Method

For each of 300 randomly-sampled VMs, we grouped CPU% readings by hour of day
(24 bins per VM). Every bin with at least 60 samples (about 5 hours of data
per VM aggregated across the month) was retained. For each retained bin we fit
four candidate distributions and scored them:

- **log-normal** (`scipy.stats.lognorm`, `floc=0`)
- **normal** (`scipy.stats.norm`)
- **gamma** (`scipy.stats.gamma`, `floc=0`)
- **Weibull** (`scipy.stats.weibull_min`, `floc=0`)

For each fit we computed the AIC and a one-sample Kolmogorov-Smirnov statistic
against the fitted CDF. The "best fit" for a bin is the family with the
smallest AIC.

Reproduction: `python fit.py` from this folder against a local copy of the
Bitbrains fastStorage trace at
`.../scratchpad/bitbrains/fastStorage/2013-8/*.csv`. Seed `42`. Runtime about
two minutes on a laptop.

## Results

**286 VMs, 6,233 hour-of-day bins.**

Best-fitting distribution per bin, by AIC:

| Family     | Share of bins | Bins  |
|------------|--------------:|------:|
| Log-normal |        66.05% | 4,117 |
| Weibull    |        17.42% | 1,086 |
| Gamma      |         9.23% |   576 |
| Normal     |         7.30% |   454 |

![Best-fit share](best_fit_share.png)

Median AIC across bins (lower is better):

| Family     | Median AIC |
|------------|-----------:|
| Log-normal |    205.7   |
| Gamma      |    250.7   |
| Weibull    |    350.9   |
| Normal     |    369.3   |

Pairwise, log-normal beats each alternative on a majority of bins, with
substantial median AIC gaps:

| Comparison                | Median AIC delta | Share where log-normal wins | Wins by delta AIC >= 2 |
|---------------------------|-----------------:|----------------------------:|----------------------:|
| Log-normal vs. Normal     |            -93.2 |                     75.55%  |               74.82%  |
| Log-normal vs. Gamma      |            -12.0 |                     66.05%  |               62.78%  |
| Log-normal vs. Weibull    |            -54.8 |                     73.42%  |               72.93%  |

(A delta of about 2 or more in AIC is the conventional threshold for
substantial evidence in favor of the lower model.)

The Kolmogorov-Smirnov test rejects every family at 5% in almost every bin,
which is expected behavior for KS with parameters estimated from data at
sample sizes of hundreds to thousands. All four families are rejected at
similar rates, so KS is not discriminating on this trace; AIC is.

## Interpretation

Log-normal is the best-fitting family among the four candidates in about
two-thirds of hourly bins in an independent, public production trace collected
two years after the original 2011 study, on a different fleet, with different
workload characteristics. The report's log-normal claim replicates.

Gamma comes closest to log-normal on this dataset (12-point median AIC gap,
losing on 66% of bins), which is consistent with both being right-skewed,
positive-support distributions: the paper's derivation from
"each new transaction adds CPU load in proportion to the load already present"
distinguishes log-normal from gamma physically, not statistically, and a
follow-up paper would want to look at the multiplicative-versus-additive
noise structure directly.

The KS behavior above is the main caveat: at these sample sizes no simple
two-parameter family passes a strict goodness-of-fit test. The right paper
framing is "log-normal is the best-fitting parametric approximation among
standard candidates", not "CPU is exactly log-normal".

## Files

- `fit.py`: the analysis script.
- `bitbrains_fit_results.csv`: per-bin results (VM, hour, sample count, mean, std, per-family AIC and KS p-value, best-by-AIC label).
- `bitbrains_summary.json`: aggregate summary written by `fit.py`.
- `best_fit_share.png`: bar chart of best-fit family shares.
