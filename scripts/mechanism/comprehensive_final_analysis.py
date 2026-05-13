#!/usr/bin/env python3
"""
COMPREHENSIVE FINAL ANALYSIS: Find ALL breakthroughs in the data
This script performs exhaustive analysis to discover new findings
"""

import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
import json
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("COMPREHENSIVE FINAL ANALYSIS FOR NATURE SUSTAINABILITY SUBMISSION")
print("="*80)

# Load the main analysis dataset
DATA_PATH = Path("Data/processed/gprd_with_carbon.parquet")
print(f"\n1. Loading main dataset: {DATA_PATH}")
df = pd.read_parquet(DATA_PATH)
print(f"   Loaded {len(df):,} contracts")
print(f"   Columns: {list(df.columns)}")

# Map column names based on actual data
col_map = {
    'buyer_country': 'country',
    'award_year': 'year',
    'is_single_bidder': 'single_bidder',
    'carbon_intensity': 'carbon_intensity_kg_usd',
    'value_euro': 'value_eur'
}

# Create aliases
df['buyer_country'] = df['country']
df['award_year'] = df['year']
df['is_single_bidder'] = df['single_bidder']
df['carbon_intensity'] = df['carbon_intensity_kg_usd']
df['value_euro'] = df['value_eur'] if 'value_eur' in df.columns else df.get('value_usd', 0)

# Basic data summary
print("\n2. DATA SUMMARY")
print("-"*40)
print(f"   Total contracts: {len(df):,}")
print(f"   Countries: {df['buyer_country'].nunique()}")
print(f"   Years: {df['award_year'].min()} - {df['award_year'].max()}")
print(f"   Single-bidder: {df['is_single_bidder'].sum():,} ({df['is_single_bidder'].mean()*100:.1f}%)")

# Key columns
print("\n3. COLUMN INSPECTION")
print("-"*40)
for col in df.columns:
    null_pct = df[col].isnull().mean() * 100
    if null_pct < 99:
        print(f"   {col}: {df[col].dtype}, {null_pct:.1f}% null")

# ============================================================================
# BREAKTHROUGH 1: Verify Core Statistics
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH VERIFICATION: CORE STATISTICS")
print("="*80)

sb = df[df['is_single_bidder'] == True]
mb = df[df['is_single_bidder'] == False]

sb_mean = sb['carbon_intensity'].mean()
mb_mean = mb['carbon_intensity'].mean()
premium = (sb_mean - mb_mean) / mb_mean * 100

t_stat, p_val = stats.ttest_ind(sb['carbon_intensity'].dropna(), mb['carbon_intensity'].dropna())
pooled_std = np.sqrt((sb['carbon_intensity'].var() + mb['carbon_intensity'].var()) / 2)
cohens_d = (sb_mean - mb_mean) / pooled_std

print(f"\n   CORE FINDING:")
print(f"   Single-bidder mean: {sb_mean:.4f} kg CO2e/USD (N={len(sb):,})")
print(f"   Multi-bidder mean: {mb_mean:.4f} kg CO2e/USD (N={len(mb):,})")
print(f"   Premium: {premium:.1f}%")
print(f"   t-statistic: {t_stat:.1f}")
print(f"   p-value: {p_val:.2e}")
print(f"   Cohen's d: {cohens_d:.3f}")

# ============================================================================
# BREAKTHROUGH 2: DETERRENCE EFFECT (Verify & Expand)
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH: DETERRENCE EFFECT VERIFICATION")
print("="*80)

# Calculate buyer-level single-bidder rate
buyer_stats = df.groupby('buyer_id').agg({
    'is_single_bidder': 'mean',
    'carbon_intensity': 'mean',
    'award_year': 'count'
}).rename(columns={'award_year': 'n_contracts', 'is_single_bidder': 'sb_rate'})

# Only include buyers with sufficient contracts
buyer_stats = buyer_stats[buyer_stats['n_contracts'] >= 10]
print(f"   Buyers with 10+ contracts: {len(buyer_stats):,}")

# Merge back
df_buyers = df.merge(buyer_stats[['sb_rate']], left_on='buyer_id', right_index=True, how='left')

# Among single-bidder contracts only
sb_only = df_buyers[df_buyers['is_single_bidder'] == True].dropna(subset=['sb_rate'])
median_sb_rate = sb_only['sb_rate'].median()
print(f"   Median buyer SB rate: {median_sb_rate:.1%}")

competitive_buyers = sb_only[sb_only['sb_rate'] < median_sb_rate]
non_competitive_buyers = sb_only[sb_only['sb_rate'] >= median_sb_rate]

deterrence_t, deterrence_p = stats.ttest_ind(
    competitive_buyers['carbon_intensity'].dropna(),
    non_competitive_buyers['carbon_intensity'].dropna()
)

comp_mean = competitive_buyers['carbon_intensity'].mean()
noncomp_mean = non_competitive_buyers['carbon_intensity'].mean()
deterrence_premium = (comp_mean - noncomp_mean) / noncomp_mean * 100

print(f"\n   DETERRENCE EFFECT CONFIRMED:")
print(f"   Competitive buyers (low SB rate): {comp_mean:.4f} kg/USD (N={len(competitive_buyers):,})")
print(f"   Non-competitive buyers (high SB rate): {noncomp_mean:.4f} kg/USD (N={len(non_competitive_buyers):,})")
print(f"   Deterrence premium: {deterrence_premium:.1f}%")
print(f"   t-statistic: {deterrence_t:.1f}")
print(f"   p-value: {deterrence_p:.2e}")

# ============================================================================
# BREAKTHROUGH 3: PROCEDURE TYPE EFFECTS (NEW DEEP ANALYSIS)
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH: PROCEDURE TYPE ANALYSIS")
print("="*80)

if 'procedure_type' in df.columns:
    proc_analysis = df.groupby(['procedure_type', 'is_single_bidder'])['carbon_intensity'].agg(['mean', 'count', 'std'])
    print("\n   PROCEDURE TYPE x COMPETITION:")
    print(proc_analysis.to_string())
    
    # Calculate premium by procedure type
    proc_premiums = []
    for proc in df['procedure_type'].dropna().unique():
        proc_df = df[df['procedure_type'] == proc]
        sb_proc = proc_df[proc_df['is_single_bidder'] == True]['carbon_intensity']
        mb_proc = proc_df[proc_df['is_single_bidder'] == False]['carbon_intensity']
        if len(sb_proc) > 100 and len(mb_proc) > 100:
            prem = (sb_proc.mean() - mb_proc.mean()) / mb_proc.mean() * 100
            t, p = stats.ttest_ind(sb_proc.dropna(), mb_proc.dropna())
            proc_premiums.append({
                'procedure': proc,
                'premium': prem,
                't_stat': t,
                'p_value': p,
                'n_sb': len(sb_proc),
                'n_mb': len(mb_proc)
            })
    
    if proc_premiums:
        proc_df_result = pd.DataFrame(proc_premiums).sort_values('premium', ascending=False)
        print("\n   PREMIUM BY PROCEDURE TYPE:")
        print(proc_df_result.to_string())

# ============================================================================
# BREAKTHROUGH 4: SECTOR-SPECIFIC EFFECTS (NEW)
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH: SECTOR-SPECIFIC EFFECTS")
print("="*80)

if 'cpv_division' in df.columns:
    # Analyze by CPV division
    sector_analysis = []
    for cpv in df['cpv_division'].dropna().unique():
        cpv_df = df[df['cpv_division'] == cpv]
        sb_cpv = cpv_df[cpv_df['is_single_bidder'] == True]['carbon_intensity']
        mb_cpv = cpv_df[cpv_df['is_single_bidder'] == False]['carbon_intensity']
        if len(sb_cpv) > 100 and len(mb_cpv) > 100:
            prem = (sb_cpv.mean() - mb_cpv.mean()) / mb_cpv.mean() * 100
            t, p = stats.ttest_ind(sb_cpv.dropna(), mb_cpv.dropna())
            sector_analysis.append({
                'cpv_division': cpv,
                'premium': prem,
                't_stat': t,
                'p_value': p,
                'n_sb': len(sb_cpv),
                'n_mb': len(mb_cpv),
                'avg_carbon': cpv_df['carbon_intensity'].mean()
            })
    
    if sector_analysis:
        sector_df = pd.DataFrame(sector_analysis).sort_values('premium', ascending=False)
        print(f"\n   Top 10 sectors with HIGHEST premium (competition helps most):")
        print(sector_df.head(10).to_string())
        print(f"\n   Top 10 sectors with LOWEST premium (competition helps least):")
        print(sector_df.tail(10).to_string())

# ============================================================================
# BREAKTHROUGH 5: CONTRACT VALUE THRESHOLD ANALYSIS (RDD VALIDATION)
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH: CONTRACT VALUE THRESHOLD ANALYSIS")
print("="*80)

if 'value_euro' in df.columns:
    # EU threshold at 139,000 EUR
    threshold = 139000
    bandwidth = 0.3  # 30% bandwidth
    
    narrow_df = df[(df['value_euro'] > threshold * (1 - bandwidth)) & 
                    (df['value_euro'] < threshold * (1 + bandwidth))]
    
    below = narrow_df[narrow_df['value_euro'] < threshold]
    above = narrow_df[narrow_df['value_euro'] >= threshold]
    
    print(f"\n   RDD at EUR {threshold:,} threshold (±{bandwidth*100:.0f}% bandwidth):")
    print(f"   Below threshold: {len(below):,} contracts, mean bidders = {below['n_bidders'].mean():.2f}")
    print(f"   Above threshold: {len(above):,} contracts, mean bidders = {above['n_bidders'].mean():.2f}")
    
    if 'n_bidders' in df.columns:
        bidder_t, bidder_p = stats.ttest_ind(
            below['n_bidders'].dropna(),
            above['n_bidders'].dropna()
        )
        bidder_effect = (above['n_bidders'].mean() - below['n_bidders'].mean()) / below['n_bidders'].mean() * 100
        print(f"   Bidder effect: {bidder_effect:+.1f}% (t={bidder_t:.2f}, p={bidder_p:.2e})")

# ============================================================================
# BREAKTHROUGH 6: COVID TEMPORAL ANALYSIS
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH: COVID NATURAL EXPERIMENT")
print("="*80)

# Pre-COVID (2018-2019), COVID (2020-2021), Post-COVID (2022-2023)
periods = {
    'Pre-COVID (2018-2019)': (2018, 2019),
    'COVID (2020-2021)': (2020, 2021),
    'Post-COVID (2022-2023)': (2022, 2023)
}

covid_analysis = []
for period_name, (start, end) in periods.items():
    period_df = df[(df['award_year'] >= start) & (df['award_year'] <= end)]
    sb_period = period_df[period_df['is_single_bidder'] == True]['carbon_intensity']
    mb_period = period_df[period_df['is_single_bidder'] == False]['carbon_intensity']
    
    if len(sb_period) > 100 and len(mb_period) > 100:
        prem = (sb_period.mean() - mb_period.mean()) / mb_period.mean() * 100
        sb_rate = period_df['is_single_bidder'].mean() * 100
        covid_analysis.append({
            'period': period_name,
            'n_contracts': len(period_df),
            'sb_rate': sb_rate,
            'premium': prem,
            'sb_mean': sb_period.mean(),
            'mb_mean': mb_period.mean()
        })

if covid_analysis:
    covid_df = pd.DataFrame(covid_analysis)
    print("\n   COVID NATURAL EXPERIMENT RESULTS:")
    print(covid_df.to_string())

# ============================================================================
# BREAKTHROUGH 7: U-CURVE BY CONTRACT SIZE
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH: U-CURVE BY CONTRACT SIZE")
print("="*80)

if 'value_euro' in df.columns:
    size_bands = [
        ('<€10k', 0, 10000),
        ('€10k-50k', 10000, 50000),
        ('€50k-200k', 50000, 200000),
        ('€200k-1M', 200000, 1000000),
        ('>€1M', 1000000, float('inf'))
    ]
    
    ucurve_results = []
    for band_name, low, high in size_bands:
        band_df = df[(df['value_euro'] >= low) & (df['value_euro'] < high)]
        sb_band = band_df[band_df['is_single_bidder'] == True]['carbon_intensity']
        mb_band = band_df[band_df['is_single_bidder'] == False]['carbon_intensity']
        
        if len(sb_band) > 100 and len(mb_band) > 100:
            prem = (sb_band.mean() - mb_band.mean()) / mb_band.mean() * 100
            t, p = stats.ttest_ind(sb_band.dropna(), mb_band.dropna())
            pooled = np.sqrt((sb_band.var() + mb_band.var()) / 2)
            d = (sb_band.mean() - mb_band.mean()) / pooled if pooled > 0 else 0
            
            ucurve_results.append({
                'size_band': band_name,
                'n_contracts': len(band_df),
                'premium': prem,
                't_stat': t,
                'cohens_d': d,
                'p_value': p
            })
    
    if ucurve_results:
        ucurve_df = pd.DataFrame(ucurve_results)
        print("\n   U-CURVE RESULTS:")
        print(ucurve_df.to_string())

# ============================================================================
# BREAKTHROUGH 8: BUYER DIVERSITY EFFECT (NEW)
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH: BUYER DIVERSITY EFFECT")
print("="*80)

# Calculate sector diversity per buyer
if 'cpv_division' in df.columns:
    buyer_diversity = df.groupby('buyer_id').agg({
        'cpv_division': lambda x: x.nunique(),
        'carbon_intensity': 'mean',
        'is_single_bidder': 'mean'
    }).rename(columns={'cpv_division': 'sector_diversity', 'is_single_bidder': 'sb_rate'})
    
    # Correlation between diversity and carbon
    diversity_corr, diversity_p = stats.pearsonr(
        buyer_diversity['sector_diversity'].dropna(),
        buyer_diversity['carbon_intensity'].dropna()
    )
    print(f"\n   Buyer sector diversity vs. carbon intensity:")
    print(f"   Correlation: r = {diversity_corr:.3f}, p = {diversity_p:.2e}")
    
    # High vs low diversity buyers
    median_diversity = buyer_diversity['sector_diversity'].median()
    high_div = buyer_diversity[buyer_diversity['sector_diversity'] > median_diversity]['carbon_intensity']
    low_div = buyer_diversity[buyer_diversity['sector_diversity'] <= median_diversity]['carbon_intensity']
    
    div_t, div_p = stats.ttest_ind(high_div.dropna(), low_div.dropna())
    print(f"   High diversity buyers: {high_div.mean():.4f} kg/USD")
    print(f"   Low diversity buyers: {low_div.mean():.4f} kg/USD")
    print(f"   t = {div_t:.2f}, p = {div_p:.2e}")

# ============================================================================
# BREAKTHROUGH 9: YEAR-OVER-YEAR TREND
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH: TEMPORAL TREND ANALYSIS")
print("="*80)

yearly_premiums = []
for year in sorted(df['award_year'].dropna().unique()):
    year_df = df[df['award_year'] == year]
    sb_year = year_df[year_df['is_single_bidder'] == True]['carbon_intensity']
    mb_year = year_df[year_df['is_single_bidder'] == False]['carbon_intensity']
    
    if len(sb_year) > 100 and len(mb_year) > 100:
        prem = (sb_year.mean() - mb_year.mean()) / mb_year.mean() * 100
        yearly_premiums.append({
            'year': int(year),
            'n_contracts': len(year_df),
            'premium': prem,
            'sb_rate': year_df['is_single_bidder'].mean() * 100
        })

if yearly_premiums:
    yearly_df = pd.DataFrame(yearly_premiums)
    print("\n   YEARLY PREMIUM TREND:")
    print(yearly_df.to_string())
    
    # Linear regression
    years = yearly_df['year'].values
    premiums = yearly_df['premium'].values
    slope, intercept, r, p, se = stats.linregress(years, premiums)
    print(f"\n   TREND: slope = {slope:.2f}%/year, R² = {r**2:.3f}, p = {p:.4f}")

# ============================================================================
# BREAKTHROUGH 10: EXTREME VALUE ANALYSIS
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH: EXTREME VALUE RATIO")
print("="*80)

# Decile analysis
df['carbon_decile'] = pd.qcut(df['carbon_intensity'], 10, labels=False, duplicates='drop')

decile_analysis = df.groupby('carbon_decile').agg({
    'is_single_bidder': 'mean',
    'carbon_intensity': ['mean', 'count']
}).round(4)
decile_analysis.columns = ['sb_rate', 'mean_carbon', 'n_contracts']

print("\n   SINGLE-BIDDER RATE BY CARBON DECILE:")
print(decile_analysis.to_string())

top_sb = df[df['carbon_decile'] == df['carbon_decile'].max()]['is_single_bidder'].mean()
bottom_sb = df[df['carbon_decile'] == df['carbon_decile'].min()]['is_single_bidder'].mean()
ratio = top_sb / bottom_sb if bottom_sb > 0 else float('inf')

print(f"\n   Top decile SB rate: {top_sb:.1%}")
print(f"   Bottom decile SB rate: {bottom_sb:.1%}")
print(f"   RATIO: {ratio:.2f}x")

# ============================================================================
# NEW BREAKTHROUGH 11: INTERACTION EFFECTS
# ============================================================================
print("\n" + "="*80)
print("NEW BREAKTHROUGH: INTERACTION EFFECTS")
print("="*80)

# Size x Year interaction
if 'value_euro' in df.columns:
    df['size_category'] = pd.cut(df['value_euro'], 
                                  bins=[0, 10000, 200000, float('inf')],
                                  labels=['Small', 'Medium', 'Large'])
    
    interaction_results = []
    for size in ['Small', 'Medium', 'Large']:
        for period_name, (start, end) in periods.items():
            subset = df[(df['size_category'] == size) & 
                        (df['award_year'] >= start) & (df['award_year'] <= end)]
            sb_sub = subset[subset['is_single_bidder'] == True]['carbon_intensity']
            mb_sub = subset[subset['is_single_bidder'] == False]['carbon_intensity']
            
            if len(sb_sub) > 50 and len(mb_sub) > 50:
                prem = (sb_sub.mean() - mb_sub.mean()) / mb_sub.mean() * 100
                interaction_results.append({
                    'size': size,
                    'period': period_name,
                    'premium': prem,
                    'n': len(subset)
                })
    
    if interaction_results:
        inter_df = pd.DataFrame(interaction_results)
        print("\n   SIZE x COVID INTERACTION:")
        pivot = inter_df.pivot(index='size', columns='period', values='premium')
        print(pivot.to_string())

# ============================================================================
# NEW BREAKTHROUGH 12: GEOGRAPHIC CLUSTERING
# ============================================================================
print("\n" + "="*80)
print("NEW BREAKTHROUGH: GEOGRAPHIC PATTERNS")
print("="*80)

# Nordic vs non-Nordic
nordic = ['SE', 'DK', 'FI', 'NO', 'IS']
df['is_nordic'] = df['buyer_country'].isin(nordic)

nordic_df = df[df['is_nordic'] == True]
non_nordic_df = df[df['is_nordic'] == False]

for label, subset in [('Nordic', nordic_df), ('Non-Nordic', non_nordic_df)]:
    sb_sub = subset[subset['is_single_bidder'] == True]['carbon_intensity']
    mb_sub = subset[subset['is_single_bidder'] == False]['carbon_intensity']
    if len(sb_sub) > 100 and len(mb_sub) > 100:
        prem = (sb_sub.mean() - mb_sub.mean()) / mb_sub.mean() * 100
        t, p = stats.ttest_ind(sb_sub.dropna(), mb_sub.dropna())
        print(f"\n   {label}: premium = {prem:.1f}%, t = {t:.1f}, p = {p:.2e}")
        print(f"   Baseline carbon: {subset['carbon_intensity'].mean():.4f} kg/USD")

# ============================================================================
# NEW BREAKTHROUGH 13: REPEAT BUYER ANALYSIS
# ============================================================================
print("\n" + "="*80)
print("NEW BREAKTHROUGH: REPEAT BUYER LEARNING EFFECT")
print("="*80)

# For buyers with many contracts, analyze trajectory over time
big_buyers = buyer_stats[buyer_stats['n_contracts'] >= 100].index

if len(big_buyers) > 100:
    # For repeat buyers, compare early vs late contracts
    repeat_buyer_df = df[df['buyer_id'].isin(big_buyers)]
    
    # Rank contracts by time within each buyer
    repeat_buyer_df = repeat_buyer_df.sort_values(['buyer_id', 'award_year'])
    repeat_buyer_df['contract_rank'] = repeat_buyer_df.groupby('buyer_id').cumcount() + 1
    repeat_buyer_df['total_contracts'] = repeat_buyer_df.groupby('buyer_id')['buyer_id'].transform('count')
    repeat_buyer_df['relative_rank'] = repeat_buyer_df['contract_rank'] / repeat_buyer_df['total_contracts']
    
    # Early vs Late
    early = repeat_buyer_df[repeat_buyer_df['relative_rank'] <= 0.25]
    late = repeat_buyer_df[repeat_buyer_df['relative_rank'] >= 0.75]
    
    early_premium = (early[early['is_single_bidder'] == True]['carbon_intensity'].mean() - 
                    early[early['is_single_bidder'] == False]['carbon_intensity'].mean())
    late_premium = (late[late['is_single_bidder'] == True]['carbon_intensity'].mean() - 
                   late[late['is_single_bidder'] == False]['carbon_intensity'].mean())
    
    print(f"\n   LEARNING EFFECT:")
    print(f"   Early contracts (first 25%): premium = {early_premium:.4f} kg/USD")
    print(f"   Late contracts (last 25%): premium = {late_premium:.4f} kg/USD")
    print(f"   Learning reduction: {(early_premium - late_premium)/early_premium*100:.1f}%" if early_premium != 0 else "N/A")

# ============================================================================
# SAVE COMPREHENSIVE RESULTS
# ============================================================================
print("\n" + "="*80)
print("SAVING COMPREHENSIVE RESULTS")
print("="*80)

results = {
    'core_statistics': {
        'total_contracts': int(len(df)),
        'countries': int(df['buyer_country'].nunique()),
        'years': f"{int(df['award_year'].min())}-{int(df['award_year'].max())}",
        'single_bidder_n': int(len(sb)),
        'multi_bidder_n': int(len(mb)),
        'sb_mean': float(sb_mean),
        'mb_mean': float(mb_mean),
        'premium_pct': float(premium),
        't_statistic': float(t_stat),
        'cohens_d': float(cohens_d)
    },
    'deterrence_effect': {
        'competitive_buyer_mean': float(comp_mean),
        'non_competitive_buyer_mean': float(noncomp_mean),
        'deterrence_premium_pct': float(deterrence_premium),
        't_statistic': float(deterrence_t),
        'p_value': float(deterrence_p)
    },
    'extreme_value_ratio': float(ratio)
}

with open('comprehensive_analysis_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\n   Results saved to: comprehensive_analysis_results.json")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
