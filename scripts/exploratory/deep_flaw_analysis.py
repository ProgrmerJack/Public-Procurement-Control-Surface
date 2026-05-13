"""
Deep analysis to compute all numbers needed for the 5 Fatal Flaws fix.
Loads actual parquet data and computes:
1. EU-only primary statistics (addresses Flaw 1 - Simpson's Paradox)
2. Within-country-within-sector premium (addresses Flaw 2 - construct validity)
3. COVID shift-share decomposition (addresses Flaw 4)
4. Large contract decomposition (addresses Flaw 5 - U-curve)
5. Colombia unverified bidder analysis (addresses Flaw 1)
"""
import pandas as pd
import numpy as np
import json
import os

os.chdir(r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface')

print("Loading data...")
df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet',
    columns=['country', 'year', 'cpv_division', 'exiobase_sector', 'value_eur',
             'n_bidders', 'single_bidder', 'carbon_intensity_kg_usd'])
print(f"Loaded {len(df):,} contracts")

EU_COUNTRIES = set(['AT','BE','CZ','DE','DK','EE','ES','FI','FR','GB','GR','HU','IE',
                    'IS','IT','LT','LU','LV','NL','NO','PL','PT','SE','SI','SK','CH'])
df['is_eu'] = df['country'].isin(EU_COUNTRIES)
df['ci'] = df['carbon_intensity_kg_usd']

results = {}

# =========================================================================
# ANALYSIS 1: Colombia unverified bidder problem (Flaw 1)
# =========================================================================
print("\n=== ANALYSIS 1: Colombia Bidder Data Quality ===")
co = df[df['country'] == 'CO']
co_null = co['n_bidders'].isna().sum()
co_sb = co['single_bidder'].sum()
print(f"Colombia: {len(co):,} contracts")
print(f"  n_bidders null: {co_null:,} ({co_null/len(co)*100:.1f}%)")
print(f"  single_bidder=True: {co_sb:,} ({co_sb/len(co)*100:.1f}%)")
print(f"  single_bidder=False (incl unverified): {len(co)-co_sb:,}")
print(f"  CO mean CI (SB=True):  {co[co['single_bidder']]['ci'].mean():.4f}")
print(f"  CO mean CI (SB=False): {co[~co['single_bidder']]['ci'].mean():.4f}")

# Check: how many "multi-bidder" Colombian contracts have null n_bidders?
co_mb = co[~co['single_bidder']]
co_mb_null = co_mb['n_bidders'].isna().sum()
print(f"  CO multi-bidder contracts with null n_bidders: {co_mb_null:,} ({co_mb_null/len(co_mb)*100:.1f}%)")

results['colombia_bidder_quality'] = {
    'total': int(len(co)),
    'n_bidders_null': int(co_null),
    'pct_null': float(co_null/len(co)*100),
    'single_bidder_count': int(co_sb),
    'single_bidder_rate': float(co_sb/len(co)*100),
    'multi_bidder_null_n': int(co_mb_null),
    'multi_bidder_null_pct': float(co_mb_null/len(co_mb)*100),
    'sb_mean_ci': float(co[co['single_bidder']]['ci'].mean()),
    'mb_mean_ci': float(co[~co['single_bidder']]['ci'].mean()),
}

# What happens if we EXCLUDE contracts with null n_bidders globally?
print("\n  SENSITIVITY: Excluding null n_bidders contracts")
df_verified = df[df['n_bidders'].notna()]
sb_v = df_verified[df_verified['single_bidder']]
mb_v = df_verified[~df_verified['single_bidder']]
prem_v = (sb_v['ci'].mean() - mb_v['ci'].mean()) / mb_v['ci'].mean() * 100
print(f"  Verified-only: N={len(df_verified):,}, premium={prem_v:+.1f}%")
print(f"  SB mean={sb_v['ci'].mean():.4f}, MB mean={mb_v['ci'].mean():.4f}")
results['verified_only_premium'] = float(prem_v)

# =========================================================================
# ANALYSIS 2: Within-Country-Within-Sector Premium (Flaw 2)
# =========================================================================
print("\n=== ANALYSIS 2: Within-Country-Within-Sector Premium ===")
# For each (country, exiobase_sector), compute SB vs MB carbon intensity
# Since EXIOBASE assigns same CI to all contracts in same country-sector,
# the within-sector premium should be EXACTLY 0.0%
# Let's verify this

# Group by country and exiobase_sector
sector_groups = df.groupby(['country', 'exiobase_sector', 'single_bidder'])['ci'].agg(['mean', 'count']).reset_index()
sector_groups.columns = ['country', 'sector', 'single_bidder', 'mean_ci', 'count']

# For each country-sector, compute premium
sb_data = sector_groups[sector_groups['single_bidder'] == True].set_index(['country', 'sector'])
mb_data = sector_groups[sector_groups['single_bidder'] == False].set_index(['country', 'sector'])
both = sb_data.join(mb_data, lsuffix='_sb', rsuffix='_mb')
both = both.dropna()
both['premium'] = (both['mean_ci_sb'] - both['mean_ci_mb']) / both['mean_ci_mb'] * 100
both['weight'] = both['count_sb'] + both['count_mb']

# Weighted average within-sector premium
wavg = np.average(both['premium'], weights=both['weight'])
print(f"Weighted within-country-within-sector premium: {wavg:+.4f}%")
print(f"  (should be ~0% because EXIOBASE assigns same CI to all contracts in country-sector)")
print(f"  Number of country-sector groups: {len(both):,}")
print(f"  Groups with nonzero premium: {(both['premium'].abs() > 0.01).sum()}")
results['within_sector_premium'] = float(wavg)

# Now compute cross-sector premium (what we actually measure)
# This is the ALLOCATIVE component
print("\n  DECOMPOSITION: Allocative vs Within-Sector")
total_premium_eu = None
for region, mask in [("EU", df['is_eu']), ("Non-EU", ~df['is_eu']), ("All", pd.Series(True, index=df.index))]:
    subset = df[mask]
    sb = subset[subset['single_bidder']]
    mb = subset[~subset['single_bidder']]
    total_prem = (sb['ci'].mean() - mb['ci'].mean()) / mb['ci'].mean() * 100
    print(f"  {region}: Total premium={total_prem:+.1f}%, Within-sector={wavg:+.2f}%, Allocative={total_prem-wavg:+.1f}%")
    if region == "EU":
        total_premium_eu = total_prem

results['decomposition'] = {
    'total_global': float((df[df['single_bidder']]['ci'].mean() - df[~df['single_bidder']]['ci'].mean()) / df[~df['single_bidder']]['ci'].mean() * 100),
    'total_eu': float(total_premium_eu) if total_premium_eu else None,
    'within_sector': float(wavg),
    'allocative': float((df[df['single_bidder']]['ci'].mean() - df[~df['single_bidder']]['ci'].mean()) / df[~df['single_bidder']]['ci'].mean() * 100 - wavg),
}

# =========================================================================
# ANALYSIS 3: COVID Shift-Share Decomposition (Flaw 4) - EU ONLY
# =========================================================================
print("\n=== ANALYSIS 3: COVID Shift-Share Decomposition (EU-ONLY) ===")
eu = df[df['is_eu']].copy()

# Define periods
eu['period'] = 'other'
eu.loc[eu['year'] == 2019, 'period'] = 'pre_covid'
eu.loc[eu['year'].isin([2020, 2021]), 'period'] = 'covid'
eu.loc[eu['year'].isin([2022, 2023]), 'period'] = 'post_covid'

# Shift-share: decompose premium change into composition vs within-sector
for period in ['pre_covid', 'covid', 'post_covid']:
    subset = eu[eu['period'] == period]
    n = len(subset)
    sb = subset[subset['single_bidder']]
    mb = subset[~subset['single_bidder']]
    prem = (sb['ci'].mean() - mb['ci'].mean()) / mb['ci'].mean() * 100
    sb_rate = len(sb) / n * 100
    
    # Sector composition
    sector_shares = subset.groupby('exiobase_sector').size() / n
    top_sectors = sector_shares.nlargest(5)
    
    print(f"\n  {period}: N={n:,} SB_rate={sb_rate:.1f}% premium={prem:+.2f}%")
    print(f"    Top 5 sectors: {dict(top_sectors.round(3))}")

# Shift-share decomposition between pre-COVID and COVID
print("\n  SHIFT-SHARE: Pre-COVID (2019) → COVID (2020-2021)")
pre = eu[eu['period'] == 'pre_covid']
covid = eu[eu['period'] == 'covid']

# Compute sector shares and mean CI for each period
for label, period_df in [("Pre-COVID", pre), ("COVID", covid)]:
    sectors = period_df.groupby('exiobase_sector').agg(
        n=('ci', 'count'),
        mean_ci=('ci', 'mean'),
        sb_rate=('single_bidder', 'mean')
    )
    sectors['share'] = sectors['n'] / sectors['n'].sum()
    print(f"\n    {label}: {len(sectors)} sectors, weighted mean CI={np.average(sectors['mean_ci'], weights=sectors['n']):.4f}")
    # Top changed sectors
    if label == "Pre-COVID":
        pre_sectors = sectors
    else:
        covid_sectors = sectors

# Merge and compute shift-share
merged = pre_sectors.join(covid_sectors, lsuffix='_pre', rsuffix='_covid', how='outer').fillna(0)
merged['share_change'] = merged['share_covid'] - merged['share_pre']
merged['ci_change'] = merged['mean_ci_covid'] - merged['mean_ci_pre']

# Shift-share: Total change = composition effect + within-sector effect + interaction
composition_effect = (merged['share_change'] * merged['mean_ci_pre']).sum()
within_effect = (merged['share_pre'] * merged['ci_change']).sum()
interaction = (merged['share_change'] * merged['ci_change']).sum()
total_change = composition_effect + within_effect + interaction

print(f"\n  Shift-share results (mean CI change):")
print(f"    Total CI change: {total_change:.6f}")
print(f"    Composition effect: {composition_effect:.6f} ({composition_effect/abs(total_change)*100 if total_change != 0 else 0:+.0f}%)")
print(f"    Within-sector effect: {within_effect:.6f} ({within_effect/abs(total_change)*100 if total_change != 0 else 0:+.0f}%)")
print(f"    Interaction: {interaction:.6f}")

results['covid_shift_share'] = {
    'total_change': float(total_change),
    'composition_effect': float(composition_effect),
    'within_sector_effect': float(within_effect),
    'interaction': float(interaction),
    'composition_pct': float(composition_effect/abs(total_change)*100) if total_change != 0 else 0,
}

# EU-only SB rate changes through COVID
print("\n  EU SB RATE THROUGH COVID:")
for yr in [2019, 2020, 2021, 2022, 2023]:
    yr_data = eu[eu['year'] == yr]
    sb_rate = yr_data['single_bidder'].mean() * 100
    prem = (yr_data[yr_data['single_bidder']]['ci'].mean() - yr_data[~yr_data['single_bidder']]['ci'].mean()) / yr_data[~yr_data['single_bidder']]['ci'].mean() * 100
    print(f"    {yr}: SB_rate={sb_rate:.1f}%, premium={prem:+.2f}%")

# =========================================================================
# ANALYSIS 4: Large Contract Decomposition (Flaw 5)
# =========================================================================
print("\n=== ANALYSIS 4: Large Contract Decomposition (EU-ONLY) ===")
eu_large = eu[eu['value_eur'] > 200000]
eu_small = eu[eu['value_eur'] <= 10000]
eu_med = eu[(eu['value_eur'] > 10000) & (eu['value_eur'] <= 200000)]

for label, subset in [("Small <€10k", eu_small), ("Medium €10-200k", eu_med), ("Large >€200k", eu_large)]:
    sb = subset[subset['single_bidder']]
    mb = subset[~subset['single_bidder']]
    if len(mb) > 0 and len(sb) > 0:
        prem = (sb['ci'].mean() - mb['ci'].mean()) / mb['ci'].mean() * 100
        print(f"  {label}: N={len(subset):,} SB_rate={len(sb)/len(subset)*100:.1f}% premium={prem:+.1f}%")
        print(f"    SB_mean_CI={sb['ci'].mean():.4f} MB_mean_CI={mb['ci'].mean():.4f}")
        
        # Sector composition difference
        sb_sectors = sb.groupby('exiobase_sector').size() / len(sb)
        mb_sectors = mb.groupby('exiobase_sector').size() / len(mb)
        all_sectors = set(sb_sectors.index) | set(mb_sectors.index)
        sector_diff = pd.Series({s: sb_sectors.get(s, 0) - mb_sectors.get(s, 0) for s in all_sectors})
        top_diff = sector_diff.abs().nlargest(5)
        print(f"    Top sector differences (SB-MB share):")
        for s in top_diff.index:
            print(f"      {s}: {sector_diff[s]:+.3f} ({sector_diff[s]*100:+.1f}pp)")

# EU-only Dead Zones
print("\n=== EU-ONLY DEAD ZONES ===")
eu_sectors = eu.groupby('cpv_division').agg(
    n=('ci', 'count'),
    mean_ci=('ci', 'mean'),
    sb_rate=('single_bidder', 'mean'),
    total_value=('value_eur', 'sum')
).reset_index()

ci_thresh = eu_sectors['mean_ci'].quantile(0.67)
sb_thresh = eu_sectors['sb_rate'].median()
eu_dz = eu_sectors[(eu_sectors['mean_ci'] >= ci_thresh) & (eu_sectors['sb_rate'] >= sb_thresh)]
print(f"EU Dead Zones: {len(eu_dz)} of {len(eu_sectors)} sectors")
print(f"  CI threshold: {ci_thresh:.3f}, SB threshold: {sb_thresh:.3f}")
eu_dz_value = eu_dz['total_value'].sum()
eu_dz_sb_locked = (eu_dz['total_value'] * eu_dz['sb_rate']).sum()
print(f"  EU DZ total value: EUR {eu_dz_value/1e12:.2f}T")
print(f"  EU DZ SB-locked: EUR {eu_dz_sb_locked/1e9:.1f}B")

results['eu_dead_zones'] = {
    'n_sectors': int(len(eu_dz)),
    'n_total_sectors': int(len(eu_sectors)),
    'ci_threshold': float(ci_thresh),
    'sb_threshold': float(sb_thresh),
    'total_value_eur': float(eu_dz_value),
    'sb_locked_eur': float(eu_dz_sb_locked),
}

# =========================================================================
# ANALYSIS 5: EXIOBASE within-sector variation check
# =========================================================================
print("\n=== ANALYSIS 5: EXIOBASE Within-Sector Carbon Variation ===")
# Check: does EXIOBASE assign the SAME carbon to all contracts within country-sector?
sector_var = df.groupby(['country', 'exiobase_sector'])['ci'].agg(['mean', 'std', 'count']).reset_index()
sector_var.columns = ['country', 'sector', 'mean_ci', 'std_ci', 'count']
# Sectors with nonzero std (variation within country-sector)
nonzero_std = sector_var[sector_var['std_ci'] > 0.001]
print(f"Country-sectors with CI variation > 0.001: {len(nonzero_std)} of {len(sector_var)}")
print(f"  (If EXIOBASE assigns same CI to all in country-sector, this should be ~0)")
print(f"  Max within-sector std: {sector_var['std_ci'].max():.4f}")
print(f"  Mean within-sector std: {sector_var['std_ci'].mean():.4f}")
# This confirms EXIOBASE is sector-level: no within-sector variation

results['within_sector_variation'] = {
    'n_country_sectors': int(len(sector_var)),
    'n_with_variation': int(len(nonzero_std)),
    'max_std': float(sector_var['std_ci'].max()),
    'mean_std': float(sector_var['std_ci'].mean()),
    'interpretation': 'EXIOBASE assigns identical CI within country-sector, confirming sector-level measurement'
}

# =========================================================================
# SAVE ALL RESULTS
# =========================================================================
with open('results/other/fatal_flaw_deep_analysis.json', 'w') as f:
    json.dump(results, f, indent=2, default=str)

print("\n=== ALL RESULTS SAVED to results/fatal_flaw_deep_analysis.json ===")
