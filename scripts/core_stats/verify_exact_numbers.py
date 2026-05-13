"""Verify exact numbers for manuscript/SI reconciliation."""
import pandas as pd
import numpy as np
from scipy import stats
import json
import warnings
warnings.filterwarnings('ignore')

print("Loading data...")
df = pd.read_parquet("Data/processed/gprd_with_carbon.parquet")
eu = df[df['country'] != 'CO'].copy()
print(f"EU-context: {len(eu):,}")

ci = eu['carbon_intensity_kg_usd']
sb = eu['single_bidder']

# 1. Overall stats
sb_ci = ci[sb == True]
mb_ci = ci[sb == False]
prem = (sb_ci.mean() - mb_ci.mean()) / mb_ci.mean() * 100
t_val, p_val = stats.ttest_ind(sb_ci, mb_ci, equal_var=False)
pooled = np.sqrt((sb_ci.var()*len(sb_ci) + mb_ci.var()*len(mb_ci))/(len(sb_ci)+len(mb_ci)))
d_val = (sb_ci.mean() - mb_ci.mean()) / pooled
print(f"\nOverall: SB={sb_ci.mean():.4f}, MB={mb_ci.mean():.4f}, prem={prem:.1f}%, t={t_val:.1f}, d={d_val:.3f}")
print(f"  SB rate: {sb.mean()*100:.1f}%")

# 2. Size bands - check breakpoints
print("\n--- SIZE BANDS ---")
for label, lo, hi in [("Small <10k", 0, 10000), ("Medium 10k-200k", 10000, 200000), ("Large >200k", 200000, 1e15)]:
    sub = eu[(eu['value_eur'] >= lo) & (eu['value_eur'] < hi)]
    sb_sub = sub[sub['single_bidder']==True]['carbon_intensity_kg_usd']
    mb_sub = sub[sub['single_bidder']==False]['carbon_intensity_kg_usd']
    prem_sub = (sb_sub.mean() - mb_sub.mean()) / mb_sub.mean() * 100
    t_sub, _ = stats.ttest_ind(sb_sub, mb_sub, equal_var=False)
    pooled_sub = np.sqrt((sb_sub.var()*len(sb_sub) + mb_sub.var()*len(mb_sub))/(len(sb_sub)+len(mb_sub)))
    d_sub = (sb_sub.mean() - mb_sub.mean()) / pooled_sub
    sb_rate = sub['single_bidder'].mean() * 100
    print(f"  {label}: N={len(sub):,}, SB={sb_rate:.1f}%, prem={prem_sub:.1f}%, d={d_sub:.3f}, t={t_sub:.1f}")

# 3. CPV divisions
n_cpv = eu['cpv_division'].nunique()
print(f"\nUnique CPV divisions: {n_cpv}")
# Also check full dataset
n_cpv_all = df['cpv_division'].nunique()
print(f"Unique CPV divisions (full): {n_cpv_all}")

# 4. Country-sector groups
if 'exiobase_sector' in eu.columns:
    cs_eu = eu.groupby(['country', 'exiobase_sector']).size()
    print(f"EU-context country-sector groups: {len(cs_eu)}")
    cs_all = df.groupby(['country', 'exiobase_sector']).size()
    print(f"All country-sector groups: {len(cs_all)}")
    n_sectors = eu['exiobase_sector'].nunique()
    n_countries = eu['country'].nunique()
    print(f"EU countries: {n_countries}, EXIOBASE sectors: {n_sectors}")
    print(f"Product: {n_countries} × {n_sectors} = {n_countries * n_sectors}")

# 5. I² heterogeneity
print("\n--- I² HETEROGENEITY ---")
country_effects = []
for c in eu['country'].unique():
    sub = eu[eu['country'] == c]
    sb_c = sub[sub['single_bidder']==True]['carbon_intensity_kg_usd']
    mb_c = sub[sub['single_bidder']==False]['carbon_intensity_kg_usd']
    if len(sb_c) > 10 and len(mb_c) > 10:
        diff = sb_c.mean() - mb_c.mean()
        se = np.sqrt(sb_c.var()/len(sb_c) + mb_c.var()/len(mb_c))
        country_effects.append({'country': c, 'diff': diff, 'se': se, 'n': len(sub)})

effects = pd.DataFrame(country_effects)
# Fixed-effects weighted mean
w = 1 / effects['se']**2
weighted_mean = (w * effects['diff']).sum() / w.sum()
Q = (w * (effects['diff'] - weighted_mean)**2).sum()
k = len(effects)
I2 = max(0, (Q - (k-1)) / Q * 100)
print(f"Q = {Q:.1f}, k = {k}, I² = {I2:.1f}%")

# 6. Positive-premium countries (EU-context)
print("\n--- POSITIVE PREMIUM COUNTRIES (EU-context) ---")
for _, row in effects.iterrows():
    prem_pct = row['diff'] / eu[eu['country']==row['country']]['carbon_intensity_kg_usd'][eu['single_bidder']==False].mean() * 100
    if prem_pct > 0:
        print(f"  {row['country']}: premium = +{prem_pct:.1f}%")

# 7. Countries list
print("\n--- ALL EU-CONTEXT COUNTRIES ---")
countries = sorted(eu['country'].unique())
print(f"Total: {len(countries)}")
print(f"List: {', '.join(countries)}")

# 8. Verify data years
print("\n--- YEARS ---")
years = sorted(eu['year'].unique())
print(f"Years in EU-context: {years}")
print(f"Min year: {min(years)}, Max year: {max(years)}")

print("\n✅ VERIFICATION COMPLETE")
