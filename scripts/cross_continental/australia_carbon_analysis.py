"""
Australian Federal Procurement (AusTender) — Competition-Carbon Analysis
========================================================================
Replicates the EU competition-carbon premium analysis for 137,550
Australian federal contracts (FY 2016-17 and FY 2017-18).

Outputs → results/australia_analysis.json
"""

import json
import pathlib
import warnings

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "Data" / "raw"
OUT = ROOT / "results" / "cross_continental" / "australia_analysis.json"

# ── 1. Load and harmonise both fiscal-year files ──────────────────────

df1 = pd.read_csv(RAW / "austender_2016_17.csv", encoding="latin-1")
df2 = pd.read_csv(RAW / "austender_2017_18.csv", encoding="latin-1")

# Harmonise column names
df1 = df1.rename(columns={"Value": "contract_value", "UNSPSC Code": "unspsc"})
df2 = df2.rename(columns={"Contract Value": "contract_value", "UNSPSC": "unspsc"})

df1["fiscal_year"] = "2016-17"
df2["fiscal_year"] = "2017-18"

keep = ["fiscal_year", "Contract ID", "Procurement Method",
        "contract_value", "unspsc", "UNSPSC Title",
        "Agency Name", "Supplier Name"]
df = pd.concat([df1[keep], df2[keep]], ignore_index=True)
print(f"Combined rows: {len(df):,}")

# ── 2. Clean values ──────────────────────────────────────────────────

df["contract_value"] = pd.to_numeric(df["contract_value"], errors="coerce")
df["unspsc"] = pd.to_numeric(df["unspsc"], errors="coerce")

# Drop rows missing value or UNSPSC
n_before = len(df)
df = df.dropna(subset=["contract_value", "unspsc"])
df = df[df["contract_value"] > 0]
df["unspsc"] = df["unspsc"].astype(int)
print(f"After cleaning (value>0 & UNSPSC present): {len(df):,}  (dropped {n_before - len(df):,})")

# ── 3. Competition classification ────────────────────────────────────

def classify_competition(method: str) -> str:
    m = str(method).strip().lower()
    if "open" in m:
        return "competitive"
    elif "limited" in m:
        return "limited"
    elif "prequalified" in m:
        return "limited"
    elif "panel" in m:
        return "limited"
    elif "select" in m:
        return "select"
    else:
        return "other"

df["competition"] = df["Procurement Method"].apply(classify_competition)

# Binary flag: non-competitive = limited + select + other non-open
df["non_competitive"] = (df["competition"] != "competitive").astype(int)

# ── 4. UNSPSC → carbon intensity mapping ─────────────────────────────

CARBON_MAP = [
    (10000000, 12999999, 0.85, "Live plants/animals/mining"),
    (15000000, 15999999, 2.10, "Fuel/lubricants"),
    (20000000, 24999999, 0.55, "Mining/construction/building"),
    (25000000, 27999999, 0.35, "Manufacturing/commercial equip"),
    (30000000, 32999999, 0.40, "Manufacturing components"),
    (40000000, 42999999, 0.30, "Distribution/HVAC"),
    (43000000, 45999999, 0.20, "IT/Communications"),
    (46000000, 49999999, 0.25, "Defense/Medical/Lab"),
    (50000000, 53999999, 0.65, "Food/beverage/personal care"),
    (55000000, 56999999, 0.15, "Real estate/cleaning"),
    (70000000, 73999999, 0.10, "Financial/legal/marketing"),
    (76000000, 78999999, 0.80, "Industrial cleaning/transport"),
    (80000000, 81999999, 0.10, "Management/HR/training"),
    (84000000, 86999999, 0.08, "Financial services"),
    (90000000, 94999999, 0.25, "Travel/food/recreation"),
    (95000000, 95999999, 0.10, "Land/buildings"),
]

def map_carbon(code: int) -> tuple:
    for lo, hi, ci, label in CARBON_MAP:
        if lo <= code <= hi:
            return ci, label
    return np.nan, "unmapped"

df[["carbon_intensity", "sector_label"]] = df["unspsc"].apply(
    lambda c: pd.Series(map_carbon(c))
)

n_mapped = df["carbon_intensity"].notna().sum()
print(f"UNSPSC mapped to CI: {n_mapped:,} / {len(df):,}  ({100*n_mapped/len(df):.1f}%)")

# Keep only mapped rows for carbon analysis
dfc = df.dropna(subset=["carbon_intensity"]).copy()
print(f"Analysis sample (mapped & cleaned): {len(dfc):,}")

# ── 5. Core statistics ───────────────────────────────────────────────

results = {}

# 5a. Counts
total_n = len(df)
pm_counts = df["Procurement Method"].value_counts().to_dict()
comp_counts = df["competition"].value_counts().to_dict()
results["sample"] = {
    "total_contracts": total_n,
    "by_procurement_method": pm_counts,
    "by_competition_class": comp_counts,
    "analysis_sample_with_CI": len(dfc),
}

# 5b. Non-competitive rate
nc_rate = df["non_competitive"].mean()
results["non_competitive_rate"] = {
    "overall": round(nc_rate, 4),
    "by_year": {
        yr: round(g["non_competitive"].mean(), 4)
        for yr, g in df.groupby("fiscal_year")
    },
}

# 5c. Carbon premium by competition type
ci_by_comp = dfc.groupby("competition")["carbon_intensity"].agg(["mean", "std", "count"])
ci_by_comp = ci_by_comp.rename(columns={"mean": "mean_CI", "std": "std_CI", "count": "n"})
results["carbon_intensity_by_competition"] = {
    idx: {"mean_CI": round(row["mean_CI"], 4),
          "std_CI": round(row["std_CI"], 4),
          "n": int(row["n"])}
    for idx, row in ci_by_comp.iterrows()
}

# 5d. Carbon premium (non-competitive minus competitive)
comp_ci = dfc.loc[dfc["competition"] == "competitive", "carbon_intensity"]
noncomp_ci = dfc.loc[dfc["competition"] != "competitive", "carbon_intensity"]

premium = noncomp_ci.mean() - comp_ci.mean()

# Cohen's d
pooled_std = np.sqrt(
    ((len(comp_ci) - 1) * comp_ci.std()**2 + (len(noncomp_ci) - 1) * noncomp_ci.std()**2)
    / (len(comp_ci) + len(noncomp_ci) - 2)
)
cohens_d = premium / pooled_std if pooled_std > 0 else np.nan

# Welch's t-test
t_stat, p_value = stats.ttest_ind(noncomp_ci, comp_ci, equal_var=False)

results["carbon_premium"] = {
    "competitive_mean_CI": round(comp_ci.mean(), 4),
    "non_competitive_mean_CI": round(noncomp_ci.mean(), 4),
    "premium": round(premium, 4),
    "cohens_d": round(cohens_d, 4),
    "welch_t_stat": round(t_stat, 4),
    "welch_p_value": float(f"{p_value:.2e}") if p_value < 0.001 else round(p_value, 6),
    "n_competitive": int(len(comp_ci)),
    "n_non_competitive": int(len(noncomp_ci)),
}

# 5e. Cross-sector correlation: sector SB rate vs sector mean CI
sector = dfc.groupby("sector_label").agg(
    mean_CI=("carbon_intensity", "mean"),
    nc_rate=("non_competitive", "mean"),
    n=("non_competitive", "count"),
).reset_index()
sector = sector[sector["n"] >= 50]  # minimum sector size

if len(sector) >= 3:
    r, p_corr = stats.pearsonr(sector["nc_rate"], sector["mean_CI"])
    rho, p_spear = stats.spearmanr(sector["nc_rate"], sector["mean_CI"])
else:
    r, p_corr, rho, p_spear = np.nan, np.nan, np.nan, np.nan

results["cross_sector_correlation"] = {
    "n_sectors": int(len(sector)),
    "pearson_r": round(r, 4) if not np.isnan(r) else None,
    "pearson_p": round(p_corr, 4) if not np.isnan(p_corr) else None,
    "spearman_rho": round(rho, 4) if not np.isnan(rho) else None,
    "spearman_p": round(p_spear, 4) if not np.isnan(p_spear) else None,
    "sectors": sector.to_dict(orient="records"),
}

# 5f. Value-weighted carbon premium
dfc["value_x_ci"] = dfc["contract_value"] * dfc["carbon_intensity"]
vw_comp = dfc.loc[dfc["competition"] == "competitive"]
vw_noncomp = dfc.loc[dfc["competition"] != "competitive"]

vw_comp_ci = vw_comp["value_x_ci"].sum() / vw_comp["contract_value"].sum()
vw_noncomp_ci = vw_noncomp["value_x_ci"].sum() / vw_noncomp["contract_value"].sum()

results["value_weighted_carbon"] = {
    "competitive_vw_CI": round(vw_comp_ci, 4),
    "non_competitive_vw_CI": round(vw_noncomp_ci, 4),
    "vw_premium": round(vw_noncomp_ci - vw_comp_ci, 4),
    "total_value_AUD": round(dfc["contract_value"].sum(), 2),
}

# 5g. Top agencies by non-competitive rate (agencies with ≥100 contracts)
agency = dfc.groupby("Agency Name").agg(
    n=("non_competitive", "count"),
    nc_rate=("non_competitive", "mean"),
    mean_CI=("carbon_intensity", "mean"),
).reset_index()
agency = agency[agency["n"] >= 100].sort_values("nc_rate", ascending=False)
results["top_agencies_by_nc_rate"] = agency.head(10).to_dict(orient="records")

# ── 6. Save ──────────────────────────────────────────────────────────

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w") as f:
    json.dump(results, f, indent=2, default=str)

print(f"\n{'='*60}")
print(f"Results saved to {OUT}")
print(f"{'='*60}")
print(f"\nKEY FINDINGS:")
print(f"  Total contracts:           {total_n:>10,}")
print(f"  Non-competitive rate:      {nc_rate:>10.1%}")
print(f"  Competitive mean CI:       {comp_ci.mean():>10.4f}")
print(f"  Non-competitive mean CI:   {noncomp_ci.mean():>10.4f}")
print(f"  Carbon premium:            {premium:>+10.4f}")
print(f"  Cohen's d:                 {cohens_d:>10.4f}")
print(f"  Welch t-stat:              {t_stat:>10.2f}")
print(f"  Welch p-value:             {p_value:>10.2e}")
print(f"  Cross-sector Pearson r:    {r:>10.4f}  (p={p_corr:.4f})")
print(f"  Cross-sector Spearman ρ:   {rho:>10.4f}  (p={p_spear:.4f})")
print(f"  N sectors (≥50 contracts): {len(sector):>10}")
