"""Reliability / calibration figure: nominal target coverage vs realized
held-out coverage, per method, on Alibaba (10s) and fastStorage (5min).
A calibrated ceiling tracks the diagonal; a sizing-safe one sits on/above it.
Reads calib_{alibaba,fastStorage}.csv from alibaba_frontier_calib.py.
"""
import pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TRACES = [("fastStorage", "Bitbrains fastStorage (5 min)"),
          ("alibaba", "Alibaba (10 s)")]
STYLE = {"lognorm": ("C0", "o", "log-normal"),
         "gauss": ("C1", "s", "Gaussian"),
         "empirical": ("C2", "^", "empirical percentile")}

fig, axes = plt.subplots(1, 2, figsize=(8, 3.6), sharey=True)
for ax, (label, title) in zip(axes, TRACES):
    df = pd.read_csv(f"calib_{label}.csv")
    ax.plot([0.88, 1.0], [0.88, 1.0], "k--", lw=0.8, alpha=0.6, label="ideal (calibrated)")
    for name, (col, mk, disp) in STYLE.items():
        d = df[df.method == name].sort_values("nominal")
        ax.plot(d.nominal, d.realized_mean_cov, color=col, marker=mk, ms=5,
                lw=1.4, label=disp)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("nominal target coverage")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0.88, 1.001)
axes[0].set_ylabel("realized held-out coverage")
axes[0].legend(fontsize=8, loc="lower right")
plt.tight_layout()
plt.savefig("fig_calibration.pdf", bbox_inches="tight")
plt.savefig("fig_calibration.png", dpi=140, bbox_inches="tight")
print("wrote fig_calibration.pdf/.png")
