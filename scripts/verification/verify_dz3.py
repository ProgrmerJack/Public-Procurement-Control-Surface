import pyarrow.parquet as pq
import numpy as np

pf = pq.read_table(r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\processed\gprd_with_carbon.parquet', 
                     columns=['value_eur', 'single_bidder', 'carbon_intensity_kg_usd', 'cpv_division', 'year', 'country'])
df = pf.to_pandas()

# EU-context (exclude Colombia)
eu = df[df['country'] != 'CO']
print('=== EU-CONTEXT ===')
print(f'N contracts: {len(eu):,}')

# Dead Zones: defined using FULL dataset for sector thresholds
cpv_all = df.groupby('cpv_division').agg(
    mean_ci=('carbon_intensity_kg_usd', 'mean'),
    sb_rate=('single_bidder', 'mean'),
    total_value=('value_eur', 'sum'),
    n_contracts=('single_bidder', 'count')
).reset_index()

dz_cpvs = cpv_all[(cpv_all['mean_ci'] >= 0.25) & (cpv_all['sb_rate'] >= 0.074)]['cpv_division'].tolist()
print(f'DZ sectors (defined globally): {sorted(dz_cpvs)}')

# EU-context Dead Zone values
eu_dz = eu[eu['cpv_division'].isin(dz_cpvs)]
eu_dz_sb = eu_dz[eu_dz['single_bidder'] == True]
print(f'EU DZ total value (cumul): EUR {eu_dz["value_eur"].sum()/1e12:.2f}T')
print(f'EU DZ SB value (cumul): EUR {eu_dz_sb["value_eur"].sum()/1e12:.2f}T')

# Per year (EU-context only)
for y in sorted(eu['year'].dropna().unique()):
    yr_dz_sb = eu_dz_sb[eu_dz_sb['year'] == y]
    print(f'  {int(y)}: SB DZ = EUR {yr_dz_sb["value_eur"].sum()/1e9:.1f}B')

# Recent years (2019-2023) average
recent = eu_dz_sb[eu_dz_sb['year'].between(2019, 2023)]
recent_annual = recent.groupby('year')['value_eur'].sum()
print(f'\n2019-2023 avg annual SB DZ: EUR {recent_annual.mean()/1e9:.1f}B')
print(f'2022-2023 avg annual SB DZ: EUR {recent_annual.loc[2022:2023].mean()/1e9:.1f}B')

# EU-context total procurement
eu_annual = eu.groupby('year')['value_eur'].sum()
print(f'\nEU total value (cumul): EUR {eu["value_eur"].sum()/1e12:.1f}T')
print(f'EU 2019-2023 avg annual: EUR {eu_annual.loc[2019:2023].mean()/1e12:.1f}T')

# CPV-level Dead Zone table
print('\n=== DEAD ZONE SECTOR DETAILS ===')
eu_cpv = eu.groupby('cpv_division').agg(
    mean_ci=('carbon_intensity_kg_usd', 'mean'),
    sb_rate=('single_bidder', 'mean'),
    total_value=('value_eur', 'sum'),
    n=('single_bidder', 'count')
).reset_index()

dz_table = eu_cpv[eu_cpv['cpv_division'].isin(dz_cpvs)].sort_values('total_value', ascending=False)
for _, row in dz_table.head(10).iterrows():
    cpv = int(row['cpv_division'])
    sb_val = eu[(eu['cpv_division']==cpv) & (eu['single_bidder']==True)]['value_eur'].sum()
    print(f'CPV {cpv:2d}: Total={row["total_value"]/1e9:.0f}B, SB_val={sb_val/1e9:.1f}B, SB_rate={row["sb_rate"]*100:.1f}%, CI={row["mean_ci"]:.2f}')

# Check CPV 33 specifically
print('\n=== CPV 33 CHECK ===')
cpv33_all = df[df['cpv_division'] == 33]
cpv33_eu = eu[eu['cpv_division'] == 33]
print(f'CPV 33 ALL: N={len(cpv33_all)}, Value={cpv33_all["value_eur"].sum()/1e9:.1f}B')
print(f'CPV 33 EU: N={len(cpv33_eu)}, Value={cpv33_eu["value_eur"].sum()/1e9:.1f}B')
if len(cpv33_all) > 0:
    print(f'  SB rate: {cpv33_all["single_bidder"].mean()*100:.1f}%')
    print(f'  Mean CI: {cpv33_all["carbon_intensity_kg_usd"].mean():.3f}')

# Also check what CPV has biggest SB lock-in
print('\n=== LARGEST SB LOCK-IN (EU-context) ===')
sb_lockings = []
for cpv in eu['cpv_division'].unique():
    sb_val = eu[(eu['cpv_division']==cpv) & (eu['single_bidder']==True)]['value_eur'].sum()
    sb_lockings.append((cpv, sb_val))
sb_lockings.sort(key=lambda x: x[1], reverse=True)
for cpv, val in sb_lockings[:10]:
    ci = eu[eu['cpv_division']==cpv]['carbon_intensity_kg_usd'].mean()
    sb = eu[eu['cpv_division']==cpv]['single_bidder'].mean()
    print(f'CPV {int(cpv):2d}: SB_val={val/1e9:.1f}B, SB_rate={sb*100:.1f}%, CI={ci:.2f}')
