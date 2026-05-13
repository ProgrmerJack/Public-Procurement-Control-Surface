#!/usr/bin/env python3
"""
Cross-validate EXIOBASE carbon intensities against OWID national CO2/GDP data.
This provides independent validation that EXIOBASE sector-country intensities
reflect real-world carbon intensity patterns.
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

# Load procurement data
print("Loading procurement data...")
df = pd.read_parquet(DATA_DIR / "processed" / "gprd_with_carbon.parquet",
                     columns=['country', 'exiobase_sector', 'carbon_intensity_kg_usd', 
                              'value_usd', 'single_bidder'])
eu = df[df['country'] != 'CO']

# Get unique country-sector carbon intensities
cs = eu.groupby(['country', 'exiobase_sector']).agg(
    ci=('carbon_intensity_kg_usd', 'first'),
    n=('value_usd', 'count')
).reset_index()

# Cross-country variation within each sector
print("\n" + "="*70)
print("CROSS-COUNTRY VARIATION WITHIN EXIOBASE SECTORS")
print("="*70)

sector_stats = []
for sect in cs['exiobase_sector'].unique():
    s = cs[cs['exiobase_sector'] == sect]
    if len(s) >= 2:
        sector_stats.append({
            'sector': sect,
            'mean_ci': s['ci'].mean(),
            'std_ci': s['ci'].std(),
            'min_ci': s['ci'].min(),
            'max_ci': s['ci'].max(),
            'n_countries': len(s),
            'cv': s['ci'].std() / s['ci'].mean() if s['ci'].mean() > 0 else 0,
            'range_ratio': s['ci'].max() / s['ci'].min() if s['ci'].min() > 0 else 0
        })

sdf = pd.DataFrame(sector_stats).sort_values('cv', ascending=False)
cv_mean = sdf['cv'].mean()
rr_mean = sdf['range_ratio'].mean()

print(f"Number of sectors: {len(sdf)}")
print(f"Mean coefficient of variation: {cv_mean:.3f} ({cv_mean*100:.1f}%)")
print(f"Mean max/min ratio: {rr_mean:.1f}x")
print(f"Sectors with CV > 20%: {(sdf['cv'] > 0.2).sum()}")
print(f"Sectors with CV > 50%: {(sdf['cv'] > 0.5).sum()}")
print(f"Sectors with max/min > 2x: {(sdf['range_ratio'] > 2).sum()}")
print(f"Sectors with max/min > 3x: {(sdf['range_ratio'] > 3).sum()}")

print("\nTop 15 sectors by cross-country variation:")
for _, row in sdf.head(15).iterrows():
    s = row['sector'][:50]
    print(f"  {s:50s} CV={row['cv']:.3f} range=[{row['min_ci']:.3f}-{row['max_ci']:.3f}] ratio={row['range_ratio']:.1f}x")

# Load OWID data
print("\n" + "="*70)
print("SECTOR-LEVEL VALIDATION: EXIOBASE CI vs OWID CO2/GDP")
print("="*70)

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

o15 = owid[(owid['year'] == 2015) & (owid['country'].isin(cmap.keys()))][['country', 'co2_per_gdp']].dropna()
o15['iso'] = o15['country'].map(cmap)

# For each sector, correlate EXIOBASE CI with OWID CO2/GDP across countries
sector_validations = []
for sect in cs['exiobase_sector'].unique():
    s = cs[cs['exiobase_sector'] == sect]
    m = pd.merge(s[['country', 'ci']], o15[['iso', 'co2_per_gdp']], 
                 left_on='country', right_on='iso')
    if len(m) >= 10:
        r, p = stats.pearsonr(m['co2_per_gdp'], m['ci'])
        rho, p_rho = stats.spearmanr(m['co2_per_gdp'], m['ci'])
        sector_validations.append({
            'sector': sect, 'r': r, 'p': p, 'rho': rho, 'p_rho': p_rho, 'n': len(m)
        })

vdf = pd.DataFrame(sector_validations).sort_values('r', ascending=False)
sig = vdf[vdf['p'] < 0.05]
sig_positive = vdf[(vdf['p'] < 0.05) & (vdf['r'] > 0)]

print(f"Sectors tested: {len(vdf)}")
print(f"Mean Pearson r: {vdf['r'].mean():.3f}")
print(f"Median Pearson r: {vdf['r'].median():.3f}")
print(f"Significant positive (p<0.05, r>0): {len(sig_positive)}/{len(vdf)} ({100*len(sig_positive)/len(vdf):.0f}%)")
print(f"Significant (p<0.05): {len(sig)}/{len(vdf)} ({100*len(sig)/len(vdf):.0f}%)")

print("\nSector-by-sector results:")
for _, row in vdf.iterrows():
    s = row['sector'][:55]
    star = '***' if row['p'] < 0.001 else '**' if row['p'] < 0.01 else '*' if row['p'] < 0.05 else ''
    print(f"  {s:55s} r={row['r']:+.3f} {star:3s} (rho={row['rho']:+.3f}, N={row['n']})")

# Overall: pool all country-sector pairs and correlate with OWID
print("\n" + "="*70)
print("POOLED VALIDATION (all country-sector pairs)")
print("="*70)

all_merged = pd.merge(cs[['country', 'exiobase_sector', 'ci']], 
                       o15[['iso', 'co2_per_gdp']], 
                       left_on='country', right_on='iso')
r_pool, p_pool = stats.pearsonr(all_merged['co2_per_gdp'], all_merged['ci'])
rho_pool, p_pool_rho = stats.spearmanr(all_merged['co2_per_gdp'], all_merged['ci'])
print(f"N country-sector pairs: {len(all_merged)}")
print(f"Pearson r = {r_pool:.4f}, p = {p_pool:.6f}")
print(f"Spearman rho = {rho_pool:.4f}, p = {p_pool_rho:.6f}")

# Between-sector variation (how much do sectors differ?)
print("\n" + "="*70)
print("BETWEEN-SECTOR vs WITHIN-SECTOR(CROSS-COUNTRY) VARIATION")
print("="*70)

sector_means = cs.groupby('exiobase_sector')['ci'].mean()
overall_std = cs['ci'].std()
between_sector_std = sector_means.std()
within_sector_std = sdf['std_ci'].mean()

print(f"Overall CI std: {overall_std:.4f}")
print(f"Between-sector std: {between_sector_std:.4f}")
print(f"Within-sector (cross-country) std: {within_sector_std:.4f}")
print(f"Between/Within ratio: {between_sector_std/within_sector_std:.1f}x")
print(f"Variance explained by sector: {(between_sector_std**2)/(overall_std**2)*100:.1f}%")

# Save results
results = {
    'cross_country_variation': {
        'n_sectors': len(sdf),
        'mean_cv': round(cv_mean, 4),
        'mean_max_min_ratio': round(rr_mean, 2),
        'sectors_cv_gt_20pct': int((sdf['cv'] > 0.2).sum()),
        'sectors_cv_gt_50pct': int((sdf['cv'] > 0.5).sum()),
    },
    'owid_validation': {
        'sectors_tested': len(vdf),
        'mean_r': round(vdf['r'].mean(), 4),
        'median_r': round(vdf['r'].median(), 4),
        'significant_positive': int(len(sig_positive)),
        'pct_significant_positive': round(100*len(sig_positive)/len(vdf), 1),
    },
    'pooled_validation': {
        'n_pairs': len(all_merged),
        'pearson_r': round(r_pool, 4),
        'spearman_rho': round(rho_pool, 4),
    },
    'variance_decomposition': {
        'between_sector_std': round(between_sector_std, 4),
        'within_sector_cross_country_std': round(within_sector_std, 4),
        'ratio': round(between_sector_std/within_sector_std, 2),
        'pct_explained_by_sector': round((between_sector_std**2)/(overall_std**2)*100, 1),
    }
}

outpath = PROJECT_ROOT / "results" / "robustness" / "cross_validation_results.json"
with open(outpath, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to {outpath}")
