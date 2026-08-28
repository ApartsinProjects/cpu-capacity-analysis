"""Diagnostics for the negative parameter-scaling result (paper Section 6).

Inspects the failing and extreme datapoints behind scaling_summary.json:
  1. R^2 distributions across VMs (both traces), tails included.
  2. Wrong-sign cases (alpha<0, gamma<0): per-bin (lam, mu, sigma) triples
     and hour-of-day trajectories for representative VMs.
  3. Good-fit cases (r2_mu >= 0.8): what distinguishes them.
  4. Direct test of the "network is a bad proxy" hypothesis: sample-level
     CPU-vs-network Spearman correlation per VM, then condition the scaling
     fits on proxy quality. If well-proxied VMs still show gamma<0, the
     mechanism (not the proxy) is the problem.

Outputs: printed stats + scoping/diag_*.png figures (180 dpi).
Run from scoping/: /c/Python314/python scaling_diagnose.py
"""
import glob, os, sys, json
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

BLUE, ORANGE, GREEN, PURPLE = "#3d65b8", "#c2542c", "#0f9268", "#8a5bb8"
plt.rcParams.update({"figure.facecolor": "white", "savefig.facecolor": "white",
                     "axes.grid": True, "grid.alpha": 0.3, "font.size": 9})

MIN_N = 60
CPU_FLOOR = 0.05
ROOT_FS  = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8"
ROOT_RND = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8"
HERE = os.path.dirname(os.path.abspath(__file__))

def load_results(label):
    df = pd.read_csv(os.path.join(HERE, f"scaling_{label}.csv"))
    df["base"] = df["vm"].str.split("/").str[-1]
    return df

def read_vm(fp):
    df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    ts = df["Timestamp [ms]"].astype(float).values
    hours = (np.floor(ts / 3600).astype(int)) % 24
    cpu = df["CPU usage [%]"].astype(float).values
    net = df["Network received throughput [KB/s]"].astype(float).values
    mask = np.isfinite(cpu) & np.isfinite(net) & (cpu >= CPU_FLOOR) & (cpu <= 100) & (net >= 0)
    return hours[mask], cpu[mask], net[mask]

def triples(hours, cpu, net):
    out = []
    for h in range(24):
        m = hours == h
        if m.sum() < MIN_N: continue
        out.append((h, float(np.mean(net[m])), float(np.mean(np.log(cpu[m]))),
                    float(np.std(np.log(cpu[m])))))
    return np.array(out)  # cols: hour, lam, mu, sigma

# ------------------------------------------------------------------ load
res = {"fastStorage": load_results("fastStorage"), "rnd": load_results("rnd")}
roots = {"fastStorage": ROOT_FS, "rnd": ROOT_RND}

print("=== 1. R2 distributions and sign counts ===")
for label, df in res.items():
    v = df.dropna(subset=["r2_mu"])
    vs = df.dropna(subset=["r2_sigma"])
    print(f"\n[{label}] n={len(df)}  r2_mu valid={len(v)}  r2_sigma valid={len(vs)}")
    for col, d in [("r2_mu", v), ("r2_sigma", vs)]:
        q = d[col].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(3).to_dict()
        print(f"  {col}: quantiles {q}  share>=0.8 {(d[col]>=0.8).mean():.3f}")
    print(f"  alpha<0: {(v['alpha']<0).mean():.3f} ({int((v['alpha']<0).sum())} VMs)")
    print(f"  gamma<0: {(vs['gamma']<0).mean():.3f} ({int((vs['gamma']<0).sum())} VMs)")
    print(f"  gamma<0 among r2_sigma>=0.5: "
          f"{(vs.loc[vs['r2_sigma']>=0.5,'gamma']<0).mean():.3f} "
          f"(n={int((vs['r2_sigma']>=0.5).sum())})")
    # what distinguishes good mu fits
    v = v.copy()
    v["lam_range"] = v["lam_max"] - v["lam_min"]
    v["log_lam_max"] = np.log10(v["lam_max"] + 1e-6)
    good = v["r2_mu"] >= 0.8
    print(f"  good-fit (r2_mu>=0.8, n={int(good.sum())}) median lam_max="
          f"{v.loc[good,'lam_max'].median():.1f} vs rest {v.loc[~good,'lam_max'].median():.1f}")
    rho = spearmanr(v["log_lam_max"], v["r2_mu"]).statistic
    print(f"  Spearman(log10 lam_max, r2_mu) = {rho:.3f}")

# ------------------------------------------------------------------ fig 1: R2 hists
fig, axes = plt.subplots(2, 2, figsize=(9, 6))
for i, (label, df) in enumerate(res.items()):
    for j, col in enumerate(["r2_mu", "r2_sigma"]):
        ax = axes[i, j]
        d = df[col].dropna().clip(lower=-0.05)
        ax.hist(d, bins=np.arange(-0.05, 1.05, 0.05),
                color=BLUE if j == 0 else ORANGE, edgecolor="white")
        ax.axvline(d.median(), color=GREEN, lw=1.5, label=f"median {d.median():.2f}")
        ax.set_title(f"{label}: {col}")
        ax.set_xlabel("$R^2$"); ax.legend(fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(HERE, "diag_r2_hist.png"), dpi=180)
plt.close()

# ------------------------------------------------------------------ 2+3. case studies
print("\n=== 2/3. Case studies (fastStorage) ===")
df = res["fastStorage"]
valid = df.dropna(subset=["r2_mu", "r2_sigma"]).copy()
# bad: gamma<0 with sigma fit that is not just noise (r2_sigma decent)
bad = valid[(valid["gamma"] < 0) & (valid["r2_sigma"] >= 0.5)].nlargest(4, "r2_sigma")
good = valid[valid["r2_mu"] >= 0.8].nlargest(4, "r2_mu")

def case_fig(rows, fname, title):
    n = len(rows)
    fig, axes = plt.subplots(3, n, figsize=(3.0 * n, 7.5))
    for k, (_, row) in enumerate(rows.iterrows()):
        fp = os.path.join(roots["fastStorage"], row["base"])
        hours, cpu, net = read_vm(fp)
        T = triples(hours, cpu, net)
        h, lam, mu, sig = T[:, 0], T[:, 1], T[:, 2], T[:, 3]
        ax = axes[0, k]
        ax.plot(h, lam, "o-", color=PURPLE, ms=3)
        ax.set_title(f"{row['base']}\nr2mu={row['r2_mu']:.2f} r2sig={row['r2_sigma']:.2f}\n"
                     f"a={row['alpha']:.3g} g={row['gamma']:.3g}", fontsize=7)
        ax.set_ylabel("net KB/s" if k == 0 else "")
        ax = axes[1, k]
        ax.plot(lam, mu, "o", color=BLUE, ms=4)
        xx = np.linspace(lam.min(), lam.max(), 50)
        ax.plot(xx, row["alpha"] * xx + row["beta"], "-", color=GREEN, lw=1)
        ax.set_xlabel("$\\lambda$ (net KB/s)"); ax.set_ylabel("$\\mu_{\\log C}$" if k == 0 else "")
        ax = axes[2, k]
        ok = lam > 0
        ax.plot(lam[ok], sig[ok], "o", color=ORANGE, ms=4)
        xx = np.linspace(max(lam[ok].min(), 1e-6), lam.max(), 100)
        ax.plot(xx, row["gamma"] / np.sqrt(xx) + row["delta"], "-", color=GREEN, lw=1)
        ax.set_xlabel("$\\lambda$"); ax.set_ylabel("$\\sigma_{\\log C}$" if k == 0 else "")
    fig.suptitle(title, y=1.0)
    plt.tight_layout()
    plt.savefig(os.path.join(HERE, fname), dpi=180, bbox_inches="tight")
    plt.close()
    for _, row in rows.iterrows():
        print(f"  {row['base']}: r2_mu={row['r2_mu']:.2f} r2_sigma={row['r2_sigma']:.2f} "
              f"alpha={row['alpha']:.4g} gamma={row['gamma']:.4g} "
              f"lam=[{row['lam_min']:.2f},{row['lam_max']:.2f}]")

print("\n-- wrong-sign gamma, good sigma fit (sigma RISES with lam):")
case_fig(bad, "diag_cases_wrong_sign.png",
         "fastStorage: gamma<0 with r2_sigma>=0.5 (sigma increases with load)")
print("\n-- best mu fits:")
case_fig(good, "diag_cases_good_mu.png", "fastStorage: best mu(lambda) fits (r2_mu>=0.8)")

# ------------------------------------------------------------------ 4. proxy test
print("\n=== 4. Proxy quality test ===")
rng = np.random.default_rng(7)
proxy_rows = []
for label, df in res.items():
    d = df.dropna(subset=["r2_mu", "r2_sigma"])
    sample = d.sample(min(120, len(d)), random_state=7)
    for _, row in sample.iterrows():
        fp = os.path.join(roots[label], row["base"])
        try:
            hours, cpu, net = read_vm(fp)
        except Exception:
            continue
        if len(cpu) < 200 or np.std(net) == 0 or np.std(cpu) == 0:
            continue
        rho = spearmanr(cpu, net).statistic
        proxy_rows.append({"trace": label, "base": row["base"], "rho_cpu_net": rho,
                           "r2_mu": row["r2_mu"], "r2_sigma": row["r2_sigma"],
                           "alpha": row["alpha"], "gamma": row["gamma"]})
pr = pd.DataFrame(proxy_rows)
pr.to_csv(os.path.join(HERE, "diag_proxy.csv"), index=False)
for label in res:
    p = pr[pr["trace"] == label]
    print(f"\n[{label}] n={len(p)} sampled VMs")
    print(f"  Spearman(CPU, net) quantiles: "
          f"{p['rho_cpu_net'].quantile([0.1,0.5,0.9]).round(2).to_dict()}")
    hi = p[p["rho_cpu_net"] >= 0.5]
    lo = p[p["rho_cpu_net"] < 0.2]
    print(f"  strongly proxied (rho>=0.5): n={len(hi)}, median r2_mu={hi['r2_mu'].median():.2f}, "
          f"gamma<0 share={(hi['gamma']<0).mean():.2f}, median gamma={hi['gamma'].median():.3f}")
    print(f"  weakly proxied (rho<0.2):   n={len(lo)}, median r2_mu={lo['r2_mu'].median():.2f}, "
          f"gamma<0 share={(lo['gamma']<0).mean():.2f}")
    rr = spearmanr(p["rho_cpu_net"], p["r2_mu"]).statistic
    print(f"  Spearman(rho_cpu_net, r2_mu) across VMs = {rr:.3f}")

fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
for ax, label, c in zip(axes, res, [BLUE, ORANGE]):
    p = pr[pr["trace"] == label]
    ax.scatter(p["rho_cpu_net"], p["r2_mu"], s=14, color=c, alpha=0.7)
    ax.set_xlabel("Spearman(CPU, net) per VM"); ax.set_ylabel("$R^2$ of $\\mu(\\lambda)$ fit")
    ax.set_title(label); ax.set_ylim(-0.05, 1.02)
plt.tight_layout()
plt.savefig(os.path.join(HERE, "diag_proxy_vs_fit.png"), dpi=180)
plt.close()

# gamma sign among well-proxied, good-sigma-fit VMs: the decisive cell
hi_all = pr[(pr["rho_cpu_net"] >= 0.5) & (pr["r2_sigma"] >= 0.5)]
print(f"\nDecisive cell: rho_cpu_net>=0.5 AND r2_sigma>=0.5: n={len(hi_all)}, "
      f"gamma<0 in {(hi_all['gamma']<0).mean():.2f} of them "
      f"(median gamma={hi_all['gamma'].median():.3f})")
print(hi_all[["trace","base","rho_cpu_net","r2_sigma","gamma"]].to_string(index=False))
print("\nDone.")
