"""
SIMPLE SANITY CHECK - Verify Sign of Carbon Effect
===================================================

Purpose: Hand-verify the direction and magnitude of carbon effect using
         the simplest possible approach (difference-in-means).

If this matches the RDD result (+1.74%), the RDD is correct.
If this shows -8.7%, there's a bug in the RDD implementation.

Author: Reanalysis Pipeline
Date: 2025-12-13
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent / 'Data' / 'processed'
RESULTS_DIR = Path(__file__).parent / 'results'
RESULTS_DIR.mkdir(exist_ok=True)

print("=" * 70)
print("SIMPLE SANITY CHECK: Carbon Effect Sign Verification")
print("=" * 70)

# Load data
print("\n1. Loading data...")
# Use the same file that run_causal_analysis.py uses
carbon_path = DATA_DIR / 'gprd_with_carbon.parquet'
if not carbon_path.exists():
    carbon_path = DATA_DIR / 'gprd_analysis.parquet'

df = pd.read_parquet(
    carbon_path,
    columns=['value_eur', 'carbon_intensity_kg_usd', 'country']
)
print(f"   Loaded from: {carbon_path.name}")
print(f"   Total contracts: {len(df):,}")

# Filter to non-null carbon
df = df[df['carbon_intensity_kg_usd'].notna()]
print(f"   With carbon data: {len(df):,}")

# Threshold
threshold = 139000
print(f"\n2. Threshold: €{threshold:,}")

# Define narrow window around threshold (±20%)
window_below = 0.8 * threshold
window_above = 1.2 * threshold
window = df[(df['value_eur'] >= window_below) & (df['value_eur'] <= window_above)]

print(f"\n3. Window: €{window_below:,.0f} to €{window_above:,.0f}")
print(f"   Contracts in window: {len(window):,}")

# Split by threshold
below = window[window['value_eur'] < threshold]['carbon_intensity_kg_usd']
above = window[window['value_eur'] >= threshold]['carbon_intensity_kg_usd']

print(f"\n4. Sample sizes:")
print(f"   Below threshold: {len(below):,}")
print(f"   Above threshold: {len(above):,}")

# Calculate means
mean_below = below.mean()
mean_above = above.mean()
diff = mean_above - mean_below
pct_change = (diff / mean_below) * 100

print(f"\n5. Carbon intensity (kg CO₂/USD):")
print(f"   Below threshold: {mean_below:.6f}")
print(f"   Above threshold: {mean_above:.6f}")

print(f"\n6. DIFFERENCE:")
print(f"   Absolute: {diff:+.6f} kg CO₂/USD")
print(f"   Percentage: {pct_change:+.2f}%")

print(f"\n7. INTERPRETATION:")
if diff > 0:
    print(f"   → Carbon INCREASES above threshold")
    print(f"   → Transparency is associated with HIGHER carbon intensity")
elif diff < 0:
    print(f"   → Carbon DECREASES above threshold")
    print(f"   → Transparency is associated with LOWER carbon intensity")
else:
    print(f"   → No difference")

# Statistical test (simple t-test)
from scipy import stats
t_stat, p_value = stats.ttest_ind(above, below, equal_var=False)

print(f"\n8. Statistical significance (Welch's t-test):")
print(f"   t-statistic: {t_stat:.4f}")
print(f"   p-value: {p_value:.4f}")
if p_value < 0.05:
    print(f"   → Statistically significant at 5% level")
else:
    print(f"   → NOT statistically significant")

# Compare to RDD result
print(f"\n9. Comparison to RDD result:")
print(f"   RDD estimate: +0.00373 kg CO₂/USD (+1.74%)")
print(f"   Simple diff:  {diff:+.6f} kg CO₂/USD ({pct_change:+.2f}%)")

if np.sign(diff) == np.sign(0.00373):
    print(f"   ✅ SIGNS MATCH - RDD result is plausible")
else:
    print(f"   ❌ SIGNS DIFFER - RDD implementation may have bug")

if abs(pct_change - 1.74) < 2:
    print(f"   ✅ MAGNITUDES SIMILAR - RDD is consistent")
else:
    print(f"   ⚠️  MAGNITUDES DIFFER - Check RDD bandwidth/weighting")

# Save results
results = pd.DataFrame([{
    'method': 'Simple difference-in-means',
    'window': f'{window_below:.0f} to {window_above:.0f}',
    'n_below': len(below),
    'n_above': len(above),
    'mean_below': mean_below,
    'mean_above': mean_above,
    'difference': diff,
    'pct_change': pct_change,
    't_statistic': t_stat,
    'p_value': p_value,
    'rdd_estimate': 0.00373,
    'rdd_pct': 1.74,
    'signs_match': np.sign(diff) == np.sign(0.00373),
    'magnitudes_similar': abs(pct_change - 1.74) < 2
}])

results.to_csv(RESULTS_DIR / 'sanity_check_simple_diff.csv', index=False)
print(f"\n10. Results saved to: {RESULTS_DIR / 'sanity_check_simple_diff.csv'}")

# Also check by country
print(f"\n{'=' * 70}")
print("COUNTRY-LEVEL SANITY CHECK")
print("=" * 70)

for country in ['CO', 'GB']:
    df_country = window[window['country'] == country]
    below_c = df_country[df_country['value_eur'] < threshold]['carbon_intensity_kg_usd']
    above_c = df_country[df_country['value_eur'] >= threshold]['carbon_intensity_kg_usd']
    
    if len(below_c) > 0 and len(above_c) > 0:
        diff_c = above_c.mean() - below_c.mean()
        pct_c = (diff_c / below_c.mean()) * 100
        
        print(f"\n{country}:")
        print(f"  n_below: {len(below_c):,}, n_above: {len(above_c):,}")
        print(f"  Difference: {diff_c:+.6f} kg CO₂/USD ({pct_c:+.2f}%)")
        
        # Compare to RDD
        if country == 'CO':
            rdd_estimate = -0.00197
            rdd_pct = -0.92
        else:  # GB
            rdd_estimate = -0.00415
            rdd_pct = -1.94
        
        print(f"  RDD estimate: {rdd_estimate:+.6f} kg CO₂/USD ({rdd_pct:+.2f}%)")
        
        if np.sign(diff_c) == np.sign(rdd_estimate):
            print(f"  ✅ Signs match")
        else:
            print(f"  ❌ Signs differ")

print(f"\n{'=' * 70}")
print("CONCLUSION")
print("=" * 70)
print(f"""
If simple difference shows:
  - POSITIVE (+1-2%): RDD is correct, transparency increases carbon
  - NEGATIVE (-8-10%): RDD has a bug (treatment/outcome sign error)
  - NEAR ZERO: Effect is fragile/noisy

Based on RDD showing +1.74%, we expect simple diff to be positive too.
""")
