"""Append parameter-scaling and sizing-eval numbers to paper/paper_macros.tex."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_MACROS = os.path.join(HERE, "..", "paper", "paper_macros.tex")

with open(os.path.join(HERE, "scaling_summary.json")) as f: scaling = json.load(f)
with open(os.path.join(HERE, "sizing_summary.json")) as f: sizing = json.load(f)

lines = ["", "% --- scaling ---"]
for label, tag in [("fastStorage","Fs"), ("rnd","Rn")]:
    s = scaling[label]
    lines += [
        f"\\newcommand{{\\Scal{tag}NVms}}{{{s['n_vms']}}}",
        f"\\newcommand{{\\Scal{tag}MuMedR}}{{{s['mu_r2']['median']:.2f}}}",
        f"\\newcommand{{\\Scal{tag}MuShareHalf}}{{{100*s['mu_r2']['share_ge_0.5']:.1f}}}",
        f"\\newcommand{{\\Scal{tag}SigMedR}}{{{s['sigma_r2']['median']:.2f}}}",
        f"\\newcommand{{\\Scal{tag}SigShareHalf}}{{{100*s['sigma_r2']['share_ge_0.5']:.1f}}}",
        f"\\newcommand{{\\Scal{tag}AlphaMed}}{{{s['alpha_median']:.4f}}}",
        f"\\newcommand{{\\Scal{tag}GammaMed}}{{{s['gamma_median']:.3f}}}",
    ]

lines += ["", "% --- sizing eval (Rnd trace, held-out last 6 days) ---"]
r = sizing["rnd"]
for method, tag in [("lognorm_ctop","LN"), ("empirical_p998","EP"),
                    ("gauss_meanksd","GA"), ("rolling_max","RM")]:
    m = r[method]
    lines += [
        f"\\newcommand{{\\Sz{tag}MeanCov}}{{{100*m['mean_coverage']:.2f}}}",
        f"\\newcommand{{\\Sz{tag}ShareTarget}}{{{100*m['share_at_target']:.1f}}}",
        f"\\newcommand{{\\Sz{tag}MedCeiling}}{{{m['median_ceiling_pct']:.2f}}}",
        f"\\newcommand{{\\Sz{tag}MedRelCost}}{{{100*m['median_rel_cost']:.1f}}}",
    ]
# also fastStorage
lines += ["", "% --- sizing eval (fastStorage) ---"]
r = sizing["fastStorage"]
for method, tag in [("lognorm_ctop","LN"), ("empirical_p998","EP"),
                    ("gauss_meanksd","GA"), ("rolling_max","RM")]:
    m = r[method]
    lines += [
        f"\\newcommand{{\\SzFs{tag}MeanCov}}{{{100*m['mean_coverage']:.2f}}}",
        f"\\newcommand{{\\SzFs{tag}ShareTarget}}{{{100*m['share_at_target']:.1f}}}",
        f"\\newcommand{{\\SzFs{tag}MedCeiling}}{{{m['median_ceiling_pct']:.2f}}}",
        f"\\newcommand{{\\SzFs{tag}MedRelCost}}{{{100*m['median_rel_cost']:.1f}}}",
    ]

with open(PAPER_MACROS, "a", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("appended", len(lines), "lines to", PAPER_MACROS)
