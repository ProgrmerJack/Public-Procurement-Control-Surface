"""
Rebuild the four main figures to match the audit-consistent manuscript
(publication plan Item 7). Figures visualise the surviving / honest results:

  Fig1  A: carbon premium vs Rule of Law (governance gradient REFUTED, rho=+0.33)
        B: premium under a fixed-effects ladder with cluster-robust t (Moulton)
  Fig2  A: Dead Zone contestability screen (carbon x single-bidder, bubble=value)
        B: coverage-stable not-yet-treated DiD effect range
  Fig3  A: E-PRTR absolute vs size-stratified premium (gap collapses)
        B: buyer-type RDD at real vs placebo cutoffs (no clean discontinuity)
  Fig4  A: country single-bidder rate change pre vs post reform
        B: reproduction of the DiD range with permutation p-values
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
FIG.mkdir(parents=True, exist_ok=True)
RES = ROOT / "results"
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"

plt.rcParams.update({"font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 150})
BLUE, RED, GREY = "#2b6cb0", "#c53030", "#718096"


def load(p):
    return json.loads((RES / p).read_text())


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    print("wrote", name)


# ---------------- Fig 1 ----------------
def fig1():
    gov = load("audit/falsifiable_governance_test.json")
    mou = load("audit/premium_country_fe_moulton.json")
    d = pd.DataFrame(gov["country_table"])
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.2, 3.6))
    a.scatter(d["rol"], d["premium_pct"], s=22, color=BLUE, zorder=3)
    m, c = np.polyfit(d["rol"], d["premium_pct"], 1)
    xs = np.linspace(d["rol"].min(), d["rol"].max(), 50)
    a.plot(xs, m * xs + c, color=RED, lw=1.5)
    a.axhline(0, color=GREY, lw=0.8, ls="--")
    a.set_xlabel("WGI Rule of Law (2018)")
    a.set_ylabel("Single-bidder carbon premium (%)")
    a.set_title(f"A  Governance gradient refuted\n"
                f"Spearman $\\rho$=+{gov['spearman_rho']:.2f} "
                f"(predicted <0; one-sided p={gov['spearman_p_one_sided_negative']:.2f})",
                fontsize=8.5, loc="left")

    order = ["M0_pooled_no_FE", "M1_country_FE", "M2_country_year_FE",
             "M3_country_cpv_FE_within_sector"]
    labels = ["pooled", "+country FE", "+country×year FE", "+country×CPV FE"]
    prem = [mou["models"][k]["premium_pct"] for k in order]
    tcl = [mou["models"][k]["t_cluster"] for k in order]
    y = np.arange(len(order))[::-1]
    cols = [RED if abs(t) < 1.96 else BLUE for t in tcl]
    b.barh(y, prem, color=cols)
    for yi, p, t in zip(y, prem, tcl):
        if p < -0.2:
            b.text(p + 0.12, yi, f"{p:+.1f}%  (t={t:+.1f})", va="center",
                   ha="left", fontsize=7.5, color="white")
        else:
            b.text(0.12, yi, f"{p:+.1f}%  (t={t:+.1f})", va="center",
                   ha="left", fontsize=7.5)
    b.set_yticks(y); b.set_yticklabels(labels)
    b.axvline(0, color=GREY, lw=0.8)
    b.set_xlim(-5.6, 1.6)
    b.set_xlabel("EU premium (%), cluster-robust at country×CPV")
    b.set_title("B  Premium under FE ladder\n(red = not significant; within-sector = 0)",
                fontsize=8.5, loc="left")
    save(fig, "Fig3_premium_governance")


# ---------------- Fig 2 ----------------
def fig2():
    did = load("causal_id/did_coverage_stable_nyt.json")
    df = pq.read_table(PARQUET, columns=[
        "country", "cpv_division", "single_bidder", "carbon_intensity_kg_usd",
        "value_eur"]).to_pandas()
    df = df[df.country != "CO"]
    g = df.groupby("cpv_division").agg(
        carbon=("carbon_intensity_kg_usd", "mean"),
        sb=("single_bidder", "mean"),
        val=("value_eur", "sum")).reset_index()
    g = g[g.val > 0]
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.2, 3.6))
    a.scatter(g.carbon, g.sb * 100, s=np.sqrt(g.val) / 3e3,
              color=BLUE, alpha=0.45, edgecolor="k", lw=0.3)
    a.axvline(0.25, color=GREY, ls="--", lw=0.8)
    a.axhline(7.4, color=GREY, ls="--", lw=0.8)
    a.set_xlabel("Sector carbon intensity (kg CO$_2$e/USD)")
    a.set_ylabel("Single-bidder rate (%)")
    a.set_title("A  Dead Zone contestability screen\n(upper-right = high carbon × weak choice)",
                fontsize=8.5, loc="left")

    panels = did["panels"]
    names = ["full_universe", "coverage_stable_observed_bidders"]
    labs = ["full universe", "coverage-stable"]
    atts = [panels[n]["aggregate_att_pp"] for n in names]
    ps = [panels[n]["permutation_p"] for n in names]
    x = np.arange(len(names))
    b.bar(x, atts, color=[GREY, BLUE], width=0.5)
    for xi, at, p in zip(x, atts, ps):
        b.text(xi, at - 0.6, f"{at:.1f} pp\nperm p={p:.3f}", ha="center", va="top",
               fontsize=8)
    b.axhline(0, color="k", lw=0.8)
    b.set_xticks(x); b.set_xticklabels(labs)
    b.set_ylabel("Not-yet-treated ATT (pp)")
    b.set_title("B  Reform effect on single-bidding\n(robust sign, imprecise magnitude; 3 cells)",
                fontsize=8.5, loc="left")
    save(fig, "Fig1_screen_did")


# ---------------- Fig 3 ----------------
def fig3():
    ep = load("within_sector/eprtr_size_stratified_intensity.json")
    rd = load("rdd/rdd_buyer_type_year_specific.json")
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.2, 3.6))
    vals = [ep["absolute_premium"]["premium_pct"],
            ep["within_emission_decile"]["weighted_premium_pct"],
            ep["within_sector_x_decile"]["weighted_premium_pct"]]
    labs = ["absolute\n(size-confounded)", "within\nemission decile",
            "within\nsector×decile"]
    a.bar(range(3), vals, color=[RED, BLUE, BLUE])
    for i, v in enumerate(vals):
        a.text(i, v + 3, f"{v:+.0f}%", ha="center", fontsize=8)
    a.axhline(0, color="k", lw=0.8)
    a.set_xticks(range(3)); a.set_xticklabels(labs, fontsize=8)
    a.set_ylabel("SB vs MB facility CO$_2$ premium (%)")
    a.set_title("A  E-PRTR: gap is a size artifact\n(+150% collapses to ~0 within size strata)",
                fontsize=8.5, loc="left")

    est = rd["estimates"]
    keys = [k for k in est if not est[k].get("insufficient")]
    short = {"central_at_CENTRAL_cutoff (predicted: jump)": "central @\ncentral*",
             "central_at_SUBCENTRAL_cutoff (placebo: null)": "central @\nsub (placebo)",
             "subcentral_at_SUBCENTRAL_cutoff (predicted: jump)": "sub @\nsub*",
             "subcentral_at_CENTRAL_cutoff (placebo: null)": "sub @\ncentral (placebo)"}
    taus = [est[k]["mse_optimal"]["tau"] for k in keys]
    ps = [est[k]["mse_optimal"]["p_value"] for k in keys]
    cols = [BLUE if "predicted" in k else RED for k in keys]
    x = np.arange(len(keys))
    b.bar(x, taus, color=cols)
    for xi, tt, p in zip(x, taus, ps):
        b.text(xi, tt + (0.04 if tt >= 0 else -0.04), f"p={p:.2g}",
               ha="center", va="bottom" if tt >= 0 else "top", fontsize=7)
    b.axhline(0, color="k", lw=0.8)
    b.set_xticks(x); b.set_xticklabels([short[k] for k in keys], fontsize=7)
    b.set_ylabel("RDD bidder-count $\\hat{\\tau}$ (MSE bw)")
    b.set_title("B  Threshold RDD fails\n(* = real cutoff; placebos also significant, wrong signs)",
                fontsize=8.5, loc="left")
    save(fig, "Fig4_negative_results")


# ---------------- Fig 4 ----------------
def fig4():
    did = load("causal_id/did_coverage_stable_nyt.json")
    cmap = did["cohort_map"]
    df = pq.read_table(PARQUET, columns=[
        "country", "year", "single_bidder", "n_bidders"]).to_pandas()
    df["year"] = df["year"].astype("Int64")
    df = df[df.country.isin(cmap.keys()) & df.n_bidders.notna()]
    df["sb"] = (df.n_bidders == 1)
    rows = []
    for c, g in df.groupby("country"):
        coh = cmap[c]
        pre = g[g.year < coh]["sb"].mean()
        post = g[g.year >= coh]["sb"].mean()
        if pd.notna(pre) and pd.notna(post):
            rows.append((c, (post - pre) * 100))
    r = pd.DataFrame(rows, columns=["country", "chg"]).sort_values("chg")
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.2, 4.0),
                               gridspec_kw={"width_ratios": [2, 1]})
    cols = [RED if v > 0 else BLUE for v in r.chg]
    a.barh(range(len(r)), r.chg, color=cols)
    a.set_yticks(range(len(r))); a.set_yticklabels(r.country, fontsize=6.5)
    a.axvline(0, color="k", lw=0.8)
    a.set_xlabel("Δ single-bidder rate, post − pre (pp)")
    a.set_title("A  Country SB-rate change\n(coverage-stable; Norway=2017)",
                fontsize=8.5, loc="left")

    p = did["panels"]
    names = ["full_universe", "coverage_stable_observed_bidders"]
    atts = [p[n]["aggregate_att_pp"] for n in names]
    perms = [p[n]["permutation_p"] for n in names]
    nullmu = [p[n]["permutation_null_mean"] for n in names]
    nullsd = [p[n]["permutation_null_sd"] for n in names]
    y = [1, 0]
    for yi, at, pm, mu, sd in zip(y, atts, perms, nullmu, nullsd):
        b.errorbar(mu, yi, xerr=sd, fmt="o", color=GREY, capsize=3)
        b.scatter([at], [yi], color=BLUE, zorder=5)
        b.text(at, yi + 0.12, f"{at:.0f} pp\np={pm:.3f}", ha="center", fontsize=7.5)
    b.axvline(0, color="k", lw=0.8)
    b.set_yticks([0, 1]); b.set_yticklabels(["coverage-\nstable", "full"], fontsize=7.5)
    b.set_ylim(-0.5, 1.6)
    b.set_xlabel("ATT vs permutation null (pp)")
    b.set_title("B  Effect vs timing-\npermutation null", fontsize=8.5, loc="left")
    save(fig, "Fig2_country_permutation")


if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4()
    print("All figures rebuilt ->", FIG)
