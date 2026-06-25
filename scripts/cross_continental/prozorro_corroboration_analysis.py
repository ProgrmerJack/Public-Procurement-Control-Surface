"""
ProZorro (Ukraine) descriptive corroboration: does the carbon x weak-competition
pattern hold in a non-EU, transition-economy system?

Competition proxy = procurement METHOD (as in the manuscript's Canada analysis):
  non-competitive (single-source) := procurementMethodType in
     {reporting, negotiation, negotiation.quick}
  competitive := e-auction / open procedures (belowThreshold, aboveThreshold*, open, ...)
Outcome per CPV division: non-competitive-method rate. Carbon weight: existing
CPV->EXIOBASE crosswalk intensities. We report Spearman(carbon, non-competitive rate)
across divisions with adequate support, mirroring the US (r=0.555) and Australia
cross-context points. Strictly descriptive (method proxy, not bid counts; cross-section).

Input:  Data/processed/prozorro_corroboration_raw.json
Output: results/cross_continental/prozorro_corroboration.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "Data" / "processed" / "prozorro_corroboration_raw.json"
XWALK = ROOT / "Data" / "reference" / "cpv_exiobase_crosswalk.csv"
OUT = ROOT / "results" / "cross_continental" / "prozorro_corroboration.json"

NONCOMP = {"reporting", "negotiation", "negotiation.quick"}
MIN_PER_DIV = 30          # min tenders for a division to enter the correlation

# EXIOBASE shorthand -> classification-weight intensity (same scale as the parquet)
INTENSITY = {
    "Agriculture": 0.85, "Coke and refined petroleum products": 1.20, "Mining": 1.20,
    "Food products": 0.65, "Textiles": 0.45, "Leather": 0.40, "Paper": 0.55,
    "Chemicals": 0.90, "Computer equipment": 0.30, "Electrical equipment": 0.40,
    "Telecommunications": 0.15, "Medical instruments": 0.30, "Motor vehicles": 0.45,
    "Weapons": 0.60, "Precision instruments": 0.28, "Furniture": 0.30,
    "Machinery": 0.35, "Mining machinery": 0.30, "Metal products": 0.75,
    "Construction": 0.50, "Computer services": 0.10, "Repair services": 0.20,
    "Hotels": 0.35, "Land transport": 0.85, "Transport support": 0.45, "Post": 0.20,
    "Utilities": 0.60, "Financial services": 0.08, "Real estate": 0.12,
    "Architectural services": 0.12, "R&D": 0.12, "Public administration": 0.20,
    "Other business services": 0.15, "Education": 0.15, "Health services": 0.25,
    "Waste management and sewerage": 0.55, "Recreation": 0.20, "Other services": 0.20,
}


def main():
    rows = json.loads(RAW.read_text(encoding="utf-8"))
    df = pd.DataFrame(rows)
    df["year"] = df["date"].str[:4]
    df = df[df["year"].isin(["2018", "2019", "2020", "2021"])]
    df = df[df["method"].notna() & df["cpv_division"].notna()]
    df["noncomp"] = df["method"].isin(NONCOMP).astype(float)

    xw = pd.read_csv(XWALK, dtype={"cpv_division": str})
    xw["intensity"] = xw["exiobase_sector"].map(INTENSITY)
    cmap = dict(zip(xw["cpv_division"], xw["intensity"]))

    g = (df.groupby("cpv_division")
           .agg(n=("noncomp", "size"), noncomp_rate=("noncomp", "mean")).reset_index())
    g["carbon"] = g["cpv_division"].map(cmap)
    sub = g[(g["n"] >= MIN_PER_DIV) & g["carbon"].notna()].copy()

    rho, p = stats.spearmanr(sub["carbon"], sub["noncomp_rate"])
    pear, pp = stats.pearsonr(sub["carbon"], sub["noncomp_rate"])

    # high- vs low-carbon non-competitive rate (split at 0.25 global threshold)
    hi = sub[sub["carbon"] >= 0.25]; lo = sub[sub["carbon"] < 0.25]

    res = {
        "source": "ProZorro public OCDS API (public.api.openprocurement.org), 2018-2021",
        "n_tenders": int(len(df)),
        "n_divisions_total": int(len(g)),
        "n_divisions_in_corr": int(len(sub)),
        "min_per_division": MIN_PER_DIV,
        "competition_proxy": "procurementMethodType (non-competitive = reporting/negotiation*)",
        "overall_noncompetitive_rate": float(df["noncomp"].mean()),
        "spearman_carbon_vs_noncomp": {"rho": float(rho), "p": float(p)},
        "pearson_carbon_vs_noncomp": {"r": float(pear), "p": float(pp)},
        "noncomp_rate_high_carbon": float(hi["noncomp_rate"].mean()) if len(hi) else None,
        "noncomp_rate_low_carbon": float(lo["noncomp_rate"].mean()) if len(lo) else None,
        "by_year_noncomp_rate": {y: float(df[df.year == y]["noncomp"].mean())
                                 for y in ["2018", "2019", "2020", "2021"]},
        "division_table": sub.sort_values("carbon", ascending=False).round(4)
                              .to_dict("records"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"N tenders: {len(df):,}  | divisions in correlation: {len(sub)}")
    print(f"Overall non-competitive rate: {df['noncomp'].mean()*100:.1f}%")
    print(f"Spearman(carbon, non-comp rate) = {rho:+.3f} (p={p:.3f})")
    print(f"Pearson = {pear:+.3f} (p={pp:.3f})")
    if len(hi) and len(lo):
        print(f"non-comp rate: high-carbon {hi['noncomp_rate'].mean()*100:.1f}% vs "
              f"low-carbon {lo['noncomp_rate'].mean()*100:.1f}%")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
