"""Build Zenodo reproducibility package for cpu-capacity-analysis.

Packages the scoping analysis scripts, per-VM result CSVs, JSON summaries,
diagnostic reports, and the paper (LaTeX + PDF + HTML) into a single
Zenodo-ready set of artifacts under ../zenodo_build/. Raw public traces
(Bitbrains fastStorage/Rnd and Alibaba cluster-trace-v2018) are not
rehosted; retrieval instructions are documented in EXTERNAL_DATA.md.
"""
import argparse, hashlib, zipfile
from pathlib import Path

REPO = Path(r"E:/Projects/Submitted/Amdocs").resolve()
OUT = REPO.parent / "zenodo_build"

# Scripts: reproducibility pipeline
SCRIPTS = [
    "scoping/fit.py", "scoping/fit_rnd.py", "scoping/fit_alibaba.py",
    "scoping/refit_ab_shared.py", "scoping/refit_form_ab.py", "scoping/refit_form_c.py",
    "scoping/scaling_fit.py", "scoping/scaling_diagnose.py", "scoping/sigma_rootcause.py",
    "scoping/sizing_eval.py", "scoping/unified_eval.py", "scoping/ml_baseline.py",
    "scoping/ml_gbm_prophet.py", "scoping/sla_sim.py", "scoping/sla_paired.py",
    "scoping/ad_cvm.py", "scoping/clt_sim.py", "scoping/frontier_claim3.py",
    "scoping/metric_sensitivity.py", "scoping/composite_proxy.py",
    "scoping/alibaba_fano.py",
    "scoping/build_paper_macros.py", "scoping/build_ci_macros.py",
    "scoping/build_ci_macros_v2.py", "scoping/build_final_macros.py",
    "scoping/build_ml_macros.py", "scoping/build_extra_macros.py",
    "scoping/bootstrap_cis.py",
]

# Diagnostic / analysis result CSVs and JSONs that back the paper's tables
RESULTS_JSON = [
    "scoping/bitbrains_summary.json", "scoping/rnd_summary.json",
    "scoping/alibaba_summary.json", "scoping/alibaba_bootstrap.json",
    "scoping/ad_cvm_summary.json", "scoping/scaling_summary.json",
    "scoping/formC_summary.json", "scoping/sizing_summary.json",
    "scoping/ml_summary.json", "scoping/ml_rich_summary.json",
    "scoping/sla_summary.json", "scoping/sla_paired_summary.json",
    "scoping/unified_fastStorage_summary.json", "scoping/unified_rnd_summary.json",
    "scoping/bootstrap_cis.json", "scoping/metric_sensitivity.json",
    "scoping/composite_proxy_summary.json", "scoping/alibaba_fano_summary.json",
    "scoping/frontier_summary.json", "scoping/refit_ab_summary.json",
    "scoping/clt_sim_summary.json",
]

RESULTS_CSV = [
    "scoping/bitbrains_fit_results.csv", "scoping/rnd_fit_results.csv",
    "scoping/alibaba_fit_results.csv",
    "scoping/refit_ab_fastStorage.csv", "scoping/refit_ab_rnd.csv",
    "scoping/formC_fastStorage.csv", "scoping/formC_rnd.csv",
    "scoping/scaling_fastStorage.csv", "scoping/scaling_rnd.csv",
    "scoping/unified_fastStorage.csv", "scoping/unified_rnd.csv",
    "scoping/sizing_fastStorage.csv", "scoping/sizing_rnd.csv",
    "scoping/ml_fastStorage.csv", "scoping/ml_rnd.csv",
    "scoping/sla_fastStorage.csv", "scoping/sla_rnd.csv",
    "scoping/ad_cvm_fastStorage.csv", "scoping/ad_cvm_rnd.csv",
    "scoping/composite_proxy.csv",
]

# Diagnostic reports (markdown)
REPORTS = [
    "scoping/SCALING_DIAGNOSIS.md", "scoping/SIGMA_ROOTCAUSE.md",
    "scoping/CLAIM_REFINEMENTS.md", "scoping/CLAIM2_REFINEMENTS.md",
    "scoping/CLAIM3_REFINEMENTS.md", "scoping/CLAIM4_REFINEMENTS.md",
    "scoping/EDITORIAL_PASS_REPORT.md", "scoping/PE_REVIEWER_REPORT.md",
    "scoping/PE_STRONG_ACCEPT_VERDICT.md", "scoping/BORG_PLAN.md",
    "scoping/README.md",
]

# Paper: LaTeX source + PDF + HTML + macros + figures
PAPER = [
    "paper/paper.tex", "paper/paper.bib", "paper/paper_macros.tex",
    "paper/paper.pdf", "paper/paper.html",
    "paper/fig_best_fit_share.pdf", "paper/fig_refit_ab.pdf",
    "paper/fig_refit_ab.png",
]

EXTERNAL_DATA_MD = """# External data (not included in this deposit)

The paper's empirical results come from three public production traces
that are hosted by their original providers. This deposit does not
rehost them (they are large and covered by their own release terms).
To reproduce the results, retrieve the traces from their canonical
sources:

## Bitbrains GWA-T-12 fastStorage and Rnd

Both traces are part of the Grid Workloads Archive at TU Delft.

- Landing page: https://atlarge-research.com/gwa-t-12/
- Direct downloads:
  - fastStorage: https://atlarge-research.com/gwa-traces/gwa_t_12_fastStorage.zip
  - Rnd:         https://atlarge-research.com/gwa-traces/gwa_t_12_rnd.zip
- Extract each zip; each CSV file inside is one VM's 5-minute-resolution
  trace over 30 days.
- Acknowledgement to Bitbrains IT Services Inc. is required per the
  trace's usage terms.

Point `ROOT_FS` in the scripts (`fit.py`, `unified_eval.py`, etc.) at
the extracted `fastStorage/2013-8` directory and `ROOT_RND` at
`rnd/rnd/2013-8`.

## Alibaba cluster-trace-v2018

Hosted by Alibaba on Aliyun OSS.

- Landing page: https://github.com/alibaba/clusterdata
- Direct download:
  http://clusterdata2018pubcn.oss-cn-beijing.aliyuncs.com/machine_usage.tar.gz
  (1.77 GB, per-machine 10-second CPU/memory/disk/network)
- Optional companion file for the mechanism test:
  http://clusterdata2018pubcn.oss-cn-beijing.aliyuncs.com/container_meta.tar.gz
  (2.5 MB, container arrival events per machine)

Extract and point the script paths in `fit_alibaba.py` and
`alibaba_fano.py` at the extracted CSVs.
"""

READMD = """# Reproducibility Artifact: A Log-Normal Model of Server CPU Utilization

Reproducibility package for the paper *A Log-Normal Model of Server CPU
Utilization Under Transaction Load: Fit, Scaling, and SLA-Aware Sizing*
by Alexander Apartsin (2026).

## Contents

- `code_and_results/` -- scoping/ analysis scripts (Python 3.11+) plus
  per-VM CSVs and JSON summaries that back every table in the paper.
- `paper/` -- LaTeX source, generated PDF, HTML mirror, figures, macros.
- `EXTERNAL_DATA.md` -- retrieval instructions for the three public
  Bitbrains and Alibaba traces (not rehosted).
- `README.md` -- this file.

## How to reproduce

1. Follow `EXTERNAL_DATA.md` to download the three source traces.
2. Update the `ROOT_FS`, `ROOT_RND`, and Alibaba paths at the top of
   each scoping script to point at your local trace directories.
3. Run:
     python scoping/fit.py
     python scoping/fit_rnd.py
     python scoping/fit_alibaba.py
     python scoping/unified_eval.py
     python scoping/bootstrap_cis.py
     python scoping/build_ci_macros_v2.py
     (in the paper/ directory) pdflatex paper && bibtex paper && pdflatex paper && pdflatex paper
4. All numeric macros in `paper/paper_macros.tex` regenerate; all tables
   and figures in the PDF trace back to the JSON summaries in
   `code_and_results/`.

## Dependencies

Python 3.11+, numpy, scipy, pandas, scikit-learn, matplotlib.

## License

MIT. See LICENSE (in the code archive).

## Citation

Cite the paper via its GitHub Pages URL or a venue-specific reference
once accepted. Cite this specific artifact via its Zenodo DOI.
"""

def add_file(zf, path: Path, arc: str):
    if not path.exists():
        print(f"  WARN missing: {path}")
        return
    zf.write(path, arc)

def build():
    OUT.mkdir(exist_ok=True)
    print(f"repo={REPO}\nout={OUT}")

    # README and EXTERNAL_DATA also at top level for browse-ability
    (OUT / "README.md").write_text(READMD, encoding="utf-8")
    (OUT / "EXTERNAL_DATA.md").write_text(EXTERNAL_DATA_MD, encoding="utf-8")

    # Code + results zip (includes README + EXTERNAL_DATA at top of the zip)
    code_zip = OUT / "code_and_results.zip"
    with zipfile.ZipFile(code_zip, "w", zipfile.ZIP_DEFLATED, 6) as zf:
        zf.writestr("code_and_results/README.md", READMD)
        zf.writestr("code_and_results/EXTERNAL_DATA.md", EXTERNAL_DATA_MD)
        for rel in SCRIPTS + RESULTS_JSON + RESULTS_CSV + REPORTS:
            add_file(zf, REPO / rel, f"code_and_results/{rel}")
    # Paper zip
    paper_zip = OUT / "paper.zip"
    with zipfile.ZipFile(paper_zip, "w", zipfile.ZIP_DEFLATED, 6) as zf:
        zf.writestr("paper/README.md", READMD)
        for rel in PAPER:
            add_file(zf, REPO / rel, rel)

    arts = [code_zip, paper_zip]
    def sha256(p):
        import hashlib
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
        return h.hexdigest()
    sums, man = [], []
    for a in arts:
        sums.append(f"{sha256(a)}  {a.name}")
        man.append(f"{a.name:32s} {a.stat().st_size/1e6:9.2f} MB")
    (OUT / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
    (OUT / "MANIFEST.txt").write_text(
        "Zenodo deposit -- cpu-capacity-analysis reproducibility artifact\n"
        + "=" * 66 + "\n" + "\n".join(man) + "\n")
    print("\n".join(man))

if __name__ == "__main__":
    build()
