#!/usr/bin/env python3
"""
FINAL MANUSCRIPT VALIDATION: Verify ALL claims against actual data
This script ensures every statistic in the manuscript is reproducible
"""

import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
import json

print("="*80)
print("FINAL MANUSCRIPT VALIDATION")
print("Verifying ALL claims against actual data")
print("="*80)

# Load data
DATA_PATH = Path("Data/processed/gprd_with_carbon.parquet")
df = pd.read_parquet(DATA_PATH)

# Create column aliases
df['award_year'] = df['year']
df['is_single_bidder'] = df['single_bidder']
df['carbon_intensity'] = df['carbon_intensity_kg_usd']
df['buyer_country'] = df['country']
df['value_euro'] = df['value_eur']

results = {"validation_timestamp": pd.Timestamp.now().isoformat(), "all_pass": True, "claims": []}

def verify_claim(claim_name, expected, actual, tolerance=0.05):
    """Verify a claim with tolerance"""
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        diff = abs(expected - actual) / max(abs(expected), 1e-10)
        passed = diff < tolerance
    else:
        passed = expected == actual
    
    result = {
        "claim": claim_name,
        "expected": str(expected),
        "actual": str(actual),
        "passed": passed
    }
    results["claims"].append(result)
    if not passed:
        results["all_pass"] = False
    
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {claim_name}")
    print(f"         Expected: {expected}, Actual: {actual}")
    return passed

# ============================================================================
# CLAIM 1: Sample Size and Composition
# ============================================================================
print("\n" + "="*60)
print("CLAIM 1: SAMPLE SIZE AND COMPOSITION")
print("="*60)

verify_claim("Total contracts", 21612129, len(df))
verify_claim("Countries", 27, df['buyer_country'].nunique())
verify_claim("Single-bidder count", 2378511, df['is_single_bidder'].sum(), tolerance=0.01)
verify_claim("Single-bidder rate", 11.0, df['is_single_bidder'].mean() * 100, tolerance=0.05)

# ============================================================================
# CLAIM 2: Core Carbon Premium
# ============================================================================
print("\n" + "="*60)
print("CLAIM 2: CORE CARBON PREMIUM")
print("="*60)

sb = df[df['is_single_bidder'] == True]['carbon_intensity']
mb = df[df['is_single_bidder'] == False]['carbon_intensity']

sb_mean = sb.mean()
mb_mean = mb.mean()
premium = (sb_mean - mb_mean) / mb_mean * 100

verify_claim("Single-bidder mean (kg/USD)", 0.337, sb_mean, tolerance=0.02)
verify_claim("Multi-bidder mean (kg/USD)", 0.294, mb_mean, tolerance=0.02)
verify_claim("Carbon premium (%)", 14.8, premium, tolerance=0.05)

t_stat, p_val = stats.ttest_ind(sb.dropna(), mb.dropna())
pooled_std = np.sqrt((sb.var() + mb.var()) / 2)
cohens_d = (sb_mean - mb_mean) / pooled_std

verify_claim("t-statistic", 331.5, t_stat, tolerance=0.02)
verify_claim("Cohen's d", 0.23, cohens_d, tolerance=0.05)

# ============================================================================
# CLAIM 3: U-CURVE
# ============================================================================
print("\n" + "="*60)
print("CLAIM 3: U-CURVE BY CONTRACT SIZE")
print("="*60)

# Small contracts (<€10k)
small = df[df['value_euro'] < 10000]
small_sb = small[small['is_single_bidder'] == True]['carbon_intensity']
small_mb = small[small['is_single_bidder'] == False]['carbon_intensity']
small_premium = (small_sb.mean() - small_mb.mean()) / small_mb.mean() * 100
small_d = (small_sb.mean() - small_mb.mean()) / np.sqrt((small_sb.var() + small_mb.var()) / 2)

verify_claim("Small (<€10k) premium (%)", 50.2, small_premium, tolerance=0.02)
verify_claim("Small (<€10k) Cohen's d", 0.75, small_d, tolerance=0.05)

# Large contracts (>€200k)
large = df[df['value_euro'] > 200000]
large_sb = large[large['is_single_bidder'] == True]['carbon_intensity']
large_mb = large[large['is_single_bidder'] == False]['carbon_intensity']
large_premium = (large_sb.mean() - large_mb.mean()) / large_mb.mean() * 100

verify_claim("Large (>€200k) premium (%)", -7.1, large_premium, tolerance=0.10)

# ============================================================================
# CLAIM 4: COVID NATURAL EXPERIMENT
# ============================================================================
print("\n" + "="*60)
print("CLAIM 4: COVID NATURAL EXPERIMENT")
print("="*60)

# Pre-COVID (2018-2019)
pre_covid = df[(df['award_year'] >= 2018) & (df['award_year'] <= 2019)]
pre_sb = pre_covid[pre_covid['is_single_bidder'] == True]['carbon_intensity']
pre_mb = pre_covid[pre_covid['is_single_bidder'] == False]['carbon_intensity']
pre_premium = (pre_sb.mean() - pre_mb.mean()) / pre_mb.mean() * 100

verify_claim("Pre-COVID premium (%)", 7.0, pre_premium, tolerance=0.10)

# During COVID (2020-2021)
covid = df[(df['award_year'] >= 2020) & (df['award_year'] <= 2021)]
covid_sb = covid[covid['is_single_bidder'] == True]['carbon_intensity']
covid_mb = covid[covid['is_single_bidder'] == False]['carbon_intensity']
covid_premium = (covid_sb.mean() - covid_mb.mean()) / covid_mb.mean() * 100

verify_claim("COVID premium (%)", 20.1, covid_premium, tolerance=0.05)

# Post-COVID (2022-2023)
post_covid = df[(df['award_year'] >= 2022) & (df['award_year'] <= 2023)]
post_sb = post_covid[post_covid['is_single_bidder'] == True]['carbon_intensity']
post_mb = post_covid[post_covid['is_single_bidder'] == False]['carbon_intensity']
post_premium = (post_sb.mean() - post_mb.mean()) / post_mb.mean() * 100

verify_claim("Post-COVID premium (%)", 0.3, post_premium, tolerance=0.50)  # Higher tolerance for small values

# ============================================================================
# CLAIM 5: DETERRENCE EFFECT
# ============================================================================
print("\n" + "="*60)
print("CLAIM 5: DETERRENCE EFFECT")
print("="*60)

# Calculate buyer-level single-bidder rate
buyer_stats = df.groupby('buyer_id').agg({
    'is_single_bidder': 'mean',
    'award_year': 'count'
}).rename(columns={'award_year': 'n_contracts', 'is_single_bidder': 'sb_rate'})

buyer_stats = buyer_stats[buyer_stats['n_contracts'] >= 10]
df_buyers = df.merge(buyer_stats[['sb_rate']], left_on='buyer_id', right_index=True, how='left')

sb_only = df_buyers[df_buyers['is_single_bidder'] == True].dropna(subset=['sb_rate'])
median_sb_rate = sb_only['sb_rate'].median()

competitive = sb_only[sb_only['sb_rate'] < median_sb_rate]['carbon_intensity']
non_competitive = sb_only[sb_only['sb_rate'] >= median_sb_rate]['carbon_intensity']

deterrence_premium = (competitive.mean() - non_competitive.mean()) / non_competitive.mean() * 100
deterrence_t, deterrence_p = stats.ttest_ind(competitive.dropna(), non_competitive.dropna())

verify_claim("Deterrence premium (%)", 1.9, deterrence_premium, tolerance=0.10)
verify_claim("Deterrence t-statistic", 22.9, deterrence_t, tolerance=0.10)

# ============================================================================
# CLAIM 6: EXTREME VALUE RATIO
# ============================================================================
print("\n" + "="*60)
print("CLAIM 6: EXTREME VALUE RATIO")
print("="*60)

df['carbon_decile'] = pd.qcut(df['carbon_intensity'], 10, labels=False, duplicates='drop')
top_decile = df[df['carbon_decile'] == df['carbon_decile'].max()]['is_single_bidder'].mean()
bottom_decile = df[df['carbon_decile'] == df['carbon_decile'].min()]['is_single_bidder'].mean()
ratio = top_decile / bottom_decile

verify_claim("Top decile SB rate (%)", 13.5, top_decile * 100, tolerance=0.10)
verify_claim("Bottom decile SB rate (%)", 6.2, bottom_decile * 100, tolerance=0.10)
verify_claim("Extreme value ratio", 2.2, ratio, tolerance=0.10)

# ============================================================================
# CLAIM 7: TEMPORAL TREND
# ============================================================================
print("\n" + "="*60)
print("CLAIM 7: TEMPORAL TREND")
print("="*60)

yearly_premiums = []
for year in sorted(df['award_year'].dropna().unique()):
    year_df = df[df['award_year'] == year]
    sb_year = year_df[year_df['is_single_bidder'] == True]['carbon_intensity']
    mb_year = year_df[year_df['is_single_bidder'] == False]['carbon_intensity']
    if len(sb_year) > 100 and len(mb_year) > 100:
        prem = (sb_year.mean() - mb_year.mean()) / mb_year.mean() * 100
        yearly_premiums.append({'year': year, 'premium': prem})

yearly_df = pd.DataFrame(yearly_premiums)
slope, intercept, r, p, se = stats.linregress(yearly_df['year'], yearly_df['premium'])

verify_claim("Temporal slope (%/year)", -2.5, slope, tolerance=0.10)
verify_claim("Temporal R²", 0.55, r**2, tolerance=0.15)

# ============================================================================
# CLAIM 8: LEARNING EFFECT (NEW)
# ============================================================================
print("\n" + "="*60)
print("CLAIM 8: LEARNING EFFECT")
print("="*60)

big_buyers = buyer_stats[buyer_stats['n_contracts'] >= 100].index
if len(big_buyers) > 100:
    repeat_buyer_df = df[df['buyer_id'].isin(big_buyers)].copy()
    repeat_buyer_df = repeat_buyer_df.sort_values(['buyer_id', 'award_year'])
    repeat_buyer_df['contract_rank'] = repeat_buyer_df.groupby('buyer_id').cumcount() + 1
    repeat_buyer_df['total_contracts'] = repeat_buyer_df.groupby('buyer_id')['buyer_id'].transform('count')
    repeat_buyer_df['relative_rank'] = repeat_buyer_df['contract_rank'] / repeat_buyer_df['total_contracts']
    
    early = repeat_buyer_df[repeat_buyer_df['relative_rank'] <= 0.25]
    late = repeat_buyer_df[repeat_buyer_df['relative_rank'] >= 0.75]
    
    early_premium = (early[early['is_single_bidder'] == True]['carbon_intensity'].mean() - 
                    early[early['is_single_bidder'] == False]['carbon_intensity'].mean())
    late_premium = (late[late['is_single_bidder'] == True]['carbon_intensity'].mean() - 
                   late[late['is_single_bidder'] == False]['carbon_intensity'].mean())
    
    learning_reduction = (early_premium - late_premium) / early_premium * 100 if early_premium != 0 else 0
    
    verify_claim("Learning reduction (%)", 8.6, learning_reduction, tolerance=0.20)

# ============================================================================
# CLAIM 9: NORDIC PARADOX
# ============================================================================
print("\n" + "="*60)
print("CLAIM 9: NORDIC PARADOX")
print("="*60)

nordic = ['SE', 'DK', 'FI', 'NO', 'IS']
nordic_df = df[df['buyer_country'].isin(nordic)]
non_nordic_df = df[~df['buyer_country'].isin(nordic)]

nordic_sb = nordic_df[nordic_df['is_single_bidder'] == True]['carbon_intensity']
nordic_mb = nordic_df[nordic_df['is_single_bidder'] == False]['carbon_intensity']
nordic_premium = (nordic_sb.mean() - nordic_mb.mean()) / nordic_mb.mean() * 100

non_nordic_sb = non_nordic_df[non_nordic_df['is_single_bidder'] == True]['carbon_intensity']
non_nordic_mb = non_nordic_df[non_nordic_df['is_single_bidder'] == False]['carbon_intensity']
non_nordic_premium = (non_nordic_sb.mean() - non_nordic_mb.mean()) / non_nordic_mb.mean() * 100

verify_claim("Nordic premium (%)", -0.3, nordic_premium, tolerance=1.0)  # Should be near zero
verify_claim("Non-Nordic premium (%)", 15.4, non_nordic_premium, tolerance=0.10)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("VALIDATION SUMMARY")
print("="*80)

passed = sum(1 for c in results["claims"] if c["passed"])
total = len(results["claims"])
print(f"\nTotal claims verified: {passed}/{total}")
print(f"Overall status: {'✅ ALL PASS' if results['all_pass'] else '❌ SOME FAILURES'}")

# Save results
with open('manuscript_validation_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to: manuscript_validation_results.json")
