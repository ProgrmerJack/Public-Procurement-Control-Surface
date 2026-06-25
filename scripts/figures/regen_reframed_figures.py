"""Regenerate the two figures invalidated by the DiD non-replication so no figure
displays a withdrawn result.
  Fig1_screen_did.pdf : (A) Dead Zone contestability screen  (B) DiD non-replication
                        (processed-extract -17/-9 pp vs raw-rebuilt canonical +10/+9.4 pp)
  Fig2_firm_emissions.pdf : firm-level emissions -- (A) high- vs low-single-bidder
                        median CO2 (EUTL)  (B) within-sector size-controlled partial rho
                        (EUTL & E-PRTR), the surviving firm-level contribution.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "NC_Submission" / "Main_Figures"
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
RES = ROOT / "results"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150})
BLUE, RED, GREY, GREEN = "#2b6cb0", "#c53030", "#718096", "#2f855a"


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    print("wrote", name)


def fig1():
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.4, 3.7))
    # (A) Dead Zone screen
    df = pq.read_table(PARQUET, columns=["country", "cpv_division", "single_bidder",
                                         "carbon_intensity_kg_usd", "value_eur"]).to_pandas()
    df = df[df.country != "CO"]
    g = df.groupby("cpv_division").agg(carbon=("carbon_intensity_kg_usd", "mean"),
                                       sb=("single_bidder", "mean"),
                                       val=("value_eur", "sum")).reset_index()
    g = g[g.val > 0]
    a.scatter(g.carbon, g.sb * 100, s=np.sqrt(g.val) / 3e3, color=BLUE, alpha=0.45,
              edgecolor="k", lw=0.3)
    a.axvline(0.25, color=GREY, ls="--", lw=0.8); a.axhline(7.4, color=GREY, ls="--", lw=0.8)
    a.set_xlabel("Sector carbon intensity (kg CO$_2$e/USD)")
    a.set_ylabel("Single-bidder rate (%)")
    a.set_title("A  Decarbonization Dead Zone screen\n(upper-right = high carbon × weak choice)",
                fontsize=8.5, loc="left")
    # (B) non-replication: extract (withdrawn) vs raw-TED rebuild (noisy null)
    labels = ["processed\nextract\n(coverage-stable)", "processed\nextract\n(full)",
              "raw-TED rebuild\n2015--2020 (R did)"]
    atts = [-17.0, -9.0, -4.35]
    los = [None, None, -14.34]; his = [None, None, 5.64]
    cols = [GREY, GREY, BLUE]
    x = np.arange(3)
    b.bar(x, atts, color=cols, width=0.55)
    b.errorbar(x[2], atts[2], yerr=[[atts[2]-los[2]], [his[2]-atts[2]]],
               fmt="none", ecolor="k", capsize=3, lw=1)
    b.axhline(0, color="k", lw=0.8)
    b.set_xticks(x); b.set_xticklabels(labels, fontsize=6.8)
    b.set_ylabel("ATT on single-bidder rate (pp)")
    b.set_title("B  Reform effect does NOT replicate\n(extract -17 pp withdrawn; rebuilt = noisy null)",
                fontsize=8.5, loc="left")
    b.text(0.5, -15.5, "withdrawn\n(extract artifact)", color=GREY, fontsize=6.8, ha="center", style="italic")
    b.text(2, 7.2, "null (CI spans 0)", color=BLUE, fontsize=7, ha="center")
    save(fig, "Fig1_screen_did")


def fig2():
    eutl = json.loads((RES / "within_sector/eutl_supplier_firm_match.json").read_text())
    eprtr = json.loads((RES / "within_sector/eprtr_supplier_firm_match.json").read_text())
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.0, 3.7))
    # (A) high vs low SB-propensity median emissions (EUTL)
    hi = eutl["emis_by_sb_propensity"]["high_sb_median_emis_t"]
    lo = eutl["emis_by_sb_propensity"]["low_sb_median_emis_t"]
    a.bar([0, 1], [lo, hi], color=[BLUE, RED], width=0.55)
    for xi, v in zip([0, 1], [lo, hi]):
        a.text(xi, v + 600, f"{v:,.0f} t", ha="center", fontsize=8)
    a.set_xticks([0, 1]); a.set_xticklabels(["low single-\nbidder firms", "high single-\nbidder firms"])
    a.set_ylabel("Median verified CO$_2$ (t/yr)")
    a.set_title("A  Single-bidder-leaning suppliers emit more\n(EU ETS, 1,105 matched firms; +70%)",
                fontsize=8.5, loc="left")
    # (B) within-sector size-controlled partial rho, two registries
    r1 = eutl["within_nace_partial_corr_size_controlled"]["partial_rho"]
    r2 = eprtr["within_sector_size_controlled"]["partial_rho"]
    b.bar([0, 1], [r1, r2], color=GREEN, width=0.5)
    for xi, v, p in zip([0, 1], [r1, r2], ["p<10$^{-5}$", "p=0.02"]):
        b.text(xi, v + 0.006, f"{v:+.2f}\n{p}", ha="center", fontsize=7.5)
    b.axhline(0, color="k", lw=0.8)
    b.set_xticks([0, 1]); b.set_xticklabels(["EU ETS\n(EUTL)", "E-PRTR\nfacilities"])
    b.set_ylabel("Within-sector partial $\\rho$\n(single-bidder rate vs CO$_2$ | firm size)")
    b.set_ylim(0, max(r1, r2) * 1.4)
    b.set_title("B  Holds within sector & size class\n(two independent registries)",
                fontsize=8.5, loc="left")
    save(fig, "Fig2_firm_emissions")


if __name__ == "__main__":
    fig1(); fig2()
    print("regenerated reframed figures ->", FIG)
