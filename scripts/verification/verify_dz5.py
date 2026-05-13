import pyarrow.parquet as pq
import numpy as np

pf = pq.read_table(r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\processed\gprd_with_carbon.parquet', 
                     columns=['value_eur', 'single_bidder', 'cpv_division', 'year', 'country'])
df = pf.to_pandas()
eu = df[df['country'] != 'CO']

# EU-context per year
for y in sorted(eu['year'].dropna().unique()):
    yr = eu[eu['year'] == y]
    print(f'{int(y)}: N={len(yr):>10,}  Value=EUR {yr["value_eur"].sum()/1e12:.2f}T')

# DZ SB rate 
dz_cpvs = ['14', '15', '18', '19', '22', '24', '30', '31', '33', '34', '35', '38', '39', '42', '43', '44', '55', '60', '63', '65', '77', '90']
eu_dz = eu[eu['cpv_division'].isin(dz_cpvs)]
sb_rate_dz = eu_dz['single_bidder'].mean()
print(f'\nEU DZ SB rate: {sb_rate_dz*100:.1f}%')
print(f'EU DZ N: {len(eu_dz):,}')

# Annual calculation using OECD baseline
# OECD says EU procurement = ~2T/yr
# DZ share = 51.5%
# DZ annual spending (OECD-scaled): 0.515 * 2T = 1.03T
# SB rate in DZ: computed above
# Annual SB DZ: 0.515 * 2T * sb_rate_dz
oecd_annual = 2e12  # EUR 2T
annual_dz = 0.515 * oecd_annual
annual_sb_dz = annual_dz * sb_rate_dz
print(f'\nOECD-scaled annual DZ: EUR {annual_dz/1e9:.0f}B')
print(f'OECD-scaled annual SB DZ: EUR {annual_sb_dz/1e9:.0f}B')
print(f'OECD-scaled Monopoly Tax (8%): EUR {0.08 * annual_sb_dz/1e9:.1f}B')
