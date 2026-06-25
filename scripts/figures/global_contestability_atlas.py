"""
Global contestability atlas (publication plan Item 5).

Turns the contestability screen into a global figure that places the EU result in
a 43-country, multi-continent context and addresses the equity/Global South gap.

Panel A: single-bidder rate across 43 countries (OECD Government at a Glance 2023),
         grouped by world region -- the global contestability landscape.
Panel B: carbon-weighted single-bidder exposure for the 27 systems with carbon
         microdata, = sum_s(value_s * carbon_s * SB_s) / sum_s(value_s * carbon_s),
         i.e. the share of carbon-intensity-weighted public spending that is
         single-sourced. This is the quantity GPP cannot reach.

Outputs: NC_Submission/Main_Figures/Fig5_global_atlas.{pdf,png}
         results/cross_continental/global_atlas_data.json
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
# Atlas is held back from the NC submission (it is the Nature Sustainability lever,
# to be done across many systems in a follow-up). Output goes to a repo deliverable
# location, NOT the submission figures directory.
FIG = ROOT / "results" / "cross_continental" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
RES = ROOT / "results"
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 150})

REGION = {
    "Austria": "OECD Europe", "Belgium": "OECD Europe", "Bulgaria": "OECD Europe",
    "Croatia": "OECD Europe", "Cyprus": "OECD Europe", "Czech Republic": "OECD Europe",
    "Denmark": "OECD Europe", "Estonia": "OECD Europe", "Finland": "OECD Europe",
    "France": "OECD Europe", "Germany": "OECD Europe", "Greece": "OECD Europe",
    "Hungary": "OECD Europe", "Ireland": "OECD Europe", "Italy": "OECD Europe",
    "Latvia": "OECD Europe", "Lithuania": "OECD Europe", "Luxembourg": "OECD Europe",
    "Malta": "OECD Europe", "Netherlands": "OECD Europe", "Poland": "OECD Europe",
    "Portugal": "OECD Europe", "Romania": "OECD Europe", "Slovakia": "OECD Europe",
    "Slovenia": "OECD Europe", "Spain": "OECD Europe", "Sweden": "OECD Europe",
    "Iceland": "OECD Europe", "Norway": "OECD Europe", "Switzerland": "OECD Europe",
    "United Kingdom": "OECD Europe",
    "Australia": "Asia-Pacific", "New Zealand": "Asia-Pacific", "Japan": "Asia-Pacific",
    "Korea": "Asia-Pacific",
    "Canada": "North America", "United States": "North America",
    "Chile": "Latin America", "Colombia": "Latin America", "Mexico": "Latin America",
    "Costa Rica": "Latin America",
    "Turkey": "Other", "Israel": "Other",
}
REGION_COLOR = {"OECD Europe": "#2b6cb0", "North America": "#2f855a",
                "Asia-Pacific": "#b7791f", "Latin America": "#c53030",
                "Other": "#6b46c1"}
ISO = {  # gprd iso -> OECD name for cross-check
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia",
    "CZ": "Czech Republic", "DK": "Denmark", "EE": "Estonia", "FI": "Finland",
    "FR": "France", "DE": "Germany", "GR": "Greece", "HU": "Hungary", "IE": "Ireland",
    "IT": "Italy", "LV": "Latvia", "LT": "Lithuania", "LU": "Luxembourg",
    "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
    "SK": "Slovakia", "SI": "Slovenia", "ES": "Spain", "SE": "Sweden",
    "IS": "Iceland", "NO": "Norway", "CH": "Switzerland", "GB": "United Kingdom",
    "CO": "Colombia",
}


def main():
    gs = json.loads((RES / "cross_continental" / "global_south_procurement.json").read_text())
    oecd = gs["oecd_single_bidder_rates"]

    # Panel B: carbon-weighted single-bidder exposure from microdata
    df = pq.read_table(PARQUET, columns=[
        "country", "cpv_division", "single_bidder", "value_eur",
        "carbon_intensity_kg_usd"]).to_pandas()
    df = df.dropna(subset=["carbon_intensity_kg_usd", "value_eur"])
    df = df[df.value_eur > 0]
    g = df.groupby(["country", "cpv_division"]).agg(
        val=("value_eur", "sum"), carbon=("carbon_intensity_kg_usd", "mean"),
        sb=("single_bidder", "mean")).reset_index()
    g["w"] = g.val * g.carbon
    expo = (g.groupby("country").apply(
        lambda x: np.average(x.sb, weights=x.w), include_groups=False)
        .rename("carbon_weighted_sb").reset_index())
    expo["name"] = expo.country.map(ISO)
    expo = expo.dropna(subset=["name"]).sort_values("carbon_weighted_sb")

    # Merge newly-acquired non-EU systems (streamed via API; method-proxy exposure)
    acq_path = RES / "cross_continental" / "acquired_global_systems.json"
    acquired = {}
    if acq_path.exists():
        for iso, rec in json.loads(acq_path.read_text()).items():
            e = rec.get("carbon_weighted_noncompetitive_exposure")
            if e is not None and rec.get("n_records", 0) >= 200:
                acquired[rec["country"]] = {"exposure": e, "iso": iso,
                                            "n": rec["n_records"],
                                            "proxy": True}

    atlas = {"oecd_sb_rates": oecd,
             "carbon_weighted_sb_exposure": {
                 r["name"]: round(float(r.carbon_weighted_sb), 4)
                 for _, r in expo.iterrows()},
             "acquired_non_eu_systems": acquired}
    (RES / "cross_continental" / "global_atlas_data.json").write_text(
        json.dumps(atlas, indent=2))

    # ---------------- Figure ----------------
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.5, 6.2),
                               gridspec_kw={"width_ratios": [1, 1]})

    # Panel A: 43-country SB rates by region
    rows = sorted(oecd.items(), key=lambda kv: kv[1])
    names = [k for k, _ in rows]
    vals = [v * 100 for _, v in rows]
    cols = [REGION_COLOR.get(REGION.get(n, "Other"), "#6b46c1") for n in names]
    y = np.arange(len(names))
    a.barh(y, vals, color=cols)
    a.set_yticks(y); a.set_yticklabels(names, fontsize=6.2)
    a.set_xlabel("Single-bidder rate (%), OECD GaaG 2023")
    a.set_title("A  Global contestability landscape\n(43 countries, 6 regions)",
                fontsize=9, loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in REGION_COLOR.values()]
    a.legend(handles, REGION_COLOR.keys(), fontsize=6.5, loc="lower right",
             frameon=False)

    # Panel B: carbon-weighted exposure (microdata + newly-acquired non-EU systems)
    names_b = list(expo.name)
    vals_b = list(expo.carbon_weighted_sb * 100)
    proxy = [False] * len(names_b)
    for cname, rec in acquired.items():
        tag = "pilot, " if rec["n"] < 10000 else ""
        names_b.append(f"{cname} ({tag}n={rec['n']:,}) *")
        vals_b.append(rec["exposure"] * 100)
        proxy.append(True)
        REGION.setdefault(cname, "Other")
    order = np.argsort(vals_b)
    names_b = [names_b[i] for i in order]
    vals_b = [vals_b[i] for i in order]
    proxy = [proxy[i] for i in order]
    yb = np.arange(len(names_b))
    colb = [REGION_COLOR.get(REGION.get(n.replace(" *", ""), "Other"), "#6b46c1")
            for n in names_b]
    bars = b.barh(yb, vals_b, color=colb,
                  hatch=["///" if p else "" for p in proxy],
                  edgecolor=["k" if p else "none" for p in proxy], linewidth=0.4)
    b.set_yticks(yb); b.set_yticklabels(names_b, fontsize=6.0)
    b.set_xlabel("Carbon-weighted single-bidder exposure (%)")
    ntot = len(names_b)
    nnew = sum(proxy)
    b.set_title(f"B  Carbon-weighted public spending\nthat is single-sourced ({ntot} systems;\n"
                f"* = {nnew} API-acquired (method proxy))",
                fontsize=9, loc="left")

    fig.suptitle("A global atlas of contestability in carbon-intensive public procurement",
                 fontsize=10.5, y=1.01)
    fig.tight_layout()
    fig.savefig(FIG / "Fig5_global_atlas.pdf", bbox_inches="tight")
    fig.savefig(FIG / "Fig5_global_atlas.png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    print("wrote Fig5_global_atlas")
    print(f"  Panel A: {len(oecd)} countries; Panel B: {len(expo)} microdata systems")
    print("  carbon-weighted SB exposure range: "
          f"{expo.carbon_weighted_sb.min()*100:.1f}%-{expo.carbon_weighted_sb.max()*100:.1f}%")


if __name__ == "__main__":
    main()
