"""
COMPREHENSIVE BREAKTHROUGH ANALYSIS
===================================
Searching for additional breakthroughs and validating all claims
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("COMPREHENSIVE BREAKTHROUGH ANALYSIS")
print("="*80)

# Load data
print("\n[1] Loading data...")
df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet')
print(f"Total contracts: {len(df):,}")
print(f"Countries: {df['country'].nunique()}")
print(f"Year range: {df['year'].min()} to {df['year'].max()}")

# Show available columns
print(f"\nAvailable columns: {list(df.columns)}")

# Rename for consistency
df['is_single_bidder'] = df['single_bidder']

# ============================================================================
# BREAKTHROUGH 1: WITHIN-SECTOR VARIANCE ANALYSIS
# Can we detect firm-level variation WITHIN sectors?
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 1: WITHIN-SECTOR VARIANCE ANALYSIS")
print("="*80)

# Calculate within-sector carbon intensity variance
sector_stats = df.groupby('exiobase_sector').agg({
    'carbon_intensity_kg_usd': ['mean', 'std', 'count'],
    'is_single_bidder': 'mean',
    'value_eur': 'mean'
}).reset_index()
sector_stats.columns = ['sector', 'carbon_mean', 'carbon_std', 'n', 'sb_rate', 'avg_value']

# Only sectors with enough contracts
sector_stats = sector_stats[sector_stats['n'] >= 1000]
sector_stats['cv'] = sector_stats['carbon_std'] / sector_stats['carbon_mean']

# Calculate within-sector competition effect
print("\nCalculating WITHIN-SECTOR competition effect for each sector...")
within_sector_effects = []

for sector in df['exiobase_sector'].unique():
    sector_df = df[df['exiobase_sector'] == sector]
    if len(sector_df) < 1000:
        continue
    
    sb = sector_df[sector_df['is_single_bidder'] == True]['carbon_intensity_kg_usd']
    mb = sector_df[sector_df['is_single_bidder'] == False]['carbon_intensity_kg_usd']
    
    if len(sb) < 100 or len(mb) < 100:
        continue
    
    # Since EXIOBASE assigns same carbon to same sector, any difference must be:
    # 1. Within-sector heterogeneity from country-sector variation
    # 2. Year variation
    # 3. Value-weighted effects
    
    diff = sb.mean() - mb.mean()
    pct_diff = 100 * diff / mb.mean() if mb.mean() > 0 else 0
    t_stat, p_val = stats.ttest_ind(sb, mb)
    
    within_sector_effects.append({
        'sector': sector,
        'n_sb': len(sb),
        'n_mb': len(mb),
        'sb_mean': sb.mean(),
        'mb_mean': mb.mean(),
        'diff': diff,
        'pct_diff': pct_diff,
        't_stat': t_stat,
        'p_val': p_val
    })

ws_df = pd.DataFrame(within_sector_effects)
ws_df = ws_df.sort_values('pct_diff', ascending=False)

print("\nTop 10 sectors where single-bidder has HIGHER carbon (within-sector):")
print(ws_df[ws_df['pct_diff'] > 0].head(10)[['sector', 'pct_diff', 't_stat', 'p_val', 'n_sb', 'n_mb']].to_string())

print("\nSectors where single-bidder has LOWER carbon:")
print(ws_df[ws_df['pct_diff'] < 0].head(5)[['sector', 'pct_diff', 't_stat', 'p_val', 'n_sb', 'n_mb']].to_string())

# Overall within-sector effect (weighted)
total_sb = ws_df['n_sb'].sum()
total_mb = ws_df['n_mb'].sum()
weighted_effect = (ws_df['pct_diff'] * (ws_df['n_sb'] + ws_df['n_mb'])).sum() / (ws_df['n_sb'] + ws_df['n_mb']).sum()
print(f"\nWeighted average within-sector effect: {weighted_effect:.2f}%")

# Count significant positive effects
sig_positive = ws_df[(ws_df['pct_diff'] > 0) & (ws_df['p_val'] < 0.05)]
sig_negative = ws_df[(ws_df['pct_diff'] < 0) & (ws_df['p_val'] < 0.05)]
print(f"Sectors with significant POSITIVE premium: {len(sig_positive)}")
print(f"Sectors with significant NEGATIVE premium: {len(sig_negative)}")

# ============================================================================
# BREAKTHROUGH 2: PRICE EFFICIENCY ANALYSIS (DOUBLE DIVIDEND)
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 2: PRICE/VALUE ANALYSIS (DOUBLE DIVIDEND)")
print("="*80)

# Check for price-related columns
price_cols = [c for c in df.columns if 'price' in c.lower() or 'value' in c.lower() or 'cost' in c.lower()]
print(f"Price-related columns: {price_cols}")

# Analyze contract value as proxy for efficiency
# Higher value for same sector = potentially higher prices
print("\nAnalyzing contract value patterns...")

# Within-sector: Are single-bidder contracts worth more (=higher prices)?
value_effects = []
for sector in df['exiobase_sector'].unique():
    sector_df = df[df['exiobase_sector'] == sector]
    if len(sector_df) < 1000:
        continue
    
    sb = sector_df[sector_df['is_single_bidder'] == True]['value_eur']
    mb = sector_df[sector_df['is_single_bidder'] == False]['value_eur']
    
    if len(sb) < 100 or len(mb) < 100:
        continue
    
    # Use median to handle outliers
    diff = sb.median() - mb.median()
    pct_diff = 100 * diff / mb.median() if mb.median() > 0 else 0
    
    value_effects.append({
        'sector': sector,
        'sb_median_eur': sb.median(),
        'mb_median_eur': mb.median(),
        'pct_diff': pct_diff
    })

ve_df = pd.DataFrame(value_effects)
print(f"\nSingle-bidder contracts value premium (within-sector):")
print(f"Mean premium: {ve_df['pct_diff'].mean():.1f}%")
print(f"Median premium: {ve_df['pct_diff'].median():.1f}%")
print(f"Sectors where SB value > MB: {(ve_df['pct_diff'] > 0).sum()} of {len(ve_df)}")

# Overall value comparison
sb_all = df[df['is_single_bidder'] == True]['value_eur']
mb_all = df[df['is_single_bidder'] == False]['value_eur']
print(f"\nOverall median values:")
print(f"Single-bidder: €{sb_all.median():,.0f}")
print(f"Multi-bidder: €{mb_all.median():,.0f}")
print(f"Difference: {100*(sb_all.median()-mb_all.median())/mb_all.median():.1f}%")

# ============================================================================
# BREAKTHROUGH 3: TEMPORAL CARBON INTENSITY TRENDS
# Is there evidence of decarbonization over time?
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 3: TEMPORAL DECARBONIZATION TRENDS")
print("="*80)

year_stats = df.groupby('year').agg({
    'carbon_intensity_kg_usd': 'mean',
    'is_single_bidder': 'mean',
    'n_bidders': 'mean'
}).reset_index()

print("\nYear-over-year trends:")
print(year_stats.to_string())

# Calculate year-over-year change in carbon intensity
if len(year_stats) > 1:
    slope, intercept, r, p, se = stats.linregress(year_stats['year'], year_stats['carbon_intensity_kg_usd'])
    print(f"\nCarbon intensity trend: {slope*100:.4f}% per year (p={p:.4f}, R²={r**2:.3f})")
    
    # How much of decarbonization is explained by reduced single-bidding?
    sb_slope, sb_int, sb_r, sb_p, sb_se = stats.linregress(year_stats['year'], year_stats['is_single_bidder'])
    print(f"Single-bidder rate trend: {sb_slope*100:.4f} pp per year (p={sb_p:.4f})")

# ============================================================================
# BREAKTHROUGH 4: CPV CODE GRANULARITY ANALYSIS
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 4: CPV CODE GRANULARITY")
print("="*80)

# Check for CPV codes
cpv_cols = [c for c in df.columns if 'cpv' in c.lower()]
print(f"CPV columns: {cpv_cols}")

if 'cpv_code' in df.columns:
    # Analyze at 2-digit CPV level
    df['cpv_2digit'] = df['cpv_code'].astype(str).str[:2]
    cpv_stats = df.groupby('cpv_2digit').agg({
        'is_single_bidder': 'mean',
        'carbon_intensity_kg_usd': 'mean',
        'value_eur': ['count', 'sum']
    }).reset_index()
    cpv_stats.columns = ['cpv_2digit', 'sb_rate', 'carbon', 'n_contracts', 'total_value']
    cpv_stats = cpv_stats.sort_values('sb_rate', ascending=False)
    
    print("\nTop 10 CPV categories by single-bidder rate:")
    print(cpv_stats.head(10).to_string())

# ============================================================================
# BREAKTHROUGH 5: COUNTRY-SPECIFIC DECOMPOSITION
# Which countries drive the result?
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 5: COUNTRY CONTRIBUTION DECOMPOSITION")
print("="*80)

country_effects = []
for country in df['country'].unique():
    c_df = df[df['country'] == country]
    
    sb = c_df[c_df['is_single_bidder'] == True]['carbon_intensity_kg_usd']
    mb = c_df[c_df['is_single_bidder'] == False]['carbon_intensity_kg_usd']
    
    if len(sb) < 100 or len(mb) < 100:
        continue
    
    diff = sb.mean() - mb.mean()
    pct_diff = 100 * diff / mb.mean() if mb.mean() > 0 else 0
    t_stat, p_val = stats.ttest_ind(sb, mb)
    
    country_effects.append({
        'country': country,
        'n': len(c_df),
        'sb_rate': c_df['is_single_bidder'].mean() * 100,
        'premium_pct': pct_diff,
        't_stat': t_stat,
        'p_val': p_val,
        'total_carbon': c_df['carbon_intensity_kg_usd'].sum(),
        'contribution_to_global': len(c_df) / len(df) * 100
    })

ce_df = pd.DataFrame(country_effects)
ce_df = ce_df.sort_values('premium_pct', ascending=False)

print("\nCountry-level carbon premiums (sorted by effect size):")
print(ce_df.head(15)[['country', 'n', 'sb_rate', 'premium_pct', 'p_val', 'contribution_to_global']].to_string())

# Identify countries with negative premium
negative_premium = ce_df[ce_df['premium_pct'] < 0]
print(f"\nCountries with NEGATIVE premium (competition increases carbon): {len(negative_premium)}")
print(negative_premium[['country', 'premium_pct', 'p_val']].to_string())

# ============================================================================
# BREAKTHROUGH 6: INTERACTION EFFECTS - COUNTRY × SIZE
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 6: COUNTRY × SIZE INTERACTION")
print("="*80)

# Define size categories
df['size_cat'] = pd.cut(df['value_eur'], 
                        bins=[0, 10000, 200000, float('inf')],
                        labels=['Small (<10k)', 'Medium (10k-200k)', 'Large (>200k)'])

interaction_results = []
for country in df['country'].unique():
    for size in df['size_cat'].dropna().unique():
        subset = df[(df['country'] == country) & (df['size_cat'] == size)]
        if len(subset) < 500:
            continue
        
        sb = subset[subset['is_single_bidder'] == True]['carbon_intensity_kg_usd']
        mb = subset[subset['is_single_bidder'] == False]['carbon_intensity_kg_usd']
        
        if len(sb) < 50 or len(mb) < 50:
            continue
        
        pct_diff = 100 * (sb.mean() - mb.mean()) / mb.mean() if mb.mean() > 0 else 0
        
        interaction_results.append({
            'country': country,
            'size': size,
            'premium_pct': pct_diff,
            'n': len(subset)
        })

int_df = pd.DataFrame(interaction_results)

# Pivot to see pattern
if len(int_df) > 0:
    pivot = int_df.pivot_table(index='country', columns='size', values='premium_pct', aggfunc='mean')
    print("\nCarbon premium by Country × Size (%):")
    print(pivot.round(1).to_string())
    
    # Summary statistics
    print("\nMean premium by size category across countries:")
    print(int_df.groupby('size')['premium_pct'].agg(['mean', 'std', 'count']))

# ============================================================================
# BREAKTHROUGH 7: EXIOBASE SECTOR × YEAR VARIATION
# Can we see temporal decarbonization within sectors?
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 7: SECTOR × YEAR TEMPORAL PATTERNS")
print("="*80)

# Check if carbon intensity varies by year within sectors (evidence of EXIOBASE temporal updates)
sector_year = df.groupby(['exiobase_sector', 'year'])['carbon_intensity_kg_usd'].mean().reset_index()
sector_year_pivot = sector_year.pivot(index='exiobase_sector', columns='year', values='carbon_intensity_kg_usd')

# Calculate year-over-year change for each sector
print("\nSector-level carbon intensity over time (sample sectors):")
print(sector_year_pivot.iloc[:10].round(3).to_string())

# ============================================================================
# BREAKTHROUGH 8: PROCUREMENT AUTHORITY ANALYSIS
# Do certain authorities drive results?
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 8: CONTRACTING AUTHORITY PATTERNS")
print("="*80)

# Check for authority columns
auth_cols = [c for c in df.columns if 'authority' in c.lower() or 'buyer' in c.lower() or 'procur' in c.lower()]
print(f"Authority-related columns: {auth_cols}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "="*80)
print("SUMMARY OF KEY FINDINGS")
print("="*80)

summary = {
    'total_contracts': len(df),
    'countries': df['country'].nunique(),
    'years': f"{df['year'].min()}-{df['year'].max()}",
    'overall_premium_pct': float(100 * (df[df['is_single_bidder']]['carbon_intensity_kg_usd'].mean() - 
                                        df[~df['is_single_bidder']]['carbon_intensity_kg_usd'].mean()) / 
                                  df[~df['is_single_bidder']]['carbon_intensity_kg_usd'].mean()),
    'within_sector_weighted_effect': float(weighted_effect),
    'sectors_with_positive_premium': int(len(sig_positive)),
    'sectors_with_negative_premium': int(len(sig_negative)),
    'countries_with_positive_premium': int((ce_df['premium_pct'] > 0).sum()),
    'countries_with_negative_premium': int((ce_df['premium_pct'] < 0).sum()),
}

print(f"\n1. Overall single-bidder carbon premium: {summary['overall_premium_pct']:.1f}%")
print(f"2. Within-sector weighted effect: {summary['within_sector_weighted_effect']:.1f}%")
print(f"3. Sectors with significant positive premium: {summary['sectors_with_positive_premium']}")
print(f"4. Sectors with significant negative premium: {summary['sectors_with_negative_premium']}")
print(f"5. Countries with positive premium: {summary['countries_with_positive_premium']}")
print(f"6. Countries with negative premium: {summary['countries_with_negative_premium']}")

# Save results
with open('results/other/breakthrough_analysis.json', 'w') as f:
    json.dump(summary, f, indent=2)

print("\n✅ Analysis complete. Results saved to results/breakthrough_analysis.json")
