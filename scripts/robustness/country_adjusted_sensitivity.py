#!/usr/bin/env python3
"""
Country-Adjusted Carbon Intensity Sensitivity Analysis

CRITICAL FINDING: The dataset uses GLOBAL sector averages (37 unique values),
NOT country-specific EXIOBASE intensities. This script:

1. Creates country-specific adjustments using OWID CO2/GDP ratios
2. Reruns the SB premium analysis with adjusted intensities  
3. Compares results to demonstrate robustness
4. Generates a cross-validation table for the SI
"""
import pandas as pd
import numpy as np
from scipy import stats
import json
from pathlib import Path

# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
PROJECT_ROOT = _d
DATA_DIR = PROJECT_ROOT / "Data"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("COUNTRY-ADJUSTED CARBON INTENSITY SENSITIVITY ANALYSIS")
print("=" * 70)

# 1. Load procurement data
print("\nLoading procurement data...")
df = pd.read_parquet(DATA_DIR / "processed" / "gprd_with_carbon.parquet",
                     columns=['country', 'exiobase_sector', 'carbon_intensity_kg_usd',
                              'value_usd', 'single_bidder', 'year'])

eu = df[df['country'] != 'CO'].copy()
print(f"EU-context contracts: {len(eu):,}")

# 2. Load OWID CO2/GDP data
print("\nLoading OWID CO2 data...")
owid = pd.read_csv(DATA_DIR / "external" / "owid_co2_data.csv")
cmap = {
    'Austria': 'AT', 'Belgium': 'BE', 'Switzerland': 'CH', 'Czechia': 'CZ',
    'Germany': 'DE', 'Denmark': 'DK', 'Estonia': 'EE', 'Spain': 'ES',
    'Finland': 'FI', 'France': 'FR', 'United Kingdom': 'GB', 'Greece': 'GR',
    'Hungary': 'HU', 'Ireland': 'IE', 'Iceland': 'IS', 'Italy': 'IT',
    'Lithuania': 'LT', 'Luxembourg': 'LU', 'Latvia': 'LV', 'Netherlands': 'NL',
    'Norway': 'NO', 'Poland': 'PL', 'Portugal': 'PT', 'Sweden': 'SE',
    'Slovenia': 'SI', 'Slovakia': 'SK'
}

# Get CO2/GDP for each country-year
owid_sub = owid[owid['country'].isin(cmap.keys())][['country', 'year', 'co2_per_gdp']].dropna()
owid_sub['iso'] = owid_sub['country'].map(cmap)

# Also get a reference year (2015) for static adjustment
o15 = owid_sub[owid_sub['year'] == 2015][['iso', 'co2_per_gdp']].copy()
eu_mean_co2_gdp = o15['co2_per_gdp'].mean()
o15['adjustment_factor'] = o15['co2_per_gdp'] / eu_mean_co2_gdp
print(f"\nOWID CO2/GDP adjustment factors (relative to EU mean {eu_mean_co2_gdp:.3f}):")
o15_sorted = o15.sort_values('adjustment_factor', ascending=False)
for _, row in o15_sorted.iterrows():
    print(f"  {row['iso']}: CO2/GDP={row['co2_per_gdp']:.3f}, factor={row['adjustment_factor']:.3f}")

# 3. Create country-adjusted carbon intensities
print("\n" + "=" * 70)
print("CREATING COUNTRY-ADJUSTED CARBON INTENSITIES")
print("=" * 70)

eu = eu.merge(o15[['iso', 'adjustment_factor']], left_on='country', right_on='iso', how='left')
# Fill missing with 1.0 (no adjustment)
eu['adjustment_factor'] = eu['adjustment_factor'].fillna(1.0)
eu['ci_adjusted'] = eu['carbon_intensity_kg_usd'] * eu['adjustment_factor']

# Check: how many unique CI values now?
n_unique_orig = eu['carbon_intensity_kg_usd'].nunique()
n_unique_adj = eu['ci_adjusted'].nunique()
print(f"Original unique CI values: {n_unique_orig}")
print(f"Adjusted unique CI values: {n_unique_adj}")

# 4. Run premium analysis with ORIGINAL data
print("\n" + "=" * 70)
print("PREMIUM COMPARISON: ORIGINAL vs COUNTRY-ADJUSTED")
print("=" * 70)

def compute_premium(data, ci_col):
    sb = data[data['single_bidder'] == True][ci_col]
    mb = data[data['single_bidder'] == False][ci_col]
    sb_mean = sb.mean()
    mb_mean = mb.mean()
    premium = (sb_mean - mb_mean) / mb_mean * 100
    t_stat, p_val = stats.ttest_ind(sb, mb, equal_var=False)
    d = (sb_mean - mb_mean) / np.sqrt((sb.var() + mb.var()) / 2)
    return {
        'sb_mean': round(sb_mean, 4),
        'mb_mean': round(mb_mean, 4),
        'premium_pct': round(premium, 2),
        't_stat': round(t_stat, 1),
        'd': round(d, 4),
        'n_sb': len(sb),
        'n_mb': len(mb),
    }

# Overall
orig = compute_premium(eu, 'carbon_intensity_kg_usd')
adj = compute_premium(eu, 'ci_adjusted')

print(f"\nOverall EU-context:")
print(f"  Original: premium={orig['premium_pct']}%, t={orig['t_stat']}, d={orig['d']}")
print(f"  Adjusted: premium={adj['premium_pct']}%, t={adj['t_stat']}, d={adj['d']}")

# By size band
results = {'overall': {'original': orig, 'adjusted': adj}, 'size_bands': {}}
for label, mask in [
    ('Small <10k', eu['value_usd'] < 10000 * 1.1),  # approximate EUR->USD
    ('Medium 10k-200k', (eu['value_usd'] >= 10000 * 1.1) & (eu['value_usd'] < 200000 * 1.1)),
    ('Large >200k', eu['value_usd'] >= 200000 * 1.1),
]:
    subset = eu[mask]
    if len(subset) > 0:
        o = compute_premium(subset, 'carbon_intensity_kg_usd')
        a = compute_premium(subset, 'ci_adjusted')
        results['size_bands'][label] = {'original': o, 'adjusted': a}
        print(f"\n{label}:")
        print(f"  Original: premium={o['premium_pct']}%, d={o['d']}")
        print(f"  Adjusted: premium={a['premium_pct']}%, d={a['d']}")

# 5. By country
print("\n" + "=" * 70)
print("COUNTRY-LEVEL PREMIUM COMPARISON")
print("=" * 70)

country_results = {}
for c in sorted(eu['country'].unique()):
    sub = eu[eu['country'] == c]
    if sub['single_bidder'].sum() >= 100:  # minimum for meaningful comparison
        o = compute_premium(sub, 'carbon_intensity_kg_usd')
        a = compute_premium(sub, 'ci_adjusted')
        country_results[c] = {'original': o['premium_pct'], 'adjusted': a['premium_pct']}
        diff = a['premium_pct'] - o['premium_pct']
        print(f"  {c}: orig={o['premium_pct']:+.1f}% -> adj={a['premium_pct']:+.1f}% (diff={diff:+.1f}%)")

results['country_comparison'] = country_results

# 6. Temporal robustness with adjusted CI
print("\n" + "=" * 70)
print("TEMPORAL ROBUSTNESS (ADJUSTED)")
print("=" * 70)

temporal_results = {}
for y in sorted(eu['year'].unique()):
    sub = eu[eu['year'] == y]
    if sub['single_bidder'].sum() >= 100:
        o = compute_premium(sub, 'carbon_intensity_kg_usd')
        a = compute_premium(sub, 'ci_adjusted')
        temporal_results[int(y)] = {'original': o['premium_pct'], 'adjusted': a['premium_pct']}
        print(f"  {y}: orig={o['premium_pct']:+.1f}% -> adj={a['premium_pct']:+.1f}%")

results['temporal_comparison'] = temporal_results

# 7. Cross-country within-sector variation with adjusted CI
print("\n" + "=" * 70)
print("CROSS-COUNTRY VARIATION (ADJUSTED)")
print("=" * 70)

cs_adj = eu.groupby(['country', 'exiobase_sector']).agg(
    ci_orig=('carbon_intensity_kg_usd', 'first'),
    ci_adj=('ci_adjusted', 'first'),
).reset_index()

sector_var = cs_adj.groupby('exiobase_sector').agg(
    cv_orig=('ci_orig', lambda x: x.std()/x.mean() if x.mean() > 0 else 0),
    cv_adj=('ci_adj', lambda x: x.std()/x.mean() if x.mean() > 0 else 0),
).reset_index()

print(f"Mean CV (original): {sector_var['cv_orig'].mean():.4f}")
print(f"Mean CV (adjusted): {sector_var['cv_adj'].mean():.4f}")
print(f"Sectors with CV > 10% (adjusted): {(sector_var['cv_adj'] > 0.1).sum()}")
print(f"Sectors with CV > 30% (adjusted): {(sector_var['cv_adj'] > 0.3).sum()}")

results['cross_country_cv'] = {
    'mean_cv_original': round(float(sector_var['cv_orig'].mean()), 4),
    'mean_cv_adjusted': round(float(sector_var['cv_adj'].mean()), 4),
}

# 8. Key conclusion
print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)

orig_prem = results['overall']['original']['premium_pct']
adj_prem = results['overall']['adjusted']['premium_pct']
# Count how many countries still negative
neg_orig = sum(1 for v in country_results.values() if v['original'] < 0)
neg_adj = sum(1 for v in country_results.values() if v['adjusted'] < 0)
total_countries = len(country_results)

print(f"Original premium: {orig_prem}%")
print(f"Country-adjusted premium: {adj_prem}%")
print(f"Premium direction: {'SAME' if (orig_prem < 0) == (adj_prem < 0) else 'REVERSED'}")
print(f"Countries with negative premium: {neg_orig}/{total_countries} (original) -> {neg_adj}/{total_countries} (adjusted)")

# All temporal premiums negative?
all_neg_orig = all(v['original'] < 0 for v in temporal_results.values())
all_neg_adj = all(v['adjusted'] < 0 for v in temporal_results.values())
print(f"All years negative: {all_neg_orig} (original) -> {all_neg_adj} (adjusted)")
print(f"\nRobustness: Country-adjustment {'CONFIRMS' if (orig_prem < 0) == (adj_prem < 0) else 'REVERSES'} the original finding.")

results['conclusion'] = {
    'premium_direction_same': (orig_prem < 0) == (adj_prem < 0),
    'countries_negative_original': neg_orig,
    'countries_negative_adjusted': neg_adj,
    'total_countries': total_countries,
    'all_years_negative_original': all_neg_orig,
    'all_years_negative_adjusted': all_neg_adj,
}

# Save
outpath = RESULTS_DIR / "country_adjusted_sensitivity.json"
with open(outpath, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to {outpath}")
