"""
OUTSIDE-THE-BOX test of the thesis's ultimate environmental claim:
does UNCONTESTED high-carbon public procurement predict SLOWER real-world decarbonization?

Static result so far: uncontested high-carbon markets contain dirtier winners. The missing
environmental link is to an OUTCOME. Here we test, at country x NACE-section level, whether
sectors with more single-bidding in public procurement decarbonised more slowly over 2012-2021,
using Eurostat air-emission accounts (GHG) and gross value added (emission intensity = GHG/GVA).

Design: decarbonization rate = OLS slope of log(GHG/GVA) on year, per country x NACE section.
Predictor: procurement single-bidder rate in that country x sector (CPV->NACE crosswalk).
Test: slope ~ single_bidder_rate, NACE-section FE (+ country FE), restricted to the carbon-
relevant productive sectors. Positive coefficient = more single-bidding -> slower decarbonization.

HONEST CAVEATS built in: ecological/correlational; public procurement is a minority of any
sector's output, so the expected signal is dilute; reverse causation and confounders unaddressed.

Output: results/outcomes/competition_vs_decarbonization.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[2]
AEA = ROOT / "Data" / "raw" / "eurostat_aea_ghg_by_nace_country_year.csv"
GVA = ROOT / "Data" / "raw" / "eurostat_gva_by_nace_country_year.csv"
CARBON = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "outcomes" / "competition_vs_decarbonization.json"

# CPV 2-digit division -> NACE section (carbon-relevant productive sectors)
CPV_NACE = {
    "03": "A", "09": "B", "14": "B", "15": "C", "16": "C", "18": "C", "19": "C",
    "22": "C", "24": "C", "30": "C", "31": "C", "32": "C", "33": "C", "34": "C",
    "35": "C", "37": "C", "38": "C", "39": "C", "41": "E", "42": "C", "43": "C",
    "44": "C", "45": "F", "48": "J", "50": "C", "60": "H", "63": "H", "64": "H",
    "65": "D", "71": "M", "72": "J", "73": "M", "77": "A", "90": "E", "92": "R",
}
# sectors where emission intensity & decarbonization are meaningful (exclude pure services)
CARBON_NACE = ["A", "B", "C", "D", "E", "F", "H"]


def slope(g):
    g = g.dropna(subset=["lint"])
    if len(g) < 5:
        return np.nan
    x = g["year"].values.astype(float)
    y = g["lint"].values
    return float(np.polyfit(x - x.mean(), y, 1)[0])


def main():
    ghg = pd.read_csv(AEA); gva = pd.read_csv(GVA)
    m = ghg.merge(gva, on=["country", "nace", "year"])
    m = m[(m["year"].between(2012, 2021)) & (m["ghg_tht"] > 0) & (m["gva_meur"] > 0)].copy()
    m["lint"] = np.log(m["ghg_tht"] / m["gva_meur"])          # log emission intensity
    dec = (m.groupby(["country", "nace"]).apply(slope, include_groups=False)
             .rename("decarb_slope").reset_index().dropna())
    # negative slope = decarbonising; we will predict the slope itself

    # procurement single-bidder rate by country x NACE (CPV->NACE)
    df = pq.read_table(CARBON, columns=["country", "cpv_division", "single_bidder"]).to_pandas()
    df = df[df["country"] != "CO"].dropna(subset=["single_bidder"])
    df["nace"] = df["cpv_division"].astype(str).map(CPV_NACE)
    df = df.dropna(subset=["nace"])
    proc = (df.groupby(["country", "nace"])
              .agg(sb_rate=("single_bidder", "mean"), n=("single_bidder", "size")).reset_index())
    proc = proc[proc["n"] >= 200]

    d = dec.merge(proc, on=["country", "nace"], how="inner")
    d = d[d["nace"].isin(CARBON_NACE)].copy()
    res = {"n_country_sector_cells": int(len(d)), "n_countries": int(d["country"].nunique()),
           "n_sectors": int(d["nace"].nunique()),
           "hypothesis": "more single-bidding -> slower decarbonization (less negative slope -> positive coef)"}

    # regressions: decarb_slope ~ sb_rate (+ FE), weighted by procurement volume
    def fit(formula):
        return smf.wls(formula, data=d, weights=np.log(d["n"])).fit(
            cov_type="cluster", cov_kwds={"groups": d["country"]})
    mA = fit("decarb_slope ~ sb_rate")
    mB = fit("decarb_slope ~ sb_rate + C(nace)")
    mC = fit("decarb_slope ~ sb_rate + C(nace) + C(country)")
    for name, mm in [("bivariate", mA), ("sector_FE", mB), ("sector_country_FE", mC)]:
        res[name] = {"sb_coef": float(mm.params["sb_rate"]), "se": float(mm.bse["sb_rate"]),
                     "p": float(mm.pvalues["sb_rate"]), "r2": float(mm.rsquared)}
    # also a simple spearman of sb_rate vs slope
    from scipy import stats
    rho, p = stats.spearmanr(d["sb_rate"], d["decarb_slope"])
    res["spearman_sb_vs_slope"] = {"rho": float(rho), "p": float(p)}
    res["mean_decarb_slope"] = float(d["decarb_slope"].mean())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"cells={res['n_country_sector_cells']} ({res['n_countries']} countries x {res['n_sectors']} sectors)")
    print(f"mean decarbonization slope = {res['mean_decarb_slope']:+.4f}/yr (neg = decarbonising)")
    for name in ["bivariate", "sector_FE", "sector_country_FE"]:
        r = res[name]
        print(f"  {name:18s}: sb_rate coef = {r['sb_coef']:+.4f} (SE {r['se']:.4f}, p={r['p']:.3f})")
    print(f"  spearman sb vs slope: rho={res['spearman_sb_vs_slope']['rho']:+.3f} (p={res['spearman_sb_vs_slope']['p']:.3f})")
    print(f"  [positive coef/rho = more single-bidding predicts SLOWER decarbonization]")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
