"""Append A-D/CvM and SLA-simulation numbers to paper/paper_macros.tex."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
PAPER_MACROS = os.path.join(HERE, "..", "paper", "paper_macros.tex")

adcvm = json.load(open(os.path.join(HERE, "ad_cvm_summary.json")))
sla   = json.load(open(os.path.join(HERE, "sla_summary.json")))

lines = ["", "% --- A-D and CvM tests ---"]
for label, tag in [("fastStorage", "Fs"), ("rnd", "Rn")]:
    a = adcvm[label]
    for stat, stag in [("ks", "KS"), ("cvm", "Cvm"), ("ad", "Ad")]:
        med = a[f"{stat}_median"]
        lines += [
            f"\\newcommand{{\\{tag}{stag}MedLN}}{{{med['lognorm']:.2f}}}",
            f"\\newcommand{{\\{tag}{stag}MedNo}}{{{med['norm']:.2f}}}",
            f"\\newcommand{{\\{tag}{stag}MedGa}}{{{med['gamma']:.2f}}}",
            f"\\newcommand{{\\{tag}{stag}MedWe}}{{{med['weibull_min']:.2f}}}",
            f"\\newcommand{{\\{tag}{stag}ShareLN}}{{{100*a[f'{stat}_share_lognorm_best']:.1f}}}",
        ]

lines += ["", "% --- SLA simulation ---"]
for label, tag in [("fastStorage", "Fs"), ("rnd", "Rn")]:
    for method, mtag in [("lognorm_ctop","LN"), ("empirical_p998","EP"),
                          ("gauss_meanksd","GA"), ("rolling_max","RM")]:
        s = sla[label][method]
        for prov in ["AWS", "GCP", "Azure"]:
            lines += [
                f"\\newcommand{{\\Sla{tag}{mtag}{prov}Credit}}{{{100*s[f'mean_credit_{prov}']:.2f}}}",
                f"\\newcommand{{\\Sla{tag}{mtag}{prov}Net}}{{{100*s[f'mean_net_revenue_ratio_{prov}']:.2f}}}",
            ]
        lines += [
            f"\\newcommand{{\\Sla{tag}{mtag}Avail}}{{{100*s['mean_availability']:.3f}}}",
            f"\\newcommand{{\\Sla{tag}{mtag}ShareNinetyNine}}{{{100*s['share_ge_99']:.1f}}}",
        ]

with open(PAPER_MACROS, "a", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("appended", len(lines), "lines")
