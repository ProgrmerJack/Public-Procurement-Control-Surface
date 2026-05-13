import pyarrow.parquet as pq
import numpy as np

pf = pq.read_table(r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\processed\gprd_with_carbon.parquet', 
                     columns=['value_eur', 'single_bidder', 'carbon_intensity_kg_usd', 'cpv_division', 'year'])
df = pf.to_pandas()

# Per year totals
yearly = df.groupby('year')['value_eur'].agg(['sum', 'count']).reset_index()
yearly.columns = ['year', 'total_value', 'n_contracts']
for _, row in yearly.iterrows():
    y = int(row['year'])
    v = row['total_value']
    n = int(row['n_contracts'])
    print(f"Year {y}: {n:>10,} contracts, EUR {v/1e12:.2f}T")

print()

# Dead Zone SB value per year
cpv_stats = df.groupby('cpv_division').agg(
    mean_ci=('carbon_intensity_kg_usd', 'mean'),
    sb_rate=('single_bidder', 'mean')
).reset_index()
dz_cpvs = cpv_stats[(cpv_stats['mean_ci'] >= 0.25) & (cpv_stats['sb_rate'] >= 0.074)]['cpv_division'].tolist()

dz_sb = df[(df['cpv_division'].isin(dz_cpvs)) & (df['single_bidder'] == True)]
yearly_dzsb = dz_sb.groupby('year')['value_eur'].sum().reset_index()
for _, row in yearly_dzsb.iterrows():
    print(f"Year {int(row['year'])}: SB DZ value = EUR {row['value_eur']/1e9:.1f}B")

print()
print('Mean annual SB DZ value:', round(yearly_dzsb['value_eur'].mean()/1e9, 1), 'B')
print('Median annual SB DZ value:', round(yearly_dzsb['value_eur'].median()/1e9, 1), 'B')

# CPV 33
cpv33 = df[df['cpv_division'] == 33]
print('\nCPV 33 total value:', round(cpv33['value_eur'].sum()/1e9, 1), 'B')
cpv33_sb = cpv33[cpv33['single_bidder'] == True]
print('CPV 33 SB value:', round(cpv33_sb['value_eur'].sum()/1e9, 1), 'B')
