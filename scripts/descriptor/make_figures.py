"""Validation figures for the Scientific Data descriptor."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "Scientific_Data_Descriptor"
RESD = ROOT / "results" / "descriptor"
FIG = PAPER / "figures"
FIG.mkdir(exist_ok=True)
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})
BLUE, RED, GREY, GREEN = "#2b6cb0", "#c53030", "#718096", "#2f855a"


def fig1():
    """All values reproduced by build_partA_panel.py / partA_validation.json."""
    val = json.loads((RESD / "partA_validation.json").read_text())
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.4, 3.6))
    # (A) single-bidder rate by year: depressed full field vs observed-bidder vs benchmark
    ey = [2015, 2016, 2017, 2018, 2019, 2020]
    full = [val["extract_full_field_single_bidder_by_year"][str(y)] for y in ey]
    obs = [val["extract_observed_single_bidder_by_year"][str(y)] for y in ey]
    a.plot(ey, [x*100 for x in full], "o-", color=RED, label="naive full single-bidder field")
    a.plot(ey, [x*100 for x in obs], "s-", color=BLUE, label="observed-bidder rate (rebuild)")
    a.axhline(29, color=GREY, ls="--", lw=1, label="official EU benchmark (~29%)")
    a.set_ylabel("Single-bidder rate (%)"); a.set_xlabel("Year"); a.set_ylim(0, 40)
    a.set_title("A  Observed-bidder rate (~30%) matches the benchmark;\nthe naive field is depressed (~18%) and falls",
                fontsize=8.5, loc="left")
    a.legend(fontsize=7, frameon=False, loc="lower left")
    # (B) the 2018 ingestion artifact: processed-extract rows / official CAN by year
    yrs = [2016, 2017, 2018, 2019, 2020]
    official = {2016: 104018, 2017: 202671, 2018: 232989, 2019: 260240, 2020: 263114}
    extract_rows = {2016: 506762, 2017: 762360, 2018: 5793300, 2019: 983068, 2020: 994896}
    ratio = [extract_rows[y] / official[y] for y in yrs]
    cols = [GREY if y != 2018 else RED for y in yrs]
    x = np.arange(len(yrs))
    b.bar(x, ratio, 0.6, color=cols)
    for xi, r in zip(x, ratio):
        b.text(xi, r + 0.4, f"{r:.1f}×", ha="center", fontsize=7.5)
    b.set_xticks(x); b.set_xticklabels([str(y) for y in yrs])
    b.set_ylabel("Processed-extract rows ÷ official CAN notices")
    b.set_ylim(0, 28)
    b.set_title("B  The 2018 extract vintage is a 24.9× ingestion artifact\n(absent from the raw-source rebuild)",
                fontsize=8.5, loc="left")
    fig.tight_layout(); fig.savefig(FIG / "fig1_partA_validation.pdf", bbox_inches="tight")
    fig.savefig(FIG / "fig1_partA_validation.png", bbox_inches="tight", dpi=150); plt.close(fig)
    print("wrote fig1")


def fig2():
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.4, 3.6))
    # (A) carbon validation scatter
    tab = json.loads((ROOT / "results" / "within_sector" / "exiobase_eurostat_validation_v2.json").read_text())["table"]
    pw = np.array([t["paper_weight"] for t in tab]); em = np.array([t["eurostat_measured"] for t in tab])
    a.scatter(pw, em, s=22, color=GREEN, alpha=0.7, edgecolor="k", lw=0.3)
    a.set_xscale("log"); a.set_yscale("log")
    a.set_xlabel("EXIOBASE sector weight (kg CO$_2$e/USD)")
    a.set_ylabel("Eurostat measured intensity (kg/€ GVA)")
    a.set_title("A  Carbon weights track measured Eurostat intensities\n(34 sectors, Spearman ρ = 0.82)",
                fontsize=8.5, loc="left")
    # (B) eForms within-tender green-wins forest (overall null + caveated high-carbon)
    rows = [("Overall (2,601 tenders)", 1.02, 0.94, 1.12, BLUE),
            ("High-carbon subset", 1.22, 1.04, 1.43, GREY),
            ("  → reweighted to pop.", 0.95, 0.75, 1.20, GREY),
            ("  → placebo FPR ~30%", None, None, None, RED)]
    y = np.arange(len(rows))[::-1]
    for yi, (lab, orr, lo, hi, c) in zip(y, rows):
        if orr is None:
            continue
        b.plot([lo, hi], [yi, yi], color=c, lw=2)
        b.plot(orr, yi, "o", color=c, ms=6)
    b.axvline(1.0, color="k", lw=0.8, ls=":")
    b.set_yticks(y); b.set_yticklabels([r[0] for r in rows], fontsize=7.5)
    b.set_xlabel("Within-tender odds ratio of winning (greener bidder)")
    b.set_title("B  eForms full-bid-set: competition is green-neutral overall\n(high-carbon signal not robust)",
                fontsize=8.5, loc="left")
    b.set_xlim(0.6, 1.6)
    fig.tight_layout(); fig.savefig(FIG / "fig2_carbon_and_eforms.pdf", bbox_inches="tight")
    fig.savefig(FIG / "fig2_carbon_and_eforms.png", bbox_inches="tight", dpi=150); plt.close(fig)
    print("wrote fig2")


if __name__ == "__main__":
    fig1(); fig2()
