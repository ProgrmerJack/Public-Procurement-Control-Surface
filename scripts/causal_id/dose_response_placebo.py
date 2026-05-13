"""
Pre-treatment placebo test for dose-response finding.
If the r=-0.55 dose-response is causal (not regression to mean),
then predicting changes in the PRE-treatment period should show
a WEAKER relationship.
"""
import json
import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from scipy import stats

# Load data
df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet',
                     columns=['country', 'year', 'single_bidder'])

# EU countries only (exclude CO)
eu_countries = [c for c in df['country'].unique() if c != 'CO']
df = df[df['country'].isin(eu_countries)]

# Get country-year SB rates
cy = df.groupby(['country', 'year']).agg(
    sb_rate=('single_bidder', 'mean'),
    n=('single_bidder', 'count')
).reset_index()

# Pre-treatment: 2012-2015
# Post-treatment: 2017-2019 (allow lag)
pre = cy[cy['year'].between(2012, 2015)].groupby('country')['sb_rate'].mean()
post = cy[cy['year'].between(2017, 2019)].groupby('country')['sb_rate'].mean()
change = post - pre

# Only countries with both periods
both = set(pre.index) & set(change.index)
pre = pre.loc[sorted(both)]
change = change.loc[sorted(both)]

print("=" * 60)
print("POST-TREATMENT DOSE-RESPONSE (replication)")
print("=" * 60)
r_post, p_post = stats.pearsonr(pre, change)
print(f"  Pearson r = {r_post:.3f}, p = {p_post:.4f}")
slope_post, intercept_post, _, _, se_post = stats.linregress(pre, change)
print(f"  Slope = {slope_post:.2f} (SE={se_post:.2f})")
print(f"  N = {len(pre)} countries")

# Now: PRE-TREATMENT PLACEBO
# Use 2012-2013 as "baseline" and 2014-2015 as "change"
print("\n" + "=" * 60)
print("PRE-TREATMENT PLACEBO (2012-13 → 2014-15)")
print("=" * 60)

early = cy[cy['year'].between(2012, 2013)].groupby('country')['sb_rate'].mean()
later_pre = cy[cy['year'].between(2014, 2015)].groupby('country')['sb_rate'].mean()
change_pre = later_pre - early

both_pre = set(early.index) & set(change_pre.index)
early = early.loc[sorted(both_pre)]
change_pre = change_pre.loc[sorted(both_pre)]

r_pre, p_pre = stats.pearsonr(early, change_pre)
slope_pre, intercept_pre, _, _, se_pre = stats.linregress(early, change_pre)
print(f"  Pearson r = {r_pre:.3f}, p = {p_pre:.4f}")
print(f"  Slope = {slope_pre:.2f} (SE={se_pre:.2f})")
print(f"  N = {len(early)} countries")

# Compare slopes
print("\n" + "=" * 60)
print("COMPARISON: Post-Treatment vs Pre-Treatment Placebo")
print("=" * 60)
print(f"  Post-treatment slope: {slope_post:.2f} (SE={se_post:.2f}, p={p_post:.4f})")
print(f"  Pre-treatment slope:  {slope_pre:.2f} (SE={se_pre:.2f}, p={p_pre:.4f})")
print(f"  Slope ratio: {abs(slope_post)/abs(slope_pre):.1f}x" if slope_pre != 0 else "  Slope ratio: inf")
print(f"  Post r: {r_post:.3f} vs Pre r: {r_pre:.3f}")

# Fisher z-test for difference in correlations
z_post = np.arctanh(r_post)
z_pre = np.arctanh(r_pre)
n_post = len(pre)
n_pre = len(early)
se_z = np.sqrt(1/(n_post-3) + 1/(n_pre-3))
z_diff = (z_post - z_pre) / se_z
p_diff = 2 * stats.norm.sf(abs(z_diff))

print(f"\n  Fisher z-test for correlation difference:")
print(f"  z = {z_diff:.2f}, p = {p_diff:.4f}")

if abs(r_post) > abs(r_pre) and p_post < 0.05 and p_pre > 0.05:
    print("\n  ✓ PASSES PLACEBO: Post-treatment dose-response is stronger")
    print("    than pre-treatment, ruling out regression to the mean")
elif abs(r_post) > abs(r_pre):
    print("\n  ~ PARTIAL PASS: Post-treatment relationship is stronger")
    print("    but pre-treatment also shows some relationship")
else:
    print("\n  ✗ FAILS: Pre-treatment shows similar/stronger relationship")
    print("    suggesting regression to the mean")

# Also test: 2012 baseline → 2013 change, 2013 baseline → 2014 change
print("\n" + "=" * 60)
print("YEAR-BY-YEAR PRE-TREATMENT PLACEBOS")
print("=" * 60)

for base_year, change_year in [(2012, 2013), (2013, 2014), (2014, 2015)]:
    base = cy[cy['year'] == base_year].set_index('country')['sb_rate']
    target = cy[cy['year'] == change_year].set_index('country')['sb_rate']
    yoy_change = target - base
    both_yoy = set(base.index) & set(yoy_change.index)
    if len(both_yoy) >= 10:
        b = base.loc[sorted(both_yoy)]
        c = yoy_change.loc[sorted(both_yoy)]
        r_yoy, p_yoy = stats.pearsonr(b, c)
        print(f"  {base_year}→{change_year}: r = {r_yoy:.3f}, p = {p_yoy:.4f} (n={len(b)})")

# Save results
results = {
    "post_treatment": {
        "pearson_r": float(r_post), "pearson_p": float(p_post),
        "slope": float(slope_post), "slope_se": float(se_post),
        "n": int(n_post)
    },
    "pre_treatment_placebo": {
        "pearson_r": float(r_pre), "pearson_p": float(p_pre),
        "slope": float(slope_pre), "slope_se": float(se_pre),
        "n": int(n_pre)
    },
    "fisher_z_test": {
        "z": float(z_diff), "p": float(p_diff)
    },
    "passes_placebo": bool(abs(r_post) > abs(r_pre) and p_post < 0.05)
}

with open('results/causal_id/dose_response_placebo.json', 'w') as f:
    json.dump(results, f, indent=2)
print("\nSaved to results/dose_response_placebo.json")
