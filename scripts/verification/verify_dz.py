import pyarrow.parquet as pq
import numpy as np

pf = pq.read_table(r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\processed\gprd_with_carbon.parquet', 
                     columns=['value_eur', 'single_bidder', 'carbon_intensity_kg_usd', 'cpv_division', 'year', 'country'])
df = pf.to_pandas()

cpv_stats = df.groupby('cpv_division').agg(
    mean_ci=('carbon_intensity_kg_usd', 'mean'),
    sb_rate=('single_bidder', 'mean'),
    total_value=('value_eur', 'sum'),
    n_contracts=('single_bidder', 'count')
).reset_index()

dz = cpv_stats[(cpv_stats['mean_ci'] >= 0.25) & (cpv_stats['sb_rate'] >= 0.074)]
print('Dead Zone sectors:', len(dz))

total_dz_val = dz['total_value'].sum()
print('Total DZ value (cumulative 12yr): EUR', round(total_dz_val/1e12, 2), 'T')

dz_contracts = df[df['cpv_division'].isin(dz['cpv_division'])]
sb_dz = dz_contracts[dz_contracts['single_bidder'] == True]
sb_dz_val = sb_dz['value_eur'].sum()
print('SB Dead Zone value (cumulative): EUR', round(sb_dz_val/1e12, 2), 'T')

n_years = 12
print('Annual DZ value:', round(total_dz_val/n_years/1e12, 2), 'T')
print('Annual SB DZ value:', round(sb_dz_val/n_years/1e12, 2), 'T')

# CPV 33
cpv33 = cpv_stats[cpv_stats['cpv_division'] == 33]
if len(cpv33) > 0:
    row = cpv33.iloc[0]
    print('\nCPV 33 total value:', round(row['total_value']/1e12, 2), 'T =', round(row['total_value']/1e9, 1), 'B')
    print('CPV 33 SB rate:', round(row['sb_rate']*100, 1), '%')

# Total procurement
total_val = df['value_eur'].sum()
print('\nTotal procurement (cumulative):', round(total_val/1e12, 1), 'T')
print('Annual procurement:', round(total_val/n_years/1e12, 2), 'T')
