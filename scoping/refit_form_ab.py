"""Per-VM Form A vs Form B refits of sigma(lambda), plus mu(lambda) fit,
on both Bitbrains traces. Reports how well Form B recovers a consistent
alpha between the mu fit and the sigma fit.

Form A (previous):  sigma(lam) = gamma/sqrt(lam) + delta
Form B (corrected): sigma(lam) = sqrt(alpha^2 * lam + sigma_eps^2)

Also produces a figure with (left) an exemplar VM's mu(lam) and sigma(lam)
with both forms overlaid, and (right) the paired alpha_mu vs alpha_sigma
scatter across VMs.
"""
import glob, os, random, sys, json
import numpy as np, pandas as pd
from scipy.optimize import curve_fit

random.seed(42)
CPU_FLOOR = 0.05
MIN_N = 60
MIN_BINS_PER_VM = 6

def read_vm(fp):
    try:
        df = pd.read_csv(fp, sep=";", engine="python", skipinitialspace=True)
    except Exception:
        return None
    df.columns = [c.strip() for c in df.columns]
    need = ["CPU usage [%]", "Timestamp [ms]", "Network received throughput [KB/s]"]
    if not all(c in df.columns for c in need): return None
    ts = df["Timestamp [ms]"].astype(float).values
    hours = (np.floor(ts / 3600).astype(int)) % 24
    cpu = df["CPU usage [%]"].astype(float).values
    net = df["Network received throughput [KB/s]"].astype(float).values
    m = np.isfinite(cpu) & np.isfinite(net) & (cpu >= CPU_FLOOR) & (cpu <= 100) & (net >= 0)
    return hours[m], cpu[m], net[m]

def per_vm_triples(hours, cpu, net):
    triples = []
    for h in range(24):
        m = hours == h
        if m.sum() < MIN_N: continue
        c = cpu[m]; n = net[m]
        triples.append((float(np.mean(n)), float(np.mean(np.log(c))), float(np.std(np.log(c)))))
    return np.array(triples)

def ols_r2(x, y):
    if len(x) < 3 or np.std(x) == 0: return np.nan, np.nan, np.nan
    A = np.vstack([x, np.ones_like(x)]).T
    (a, b), *_ = np.linalg.lstsq(A, y, rcond=None)
    ypred = A @ np.array([a, b])
    ss_res = float(np.sum((y - ypred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return float(a), float(b), float(r2)

def formA(lam, sig):
    return ols_r2(1.0 / np.sqrt(lam), sig)

def formB(lam, sig):
    def f(l, a, s):
        return np.sqrt(np.maximum(a * a * l + s * s, 1e-12))
    try:
        popt, _ = curve_fit(f, lam, sig, p0=[0.01, np.median(sig)], maxfev=3000,
                             bounds=([0, 0], [np.inf, np.inf]))
        a_hat, s_hat = float(popt[0]), float(popt[1])
        pred = f(lam, a_hat, s_hat)
        ss_res = float(np.sum((sig - pred) ** 2))
        ss_tot = float(np.sum((sig - sig.mean()) ** 2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
        return a_hat, s_hat, float(r2)
    except Exception:
        return np.nan, np.nan, np.nan

def process(files):
    rows = []
    for i, fp in enumerate(files):
        r = read_vm(fp)
        if r is None: continue
        hours, cpu, net = r
        triples = per_vm_triples(hours, cpu, net)
        if len(triples) < MIN_BINS_PER_VM: continue
        lam = triples[:, 0]; mu = triples[:, 1]; sig = triples[:, 2]
        if lam.min() <= 0: continue
        # mu(lam) = alpha_mu * lam + beta
        a_mu, b_mu, r2_mu = ols_r2(lam, mu)
        # Form A sigma
        gA, dA, r2A = formA(lam, sig)
        # Form B sigma
        aB, sB, r2B = formB(lam, sig)
        rows.append({
            "vm": os.path.relpath(fp).replace("\\", "/"),
            "n_bins": int(len(triples)),
            "lam_min": float(lam.min()), "lam_max": float(lam.max()),
            "alpha_mu": a_mu, "beta_mu": b_mu, "r2_mu": r2_mu,
            "gammaA": gA, "deltaA": dA, "r2A": r2A,
            "alpha_sig": aB, "sigma_eps": sB, "r2B": r2B,
        })
        if (i + 1) % 25 == 0:
            print(f"  {i+1} files, {len(rows)} VMs kept", file=sys.stderr)
    return pd.DataFrame(rows)

def summarize(df):
    out = {"n_vms": int(len(df))}
    for c in ["r2A", "r2B", "r2_mu"]:
        out[f"median_{c}"] = float(df[c].median())
    # Cohort where BOTH the mu fit and the Form B sigma fit are meaningful
    ok = (df["r2_mu"] >= 0.5) & (df["r2B"] >= 0.3) & (df["alpha_mu"] > 0) & (df["alpha_sig"] > 0)
    coh = df[ok]
    out["cohort_n"] = int(len(coh))
    if len(coh) > 3:
        ratio = coh["alpha_sig"] / coh["alpha_mu"]
        out["alpha_ratio_median"] = float(ratio.median())
        out["alpha_ratio_p25"] = float(ratio.quantile(0.25))
        out["alpha_ratio_p75"] = float(ratio.quantile(0.75))
        out["alpha_agree_within_2x"] = float(((ratio >= 0.5) & (ratio <= 2.0)).mean())
        out["alpha_agree_within_5x"] = float(((ratio >= 0.2) & (ratio <= 5.0)).mean())
        # Spearman correlation
        from scipy.stats import spearmanr
        rho, p = spearmanr(coh["alpha_mu"], coh["alpha_sig"])
        out["spearman_alpha_mu_sig"] = float(rho)
        out["spearman_p"] = float(p)
    # Form B vs Form A R2 comparison
    diff = df["r2B"] - df["r2A"]
    out["formB_better_by_r2"] = float((diff > 0).mean())
    out["median_r2B_minus_r2A"] = float(diff.median())
    return out

ROOT_FS  = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/bitbrains/fastStorage/2013-8"
ROOT_RND = r"E:/tmp/claude/E--Projects-Submitted-Amdocs/34878466-835f-474b-a49b-ee8b3bc3dbdb/scratchpad/rnd/rnd/2013-8"

results = {}
per_vm_all = {}
for label, root in [("fastStorage", ROOT_FS), ("rnd", ROOT_RND)]:
    files = sorted(glob.glob(os.path.join(root, "*.csv")))
    sample = random.sample(files, min(300, len(files)))
    print(f"### {label}: {len(sample)} files", file=sys.stderr)
    df = process(sample)
    df.to_csv(f"refit_ab_{label}.csv", index=False)
    per_vm_all[label] = df
    results[label] = summarize(df)

with open("refit_ab_summary.json", "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))

# ---- Figure: exemplar + paired-alpha scatter ----
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Exemplar: a well-fitting fastStorage VM
df_fs = per_vm_all["fastStorage"]
cand = df_fs[(df_fs["r2_mu"] >= 0.7) & (df_fs["r2B"] >= 0.5) &
             (df_fs["alpha_sig"] > 0) & (df_fs["alpha_mu"] > 0)].sort_values("r2B", ascending=False)
if len(cand):
    ex_row = cand.iloc[0]
    ex_fp = os.path.join(ROOT_FS, os.path.basename(ex_row["vm"]))
    hours, cpu, net = read_vm(ex_fp)
    triples = per_vm_triples(hours, cpu, net)
    lam = triples[:, 0]; mu = triples[:, 1]; sig = triples[:, 2]
    order = np.argsort(lam)
    lam = lam[order]; mu = mu[order]; sig = sig[order]
else:
    ex_row = None

fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.6))

# Panel 1: mu vs lam (linear fit)
ax = axes[0]
if ex_row is not None:
    ax.scatter(lam, mu, color="#3d65b8", s=32, zorder=3)
    xs = np.linspace(lam.min(), lam.max(), 200)
    ax.plot(xs, ex_row["alpha_mu"] * xs + ex_row["beta_mu"], color="#c2542c", lw=1.7,
            label=f"μ̂ = {ex_row['alpha_mu']:.4f}·λ + {ex_row['beta_mu']:.2f}, R²={ex_row['r2_mu']:.2f}")
    ax.set_xlabel("λ (mean net KB/s)"); ax.set_ylabel("μ (log CPU%)")
    ax.set_title(f"μ(λ) linear fit  ·  VM {os.path.basename(ex_row['vm']).replace('.csv','')}")
    ax.legend(fontsize=9, frameon=False)
    ax.grid(True, color="#e6e6e3", lw=0.7); ax.set_axisbelow(True)
    for sp in ax.spines.values(): sp.set_color("#dcdcda")
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)

# Panel 2: sigma vs lam with Form A and Form B
ax = axes[1]
if ex_row is not None:
    ax.scatter(lam, sig, color="#3d65b8", s=32, zorder=3, label="observed σ")
    xs = np.linspace(lam.min(), lam.max(), 400)
    yA = ex_row["gammaA"] / np.sqrt(xs) + ex_row["deltaA"]
    ax.plot(xs, yA, color="#c2542c", lw=1.7, label=f"Form A (previous), R²={ex_row['r2A']:.2f}")
    yB = np.sqrt(ex_row["alpha_sig"]**2 * xs + ex_row["sigma_eps"]**2)
    ax.plot(xs, yB, color="#0f9268", lw=1.7, label=f"Form B (corrected), R²={ex_row['r2B']:.2f}")
    ax.set_xlabel("λ (mean net KB/s)"); ax.set_ylabel("σ (log CPU%)")
    ax.set_title("σ(λ): Form A vs Form B")
    ax.legend(fontsize=9, frameon=False, loc="best")
    ax.grid(True, color="#e6e6e3", lw=0.7); ax.set_axisbelow(True)
    for sp in ax.spines.values(): sp.set_color("#dcdcda")
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)

# Panel 3: paired alpha_mu vs alpha_sig across the cohort
ax = axes[2]
for lbl, color in [("fastStorage", "#3d65b8"), ("rnd", "#c2542c")]:
    d = per_vm_all[lbl]
    ok = (d["r2_mu"] >= 0.5) & (d["r2B"] >= 0.3) & (d["alpha_mu"] > 0) & (d["alpha_sig"] > 0)
    coh = d[ok]
    if len(coh):
        ax.scatter(coh["alpha_mu"], coh["alpha_sig"], s=20, alpha=0.55, color=color, label=f"{lbl} (n={len(coh)})")
mn = min(1e-4, ax.get_xlim()[0] if ax.get_xlim()[0] > 0 else 1e-4)
mx = max(ax.get_xlim()[1], ax.get_ylim()[1])
ax.plot([mn, mx], [mn, mx], color="#878d96", ls="--", lw=1, label="α_μ = α_σ")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("α̂ from μ fit"); ax.set_ylabel("α̂ from σ (Form B) fit")
ax.set_title("Per-VM mechanism consistency")
ax.legend(fontsize=9, frameon=False, loc="lower right")
ax.grid(True, color="#e6e6e3", lw=0.7); ax.set_axisbelow(True)
for sp in ax.spines.values(): sp.set_color("#dcdcda")
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)

fig.suptitle("Bitbrains: μ(λ) linear, σ(λ) under Form A (paper's previous) vs Form B (corrected)",
             fontsize=11, y=1.02)
plt.tight_layout()
plt.savefig("refit_ab.png", dpi=180, facecolor="white", bbox_inches="tight")
print("figure saved")
