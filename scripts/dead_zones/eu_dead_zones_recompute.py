"""Recompute Dead Zones using EU-context data only, with 2018 robustness check."""
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

print("=== EU-CONTEXT DEAD ZONE ANALYSIS ===")
print(f"Total EU-context contracts: {len(eu):,}")
total_val = eu["value_eur"].sum()
print(f"Total EU-context value (EUR): {total_val:,.0f}")

# Yearly breakdown to see 2018 anomaly
print("\n=== YEARLY BREAKDOWN ===")
for yr in sorted(eu["year"].unique()):
    sub = eu[eu["year"] == yr]
    n = len(sub)
    v = sub["value_eur"].sum()
    pct = v / total_val * 100
    print(f"  {int(yr)}: N={n:>10,}  Val=EUR {v/1e9:>10.1f}B  ({pct:.1f}% of total)")

# Sector-level stats
sectors = []
for cpv, grp in eu.groupby("cpv_division"):
    if str(cpv) == 'na' or pd.isna(cpv):
        continue
    sb = grp[grp["single_bidder"] == True]
    sectors.append({
        "cpv": str(cpv),
        "n": len(grp),
        "sb_rate": grp["single_bidder"].mean(),
        "ci_mean": grp["carbon_intensity_kg_usd"].mean(),
        "total_val": grp["value_eur"].sum(),
        "sb_val": sb["value_eur"].sum(),
        "total_carbon_kg": grp["carbon_footprint_kg"].sum(),
        "sb_carbon_kg": sb["carbon_footprint_kg"].sum(),
    })
sdf = pd.DataFrame(sectors)

ci_67th = sdf["ci_mean"].quantile(0.67)
sb_median = sdf["sb_rate"].median()
print(f"\nCI 67th percentile: {ci_67th:.4f} kg/USD")
print(f"SB rate median: {sb_median*100:.2f}%")

dz = sdf[(sdf["ci_mean"] >= ci_67th) & (sdf["sb_rate"] >= sb_median)]
print(f"\n=== EU-CONTEXT DEAD ZONES ===")
print(f"Dead Zone sectors: {len(dz)}")
print(f"DZ total value: EUR {dz['total_val'].sum()/1e12:.3f}T")
print(f"DZ SB-locked value: EUR {dz['sb_val'].sum()/1e12:.3f}T")
print(f"DZ total carbon: {dz['total_carbon_kg'].sum()/1e9:.1f} Mt CO2e")
print(f"DZ SB carbon: {dz['sb_carbon_kg'].sum()/1e9:.1f} Mt CO2e")

print("\n--- Top Dead Zone Sectors ---")
for _, r in dz.sort_values("sb_val", ascending=False).head(20).iterrows():
    print(f"  CPV {r['cpv']:>4s}: SB={r['sb_rate']*100:5.1f}%  CI={r['ci_mean']:.3f}  "
          f"SBval=EUR {r['sb_val']/1e9:>8.1f}B  Carbon={r['total_carbon_kg']/1e9:>8.1f}Mt")

# ============ ROBUSTNESS: EXCLUDING 2018 ============
print("\n=== ROBUSTNESS: EXCLUDING 2018 ===")
eu_no18 = eu[eu["year"] != 2018]
print(f"Contracts without 2018: {len(eu_no18):,}")
print(f"Value without 2018: EUR {eu_no18['value_eur'].sum()/1e12:.3f}T")

sectors2 = []
for cpv, grp in eu_no18.groupby("cpv_division"):
    if str(cpv) == 'na' or pd.isna(cpv):
        continue
    sb = grp[grp["single_bidder"] == True]
    sectors2.append({
        "cpv": str(cpv),
        "n": len(grp),
        "sb_rate": grp["single_bidder"].mean(),
        "ci_mean": grp["carbon_intensity_kg_usd"].mean(),
        "total_val": grp["value_eur"].sum(),
        "sb_val": sb["value_eur"].sum(),
        "total_carbon_kg": grp["carbon_footprint_kg"].sum(),
    })
sdf2 = pd.DataFrame(sectors2)
ci2 = sdf2["ci_mean"].quantile(0.67)
sb2 = sdf2["sb_rate"].median()
dz2 = sdf2[(sdf2["ci_mean"] >= ci2) & (sdf2["sb_rate"] >= sb2)]
print(f"DZ sectors (no 2018): {len(dz2)}")
print(f"DZ SB-locked (no 2018): EUR {dz2['sb_val'].sum()/1e12:.3f}T")
print(f"DZ carbon (no 2018): {dz2['total_carbon_kg'].sum()/1e9:.1f} Mt CO2e")

# ============ ANNUALIZED FIGURES ============
print("\n=== ANNUALIZED DEAD ZONE FIGURES (2019-2023, excl 2018 anomaly) ===")
eu_recent = eu[(eu["year"] >= 2019) & (eu["year"] <= 2023)]
n_years = 5
annual_val = eu_recent["value_eur"].sum() / n_years
annual_sb_val = eu_recent[eu_recent["single_bidder"] == True]["value_eur"].sum() / n_years
annual_carbon = eu_recent["carbon_footprint_kg"].sum() / n_years
print(f"Annual EU procurement: EUR {annual_val/1e9:.1f}B")
print(f"Annual SB value: EUR {annual_sb_val/1e9:.1f}B")
print(f"Annual carbon: {annual_carbon/1e9:.1f} Mt CO2e")

# Annual dead zone
sectors3 = []
for cpv, grp in eu_recent.groupby("cpv_division"):
    if str(cpv) == 'na' or pd.isna(cpv):
        continue
    sb = grp[grp["single_bidder"] == True]
    sectors3.append({
        "cpv": str(cpv),
        "n": len(grp),
        "sb_rate": grp["single_bidder"].mean(),
        "ci_mean": grp["carbon_intensity_kg_usd"].mean(),
        "total_val": grp["value_eur"].sum(),
        "sb_val": sb["value_eur"].sum(),
        "total_carbon_kg": grp["carbon_footprint_kg"].sum(),
        "sb_carbon_kg": sb["carbon_footprint_kg"].sum(),
    })
sdf3 = pd.DataFrame(sectors3)
ci3 = sdf3["ci_mean"].quantile(0.67)
sb3 = sdf3["sb_rate"].median()
dz3 = sdf3[(sdf3["ci_mean"] >= ci3) & (sdf3["sb_rate"] >= sb3)]

annual_dz_val = dz3["total_val"].sum() / n_years
annual_dz_sb = dz3["sb_val"].sum() / n_years
annual_dz_carbon = dz3["total_carbon_kg"].sum() / n_years
annual_dz_sb_carbon = dz3["sb_carbon_kg"].sum() / n_years

print(f"Annual DZ procurement: EUR {annual_dz_val/1e9:.1f}B")
print(f"Annual DZ SB-locked: EUR {annual_dz_sb/1e9:.1f}B")
print(f"Annual DZ carbon: {annual_dz_carbon/1e9:.1f} Mt CO2e")
print(f"Annual DZ SB carbon: {annual_dz_sb_carbon/1e9:.1f} Mt CO2e")
print(f"DZ sectors (2019-2023): {len(dz3)}")
print(f"Monopoly Tax (8%): EUR {annual_dz_sb*0.08/1e9:.1f}B")

# ============ COUNTRY-LEVEL NDC MAPPING ============
print("\n=== COUNTRY-LEVEL NDC MAPPING (2019-2023 annual average) ===")
# National emissions (2019, Mt CO2e excl LULUCF)
national_emissions = {
    "DE": 810, "GB": 398, "FR": 376, "IT": 352, "ES": 270,
    "PL": 355, "NL": 160, "CZ": 130, "BE": 115, "RO": 115,
    "AT": 80, "SE": 50, "DK": 45, "FI": 53, "PT": 60,
    "HU": 64, "IE": 60, "BG": 60, "SK": 42, "HR": 24,
    "LT": 20, "LV": 12, "EE": 16, "SI": 17,
    "NO": 50, "CH": 46, "IS": 4,
}

for country_code in ["DE", "GB", "FR", "IT", "PL", "ES"]:
    c_data = eu_recent[eu_recent["country"] == country_code]
    if len(c_data) == 0:
        continue
    c_sb = c_data[c_data["single_bidder"] == True]
    annual_c_carbon = c_data["carbon_footprint_kg"].sum() / n_years / 1e9  # Mt
    annual_c_sb_carbon = c_sb["carbon_footprint_kg"].sum() / n_years / 1e9
    annual_c_val = c_data["value_eur"].sum() / n_years / 1e9
    c_sb_rate = c_data["single_bidder"].mean() * 100
    nat_em = national_emissions.get(country_code, 0)
    pct_of_national = (annual_c_sb_carbon / nat_em * 100) if nat_em > 0 else 0
    # NDC target: 55% reduction from 1990 = need to reduce by ~X Mt
    # Approx: 1990 emissions ~ 2019/0.65 (since 35% down already)
    ndc_reduction = nat_em * 0.55 / 0.65  # rough remaining reduction needed
    pct_of_ndc = (annual_c_sb_carbon / ndc_reduction * 100) if ndc_reduction > 0 else 0
    
    print(f"\n  {country_code}: {len(c_data):,} contracts (2019-23)")
    print(f"    Annual procurement: EUR {annual_c_val:.1f}B")
    print(f"    SB rate: {c_sb_rate:.1f}%")
    print(f"    Annual procurement carbon: {annual_c_carbon:.1f} Mt CO2e")
    print(f"    Annual SB carbon: {annual_c_sb_carbon:.1f} Mt CO2e")
    print(f"    National emissions (2019): {nat_em} Mt CO2e")
    print(f"    SB carbon as % of national: {pct_of_national:.1f}%")
    print(f"    SB carbon as % of NDC reduction: {pct_of_ndc:.1f}%")

# ============ SAVE ALL RESULTS ============
results = {
    "eu_context": {
        "total_contracts": int(len(eu)),
        "total_value_eur": float(total_val),
        "dead_zone_sectors": int(len(dz)),
        "dead_zone_total_value_eur": float(dz["total_val"].sum()),
        "dead_zone_sb_locked_eur": float(dz["sb_val"].sum()),
        "dead_zone_total_carbon_mt": float(dz["total_carbon_kg"].sum() / 1e9),
        "dead_zone_sb_carbon_mt": float(dz["sb_carbon_kg"].sum() / 1e9),
        "ci_67th_threshold": float(ci_67th),
        "sb_median_threshold": float(sb_median),
    },
    "annualized_2019_2023": {
        "annual_procurement_eur": float(annual_val),
        "annual_sb_value_eur": float(annual_sb_val),
        "annual_carbon_mt": float(annual_carbon / 1e9),
        "annual_dz_procurement_eur": float(annual_dz_val),
        "annual_dz_sb_locked_eur": float(annual_dz_sb),
        "annual_dz_carbon_mt": float(annual_dz_carbon / 1e9),
        "annual_dz_sb_carbon_mt": float(annual_dz_sb_carbon / 1e9),
        "dz_sectors": int(len(dz3)),
        "monopoly_tax_8pct_eur": float(annual_dz_sb * 0.08),
    },
    "robustness_no_2018": {
        "contracts": int(len(eu_no18)),
        "value_eur": float(eu_no18["value_eur"].sum()),
        "dz_sectors": int(len(dz2)),
        "dz_sb_locked_eur": float(dz2["sb_val"].sum()),
    },
}
out_path = ROOT / "results" / "dead_zones" / "eu_context_dead_zones.json"
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\n\nSaved results to {out_path}")
