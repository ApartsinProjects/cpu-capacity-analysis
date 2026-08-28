"""Append ML-baseline numbers to paper/paper_macros.tex."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
PM = os.path.join(HERE, "..", "paper", "paper_macros.tex")
ml = json.load(open(os.path.join(HERE, "ml_summary.json")))

lines = ["", "% --- ML-baseline sizing ---"]
for label, tag in [("fastStorage","Fs"), ("rnd","Rn")]:
    for method, mtag in [("ml_gbm_p998","MLGB"), ("ewmq_p998","EWMQ")]:
        s = ml[label][method]
        lines += [
            f"\\newcommand{{\\Sz{tag}{mtag}MeanCov}}{{{100*s['mean_coverage']:.2f}}}",
            f"\\newcommand{{\\Sz{tag}{mtag}ShareTarget}}{{{100*s['share_at_target']:.1f}}}",
            f"\\newcommand{{\\Sz{tag}{mtag}MedCeiling}}{{{s['median_ceiling_pct']:.2f}}}",
            f"\\newcommand{{\\Sz{tag}{mtag}MedRelCost}}{{{100*s['median_rel_cost']:.1f}}}",
        ]

with open(PM, "a", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("appended", len(lines), "lines")
