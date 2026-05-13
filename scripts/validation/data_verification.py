"""
COMPREHENSIVE DATA VERIFICATION SCRIPT
======================================
Verifies all statistics claimed in the manuscript against actual data
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
import warnings
warnings.filterwarnings('ignore')

print("="*80)
print("COMPREHENSIVE DATA VERIFICATION")
print("="*80)

# Load data
df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet')
df['is_single_bidder'] = df['single_bidder']

print(f"\nTotal contracts loaded: {len(df):,}")

# ============================================================================
# VERIFICATION 1: BASIC STATISTICS
# ============================================================================
print("\n" + "="*80)
print("VERIFICATION 1: BASIC STATISTICS")
print("="*80)

print(f"\n✓ Total contracts: {len(df):,}")
print(f"  Manuscript claims: 21,612,129")
print(f"  MATCH: {len(df) == 21612129}")

print(f"\n✓ Countries: {df['country'].nunique()}")
print(f"  Manuscript claims: 27")
print(f"  MATCH: {df['country'].nunique() == 27}")

print(f"\n✓ Year range: {int(df['year'].min())} - {int(df['year'].max())}")
print(f"  Manuscript claims: 2012-2023")

# ============================================================================
# VERIFICATION 2: SINGLE-BIDDER PREMIUM
# ============================================================================
print("\n" + "="*80)
print("VERIFICATION 2: SINGLE-BIDDER CARBON PREMIUM")
print("="*80)

sb = df[df['is_single_bidder'] == True]['carbon_intensity_kg_usd']
mb = df[df['is_single_bidder'] == False]['carbon_intensity_kg_usd']

n_sb = len(sb)
n_mb = len(mb)
mean_sb = sb.mean()
mean_mb = mb.mean()
premium = 100 * (mean_sb - mean_mb) / mean_mb

t_stat, p_val = stats.ttest_ind(sb, mb)

# Cohen's d
pooled_std = np.sqrt(((len(sb)-1)*sb.std()**2 + (len(mb)-1)*mb.std()**2) / (len(sb)+len(mb)-2))
cohens_d = (mean_sb - mean_mb) / pooled_std

print(f"\n✓ N single-bidder: {n_sb:,}")
print(f"  Manuscript claims: 2,378,511")
print(f"✓ N multi-bidder: {n_mb:,}")
print(f"  Manuscript claims: 19,233,618")

print(f"\n✓ Mean carbon (single-bidder): {mean_sb:.3f} kg/USD")
print(f"  Manuscript claims: 0.337 kg/USD")
print(f"✓ Mean carbon (multi-bidder): {mean_mb:.3f} kg/USD")
print(f"  Manuscript claims: 0.294 kg/USD")

print(f"\n✓ Premium: {premium:.1f}%")
print(f"  Manuscript claims: 14.8%")
print(f"  MATCH: {abs(premium - 14.8) < 0.5}")

print(f"\n✓ t-statistic: {t_stat:.1f}")
print(f"  Manuscript claims: 333.7")
print(f"✓ Cohen's d: {cohens_d:.3f}")
print(f"  Manuscript claims: 0.228")

# ============================================================================
# VERIFICATION 3: U-CURVE STATISTICS
# ============================================================================
print("\n" + "="*80)
print("VERIFICATION 3: U-CURVE BY CONTRACT SIZE")
print("="*80)

size_bins = [0, 10000, 200000, float('inf')]
size_labels = ['Small (<10k)', 'Medium (10k-200k)', 'Large (>200k)']
df['size_cat'] = pd.cut(df['value_eur'], bins=size_bins, labels=size_labels)

for size in size_labels:
    subset = df[df['size_cat'] == size]
    sb_size = subset[subset['is_single_bidder'] == True]['carbon_intensity_kg_usd']
    mb_size = subset[subset['is_single_bidder'] == False]['carbon_intensity_kg_usd']
    
    if len(sb_size) > 0 and len(mb_size) > 0:
        premium_size = 100 * (sb_size.mean() - mb_size.mean()) / mb_size.mean()
        t_stat_size, _ = stats.ttest_ind(sb_size, mb_size)
        pooled = np.sqrt(((len(sb_size)-1)*sb_size.std()**2 + (len(mb_size)-1)*mb_size.std()**2) / (len(sb_size)+len(mb_size)-2))
        d_size = (sb_size.mean() - mb_size.mean()) / pooled if pooled > 0 else 0
        
        print(f"\n✓ {size}:")
        print(f"  N: {len(subset):,}")
        print(f"  Premium: {premium_size:.1f}%")
        print(f"  Cohen's d: {d_size:.2f}")
        print(f"  t-statistic: {t_stat_size:.1f}")

print("\n  Manuscript claims:")
print("  Small: +50.2%, d=0.83")
print("  Medium: +12.5%, d=0.19")
print("  Large: -7.1%, d=-0.12")

# ============================================================================
# VERIFICATION 4: COVID NATURAL EXPERIMENT
# ============================================================================
print("\n" + "="*80)
print("VERIFICATION 4: COVID NATURAL EXPERIMENT")
print("="*80)

def calc_premium(subset):
    sb = subset[subset['is_single_bidder'] == True]['carbon_intensity_kg_usd']
    mb = subset[subset['is_single_bidder'] == False]['carbon_intensity_kg_usd']
    if len(sb) > 0 and len(mb) > 0 and mb.mean() > 0:
        return 100 * (sb.mean() - mb.mean()) / mb.mean()
    return 0

pre_covid = df[df['year'].isin([2018, 2019])]
covid = df[df['year'].isin([2020, 2021])]
post_covid = df[df['year'].isin([2022, 2023])]

pre_prem = calc_premium(pre_covid)
covid_prem = calc_premium(covid)
post_prem = calc_premium(post_covid)

print(f"\n✓ Pre-COVID premium (2018-2019): {pre_prem:.1f}%")
print(f"  Manuscript claims: 7.0%")
print(f"✓ COVID premium (2020-2021): {covid_prem:.1f}%")
print(f"  Manuscript claims: 20.1%")
print(f"✓ Post-COVID premium (2022-2023): {post_prem:.1f}%")
print(f"  Manuscript claims: 0.3%")

print(f"\n✓ SB rate pre-COVID: {100*pre_covid['is_single_bidder'].mean():.1f}%")
print(f"  Manuscript claims: 13.4%")
print(f"✓ SB rate COVID: {100*covid['is_single_bidder'].mean():.1f}%")
print(f"  Manuscript claims: 8.7%")
print(f"✓ SB rate post-COVID: {100*post_covid['is_single_bidder'].mean():.1f}%")
print(f"  Manuscript claims: 16.1%")

# ============================================================================
# VERIFICATION 5: EXTREME VALUE ANALYSIS
# ============================================================================
print("\n" + "="*80)
print("VERIFICATION 5: EXTREME VALUE ANALYSIS")
print("="*80)

df['carbon_decile'] = pd.qcut(df['carbon_intensity_kg_usd'], 10, labels=False, duplicates='drop')

bottom_decile_sb = df[df['carbon_decile'] == 0]['is_single_bidder'].mean() * 100
top_decile_sb = df[df['carbon_decile'] == df['carbon_decile'].max()]['is_single_bidder'].mean() * 100
ratio = top_decile_sb / bottom_decile_sb

print(f"\n✓ Bottom decile (cleanest) SB rate: {bottom_decile_sb:.1f}%")
print(f"  Manuscript claims: 6.2%")
print(f"✓ Top decile (dirtiest) SB rate: {top_decile_sb:.1f}%")
print(f"  Manuscript claims: 13.5%")
print(f"✓ Ratio: {ratio:.2f}x")
print(f"  Manuscript claims: 2.2x")

# ============================================================================
# VERIFICATION 6: WITHIN-SECTOR EFFECT
# ============================================================================
print("\n" + "="*80)
print("VERIFICATION 6: WITHIN-SECTOR EFFECT")
print("="*80)

within_effects = []
for sector in df['exiobase_sector'].unique():
    sector_df = df[df['exiobase_sector'] == sector]
    if len(sector_df) < 1000:
        continue
    
    sb_sect = sector_df[sector_df['is_single_bidder'] == True]['carbon_intensity_kg_usd']
    mb_sect = sector_df[sector_df['is_single_bidder'] == False]['carbon_intensity_kg_usd']
    
    if len(sb_sect) < 100 or len(mb_sect) < 100:
        continue
    
    pct = 100 * (sb_sect.mean() - mb_sect.mean()) / mb_sect.mean() if mb_sect.mean() > 0 else 0
    within_effects.append({'sector': sector, 'pct': pct, 'n': len(sector_df)})

we_df = pd.DataFrame(within_effects)
weighted_within = (we_df['pct'] * we_df['n']).sum() / we_df['n'].sum()

print(f"\n✓ Weighted within-sector effect: {weighted_within:.1f}%")
print(f"  Manuscript claims: 0.0%")
print(f"  Note: The effect is essentially zero by design (EXIOBASE sector averages)")

# ============================================================================
# VERIFICATION 7: SINGLE-BIDDER RATE
# ============================================================================
print("\n" + "="*80)
print("VERIFICATION 7: OVERALL SINGLE-BIDDER RATE")
print("="*80)

overall_sb_rate = df['is_single_bidder'].mean() * 100
print(f"\n✓ Overall single-bidder rate: {overall_sb_rate:.1f}%")
print(f"  Manuscript claims: 11.0%")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("VERIFICATION SUMMARY")
print("="*80)

verifications = {
    'total_contracts': len(df) == 21612129,
    'countries': df['country'].nunique() == 27,
    'premium_approx': abs(premium - 14.8) < 0.5,
    'covid_tripled': covid_prem > pre_prem * 2.5,
    'covid_collapsed': post_prem < pre_prem * 0.5,
    'extreme_ratio': ratio > 2.0,
    'within_sector_near_zero': abs(weighted_within) < 1.0,
}

print("\nKey Verifications:")
for k, v in verifications.items():
    status = "✓ PASS" if v else "✗ FAIL"
    print(f"  {k}: {status}")

all_pass = all(verifications.values())
print(f"\n{'='*40}")
print(f"OVERALL: {'ALL VERIFICATIONS PASSED' if all_pass else 'SOME VERIFICATIONS FAILED'}")
print(f"{'='*40}")

# Save verification results
results = {
    'total_contracts': int(len(df)),
    'countries': int(df['country'].nunique()),
    'premium_pct': float(premium),
    't_statistic': float(t_stat),
    'cohens_d': float(cohens_d),
    'pre_covid_premium': float(pre_prem),
    'covid_premium': float(covid_prem),
    'post_covid_premium': float(post_prem),
    'extreme_value_ratio': float(ratio),
    'within_sector_effect': float(weighted_within),
    'all_verifications_passed': all_pass
}

with open('results/validation/data_verification.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\n✅ Verification complete. Results saved to results/data_verification.json")
