"""Root-cause decomposition of the observed sigma(lambda) growth (gamma_hat < 0).

Cohort: all VMs with gamma_hat < 0 and R^2_sigma >= 0.5 on each trace
(scaling_fastStorage.csv / scaling_rnd.csv). For each VM, within each
hour-of-day bin (>=60 samples), the variance of log CPU is decomposed by
the law of total variance over calendar days:

    Var_total = Var_between_day + Var_within_day
    Var_between = sum_d n_d (m_d - m)^2 / N   (day means differ)
    Var_within  = sum_d n_d v_d / N           (dispersion inside one day-hour)

Candidate mechanisms tested per VM across its bins:
  M1 multiplicative day-to-day fluctuation: Spearman(lambda, sqrt(Var_between))
     and the between-day share of total variance.
  M2 workload-mode switching: 2-vs-1 component Gaussian-mixture BIC on the
     pooled log-CPU of each bin (bimodal if BIC_2 < BIC_1 - 10 and both
     weights >= 0.10); compare bimodal rate in top vs bottom lambda tercile.
  M3 saturation ceiling: fraction of samples with CPU > 90%, and skewness of
     log CPU, per bin; Spearman against lambda.
  M4 I/O feed-forward: across VMs, Spearman(mean disk+net throughput,
     mean per-bin sigma).

Outputs: printed stats, rc_decomp.csv (per-bin rows), scoping/rc_*.png.
Run from scoping/: /c/Python314/python sigma_rootcause.py
"""
import os, warnings
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, skew
from sklearn.mixture import GaussianMixture

warnings.filterwarnings("ignore")

BLUE, ORANGE, GREEN, PURPLE = "#3d65b8", "#c2542c", "#0f9268", "#8a5bb8"
plt.rcParams.update({"figure.facecolor": "white", "savefig.facecolor": "white",
                     "axes.grid": True, "grid.alpha": 0.3, "font.size": 9})

MIN_N = 60
CPU_FLOOR = 0.05
BIC_MARGIN = 10.0
MIN_W = 0.10
ROOT = {"fastStorage": r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8",
        "rnd": r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8"}
HERE = os.path.dirname(os.path.abspath(__file__))


def read_vm(fp):
    df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    ts = df["Timestamp [ms]"].astype(float).values
    cpu = df["CPU usage [%]"].astype(float).values
    net = df["Network received throughput [KB/s]"].astype(float).values
    dr = df["Disk read throughput [KB/s]"].astype(float).values
    dw = df["Disk write throughput [KB/s]"].astype(float).values
    mask = (np.isfinite(cpu) & np.isfinite(net) & (cpu >= CPU_FLOOR)
            & (cpu <= 100) & (net >= 0))
    ts, cpu, net = ts[mask], cpu[mask], net[mask]
    io = np.nan_to_num(dr[mask], nan=0.0) + np.nan_to_num(dw[mask], nan=0.0)
    hour = (np.floor(ts / 3600).astype(int)) % 24
    day = np.floor(ts / 86400).astype(int)
    return hour, day, cpu, net, io


def bin_rows(hour, day, cpu, net, io):
    rows = []
    for h in range(24):
        m = hour == h
        if m.sum() < MIN_N:
            continue
        x = np.log(cpu[m]); d = day[m]; c = cpu[m]
        N = len(x); mean_all = x.mean(); v_tot = x.var()
        vb = vw = 0.0
        for dd in np.unique(d):
            xd = x[d == dd]; nd = len(xd)
            vb += nd * (xd.mean() - mean_all) ** 2
            vw += nd * xd.var()
        vb /= N; vw /= N
        # GMM 1 vs 2 components on pooled bin
        X = x.reshape(-1, 1)
        try:
            g1 = GaussianMixture(1, random_state=0).fit(X)
            g2 = GaussianMixture(2, n_init=3, random_state=0).fit(X)
            bimodal = (g2.bic(X) < g1.bic(X) - BIC_MARGIN
                       and g2.weights_.min() >= MIN_W)
            sep = float(abs(g2.means_[0, 0] - g2.means_[1, 0]))
        except Exception:
            bimodal, sep = False, np.nan
        rows.append(dict(hour=h, n=N, lam=float(net[m].mean()),
                         io=float(io[m].mean()),
                         sigma=float(np.sqrt(v_tot)),
                         sig_between=float(np.sqrt(vb)),
                         sig_within=float(np.sqrt(vw)),
                         frac_between=float(vb / v_tot) if v_tot > 0 else np.nan,
                         bimodal=bool(bimodal), gmm_sep=sep,
                         skew=float(skew(x)),
                         frac90=float((c > 90).mean()),
                         p95=float(np.percentile(c, 95))))
    return pd.DataFrame(rows)


def sp(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 5 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return np.nan
    return spearmanr(a[ok], b[ok]).statistic


# ------------------------------------------------------------------ cohort
proxy = pd.read_csv(os.path.join(HERE, "diag_proxy.csv"))
vm_rows, bin_all = [], []
for label in ROOT:
    res = pd.read_csv(os.path.join(HERE, f"scaling_{label}.csv"))
    res["base"] = res["vm"].str.split("/").str[-1]
    coh = res[(res["gamma"] < 0) & (res["r2_sigma"] >= 0.5)]
    print(f"[{label}] cohort n={len(coh)} (gamma<0 & r2_sigma>=0.5)")
    for _, row in coh.iterrows():
        fp = os.path.join(ROOT[label], row["base"])
        hour, day, cpu, net, io = read_vm(fp)
        B = bin_rows(hour, day, cpu, net, io)
        if len(B) < 6:
            continue
        B["trace"], B["vm"] = label, row["base"]
        bin_all.append(B)
        terc = np.percentile(B["lam"], [33.3, 66.7])
        lo, hi = B[B["lam"] <= terc[0]], B[B["lam"] >= terc[1]]
        rho_p = proxy.loc[(proxy["trace"] == label) & (proxy["base"] == row["base"]),
                          "rho_cpu_net"]
        vm_rows.append(dict(
            trace=label, vm=row["base"], n_bins=len(B),
            gamma=row["gamma"], r2_sigma=row["r2_sigma"],
            rho_cpu_net=float(rho_p.iloc[0]) if len(rho_p) else np.nan,
            rho_lam_sigma=sp(B["lam"], B["sigma"]),
            rho_lam_sb=sp(B["lam"], B["sig_between"]),
            rho_lam_sw=sp(B["lam"], B["sig_within"]),
            med_frac_between=float(B["frac_between"].median()),
            frac_between_hi=float(hi["frac_between"].median()),
            frac_between_lo=float(lo["frac_between"].median()),
            bimodal_share=float(B["bimodal"].mean()),
            bimodal_hi=float(hi["bimodal"].mean()),
            bimodal_lo=float(lo["bimodal"].mean()),
            rho_lam_frac90=sp(B["lam"], B["frac90"]),
            max_frac90=float(B["frac90"].max()),
            max_p95=float(B["p95"].max()),
            rho_lam_skew=sp(B["lam"], B["skew"]),
            med_skew_hi=float(hi["skew"].median()),
            mean_io=float(B["io"].mean()), mean_net=float(B["lam"].mean()),
            mean_sigma=float(B["sigma"].median())))

vm = pd.DataFrame(vm_rows)
bins = pd.concat(bin_all, ignore_index=True)
bins.to_csv(os.path.join(HERE, "rc_decomp.csv"), index=False)
print(f"\nTotal cohort VMs analyzed: {len(vm)} "
      f"({(vm['trace']=='fastStorage').sum()} fastStorage, {(vm['trace']=='rnd').sum()} rnd)")

# ------------------------------------------------------------------ M1
print("\n=== M1: between-day vs within-day decomposition ===")
for label in ROOT:
    v = vm[vm["trace"] == label]
    print(f"[{label}] n={len(v)}")
    print(f"  median Spearman(lam, sigma_between) = {v['rho_lam_sb'].median():.2f} "
          f"(positive in {(v['rho_lam_sb']>0).sum()}/{v['rho_lam_sb'].notna().sum()})")
    print(f"  median Spearman(lam, sigma_within)  = {v['rho_lam_sw'].median():.2f} "
          f"(positive in {(v['rho_lam_sw']>0).sum()}/{v['rho_lam_sw'].notna().sum()})")
    print(f"  median between-day variance share: all bins {v['med_frac_between'].median():.2f}, "
          f"high-lam tercile {v['frac_between_hi'].median():.2f}, "
          f"low-lam tercile {v['frac_between_lo'].median():.2f}")

# ------------------------------------------------------------------ M2
print("\n=== M2: bimodality (2-comp GMM BIC) ===")
for label in ROOT:
    v = vm[vm["trace"] == label]
    print(f"[{label}] median bimodal share of bins = {v['bimodal_share'].median():.2f}")
    print(f"  bimodal rate high-lam tercile {v['bimodal_hi'].median():.2f} "
          f"vs low-lam {v['bimodal_lo'].median():.2f}; "
          f"hi>lo in {(v['bimodal_hi']>v['bimodal_lo']).sum()}/{len(v)} VMs, "
          f"hi<lo in {(v['bimodal_hi']<v['bimodal_lo']).sum()}/{len(v)}")
b = bins
print(f"  pooled bins: bimodal in {b['bimodal'].mean():.2f} of {len(b)} bins; "
      f"median GMM separation among bimodal = "
      f"{b.loc[b['bimodal'],'gmm_sep'].median():.2f} log units")

# ------------------------------------------------------------------ M3
print("\n=== M3: saturation ceiling ===")
for label in ROOT:
    v = vm[vm["trace"] == label]
    print(f"[{label}] max frac(CPU>90) across bins: median {v['max_frac90'].median():.4f}, "
          f"90th pct {v['max_frac90'].quantile(0.9):.4f}; "
          f"VMs ever exceeding 5% of samples >90: {(v['max_frac90']>0.05).sum()}/{len(v)}")
    print(f"  max p95 CPU: median {v['max_p95'].median():.1f}%")
    print(f"  median Spearman(lam, frac90) = {v['rho_lam_frac90'].median():.2f}; "
          f"median Spearman(lam, skew) = {v['rho_lam_skew'].median():.2f}; "
          f"median skew in high-lam bins = {v['med_skew_hi'].median():.2f}")

# ------------------------------------------------------------------ M4
print("\n=== M4: I/O feed-forward (across VMs) ===")
for label in ROOT:
    v = vm[vm["trace"] == label]
    r_io = sp(np.log10(v["mean_io"] + 1e-3), v["mean_sigma"])
    r_net = sp(np.log10(v["mean_net"] + 1e-3), v["mean_sigma"])
    print(f"[{label}] Spearman(log mean disk I/O, median sigma) = {r_io:.2f}; "
          f"Spearman(log mean net, median sigma) = {r_net:.2f}  (n={len(v)})")

# ------------------------------------------------------------------ failing/extreme inspection
print("\n=== Extreme-VM inspection ===")
for name in ["1025.csv", "1091.csv", "1003.csv"]:
    B = bins[(bins["vm"] == name) & (bins["trace"] == "fastStorage")]
    if len(B) == 0:
        continue
    B = B.sort_values("lam")
    lo, hi = B.iloc[:4], B.iloc[-4:]
    print(f"{name}: lam lo bins sigma={lo['sigma'].mean():.2f} "
          f"(between {lo['sig_between'].mean():.2f} / within {lo['sig_within'].mean():.2f}, "
          f"bimodal {lo['bimodal'].mean():.2f}) | lam hi bins sigma={hi['sigma'].mean():.2f} "
          f"(between {hi['sig_between'].mean():.2f} / within {hi['sig_within'].mean():.2f}, "
          f"bimodal {hi['bimodal'].mean():.2f}, frac90 {hi['frac90'].max():.3f})")

# ------------------------------------------------------------------ figures
# Fig 1: per-VM Spearman(lam, sigma_between) vs Spearman(lam, sigma_within)
fig, axes = plt.subplots(1, 2, figsize=(9, 4))
for ax, label, c in zip(axes, ROOT, [BLUE, ORANGE]):
    v = vm[vm["trace"] == label]
    ax.scatter(v["rho_lam_sb"], v["rho_lam_sw"], s=20, color=c, alpha=0.75)
    ax.axhline(0, color="0.5", lw=0.8); ax.axvline(0, color="0.5", lw=0.8)
    ax.plot([-1, 1], [-1, 1], "--", color="0.7", lw=0.8)
    ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05)
    ax.set_xlabel("Spearman($\\lambda$, $\\sigma_{between-day}$)")
    ax.set_ylabel("Spearman($\\lambda$, $\\sigma_{within-day}$)")
    ax.set_title(f"{label} (n={len(v)} cohort VMs)")
plt.tight_layout()
plt.savefig(os.path.join(HERE, "rc_decomposition.png"), dpi=180)
plt.close()

# Fig 2: between-day variance share, pooled bins, vs lambda rank within VM
fig, axes = plt.subplots(1, 2, figsize=(9, 4))
for ax, label, c in zip(axes, ROOT, [BLUE, ORANGE]):
    v = vm[vm["trace"] == label]
    ax.hist(v["med_frac_between"].dropna(), bins=np.arange(0, 1.05, 0.05),
            color=c, edgecolor="white")
    med = v["med_frac_between"].median()
    ax.axvline(med, color=GREEN, lw=1.5, label=f"median {med:.2f}")
    ax.set_xlabel("median between-day share of Var(log CPU) per VM")
    ax.set_ylabel("VMs"); ax.set_title(label); ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(HERE, "rc_between_share.png"), dpi=180)
plt.close()

# Fig 3: bimodality rate by lambda tercile (paired) + saturation summary
fig, axes = plt.subplots(1, 2, figsize=(9, 4))
ax = axes[0]
for label, c, dx in [("fastStorage", BLUE, -0.06), ("rnd", ORANGE, 0.06)]:
    v = vm[vm["trace"] == label]
    for _, r in v.iterrows():
        ax.plot([0 + dx, 1 + dx], [r["bimodal_lo"], r["bimodal_hi"]],
                "-o", color=c, alpha=0.35, ms=3, lw=0.8)
    ax.plot([0 + dx, 1 + dx], [v["bimodal_lo"].median(), v["bimodal_hi"].median()],
            "-s", color=c, lw=2.5, ms=7, label=f"{label} median")
ax.set_xticks([0, 1]); ax.set_xticklabels(["low-$\\lambda$ tercile", "high-$\\lambda$ tercile"])
ax.set_ylabel("share of bins bimodal (GMM BIC)"); ax.legend()
ax.set_title("M2: bimodality by load tercile")
ax = axes[1]
for label, c in [("fastStorage", BLUE), ("rnd", ORANGE)]:
    v = vm[vm["trace"] == label]
    ax.scatter(v["max_p95"], v["rho_lam_sigma"], s=20, color=c, alpha=0.75, label=label)
ax.axvline(90, color=GREEN, lw=1.2, label="90% CPU")
ax.set_xlabel("max p95 CPU (%) across bins"); ax.set_ylabel("Spearman($\\lambda$, $\\sigma$)")
ax.set_title("M3: how close does the cohort get to the ceiling"); ax.legend(fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(HERE, "rc_bimodal_saturation.png"), dpi=180)
plt.close()

# Fig 4: sigma components vs lambda for two exemplar VMs
ex = [("fastStorage", "1025.csv"), ("fastStorage", "1091.csv")]
fig, axes = plt.subplots(1, 2, figsize=(9, 4))
for ax, (label, name) in zip(axes, ex):
    B = bins[(bins["vm"] == name) & (bins["trace"] == label)].sort_values("lam")
    ax.plot(B["lam"], B["sigma"], "o-", color=PURPLE, ms=4, label="$\\sigma$ total")
    ax.plot(B["lam"], B["sig_between"], "s-", color=BLUE, ms=4, label="between-day")
    ax.plot(B["lam"], B["sig_within"], "^-", color=ORANGE, ms=4, label="within-day")
    ax.set_xlabel("$\\lambda$ (net KB/s)"); ax.set_ylabel("$\\sigma_{\\log C}$")
    ax.set_title(f"{label}/{name}"); ax.legend(fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(HERE, "rc_exemplars.png"), dpi=180)
plt.close()

vm.to_csv(os.path.join(HERE, "rc_vm_summary.csv"), index=False)
print("\nSaved rc_decomp.csv, rc_vm_summary.csv, rc_*.png")
