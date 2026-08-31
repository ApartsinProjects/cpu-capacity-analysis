"""Coverage-vs-capacity efficient frontier: for each sizing method, the
median reserved capacity needed to reach a given realized coverage, swept
over the method's parameter. Lower curve = more efficient. The log-normal
ceiling sits on the efficient frontier; the rolling maximum is far above it
(wasteful); the empirical percentile turns up at high coverage because it
cannot extrapolate past the observed maximum, while the parametric ceiling
extrapolates the tail smoothly.
Reads frontier_{fastStorage,alibaba}.csv from alibaba_frontier_calib.py.
"""
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False})
TRACES = [("fastStorage", "Bitbrains fastStorage (5 min)"),
          ("alibaba", "Alibaba (10 s)")]
STYLE = [("lognorm", "#1f77b4", "-", "log-normal"),
         ("gauss", "#ff7f0e", "--", "Gaussian mean+kσ"),
         ("empirical", "#2ca02c", "-.", "empirical percentile"),
         ("rolling_max", "#d62728", ":", "rolling maximum")]

def pareto_lower(d):
    """Keep the efficiency frontier: sort by coverage, running-min capacity."""
    d = d.sort_values("mean_coverage")
    return d

fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.6))
for ax, (label, title) in zip(axes, TRACES):
    fr = pd.read_csv(f"frontier_{label}.csv")
    for name, col, ls, disp in STYLE:
        d = fr[fr.method == name].sort_values("mean_coverage")
        d = d[(d.mean_coverage >= 0.85)]
        ax.plot(d.mean_coverage, d.median_ceiling, color=col, ls=ls, lw=1.8, label=disp)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("realized coverage")
    ax.set_ylabel("reserved capacity (median ceiling, CPU\\%)" if label=="fastStorage" else "reserved capacity (median ceiling, CPU\\%)")
    ax.axvline(0.998, color="gray", lw=0.7, ls=(0, (1, 2)), alpha=0.7)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(0.85, 1.0)
axes[0].legend(fontsize=8, loc="upper left", frameon=False)
axes[1].annotate("target\n99.8%", xy=(0.998, axes[1].get_ylim()[1]),
                 xytext=(0.93, axes[1].get_ylim()[1]*0.92), fontsize=7, color="gray")
fig.suptitle("Reserved capacity to reach a target coverage (lower is better)", fontsize=10)
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig("fig_frontier.pdf", bbox_inches="tight")
plt.savefig("fig_frontier.png", dpi=140, bbox_inches="tight")
print("wrote fig_frontier.pdf/.png")
