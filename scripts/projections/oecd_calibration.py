"""Compute OECD-calibrated procurement, Dead Zone, Monopoly Tax, and NDC numbers."""
import pyarrow.parquet as pq
import pandas as pd
import numpy as np
import json
from pathlib import Path

# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
ROOT = _d
df = pq.read_table(ROOT / "Data/processed/gprd_with_carbon.parquet").to_pandas()
eu = df[df["country"] != "CO"].copy()

# ============ OECD DATA ============
# Source: OECD Government at a Glance 2023
# Public procurement as % of GDP (2021 data, latest available)
oecd_pct_gdp = {
    "DE": 0.135, "FR": 0.145, "IT": 0.115, "ES": 0.105, "NL": 0.137,
    "PL": 0.105, "BE": 0.120, "AT": 0.120, "SE": 0.160, "DK": 0.135,
    "FI": 0.155, "PT": 0.105, "CZ": 0.115, "RO": 0.085, "HU": 0.105,
    "IE": 0.095, "BG": 0.080, "SK": 0.105, "HR": 0.100, "LT": 0.100,
    "LV": 0.105, "EE": 0.115, "SI": 0.120,
    "GB": 0.130, "NO": 0.155, "CH": 0.085, "IS": 0.120,
}

# GDP 2023 (EUR billions, approximate)
gdp_2023_eur = {
    "DE": 4121, "FR": 2803, "IT": 2085, "ES": 1462, "NL": 1008,
    "PL": 688, "BE": 582, "AT": 477, "SE": 552, "DK": 382,
    "FI": 275, "PT": 268, "CZ": 291, "RO": 318, "HU": 189,
    "IE": 502, "BG": 99, "SK": 116, "HR": 71, "LT": 67,
    "LV": 40, "EE": 36, "SI": 61,
    "GB": 2943, "NO": 434, "CH": 700, "IS": 26,
}

# National GHG emissions 2019 (Mt CO2e, excl LULUCF)
national_ghg = {
    "DE": 810, "FR": 376, "IT": 352, "ES": 270, "NL": 160,
    "PL": 355, "BE": 115, "AT": 80, "SE": 50, "DK": 45,
    "FI": 53, "PT": 60, "CZ": 130, "RO": 115, "HU": 64,
    "IE": 60, "BG": 60, "SK": 42, "HR": 24, "LT": 20,
    "LV": 12, "EE": 16, "SI": 17,
    "GB": 398, "NO": 50, "CH": 46, "IS": 4,
}

# NDC targets (55% reduction from 1990 for EU; UK Climate Change Act 78% by 2035)
# Approximate remaining reductions needed from 2019 levels
ndc_reduction_pct = {  # % reduction still needed from 2019 to meet NDC
    "DE": 0.40, "FR": 0.35, "IT": 0.40, "ES": 0.35, "NL": 0.40,
    "PL": 0.45, "BE": 0.35, "AT": 0.35, "SE": 0.20, "DK": 0.40,
    "FI": 0.30, "PT": 0.30, "CZ": 0.40, "RO": 0.20, "HU": 0.35,
    "IE": 0.40, "BG": 0.25, "SK": 0.35, "HR": 0.30, "LT": 0.30,
    "LV": 0.25, "EE": 0.35, "SI": 0.30,
    "GB": 0.45, "NO": 0.40, "CH": 0.40, "IS": 0.35,
}

print("=" * 70)
print("OECD-CALIBRATED EU PROCUREMENT ANALYSIS")
print("=" * 70)

# Total EU-context procurement (OECD-calibrated)
total_oecd_procurement = sum(
    gdp_2023_eur.get(c, 0) * oecd_pct_gdp.get(c, 0.12)
    for c in eu["country"].unique()
    if c in gdp_2023_eur
)
print(f"\nTotal EU-context annual procurement (OECD): EUR {total_oecd_procurement:.0f}B")

# From our data: SB rates and CI by country
print("\n--- COUNTRY-LEVEL ANALYSIS ---")
results = {}
for country in sorted(eu["country"].unique()):
    c = eu[eu["country"] == country]
    sb = c[c["single_bidder"] == True]
    sb_rate = c["single_bidder"].mean()
    avg_ci = c["carbon_intensity_kg_usd"].mean()
    sb_ci = sb["carbon_intensity_kg_usd"].mean() if len(sb) > 0 else 0
    
    oecd_proc = gdp_2023_eur.get(country, 0) * oecd_pct_gdp.get(country, 0.12)
    oecd_sb = oecd_proc * sb_rate  # EUR B
    
    # Carbon from OECD-calibrated spending
    # Convert EUR to USD (approx 1.09)
    oecd_proc_usd = oecd_proc * 1.09  # billions USD
    # B USD * kg/USD = B kg = Mt CO2e (since 1 Mt = 10^9 kg = 1 B kg)
    oecd_carbon_mt = oecd_proc_usd * avg_ci  # Mt CO2e
    oecd_sb_carbon_mt = oecd_sb * 1.09 * sb_ci
    
    nat_em = national_ghg.get(country, 0)
    ndc_red = nat_em * ndc_reduction_pct.get(country, 0.35)
    
    pct_national = (oecd_sb_carbon_mt / nat_em * 100) if nat_em > 0 else 0
    pct_ndc = (oecd_sb_carbon_mt / ndc_red * 100) if ndc_red > 0 else 0
    
    results[country] = {
        "n_contracts": len(c),
        "sb_rate": float(sb_rate),
        "avg_ci": float(avg_ci),
        "sb_ci": float(sb_ci),
        "oecd_procurement_eurB": float(oecd_proc),
        "oecd_sb_eurB": float(oecd_sb),
        "oecd_carbon_mt": float(oecd_carbon_mt),
        "oecd_sb_carbon_mt": float(oecd_sb_carbon_mt),
        "national_ghg_mt": float(nat_em),
        "ndc_reduction_mt": float(ndc_red),
        "sb_pct_national": float(pct_national),
        "sb_pct_ndc": float(pct_ndc),
    }
    
    if country in ["DE", "GB", "FR", "IT", "PL", "ES"]:
        print(f"\n  {country}:")
        print(f"    Contracts: {len(c):,}")
        print(f"    SB rate: {sb_rate*100:.1f}%")
        print(f"    Avg CI: {avg_ci:.3f} kg/USD")
        print(f"    OECD procurement: EUR {oecd_proc:.0f}B")
        print(f"    OECD SB spending: EUR {oecd_sb:.1f}B")
        print(f"    OECD procurement carbon: {oecd_carbon_mt:.1f} Mt CO2e")
        print(f"    OECD SB carbon: {oecd_sb_carbon_mt:.1f} Mt CO2e")
        print(f"    National GHG: {nat_em} Mt")
        print(f"    SB carbon as % national: {pct_national:.1f}%")
        print(f"    SB carbon as % NDC reduction: {pct_ndc:.1f}%")

# Totals
total_sb_rate = eu["single_bidder"].mean()
total_avg_ci = eu["carbon_intensity_kg_usd"].mean()
total_sb_ci = eu[eu["single_bidder"] == True]["carbon_intensity_kg_usd"].mean()

total_sb_eurB = total_oecd_procurement * total_sb_rate
total_monopoly_tax = total_sb_eurB * 0.08
total_carbon_mt = total_oecd_procurement * 1.09 * total_avg_ci  # Mt
total_sb_carbon_mt = total_sb_eurB * 1.09 * total_sb_ci

print(f"\n{'='*70}")
print(f"EU-CONTEXT TOTALS (OECD-calibrated)")
print(f"{'='*70}")
print(f"Annual procurement: EUR {total_oecd_procurement:.0f}B")
print(f"SB rate: {total_sb_rate*100:.1f}%")
print(f"SB spending: EUR {total_sb_eurB:.0f}B")
print(f"Monopoly Tax (8%): EUR {total_monopoly_tax:.0f}B")
print(f"Total procurement carbon: {total_carbon_mt:.0f} Mt CO2e")
print(f"SB procurement carbon: {total_sb_carbon_mt:.0f} Mt CO2e")

# Total EU national emissions and NDC
total_nat_ghg = sum(national_ghg.get(c, 0) for c in eu["country"].unique())
total_ndc_red = sum(national_ghg.get(c, 0) * ndc_reduction_pct.get(c, 0.35) for c in eu["country"].unique())
print(f"Total EU-context national GHG: {total_nat_ghg} Mt")
print(f"Total NDC reduction needed: {total_ndc_red:.0f} Mt")
print(f"SB carbon as % of total national: {total_sb_carbon_mt/total_nat_ghg*100:.1f}%")
print(f"SB carbon as % of NDC reduction: {total_sb_carbon_mt/total_ndc_red*100:.1f}%")

# Dead Zone analysis with OECD calibration
print(f"\n{'='*70}")
print(f"DEAD ZONE ANALYSIS (EU-CONTEXT, OECD-CALIBRATED)")
print(f"{'='*70}")

# Get sector shares from our data (these are proportional, so TED inflation cancels)
sector_shares = eu.groupby("cpv_division").agg(
    val_share=("value_eur", lambda x: x.sum() / eu["value_eur"].sum()),
    sb_rate=("single_bidder", "mean"),
    ci_mean=("carbon_intensity_kg_usd", "mean"),
    n=("single_bidder", "count"),
).reset_index()
sector_shares = sector_shares[sector_shares["cpv_division"] != "na"]

ci_67 = sector_shares["ci_mean"].quantile(0.67)
sb_med = sector_shares["sb_rate"].median()

dz = sector_shares[(sector_shares["ci_mean"] >= ci_67) & (sector_shares["sb_rate"] >= sb_med)]
dz_val_share = dz["val_share"].sum()
dz_avg_sb = (dz["sb_rate"] * dz["val_share"]).sum() / dz_val_share if dz_val_share > 0 else 0.17
dz_avg_ci = (dz["ci_mean"] * dz["val_share"]).sum() / dz_val_share if dz_val_share > 0 else 0.5

dz_oecd_eurB = total_oecd_procurement * dz_val_share
dz_sb_eurB = dz_oecd_eurB * dz_avg_sb
dz_monopoly_tax = dz_sb_eurB * 0.08
dz_carbon_mt = dz_oecd_eurB * 1.09 * dz_avg_ci  # Mt
dz_sb_carbon_mt = dz_sb_eurB * 1.09 * dz_avg_ci

print(f"Dead Zone sectors: {len(dz)}")
print(f"DZ share of procurement: {dz_val_share*100:.1f}%")
print(f"DZ procurement (OECD): EUR {dz_oecd_eurB:.0f}B")
print(f"DZ average SB rate: {dz_avg_sb*100:.1f}%")
print(f"DZ SB spending (OECD): EUR {dz_sb_eurB:.0f}B")
print(f"DZ Monopoly Tax: EUR {dz_monopoly_tax:.1f}B")
print(f"DZ carbon: {dz_carbon_mt:.0f} Mt CO2e")
print(f"DZ SB carbon: {dz_sb_carbon_mt:.0f} Mt CO2e")

print("\n--- Dead Zone Sectors ---")
for _, r in dz.sort_values("val_share", ascending=False).iterrows():
    cpv = r["cpv_division"]
    print(f"  CPV {cpv}: SB={r['sb_rate']*100:.1f}%  CI={r['ci_mean']:.3f}  Share={r['val_share']*100:.2f}%  N={r['n']:,}")

# ============ G20 PROJECTION ============
print(f"\n{'='*70}")
print(f"G20 PROJECTION (OECD-CALIBRATED)")
print(f"{'='*70}")

g20_procurement_usdT = 11.0  # OECD 2023
g20_sb_rate = 0.17  # conservative: EU rate
g20_sb_usdT = g20_procurement_usdT * g20_sb_rate
g20_monopoly_tax_usdB = g20_sb_usdT * 0.08 * 1000  # convert T to B

# DZ in G20
g20_dz_usdT = g20_procurement_usdT * dz_val_share
g20_dz_sb_usdT = g20_dz_usdT * dz_avg_sb
g20_dz_carbon_mt = g20_dz_usdT * 1000 * dz_avg_ci  # T USD * 1000 = B USD; B USD * kg/USD = Mt

# NDC context: G20 = ~80% of global emissions = ~42 Gt CO2e
g20_emissions_gt = 42  # approximate

print(f"G20 procurement: ${g20_procurement_usdT}T")
print(f"G20 SB spending (at {g20_sb_rate*100:.0f}%): ${g20_sb_usdT:.1f}T")
print(f"G20 Monopoly Tax (8%): ${g20_monopoly_tax_usdB:.0f}B")
print(f"G20 DZ procurement: ${g20_dz_usdT*1000:.0f}B")
print(f"G20 DZ SB spending: ${g20_dz_sb_usdT*1000:.0f}B")
print(f"G20 DZ carbon: {g20_dz_carbon_mt:.0f} Mt CO2e")
print(f"G20 total procurement carbon: {g20_procurement_usdT*1000*total_avg_ci:.0f} Mt CO2e")

# Green Premium offset
green_premium_pct = 0.15  # 15% average (10-20% range)
green_premium_cost = g20_dz_usdT * green_premium_pct * 1000  # $B
print(f"\nGreen Premium for DZ sectors (15%): ${green_premium_cost:.0f}B")
print(f"Monopoly Tax / Green Premium ratio: {g20_monopoly_tax_usdB/green_premium_cost:.1f}x")
print(f"Self-funding: {'YES' if g20_monopoly_tax_usdB > green_premium_cost else 'NO'}")

# Save
output = {
    "eu_oecd": {
        "annual_procurement_eurB": round(total_oecd_procurement),
        "sb_rate": round(total_sb_rate, 3),
        "sb_spending_eurB": round(total_sb_eurB),
        "monopoly_tax_eurB": round(total_monopoly_tax),
        "total_carbon_mt": round(total_carbon_mt),
        "sb_carbon_mt": round(total_sb_carbon_mt),
        "sb_pct_national_ghg": round(total_sb_carbon_mt / total_nat_ghg * 100, 1),
        "sb_pct_ndc": round(total_sb_carbon_mt / total_ndc_red * 100, 1),
    },
    "dead_zones_oecd": {
        "n_sectors": len(dz),
        "val_share_pct": round(dz_val_share * 100, 1),
        "procurement_eurB": round(dz_oecd_eurB),
        "sb_spending_eurB": round(dz_sb_eurB),
        "monopoly_tax_eurB": round(dz_monopoly_tax, 1),
        "carbon_mt": round(dz_carbon_mt),
        "sb_carbon_mt": round(dz_sb_carbon_mt),
    },
    "g20": {
        "procurement_usdT": g20_procurement_usdT,
        "sb_rate": g20_sb_rate,
        "sb_spending_usdT": round(g20_sb_usdT, 1),
        "monopoly_tax_usdB": round(g20_monopoly_tax_usdB),
        "dz_procurement_usdB": round(g20_dz_usdT * 1000),
        "dz_carbon_mt": round(g20_dz_carbon_mt),
        "green_premium_cost_usdB": round(green_premium_cost),
        "self_funding_ratio": round(g20_monopoly_tax_usdB / green_premium_cost, 1),
    },
    "country_ndc": {c: {
        "sb_pct_national": round(v["sb_pct_national"], 1),
        "sb_pct_ndc": round(v["sb_pct_ndc"], 1),
        "sb_carbon_mt": round(v["oecd_sb_carbon_mt"], 1),
    } for c, v in results.items() if c in ["DE", "GB", "FR", "IT", "PL", "ES"]},
}
with open(ROOT / "results" / "projections" / "oecd_calibrated_numbers.json", "w") as f:
    json.dump(output, f, indent=2)
print(f"\nSaved to results/oecd_calibrated_numbers.json")
