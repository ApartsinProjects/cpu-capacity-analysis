"""Controlled test of the CLT-regime prediction, and of two competing
functional forms for sigma(lambda).

Mechanism (paper Section 3):
    log C_j = alpha * n_j + beta + eps_j
where n_j is the count of arrivals in window j (Poisson-lambda) and eps_j is
per-window multiplicative noise (std sigma_mult, independent of lambda).

Two ways to summarize the variance of log C at a bin with intensity lambda:

    Form A (paper's stated form, Section 6):
        sigma_log_C(lambda) = gamma / sqrt(lambda) + delta

    Form B (direct derivation from the mechanism):
        Var(log C) = alpha^2 * Var(n) + Var(eps) = alpha^2 * lambda + sigma_mult^2
        sigma_log_C(lambda) = sqrt( alpha^2 * lambda + sigma_mult^2 )

Form B increases with lambda. Form A decreases. They are not the same
function; the paper's "for large lambda this gives sigma ~ gamma/sqrt(lambda)
+ delta" appears to conflate standard deviation with coefficient of variation
(CV of Poisson-lambda is 1/sqrt(lambda), but sd(log C) is not CV(C)).

This simulator generates data under the mechanism at realistic parameters
and at two sampling resolutions (5 s vs 5 min), fits both forms per resolution,
and reports which form actually captures the observed sigma(lambda).

The prediction: Form B fits well at both resolutions with the same physical
alpha; Form A gives a negative gamma (because sigma increases with lambda)
and lower R^2. If the observed Bitbrains data shows increasing sigma with
lambda, that is consistent with the mechanism under Form B and inconsistent
with the paper's Form A.
"""
import json, numpy as np
from scipy import stats
from scipy.optimize import curve_fit

RNG = np.random.default_rng(42)
DAYS = 30

# Realistic parameters (matched to Bitbrains-scale CPU%: 5-90%)
ALPHA = 0.003          # keep CPU in a plausible unsaturated range
BETA_LOG = np.log(8)   # baseline CPU% at zero load
SIGMA_MULT = 0.20      # per-window multiplicative noise (log space)

# 24 hour-of-day bins with a smooth diurnal load profile (events per hour)
LAMBDA_HOUR = np.concatenate([
    np.linspace(1_500, 25_000, 12),
    np.linspace(25_000, 1_500, 12),
])

RESOLUTIONS = {"5s": 5.0, "5min": 300.0}


def simulate(window_sec, lambda_hour, days=DAYS):
    lam_win = lambda_hour * window_sec / 3600.0
    windows_per_hour = int(3600 / window_sec)
    samples = []
    for _ in range(days * windows_per_hour):
        n = RNG.poisson(lam_win)
        eps = RNG.normal(0, SIGMA_MULT)
        samples.append(ALPHA * n + BETA_LOG + eps)
    return np.array(samples), lam_win


def fit_A(lam, sig):
    """sigma = gamma / sqrt(lam) + delta."""
    x = 1.0 / np.sqrt(lam)
    A = np.vstack([x, np.ones_like(x)]).T
    (g, d), *_ = np.linalg.lstsq(A, sig, rcond=None)
    pred = A @ np.array([g, d])
    ss_res = np.sum((sig - pred) ** 2); ss_tot = np.sum((sig - sig.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return float(g), float(d), float(r2)


def fit_B(lam, sig):
    """sigma = sqrt(alpha^2 * lam + s_mult^2). Fit alpha_hat, s_mult_hat by NLS."""
    def f(l, a, s): return np.sqrt(a * a * l + s * s)
    try:
        popt, _ = curve_fit(f, lam, sig, p0=[0.005, 0.3], maxfev=2000)
        a_hat, s_hat = float(popt[0]), float(popt[1])
        pred = f(lam, a_hat, s_hat)
        ss_res = float(np.sum((sig - pred) ** 2))
        ss_tot = float(np.sum((sig - sig.mean()) ** 2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
        return a_hat, s_hat, float(r2)
    except Exception:
        return float("nan"), float("nan"), float("nan")


def run(label, window_sec):
    lam_win_all, mu_all, sig_all = [], [], []
    for lam_h in LAMBDA_HOUR:
        samples, lw = simulate(window_sec, lam_h)
        lam_win_all.append(lw)
        mu_all.append(float(samples.mean()))
        sig_all.append(float(samples.std()))
    lam = np.array(lam_win_all); mu = np.array(mu_all); sig = np.array(sig_all)
    gA, dA, r2A = fit_A(lam, sig)
    aB, sB, r2B = fit_B(lam, sig)
    return {
        "label": label, "window_sec": window_sec,
        "lam_min": float(lam.min()), "lam_max": float(lam.max()),
        "sig_min": float(sig.min()), "sig_max": float(sig.max()),
        "sig_direction": "increasing" if sig[-1] > sig[0] * 1.1 else
                         "decreasing" if sig[-1] < sig[0] * 0.9 else "flat",
        "formA_paper": {"gamma": gA, "delta": dA, "R2": r2A,
                        "matches_prediction": gA > 0},
        "formB_derivation": {"alpha_hat": aB, "sigma_mult_hat": sB, "R2": r2B,
                              "alpha_true": ALPHA, "sigma_mult_true": SIGMA_MULT},
        "lam_arr": lam.tolist(), "sig_arr": sig.tolist(),
    }


results = {label: run(label, ws) for label, ws in RESOLUTIONS.items()}
with open("clt_sim_summary.json", "w") as f:
    json.dump({k: {kk: v for kk, v in r.items() if kk not in ("lam_arr","sig_arr")}
               for k, r in results.items()}, f, indent=2)

# Plot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(9.8, 3.8))
for ax, (label, r) in zip(axes, results.items()):
    lam = np.array(r["lam_arr"]); sig = np.array(r["sig_arr"])
    ax.scatter(lam, sig, color="#3d65b8", s=34, zorder=3, label="simulated σ")
    xs = np.logspace(np.log10(lam.min()*0.9), np.log10(lam.max()*1.1), 200)
    yA = r["formA_paper"]["gamma"] / np.sqrt(xs) + r["formA_paper"]["delta"]
    ax.plot(xs, yA, color="#c2542c", lw=1.7,
            label=f"Form A: γ={r['formA_paper']['gamma']:.3f}, R²={r['formA_paper']['R2']:.2f}")
    aB = r["formB_derivation"]["alpha_hat"]; sB = r["formB_derivation"]["sigma_mult_hat"]
    yB = np.sqrt(aB * aB * xs + sB * sB)
    ax.plot(xs, yB, color="#0f9268", lw=1.7,
            label=f"Form B: α̂={aB:.4f}, σ_ε̂={sB:.3f}, R²={r['formB_derivation']['R2']:.2f}")
    ax.set_xscale("log")
    ax.set_xlabel("λ (events per window)")
    ax.set_ylabel("σ(log CPU)")
    ax.set_title(f"{label} window: σ {r['sig_direction']} ({r['sig_min']:.2f} → {r['sig_max']:.2f})")
    ax.grid(True, color="#e6e6e3", lw=0.7); ax.set_axisbelow(True)
    for sp in ax.spines.values(): sp.set_color("#dcdcda")
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.legend(fontsize=9, frameon=False, loc="best")
fig.suptitle(
    f"σ(λ) under the multiplicative-overhead mechanism (α={ALPHA}, σ_ε={SIGMA_MULT})",
    fontsize=11, y=1.02,
)
plt.tight_layout()
plt.savefig("clt_sim.png", dpi=180, facecolor="white", bbox_inches="tight")

print(json.dumps({k: {kk: v for kk, v in r.items() if kk not in ("lam_arr","sig_arr")}
                  for k, r in results.items()}, indent=2))
