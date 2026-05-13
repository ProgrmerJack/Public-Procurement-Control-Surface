#!/usr/bin/env python3
"""
Enhanced EU ETS within-sector analysis using facility-level EUTL data.
"""

import pandas as pd
import numpy as np
import json
import zipfile
import os
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

print("\n" + "="*80)
print("STEP 1: LOADING FACILITY-LEVEL EUTL DATA")
print("="*80)

# Extract EUTL data
eutl_zip = 'Data/eutl_data.zip'
with zipfile.ZipFile(eutl_zip, 'r') as z:
    # Load key tables
    installation_df = pd.read_csv(z.open('installation.csv'), low_memory=False)
    activity_df = pd.read_csv(z.open('activity_type.csv'))
    compliance_df = pd.read_csv(z.open('compliance.csv'), low_memory=False)
    
print(f"✓ Installation data: {len(installation_df)} facilities")
print(f"✓ Activity types: {len(activity_df)} types")
print(f"✓ Compliance data: {len(compliance_df)} records")

# ============================================================================
# 2. PREPARE FACILITY-LEVEL DATA
# ============================================================================

print("\n" + "="*80)
print("STEP 2: PREPARING FACILITY-LEVEL EMISSIONS DATA")
print("="*80)

# Get emissions by facility
facility_emissions = compliance_df[['installation_id', 'year', 'verified']].copy()
facility_emissions = facility_emissions.dropna(subset=['verified'])
facility_emissions['verified'] = pd.to_numeric(facility_emissions['verified'], errors='coerce')
facility_emissions = facility_emissions[facility_emissions['verified'] > 0]

# Merge with installation data to get sector and country
facility_emissions = facility_emissions.merge(
    installation_df[['id', 'activity_id', 'country_id']],
    left_on='installation_id',
    right_on='id',
    how='left'
)

# Merge with activity types to get sector names
facility_emissions = facility_emissions.merge(
    activity_df.rename(columns={'id': 'activity_id', 'description': 'sector'}),
    on='activity_id',
    how='left'
)

facility_emissions = facility_emissions.dropna(subset=['sector', 'country_id', 'year'])
facility_emissions = facility_emissions.rename(columns={'country_id': 'country', 'verified': 'emission'})

print(f"✓ Facility-year-emission records: {len(facility_emissions)}")
print(f"  Countries: {facility_emissions['country'].nunique()}")
print(f"  Sectors: {facility_emissions['sector'].nunique()}")
print(f"  Years: {facility_emissions['year'].min()}-{facility_emissions['year'].max()}")

print(f"\nSector coverage:")
sector_counts = facility_emissions['sector'].value_counts()
print(sector_counts.head(10).to_string())

# ============================================================================
# 3. CALCULATE WITHIN-SECTOR FACILITY-LEVEL VARIATION
# ============================================================================

print("\n" + "="*80)
print("STEP 3: CALCULATING FACILITY-LEVEL WITHIN-SECTOR VARIATION")
print("="*80)

facility_stats = []

for (country, sector, year), group in facility_emissions.groupby(['country', 'sector', 'year']):
    emissions = group['emission'].values
    
    if len(emissions) >= 2:  # Need at least 2 facilities for variation metrics
        mean_em = np.mean(emissions)
        std_em = np.std(emissions)
        cv = (std_em / mean_em) if mean_em > 0 else 0
        
        p10 = np.percentile(emissions, 10)
        p25 = np.percentile(emissions, 25)
        p50 = np.percentile(emissions, 50)
        p75 = np.percentile(emissions, 75)
        p90 = np.percentile(emissions, 90)
        
        ratio_p90_p10 = p90 / p10 if p10 > 0 else np.nan
        ratio_p90_p50 = p90 / p50 if p50 > 0 else np.nan
        ratio_p50_p10 = p50 / p10 if p10 > 0 else np.nan
        
        # Gini coefficient
        sorted_em = np.sort(emissions)
        n = len(sorted_em)
        gini = (2 * np.sum((n + 1 - np.arange(1, n+1)) * sorted_em)) / (n * np.sum(sorted_em)) - (n + 1) / n
        
        facility_stats.append({
            'country': country,
            'sector': sector,
            'year': year,
            'n_facilities': len(emissions),
            'mean_emissions': mean_em,
            'std_emissions': std_em,
            'cv': cv,
            'p10': p10,
            'p25': p25,
            'p50': p50,
            'p75': p75,
            'p90': p90,
            'p90_p10_ratio': ratio_p90_p10,
            'p90_p50_ratio': ratio_p90_p50,
            'p50_p10_ratio': ratio_p50_p10,
            'gini': gini,
            'min': np.min(emissions),
            'max': np.max(emissions)
        })

df_facility_stats = pd.DataFrame(facility_stats)

print(f"\n✓ Calculated statistics for {len(df_facility_stats)} sector-country-year groups")
print(f"  Average facilities per group: {df_facility_stats['n_facilities'].mean():.1f}")

# ============================================================================
# 4. OVERALL WITHIN-SECTOR VARIATION SUMMARY
# ============================================================================

print("\n" + "="*80)
print("STEP 4: WITHIN-SECTOR VARIATION SUMMARY STATISTICS")
print("="*80)

print("\nCoefficient of Variation (CV):")
cv_stats = {
    'mean': df_facility_stats['cv'].mean(),
    'median': df_facility_stats['cv'].median(),
    'std': df_facility_stats['cv'].std(),
    'p25': df_facility_stats['cv'].quantile(0.25),
    'p75': df_facility_stats['cv'].quantile(0.75),
    'min': df_facility_stats['cv'].min(),
    'max': df_facility_stats['cv'].max()
}

for k, v in cv_stats.items():
    print(f"  {k:10s}: {v:.4f}")

print("\nP90/P10 Ratios:")
p90p10_stats = {
    'mean': df_facility_stats['p90_p10_ratio'].mean(),
    'median': df_facility_stats['p90_p10_ratio'].median(),
    'std': df_facility_stats['p90_p10_ratio'].std(),
    'p25': df_facility_stats['p90_p10_ratio'].quantile(0.25),
    'p75': df_facility_stats['p90_p10_ratio'].quantile(0.75),
}

for k, v in p90p10_stats.items():
    if not np.isnan(v):
        print(f"  {k:10s}: {v:.2f}x")

print("\nGini Coefficients:")
gini_stats = {
    'mean': df_facility_stats['gini'].mean(),
    'median': df_facility_stats['gini'].median(),
    'std': df_facility_stats['gini'].std(),
    'p25': df_facility_stats['gini'].quantile(0.25),
    'p75': df_facility_stats['gini'].quantile(0.75),
}

for k, v in gini_stats.items():
    print(f"  {k:10s}: {v:.4f}")

# Top sectors by variation
print("\n" + "-"*80)
print("TOP 15 SECTORS BY WITHIN-SECTOR VARIATION (CV):")
print("-"*80)

sector_summary = df_facility_stats.groupby('sector').agg({
    'cv': ['mean', 'median', 'std', 'count'],
    'p90_p10_ratio': 'mean',
    'gini': 'mean',
    'n_facilities': 'mean'
}).round(4)

sector_summary.columns = ['_'.join(col).strip() for col in sector_summary.columns.values]
sector_summary = sector_summary.sort_values('cv_mean', ascending=False)

for idx, (sector, row) in enumerate(sector_summary.head(15).iterrows(), 1):
    print(f"\n{idx}. {sector}")
    print(f"   CV: {row['cv_mean']:.4f} (median: {row['cv_median']:.4f})")
    print(f"   P90/P10: {row['p90_p10_ratio_mean']:.2f}x")
    print(f"   Gini: {row['gini_mean']:.4f}")
    print(f"   Facilities/group: {row['n_facilities_mean']:.1f}, Groups: {int(row['cv_count'])}")

# ============================================================================
# 5. ESTIMATE CORRECTED PROCUREMENT PREMIUM
# ============================================================================

print("\n" + "="*80)
print("STEP 5: ESTIMATING CORRECTED PROCUREMENT PREMIUM")
print("="*80)

premium_scenarios = {
    'p25_vs_p50': (df_facility_stats['p50'] - df_facility_stats['p25']) / df_facility_stats['p50'] * 100,
    'p10_vs_p50': (df_facility_stats['p50'] - df_facility_stats['p10']) / df_facility_stats['p50'] * 100,
    'p25_vs_p75': (df_facility_stats['p75'] - df_facility_stats['p25']) / df_facility_stats['p75'] * 100,
    'p10_vs_p90': (df_facility_stats['p90'] - df_facility_stats['p10']) / df_facility_stats['p90'] * 100,
}

print("\nProcurement Premium Scenarios (% emissions reduction):")
for scenario, values in premium_scenarios.items():
    values = values[values.notna()]
    print(f"\n{scenario}:")
    print(f"  Mean: {values.mean():6.2f}%")
    print(f"  Median: {values.median():6.2f}%")
    print(f"  P25: {values.quantile(0.25):6.2f}%")
    print(f"  P75: {values.quantile(0.75):6.2f}%")
    print(f"  Max: {values.max():6.2f}%")

# ============================================================================
# 6. EFFECT SIZE CALCULATION
# ============================================================================

print("\n" + "="*80)
print("STEP 6: COMPUTING EFFECT SIZES")
print("="*80)

# Cohen's d for within-sector competitive selection
# d = (μ_high - μ_low) / σ

# Scenario 1: Competitive selection at P25 vs average (P50)
d_p25_vs_p50 = (df_facility_stats['p50'] - df_facility_stats['p25']) / df_facility_stats['std_emissions']
d_p25_vs_p50 = d_p25_vs_p50[d_p25_vs_p50.notna()]

# Scenario 2: Selection at P10 vs average  
d_p10_vs_p50 = (df_facility_stats['p50'] - df_facility_stats['p10']) / df_facility_stats['std_emissions']
d_p10_vs_p50 = d_p10_vs_p50[d_p10_vs_p50.notna()]

# Scenario 3: More aggressive: top 25% average vs median
d_aggressive = df_facility_stats['cv'].mean() * (premium_scenarios['p25_vs_p50'].mean() / 100)

print(f"\nCohen's d Effect Sizes:")
print(f"\n  P25 vs P50 (conservative competitive selection):")
print(f"    Mean d: {d_p25_vs_p50.mean():.4f}")
print(f"    Median d: {d_p25_vs_p50.median():.4f}")
print(f"    Std: {d_p25_vs_p50.std():.4f}")

print(f"\n  P10 vs P50 (more aggressive):")
print(f"    Mean d: {d_p10_vs_p50.mean():.4f}")
print(f"    Median d: {d_p10_vs_p50.median():.4f}")
print(f"    Std: {d_p10_vs_p50.std():.4f}")

print(f"\n  Estimate from CV: {-d_aggressive:.4f}")

# ============================================================================
# 7. TELESCOPING ANALYSIS
# ============================================================================

print("\n" + "="*80)
print("STEP 7: MULTI-LEVEL EFFECT SIZE TELESCOPING")
print("="*80)

# Known benchmarks
exiobase_d = -0.08
eurostat_between = -0.178
eurostat_within = -0.002

# Our estimates
our_cv_mean = df_facility_stats['cv'].mean()
our_premium_median = premium_scenarios['p25_vs_p50'].median()
our_d_estimate = -d_p25_vs_p50.median()  # negative because lower is better

print("\n1. EXIOBASE (200 sectors):")
print(f"   - Allocative effect size (d): {exiobase_d:.4f}")
print(f"   - Within-sector variation: 0% (by construction)")

print("\n2. EUROSTAT (648 sectors):")
print(f"   - Between-sector effect: {eurostat_between:.1%}")
print(f"   - Within-sector effect: {eurostat_within:.1%}")

print("\n3. EUTL FACILITY-LEVEL DATA:")
print(f"   - Mean CV: {our_cv_mean:.4f}")
print(f"   - Median procurement premium (P25 vs P50): {our_premium_median:.2f}%")
print(f"   - Estimated effect size (d, P25 vs P50): {our_d_estimate:.4f}")
print(f"   - Amplification vs EXIOBASE: {our_d_estimate/exiobase_d:.1f}x")
print(f"   - Amplification vs Eurostat within: {abs(our_d_estimate)/abs(eurostat_within):.0f}x")

print("\n" + "-"*80)
print("KEY INSIGHT:")
print("-"*80)
print(f"""
EU ETS facility-level data reveals substantial within-sector heterogeneity:

• CV of {our_cv_mean:.4f} indicates significant variation relative to mean
• Firms in the 25th percentile emit {our_premium_median:.1f}% less than median
• This represents a Cohen's d of {our_d_estimate:.4f}

Comparison to aggregated approaches:
• EXIOBASE assumes zero within-sector variation (d=0)
• Our facility data suggests d={our_d_estimate:.4f}
• This is {abs(our_d_estimate)/abs(exiobase_d):.0f}x the magnitude of EXIOBASE's measured effect

This explains a major limitation: EXIOBASE's identical carbon intensities
within country-sectors overlook opportunities that facility-level procurement
could capture through competition for lower-emitting suppliers.
""")

# ============================================================================
# 8. SAVE RESULTS
# ============================================================================

print("\n" + "="*80)
print("STEP 8: SAVING COMPREHENSIVE RESULTS")
print("="*80)

Path('results').mkdir(parents=True, exist_ok=True)

results = {
    'metadata': {
        'analysis_type': 'EU ETS facility-level within-sector carbon intensity',
        'data_sources': ['EUTL facility-level compliance data', 'EU ETS aggregated data'],
        'date_generated': pd.Timestamp.now().isoformat(),
        'description': 'Estimates within-sector carbon heterogeneity and competitive procurement premium',
    },
    'data_summary': {
        'total_facility_records': int(len(facility_emissions)),
        'sector_country_year_groups': int(len(df_facility_stats)),
        'countries': int(facility_emissions['country'].nunique()),
        'sectors': int(facility_emissions['sector'].nunique()),
        'years': f"{int(facility_emissions['year'].min())}-{int(facility_emissions['year'].max())}",
        'avg_facilities_per_group': float(df_facility_stats['n_facilities'].mean()),
    },
    'within_sector_variation': {
        'coefficient_of_variation': {k: float(v) for k, v in cv_stats.items()},
        'p90_p10_ratio': {k: float(v) if not np.isnan(v) else None for k, v in p90p10_stats.items()},
        'gini_coefficient': {k: float(v) for k, v in gini_stats.items()},
    },
    'procurement_premium': {
        'p25_vs_p50_pct': {
            'mean': float(premium_scenarios['p25_vs_p50'].mean()),
            'median': float(premium_scenarios['p25_vs_p50'].median()),
            'p25': float(premium_scenarios['p25_vs_p50'].quantile(0.25)),
            'p75': float(premium_scenarios['p25_vs_p50'].quantile(0.75)),
            'min': float(premium_scenarios['p25_vs_p50'].min()),
            'max': float(premium_scenarios['p25_vs_p50'].max()),
        },
        'p10_vs_p50_pct': {
            'mean': float(premium_scenarios['p10_vs_p50'].mean()),
            'median': float(premium_scenarios['p10_vs_p50'].median()),
            'p25': float(premium_scenarios['p10_vs_p50'].quantile(0.25)),
            'p75': float(premium_scenarios['p10_vs_p50'].quantile(0.75)),
        },
        'p10_vs_p90_pct': {
            'mean': float(premium_scenarios['p10_vs_p90'].mean()),
            'median': float(premium_scenarios['p10_vs_p90'].median()),
        },
    },
    'effect_sizes': {
        'exiobase_200_sectors': {
            'allocative_d': exiobase_d,
            'within_sector_d': 0.0,
            'note': 'Zero within-sector variation by construction'
        },
        'eurostat_648_sectors': {
            'between_sector_effect': eurostat_between,
            'within_sector_effect': eurostat_within,
            'ratio_within_to_between': float(eurostat_within / eurostat_between) if eurostat_between != 0 else 0,
        },
        'eutl_facility_level': {
            'mean_cv': float(our_cv_mean),
            'median_procurement_premium_pct': float(our_premium_median),
            'effect_size_d_p25_vs_p50': {
                'mean': float(d_p25_vs_p50.mean()),
                'median': float(d_p25_vs_p50.median()),
                'std': float(d_p25_vs_p50.std()),
            },
            'effect_size_d_p10_vs_p50': {
                'mean': float(d_p10_vs_p50.mean()),
                'median': float(d_p10_vs_p50.median()),
            },
            'amplification_vs_exiobase': float(our_d_estimate / exiobase_d),
            'amplification_vs_eurostat_within': float(abs(our_d_estimate) / abs(eurostat_within)),
        }
    },
    'key_findings': {
        'within_sector_heterogeneity': f'Facility-level CV of {our_cv_mean:.4f} indicates substantial variation',
        'competitive_premium': f'{our_premium_median:.2f}% reduction when selecting P25 vs median',
        'effect_size': f'Estimated d={our_d_estimate:.4f}, {abs(our_d_estimate)/abs(exiobase_d):.0f}x larger than EXIOBASE',
        'exiobase_limitation': 'Zero within-sector variation severely underestimates procurement leverage',
        'policy_implication': 'Procurement can access significant low-emission suppliers within each country-sector group'
    }
}

with open('results/within_sector/eu_ets_within_sector_analysis.json', 'w') as f:
    json.dump(results, f, indent=2)

print("✓ Results saved to: results/eu_ets_within_sector_analysis.json")

# Save detailed facility statistics
df_facility_stats_clean = df_facility_stats.fillna(0)
df_facility_stats_clean.to_csv('results/csv/facility_level_sector_statistics.csv', index=False)
print("✓ Detailed statistics saved to: results/facility_level_sector_statistics.csv")

# Save top sectors for reference
sector_summary_export = sector_summary.head(20).reset_index()
sector_summary_export.to_csv('results/csv/top_20_sectors_by_heterogeneity.csv', index=False)
print("✓ Top sectors saved to: results/top_20_sectors_by_heterogeneity.csv")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)

# ============================================================================
# 2. PREPARE FACILITY-LEVEL DATA
# ============================================================================

print("\n" + "="*80)
print("STEP 2: PREPARING FACILITY-LEVEL EMISSIONS DATA")
print("="*80)

# Get emissions by facility
facility_emissions = compliance_df[['installation_id', 'year', 'verified_emission']].copy()
facility_emissions = facility_emissions.dropna(subset=['verified_emission'])
facility_emissions['verified_emission'] = pd.to_numeric(facility_emissions['verified_emission'], errors='coerce')
facility_emissions = facility_emissions[facility_emissions['verified_emission'] > 0]

# Merge with installation data to get sector and country
facility_emissions = facility_emissions.merge(
    installation_df[['id', 'mainActivityType_id', 'geolocation_country']],
    left_on='installation_id',
    right_on='id',
    how='left'
)

# Merge with activity types to get sector names
facility_emissions = facility_emissions.merge(
    activity_df.rename(columns={'id': 'mainActivityType_id', 'description': 'sector'}),
    on='mainActivityType_id',
    how='left'
)

facility_emissions = facility_emissions.dropna(subset=['sector', 'geolocation_country', 'year'])

print(f"✓ Facility-year-emission records: {len(facility_emissions)}")
print(f"  Countries: {facility_emissions['geolocation_country'].nunique()}")
print(f"  Sectors: {facility_emissions['sector'].nunique()}")
print(f"  Years: {facility_emissions['year'].min()}-{facility_emissions['year'].max()}")

# ============================================================================
# 3. CALCULATE WITHIN-SECTOR FACILITY-LEVEL VARIATION
# ============================================================================

print("\n" + "="*80)
print("STEP 3: CALCULATING FACILITY-LEVEL WITHIN-SECTOR VARIATION")
print("="*80)

facility_stats = []

for (country, sector, year), group in facility_emissions.groupby(['geolocation_country', 'sector', 'year']):
    emissions = group['verified_emission'].values
    
    if len(emissions) >= 2:  # Need at least 2 facilities for variation metrics
        mean_em = np.mean(emissions)
        std_em = np.std(emissions)
        cv = (std_em / mean_em) if mean_em > 0 else 0
        
        p10 = np.percentile(emissions, 10)
        p25 = np.percentile(emissions, 25)
        p50 = np.percentile(emissions, 50)
        p75 = np.percentile(emissions, 75)
        p90 = np.percentile(emissions, 90)
        
        ratio_p90_p10 = p90 / p10 if p10 > 0 else np.nan
        ratio_p90_p50 = p90 / p50 if p50 > 0 else np.nan
        ratio_p50_p10 = p50 / p10 if p10 > 0 else np.nan
        
        # Gini coefficient
        sorted_em = np.sort(emissions)
        n = len(sorted_em)
        gini = (2 * np.sum((n + 1 - np.arange(1, n+1)) * sorted_em)) / (n * np.sum(sorted_em)) - (n + 1) / n
        
        facility_stats.append({
            'country': country,
            'sector': sector,
            'year': year,
            'n_facilities': len(emissions),
            'mean_emissions': mean_em,
            'std_emissions': std_em,
            'cv': cv,
            'p10': p10,
            'p25': p25,
            'p50': p50,
            'p75': p75,
            'p90': p90,
            'p90_p10_ratio': ratio_p90_p10,
            'p90_p50_ratio': ratio_p90_p50,
            'p50_p10_ratio': ratio_p50_p10,
            'gini': gini,
            'min': np.min(emissions),
            'max': np.max(emissions)
        })

df_facility_stats = pd.DataFrame(facility_stats)

print(f"\n✓ Calculated statistics for {len(df_facility_stats)} sector-country-year groups")
print(f"  With 2+ facilities: {len(df_facility_stats)}")
print(f"  Average facilities per group: {df_facility_stats['n_facilities'].mean():.1f}")

# ============================================================================
# 4. OVERALL WITHIN-SECTOR VARIATION SUMMARY
# ============================================================================

print("\n" + "="*80)
print("STEP 4: WITHIN-SECTOR VARIATION SUMMARY STATISTICS")
print("="*80)

print("\nCoefficient of Variation (CV):")
cv_stats = {
    'mean': df_facility_stats['cv'].mean(),
    'median': df_facility_stats['cv'].median(),
    'std': df_facility_stats['cv'].std(),
    'p25': df_facility_stats['cv'].quantile(0.25),
    'p75': df_facility_stats['cv'].quantile(0.75),
    'min': df_facility_stats['cv'].min(),
    'max': df_facility_stats['cv'].max()
}

for k, v in cv_stats.items():
    if k in ['mean', 'median', 'std', 'min', 'max']:
        print(f"  {k:10s}: {v:.4f}")
    else:
        print(f"  {k:10s}: {v:.4f}")

print("\nP90/P10 Ratios:")
p90p10_stats = {
    'mean': df_facility_stats['p90_p10_ratio'].mean(),
    'median': df_facility_stats['p90_p10_ratio'].median(),
    'std': df_facility_stats['p90_p10_ratio'].std(),
    'p25': df_facility_stats['p90_p10_ratio'].quantile(0.25),
    'p75': df_facility_stats['p90_p10_ratio'].quantile(0.75),
}

for k, v in p90p10_stats.items():
    if not np.isnan(v):
        print(f"  {k:10s}: {v:.2f}x")

print("\nGini Coefficients:")
gini_stats = {
    'mean': df_facility_stats['gini'].mean(),
    'median': df_facility_stats['gini'].median(),
    'std': df_facility_stats['gini'].std(),
    'p25': df_facility_stats['gini'].quantile(0.25),
    'p75': df_facility_stats['gini'].quantile(0.75),
}

for k, v in gini_stats.items():
    print(f"  {k:10s}: {v:.4f}")

# Top sectors by variation
print("\n" + "-"*80)
print("TOP 15 SECTORS BY WITHIN-SECTOR VARIATION (CV):")
print("-"*80)

sector_summary = df_facility_stats.groupby('sector').agg({
    'cv': ['mean', 'median', 'std', 'count'],
    'p90_p10_ratio': 'mean',
    'gini': 'mean',
    'n_facilities': 'mean'
}).round(4)

sector_summary.columns = ['_'.join(col).strip() for col in sector_summary.columns.values]
sector_summary = sector_summary.sort_values('cv_mean', ascending=False)

for idx, (sector, row) in enumerate(sector_summary.head(15).iterrows(), 1):
    print(f"\n{idx}. {sector}")
    print(f"   CV: {row['cv_mean']:.4f} (median: {row['cv_median']:.4f})")
    print(f"   P90/P10: {row['p90_p10_ratio_mean']:.2f}x")
    print(f"   Gini: {row['gini_mean']:.4f}")
    print(f"   Facilities/group: {row['n_facilities_mean']:.1f}, Groups: {int(row['cv_count'])}")

# ============================================================================
# 5. ESTIMATE CORRECTED PROCUREMENT PREMIUM
# ============================================================================

print("\n" + "="*80)
print("STEP 5: ESTIMATING CORRECTED PROCUREMENT PREMIUM")
print("="*80)

premium_scenarios = {
    'p25_vs_p50': (df_facility_stats['p50'] - df_facility_stats['p25']) / df_facility_stats['p50'] * 100,
    'p10_vs_p50': (df_facility_stats['p50'] - df_facility_stats['p10']) / df_facility_stats['p50'] * 100,
    'p25_vs_p75': (df_facility_stats['p75'] - df_facility_stats['p25']) / df_facility_stats['p75'] * 100,
    'p10_vs_p90': (df_facility_stats['p90'] - df_facility_stats['p10']) / df_facility_stats['p90'] * 100,
}

print("\nProcurement Premium Scenarios (% emissions reduction):")
for scenario, values in premium_scenarios.items():
    values = values[values.notna()]
    print(f"\n{scenario}:")
    print(f"  Mean: {values.mean():6.2f}%")
    print(f"  Median: {values.median():6.2f}%")
    print(f"  P25: {values.quantile(0.25):6.2f}%")
    print(f"  P75: {values.quantile(0.75):6.2f}%")
    print(f"  Max: {values.max():6.2f}%")

# ============================================================================
# 6. EFFECT SIZE CALCULATION
# ============================================================================

print("\n" + "="*80)
print("STEP 6: COMPUTING EFFECT SIZES")
print("="*80)

# Cohen's d for within-sector competitive selection
# Assuming normal distribution, d = (μ_high - μ_low) / σ

# Scenario 1: Competitive selection at P25 vs average (P50)
d_p25_vs_p50 = (df_facility_stats['p50'] - df_facility_stats['p25']) / df_facility_stats['std_emissions']
d_p25_vs_p50 = d_p25_vs_p50[d_p25_vs_p50.notna()]

# Scenario 2: Selection at P10 vs average  
d_p10_vs_p50 = (df_facility_stats['p50'] - df_facility_stats['p10']) / df_facility_stats['std_emissions']
d_p10_vs_p50 = d_p10_vs_p50[d_p10_vs_p50.notna()]

# Scenario 3: More aggressive: top 25% average vs median
d_aggressive = df_facility_stats['cv'].mean() * (premium_scenarios['p25_vs_p50'].mean() / 100)

print(f"\nCohen's d Effect Sizes:")
print(f"\n  P25 vs P50 (conservative competitive selection):")
print(f"    Mean d: {d_p25_vs_p50.mean():.4f}")
print(f"    Median d: {d_p25_vs_p50.median():.4f}")
print(f"    Std: {d_p25_vs_p50.std():.4f}")

print(f"\n  P10 vs P50 (more aggressive):")
print(f"    Mean d: {d_p10_vs_p50.mean():.4f}")
print(f"    Median d: {d_p10_vs_p50.median():.4f}")
print(f"    Std: {d_p10_vs_p50.std():.4f}")

print(f"\n  Estimate from CV: {-d_aggressive:.4f}")

# ============================================================================
# 7. TELESCOPING ANALYSIS
# ============================================================================

print("\n" + "="*80)
print("STEP 7: MULTI-LEVEL EFFECT SIZE TELESCOPING")
print("="*80)

# Known benchmarks
exiobase_d = -0.08
eurostat_between = -0.178
eurostat_within = -0.002

# Our estimates
our_cv_mean = df_facility_stats['cv'].mean()
our_premium_median = premium_scenarios['p25_vs_p50'].median()
our_d_estimate = -d_p25_vs_p50.median()  # negative because lower is better

print("\n1. EXIOBASE (200 sectors):")
print(f"   - Allocative effect size (d): {exiobase_d:.4f}")
print(f"   - Within-sector variation: 0% (by construction)")

print("\n2. EUROSTAT (648 sectors):")
print(f"   - Between-sector effect: {eurostat_between:.1%}")
print(f"   - Within-sector effect: {eurostat_within:.1%}")

print("\n3. EUTL FACILITY-LEVEL DATA:")
print(f"   - Mean CV: {our_cv_mean:.4f}")
print(f"   - Median procurement premium (P25 vs P50): {our_premium_median:.2f}%")
print(f"   - Estimated effect size (d, P25 vs P50): {our_d_estimate:.4f}")
print(f"   - Amplification vs EXIOBASE: {our_d_estimate/exiobase_d:.1f}x")
print(f"   - Amplification vs Eurostat within: {our_d_estimate/eurostat_within:.0f}x")

print("\n" + "-"*80)
print("KEY INSIGHT:")
print("-"*80)
print(f"""
EU ETS facility-level data reveals substantial within-sector heterogeneity:

• CV of {our_cv_mean:.4f} indicates significant variation relative to mean
• Firms in the 25th percentile emit {our_premium_median:.1f}% less than median
• This represents a Cohen's d of {our_d_estimate:.4f}

Comparison to aggregated approaches:
• EXIOBASE assumes zero within-sector variation (d=0)
• Our facility data suggests d={our_d_estimate:.4f}
• This is {our_d_estimate/exiobase_d:.0f}x the magnitude of EXIOBASE's measured effect

This explains a major limitation: EXIOBASE's identical carbon intensities
within country-sectors overlook opportunities that facility-level procurement
could capture through competition for lower-emitting suppliers.
""")

# ============================================================================
# 8. SAVE RESULTS
# ============================================================================

print("\n" + "="*80)
print("STEP 8: SAVING COMPREHENSIVE RESULTS")
print("="*80)

Path('results').mkdir(parents=True, exist_ok=True)

results = {
    'metadata': {
        'analysis_type': 'EU ETS facility-level within-sector carbon intensity',
        'data_sources': ['EUTL facility-level compliance data', 'EU ETS aggregated data'],
        'date_generated': pd.Timestamp.now().isoformat(),
        'description': 'Estimates within-sector carbon heterogeneity and competitive procurement premium',
    },
    'data_summary': {
        'total_facility_records': int(len(facility_emissions)),
        'sector_country_year_groups': int(len(df_facility_stats)),
        'countries': int(facility_emissions['geolocation_country'].nunique()),
        'sectors': int(facility_emissions['sector'].nunique()),
        'years': f"{int(facility_emissions['year'].min())}-{int(facility_emissions['year'].max())}",
        'avg_facilities_per_group': float(df_facility_stats['n_facilities'].mean()),
    },
    'within_sector_variation': {
        'coefficient_of_variation': {k: float(v) for k, v in cv_stats.items()},
        'p90_p10_ratio': {k: float(v) if not np.isnan(v) else None for k, v in p90p10_stats.items()},
        'gini_coefficient': {k: float(v) for k, v in gini_stats.items()},
    },
    'procurement_premium': {
        'p25_vs_p50_pct': {
            'mean': float(premium_scenarios['p25_vs_p50'].mean()),
            'median': float(premium_scenarios['p25_vs_p50'].median()),
            'p25': float(premium_scenarios['p25_vs_p50'].quantile(0.25)),
            'p75': float(premium_scenarios['p25_vs_p50'].quantile(0.75)),
            'min': float(premium_scenarios['p25_vs_p50'].min()),
            'max': float(premium_scenarios['p25_vs_p50'].max()),
        },
        'p10_vs_p50_pct': {
            'mean': float(premium_scenarios['p10_vs_p50'].mean()),
            'median': float(premium_scenarios['p10_vs_p50'].median()),
            'p25': float(premium_scenarios['p10_vs_p50'].quantile(0.25)),
            'p75': float(premium_scenarios['p10_vs_p50'].quantile(0.75)),
        },
        'p10_vs_p90_pct': {
            'mean': float(premium_scenarios['p10_vs_p90'].mean()),
            'median': float(premium_scenarios['p10_vs_p90'].median()),
        },
    },
    'effect_sizes': {
        'exiobase_200_sectors': {
            'allocative_d': exiobase_d,
            'within_sector_d': 0.0,
            'note': 'Zero within-sector variation by construction'
        },
        'eurostat_648_sectors': {
            'between_sector_effect': eurostat_between,
            'within_sector_effect': eurostat_within,
            'ratio_within_to_between': float(eurostat_within / eurostat_between) if eurostat_between != 0 else 0,
        },
        'eutl_facility_level': {
            'mean_cv': float(our_cv_mean),
            'median_procurement_premium_pct': float(our_premium_median),
            'effect_size_d_p25_vs_p50': {
                'mean': float(d_p25_vs_p50.mean()),
                'median': float(d_p25_vs_p50.median()),
                'std': float(d_p25_vs_p50.std()),
            },
            'effect_size_d_p10_vs_p50': {
                'mean': float(d_p10_vs_p50.mean()),
                'median': float(d_p10_vs_p50.median()),
            },
            'amplification_vs_exiobase': float(our_d_estimate / exiobase_d),
            'amplification_vs_eurostat_within': float(our_d_estimate / eurostat_within) if eurostat_within != 0 else 'undefined',
        }
    },
    'key_findings': {
        'within_sector_heterogeneity': f'Facility-level CV of {our_cv_mean:.4f} indicates substantial variation',
        'competitive_premium': f'{our_premium_median:.2f}% reduction when selecting P25 vs median',
        'effect_size': f'Estimated d={our_d_estimate:.4f}, {our_d_estimate/exiobase_d:.0f}x larger than EXIOBASE',
        'exiobase_limitation': 'Zero within-sector variation severely underestimates procurement leverage',
        'policy_implication': 'Procurement can access significant low-emission suppliers within each country-sector group'
    }
}

with open('results/within_sector/eu_ets_within_sector_analysis.json', 'w') as f:
    json.dump(results, f, indent=2)

print("✓ Results saved to: results/eu_ets_within_sector_analysis.json")

# Save detailed facility statistics
df_facility_stats_clean = df_facility_stats.fillna(0)
df_facility_stats_clean.to_csv('results/csv/facility_level_sector_statistics.csv', index=False)
print("✓ Detailed statistics saved to: results/facility_level_sector_statistics.csv")

# Save top sectors for reference
sector_summary_export = sector_summary.head(20).reset_index()
sector_summary_export.to_csv('results/csv/top_20_sectors_by_heterogeneity.csv', index=False)
print("✓ Top sectors saved to: results/top_20_sectors_by_heterogeneity.csv")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
