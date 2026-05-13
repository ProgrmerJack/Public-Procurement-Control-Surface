"""
DEEP BREAKTHROUGH ANALYSIS - Part 2
===================================
Finding additional breakthroughs and validating the Double Dividend
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("DEEP BREAKTHROUGH ANALYSIS - Part 2")
print("="*80)

# Load data
df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet')
df['is_single_bidder'] = df['single_bidder']

print(f"Total contracts: {len(df):,}")

# ============================================================================
# BREAKTHROUGH 9: THE DOUBLE DIVIDEND - Combined Price + Carbon Analysis
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 9: THE DOUBLE DIVIDEND")
print("="*80)

# Calculate standardized price (value relative to sector median)
print("\nCalculating price premium within sectors...")

sector_medians = df.groupby('exiobase_sector')['value_eur'].median().to_dict()
df['sector_median_value'] = df['exiobase_sector'].map(sector_medians)
df['value_ratio'] = df['value_eur'] / df['sector_median_value']

# Compare value ratios between single and multi-bidder
sb_ratio = df[df['is_single_bidder'] == True]['value_ratio']
mb_ratio = df[df['is_single_bidder'] == False]['value_ratio']

print(f"\nWithin-sector value ratio analysis:")
print(f"Single-bidder mean value ratio: {sb_ratio.mean():.3f}x sector median")
print(f"Multi-bidder mean value ratio: {mb_ratio.mean():.3f}x sector median")
print(f"Price premium (single vs multi): {100*(sb_ratio.mean()/mb_ratio.mean() - 1):.1f}%")

# Statistical test
t_stat, p_val = stats.ttest_ind(sb_ratio.dropna(), mb_ratio.dropna())
print(f"t-statistic: {t_stat:.2f}, p-value: {p_val:.2e}")

# THE DOUBLE TAX: Combined carbon + price
carbon_premium = 14.8  # From our analysis
price_premium_within_sector = 100*(sb_ratio.mean()/mb_ratio.mean() - 1)

print(f"\n*** THE DOUBLE TAX ***")
print(f"Carbon Premium: +{carbon_premium:.1f}%")
print(f"Price Premium (within-sector): +{price_premium_within_sector:.1f}%")
print(f"Combined Inefficiency Tax: +{carbon_premium + price_premium_within_sector:.1f}%")

# ============================================================================
# BREAKTHROUGH 10: PROCUREMENT METHOD ANALYSIS
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 10: PROCUREMENT METHOD ANALYSIS")
print("="*80)

method_stats = df.groupby('procurement_method').agg({
    'carbon_intensity_kg_usd': 'mean',
    'is_single_bidder': 'mean',
    'value_eur': ['count', 'median'],
    'n_bidders': 'mean'
}).reset_index()
method_stats.columns = ['method', 'carbon', 'sb_rate', 'n', 'median_value', 'avg_bidders']
method_stats = method_stats.sort_values('carbon', ascending=False)

print("\nProcurement methods by carbon intensity:")
print(method_stats.to_string())

# ============================================================================
# BREAKTHROUGH 11: BUYER CONCENTRATION ANALYSIS
# Do concentrated buyers (few unique suppliers) have higher carbon?
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 11: BUYER BEHAVIOR ANALYSIS")
print("="*80)

# Calculate buyer-level statistics
buyer_stats = df.groupby('buyer_id').agg({
    'supplier_id': 'nunique',
    'carbon_intensity_kg_usd': 'mean',
    'is_single_bidder': 'mean',
    'value_eur': ['count', 'sum']
}).reset_index()
buyer_stats.columns = ['buyer_id', 'unique_suppliers', 'avg_carbon', 'sb_rate', 'n_contracts', 'total_value']

# Only buyers with significant activity
buyer_stats = buyer_stats[buyer_stats['n_contracts'] >= 10]

# Correlation: Do buyers with fewer suppliers have higher carbon?
corr, p = stats.pearsonr(buyer_stats['unique_suppliers'], buyer_stats['avg_carbon'])
print(f"\nCorrelation between supplier diversity and carbon intensity:")
print(f"r = {corr:.4f}, p = {p:.2e}")

# Tercile analysis
buyer_stats['diversity_tercile'] = pd.qcut(buyer_stats['unique_suppliers'], 3, labels=['Low', 'Medium', 'High'])
tercile_stats = buyer_stats.groupby('diversity_tercile').agg({
    'avg_carbon': 'mean',
    'sb_rate': 'mean',
    'n_contracts': 'sum'
})
print("\nBuyer supplier diversity terciles:")
print(tercile_stats.to_string())

# ============================================================================
# BREAKTHROUGH 12: EMERGENCY/CRISIS PROCUREMENT DEEP DIVE
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 12: COVID-19 DETAILED ANALYSIS")
print("="*80)

# Filter to valid year/month data
recent = df[(df['year'] >= 2018) & (df['year'].notna()) & (df['month'].notna())]
recent['year_int'] = recent['year'].astype(int)
recent['month_int'] = recent['month'].fillna(1).astype(int)

# Focus on 2018-2023
yearly_stats = recent.groupby('year_int').agg({
    'carbon_intensity_kg_usd': 'mean',
    'is_single_bidder': 'mean',
    'n_bidders': 'mean',
    'value_eur': ['count', 'mean']
}).reset_index()
yearly_stats.columns = ['year', 'carbon', 'sb_rate', 'avg_bidders', 'n_contracts', 'avg_value']

print("\nYearly trends (2018-2023):")
print(yearly_stats.to_string())

# Calculate carbon premium by year
yearly_premium = []
for y in recent['year_int'].unique():
    y_df = recent[recent['year_int'] == y]
    sb = y_df[y_df['is_single_bidder'] == True]['carbon_intensity_kg_usd'].mean()
    mb = y_df[y_df['is_single_bidder'] == False]['carbon_intensity_kg_usd'].mean()
    prem = 100 * (sb - mb) / mb if mb > 0 else 0
    yearly_premium.append({'year': y, 'premium': prem})

yp_df = pd.DataFrame(yearly_premium).sort_values('year')
print("\nSingle-bidder carbon premium by year:")
print(yp_df.to_string())

# Pre-COVID vs COVID vs Post-COVID
pre_covid = df[df['year'].isin([2018, 2019])]
covid = df[df['year'].isin([2020, 2021])]
post_covid = df[df['year'].isin([2022, 2023])]

def calc_premium(subset):
    sb = subset[subset['is_single_bidder'] == True]['carbon_intensity_kg_usd'].mean()
    mb = subset[subset['is_single_bidder'] == False]['carbon_intensity_kg_usd'].mean()
    return 100 * (sb - mb) / mb if mb > 0 else 0

print("\n*** COVID NATURAL EXPERIMENT ***")
print(f"Pre-COVID (2018-2019) premium: {calc_premium(pre_covid):.1f}%")
print(f"COVID (2020-2021) premium: {calc_premium(covid):.1f}%")
print(f"Post-COVID (2022-2023) premium: {calc_premium(post_covid):.1f}%")

# Single-bidder rates during these periods
print(f"\nSingle-bidder rates:")
print(f"Pre-COVID: {100*pre_covid['is_single_bidder'].mean():.1f}%")
print(f"COVID: {100*covid['is_single_bidder'].mean():.1f}%")
print(f"Post-COVID: {100*post_covid['is_single_bidder'].mean():.1f}%")

# ============================================================================
# BREAKTHROUGH 13: SECTOR-COUNTRY INTERACTION (2D HEATMAP DATA)
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 13: SECTOR × COUNTRY PREMIUM PATTERNS")
print("="*80)

# Top sectors and top countries
top_sectors = df['exiobase_sector'].value_counts().head(10).index.tolist()
top_countries = ['DE', 'FR', 'PL', 'ES', 'IT', 'CO', 'GB', 'CZ', 'GR', 'LT']

interaction_data = []
for sector in top_sectors:
    for country in top_countries:
        subset = df[(df['exiobase_sector'] == sector) & (df['country'] == country)]
        if len(subset) < 500:
            continue
        
        sb = subset[subset['is_single_bidder'] == True]['carbon_intensity_kg_usd']
        mb = subset[subset['is_single_bidder'] == False]['carbon_intensity_kg_usd']
        
        if len(sb) < 50 or len(mb) < 50:
            continue
        
        prem = 100 * (sb.mean() - mb.mean()) / mb.mean() if mb.mean() > 0 else 0
        interaction_data.append({'sector': sector, 'country': country, 'premium': prem, 'n': len(subset)})

int_df = pd.DataFrame(interaction_data)
if len(int_df) > 0:
    pivot = int_df.pivot_table(index='sector', columns='country', values='premium')
    print("\nSector × Country carbon premium (%):")
    print(pivot.round(1).to_string())

# ============================================================================
# BREAKTHROUGH 14: CARBON FOOTPRINT TOTAL IMPACT
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 14: TOTAL CARBON FOOTPRINT IMPACT")
print("="*80)

# Total carbon footprint
total_carbon = df['carbon_footprint_tonnes'].sum()
sb_carbon = df[df['is_single_bidder'] == True]['carbon_footprint_tonnes'].sum()
mb_carbon = df[df['is_single_bidder'] == False]['carbon_footprint_tonnes'].sum()

print(f"\nTotal carbon footprint: {total_carbon/1e9:.2f} billion tonnes CO2e")
print(f"Single-bidder contracts: {sb_carbon/1e9:.2f} billion tonnes ({100*sb_carbon/total_carbon:.1f}%)")
print(f"Multi-bidder contracts: {mb_carbon/1e9:.2f} billion tonnes ({100*mb_carbon/total_carbon:.1f}%)")

# If single-bidder contracts achieved multi-bidder intensity
sb_contracts = df[df['is_single_bidder'] == True]
mb_avg_intensity = df[df['is_single_bidder'] == False]['carbon_intensity_kg_usd'].mean()
sb_value_total = sb_contracts['value_usd'].sum()

# Counterfactual carbon if SB contracts had MB intensity
counterfactual_carbon = sb_value_total * mb_avg_intensity / 1000  # Convert to tonnes
actual_sb_carbon = sb_carbon

savings_potential = actual_sb_carbon - counterfactual_carbon
print(f"\nCounterfactual analysis:")
print(f"Actual SB carbon: {actual_sb_carbon/1e6:.1f} million tonnes")
print(f"If SB had MB intensity: {counterfactual_carbon/1e6:.1f} million tonnes")
print(f"Potential savings: {savings_potential/1e6:.1f} million tonnes")
print(f"Savings as % of total: {100*savings_potential/total_carbon:.2f}%")

# ============================================================================
# BREAKTHROUGH 15: EXTREME VALUE ANALYSIS (Model-Free Validation)
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH 15: EXTREME VALUE ANALYSIS")
print("="*80)

# Top and bottom carbon deciles
df['carbon_decile'] = pd.qcut(df['carbon_intensity_kg_usd'], 10, labels=False, duplicates='drop')

decile_sb_rates = df.groupby('carbon_decile')['is_single_bidder'].mean() * 100
print("\nSingle-bidder rate by carbon intensity decile:")
print(decile_sb_rates.round(2).to_string())

# Key ratio
bottom_decile_sb = df[df['carbon_decile'] == 0]['is_single_bidder'].mean() * 100
top_decile_sb = df[df['carbon_decile'] == df['carbon_decile'].max()]['is_single_bidder'].mean() * 100
print(f"\nBottom decile (cleanest) SB rate: {bottom_decile_sb:.1f}%")
print(f"Top decile (dirtiest) SB rate: {top_decile_sb:.1f}%")
print(f"Ratio: {top_decile_sb/bottom_decile_sb:.2f}x")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("BREAKTHROUGH SUMMARY")
print("="*80)

summary = {
    'double_tax': {
        'carbon_premium': carbon_premium,
        'price_premium_within_sector': float(price_premium_within_sector),
        'combined_inefficiency': float(carbon_premium + price_premium_within_sector)
    },
    'covid_natural_experiment': {
        'pre_covid_premium': float(calc_premium(pre_covid)),
        'covid_premium': float(calc_premium(covid)),
        'post_covid_premium': float(calc_premium(post_covid)),
        'pre_covid_sb_rate': float(pre_covid['is_single_bidder'].mean()),
        'covid_sb_rate': float(covid['is_single_bidder'].mean()),
        'post_covid_sb_rate': float(post_covid['is_single_bidder'].mean())
    },
    'extreme_value': {
        'top_decile_sb_rate': float(top_decile_sb),
        'bottom_decile_sb_rate': float(bottom_decile_sb),
        'ratio': float(top_decile_sb/bottom_decile_sb)
    },
    'total_impact': {
        'total_carbon_billion_tonnes': float(total_carbon/1e9),
        'savings_potential_million_tonnes': float(savings_potential/1e6)
    }
}

print(json.dumps(summary, indent=2))

with open('results/other/deep_breakthrough_analysis.json', 'w') as f:
    json.dump(summary, f, indent=2)

print("\n✅ Deep analysis complete!")
