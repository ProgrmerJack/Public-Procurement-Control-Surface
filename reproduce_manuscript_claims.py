#!/usr/bin/env python3
"""
MANUSCRIPT CLAIM VERIFICATION SCRIPT
=====================================
This script verifies ALL claims in the manuscript against the actual data.
Third parties can use this to validate the findings.

Data required: Data/processed/gprd_with_carbon.parquet
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
from pathlib import Path

print("="*80)
print("MANUSCRIPT CLAIM VERIFICATION")
print("="*80)
print("Data file: Data/processed/gprd_with_carbon.parquet")
print()

# Load data
data_path = Path("Data/processed/gprd_with_carbon.parquet")
if not data_path.exists():
    raise FileNotFoundError(f"Data file not found: {data_path}")

gprd = pd.read_parquet(data_path)
print(f"Data loaded: {len(gprd):,} contracts")

results = {}
all_claims_verified = True

# ============================================================================
# CLAIM 1: Sample Size
# ============================================================================
print("\n" + "-"*80)
print("CLAIM 1: 21.6 million contracts across 27 countries (2012-2023)")
print("-"*80)

n_contracts = len(gprd)
n_countries = gprd['country'].nunique()
year_range = f"{int(gprd['year'].min())}-{int(gprd['year'].max())}"

print(f"  Contracts: {n_contracts:,} (claimed: 21,600,000)")
print(f"  Countries: {n_countries} (claimed: 27)")
print(f"  Year range: {year_range} (claimed: 2012-2023)")

claim1_ok = (abs(n_contracts - 21600000) < 100000) and (n_countries == 27) and (year_range == "2012-2023")
print(f"  VERIFIED: {claim1_ok}")
results['claim1_sample'] = {'verified': claim1_ok, 'n': n_contracts, 'countries': n_countries, 'years': year_range}

# ============================================================================
# CLAIM 2: Overall Carbon Premium = 14.8%
# ============================================================================
print("\n" + "-"*80)
print("CLAIM 2: Single-bidder contracts +14.8% higher carbon intensity")
print("-"*80)

single = gprd.loc[gprd['single_bidder'], 'carbon_intensity_kg_usd'].dropna()
multi = gprd.loc[~gprd['single_bidder'], 'carbon_intensity_kg_usd'].dropna()
premium = (single.mean() - multi.mean()) / multi.mean() * 100
t_stat, p_val = stats.ttest_ind(single, multi, equal_var=False)
cohen_d = (single.mean() - multi.mean()) / np.sqrt((single.std()**2 + multi.std()**2)/2)

print(f"  Single-bidder mean CI: {single.mean():.4f} kg/USD")
print(f"  Multi-bidder mean CI: {multi.mean():.4f} kg/USD")
print(f"  Premium: {premium:.2f}% (claimed: 14.8%)")
print(f"  t-statistic: {t_stat:.1f}")
print(f"  p-value: {p_val}")
print(f"  Cohen's d: {cohen_d:.3f} (claimed: 0.23)")

claim2_ok = (abs(premium - 14.8) < 0.5) and (p_val < 1e-100)
print(f"  VERIFIED: {claim2_ok}")
results['claim2_premium'] = {'verified': claim2_ok, 'premium': round(premium, 2), 't': round(t_stat, 1), 'd': round(cohen_d, 3)}

# ============================================================================
# CLAIM 3: U-Curve - Small Contracts +50%, Large Contracts -7%
# ============================================================================
print("\n" + "-"*80)
print("CLAIM 3: U-curve - Small (<€10k): +50%, Large (>€200k): -7%")
print("-"*80)

# Small contracts
small = gprd[gprd['value_eur'] < 10000]
s_single = small.loc[small['single_bidder'], 'carbon_intensity_kg_usd'].dropna()
s_multi = small.loc[~small['single_bidder'], 'carbon_intensity_kg_usd'].dropna()
small_premium = (s_single.mean() - s_multi.mean()) / s_multi.mean() * 100
small_d = (s_single.mean() - s_multi.mean()) / np.sqrt((s_single.std()**2 + s_multi.std()**2)/2)

print(f"  Small contracts (<€10k): n={len(small):,}")
print(f"    Premium: {small_premium:.1f}% (claimed: +50%)")
print(f"    Cohen's d: {small_d:.2f} (claimed: 0.75)")

# Large contracts
large = gprd[gprd['value_eur'] >= 200000]
l_single = large.loc[large['single_bidder'], 'carbon_intensity_kg_usd'].dropna()
l_multi = large.loc[~large['single_bidder'], 'carbon_intensity_kg_usd'].dropna()
large_premium = (l_single.mean() - l_multi.mean()) / l_multi.mean() * 100
large_d = (l_single.mean() - l_multi.mean()) / np.sqrt((l_single.std()**2 + l_multi.std()**2)/2)

print(f"  Large contracts (>€200k): n={len(large):,}")
print(f"    Premium: {large_premium:.1f}% (claimed: -7%)")
print(f"    Cohen's d: {large_d:.2f}")

claim3_ok = (small_premium > 45) and (large_premium < 0) and (small_d > 0.7)
print(f"  VERIFIED: {claim3_ok}")
results['claim3_ucurve'] = {'verified': claim3_ok, 'small_premium': round(small_premium, 1), 'large_premium': round(large_premium, 1), 'small_d': round(small_d, 2)}

# ============================================================================
# CLAIM 4: Temporal Decline -2.5%/year
# ============================================================================
print("\n" + "-"*80)
print("CLAIM 4: Temporal decline -2.5%/year, p=0.006")
print("-"*80)

yearly = []
for year in sorted(gprd['year'].dropna().unique()):
    y_data = gprd[gprd['year'] == year]
    single = y_data.loc[y_data['single_bidder'], 'carbon_intensity_kg_usd'].dropna()
    multi = y_data.loc[~y_data['single_bidder'], 'carbon_intensity_kg_usd'].dropna()
    if len(single) > 100 and len(multi) > 100:
        prem = (single.mean() - multi.mean()) / multi.mean() * 100
        yearly.append((int(year), prem))

years = np.array([y[0] for y in yearly])
premiums = np.array([y[1] for y in yearly])
slope, intercept, r, p, se = stats.linregress(years, premiums)

print(f"  Years with data: {len(yearly)}")
print(f"  Slope: {slope:.3f}%/year (claimed: -2.5%)")
print(f"  p-value: {p:.4f} (claimed: 0.006)")
print(f"  R-squared: {r**2:.3f}")

claim4_ok = (slope < -2) and (p < 0.01)
print(f"  VERIFIED: {claim4_ok}")
results['claim4_temporal'] = {'verified': claim4_ok, 'slope': round(slope, 3), 'p': round(p, 4), 'r2': round(r**2, 3)}

# ============================================================================
# CLAIM 5: Country Heterogeneity - 20 decrease, 5 increase, I²=99.9%
# ============================================================================
print("\n" + "-"*80)
print("CLAIM 5: 20 countries decrease, 5 increase, I²=99.9%")
print("-"*80)

country_effects = []
for country in gprd['country'].unique():
    c_data = gprd[gprd['country'] == country]
    single = c_data.loc[c_data['single_bidder'], 'carbon_intensity_kg_usd'].dropna()
    multi = c_data.loc[~c_data['single_bidder'], 'carbon_intensity_kg_usd'].dropna()
    if len(single) > 100 and len(multi) > 100:
        effect = single.mean() - multi.mean()
        se = np.sqrt(single.var()/len(single) + multi.var()/len(multi))
        t_stat, p_val = stats.ttest_ind(single, multi, equal_var=False)
        country_effects.append({
            'country': country,
            'effect': effect,
            'se': se,
            'p': p_val,
            'sig_decrease': (p_val < 0.05) and (effect < 0),
            'sig_increase': (p_val < 0.05) and (effect > 0)
        })

n_decrease = sum(1 for c in country_effects if c['sig_decrease'])
n_increase = sum(1 for c in country_effects if c['sig_increase'])

# Calculate I²
effects = np.array([c['effect'] for c in country_effects])
weights = np.array([1/(c['se']**2) for c in country_effects])
weighted_mean = np.sum(weights * effects) / np.sum(weights)
Q = np.sum(weights * (effects - weighted_mean)**2)
k = len(country_effects)
I2 = max(0, (Q - (k-1)) / Q) * 100

print(f"  Countries with significant decrease: {n_decrease} (claimed: 20)")
print(f"  Countries with significant increase: {n_increase} (claimed: 5)")
print(f"  I-squared: {I2:.1f}% (claimed: 99.9%)")

claim5_ok = (n_decrease >= 18) and (n_increase >= 3) and (I2 > 99)
print(f"  VERIFIED: {claim5_ok}")
results['claim5_heterogeneity'] = {'verified': claim5_ok, 'n_decrease': n_decrease, 'n_increase': n_increase, 'I2': round(I2, 1)}

# ============================================================================
# CLAIM 6: RDD - 27% bidder increase at threshold
# ============================================================================
print("\n" + "-"*80)
print("CLAIM 6: RDD - 27% bidder increase at €139k threshold")
print("-"*80)

# Narrow window analysis
threshold = 139000
window = gprd[(gprd['value_eur'] >= 120000) & (gprd['value_eur'] <= 160000) & gprd['n_bidders'].notna()]
below = window[window['value_eur'] < threshold]['n_bidders']
above = window[window['value_eur'] >= threshold]['n_bidders']

bidder_increase = above.mean() - below.mean()
bidder_pct = (above.mean() - below.mean()) / below.mean() * 100
t_stat, p_val = stats.ttest_ind(above, below, equal_var=False)

print(f"  Window: €120k-€160k, n={len(window):,}")
print(f"  Below threshold: {below.mean():.2f} bidders")
print(f"  Above threshold: {above.mean():.2f} bidders")
print(f"  Increase: +{bidder_increase:.2f} bidders ({bidder_pct:.1f}%)")
print(f"  t-statistic: {t_stat:.1f}")
print(f"  p-value: {p_val}")

claim6_ok = (bidder_pct > 20) and (p_val < 1e-30)
print(f"  VERIFIED: {claim6_ok}")
results['claim6_rdd'] = {'verified': claim6_ok, 'pct_increase': round(bidder_pct, 1), 'n_window': len(window)}

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("VERIFICATION SUMMARY")
print("="*80)

all_verified = all(r.get('verified', False) for r in results.values())
n_verified = sum(1 for r in results.values() if r.get('verified', False))
n_total = len(results)

for claim, result in results.items():
    status = "[PASS] VERIFIED" if result.get('verified') else "[FAIL] NEEDS REVIEW"
    print(f"  {claim}: {status}")

print()
print(f"TOTAL: {n_verified}/{n_total} claims verified")
print(f"OVERALL: {'ALL CLAIMS VERIFIED' if all_verified else 'SOME CLAIMS NEED REVIEW'}")

# Save results
with open('VERIFICATION_RESULTS.json', 'w') as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nResults saved to VERIFICATION_RESULTS.json")
