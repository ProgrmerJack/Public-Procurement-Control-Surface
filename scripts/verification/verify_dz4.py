import pyarrow.parquet as pq
import numpy as np

pf = pq.read_table(r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\processed\gprd_with_carbon.parquet', 
                     columns=['value_eur', 'single_bidder', 'carbon_intensity_kg_usd', 'cpv_division', 'year', 'country'])
df = pf.to_pandas()
eu = df[df['country'] != 'CO']

# Check CPV 33 with string comparison
cpv33 = eu[eu['cpv_division'] == '33']
print(f'CPV 33 (string match): N={len(cpv33):,}, Value={cpv33["value_eur"].sum()/1e9:.1f}B')
if len(cpv33) > 0:
    sb33 = cpv33[cpv33['single_bidder'] == True]
    print(f'  SB: N={len(sb33):,}, Value={sb33["value_eur"].sum()/1e9:.1f}B')
    print(f'  SB rate: {len(sb33)/len(cpv33)*100:.1f}%')
    print(f'  Mean value per contract: EUR {cpv33["value_eur"].mean():,.0f}')
    print(f'  Median value per contract: EUR {cpv33["value_eur"].median():,.0f}')
    # Check for outliers
    q99 = cpv33['value_eur'].quantile(0.99)
    q999 = cpv33['value_eur'].quantile(0.999)
    maxv = cpv33['value_eur'].max()
    print(f'  99th pctile: EUR {q99:,.0f}')
    print(f'  99.9th pctile: EUR {q999:,.0f}')  
    print(f'  Max: EUR {maxv:,.0f}')
    
    # Top 10 largest contracts
    top10 = cpv33.nlargest(10, 'value_eur')
    print('\n  Top 10 contracts:')
    for _, r in top10.iterrows():
        print(f'    EUR {r["value_eur"]:>15,.0f} | {r["country"]} | {int(r["year"])} | SB={r["single_bidder"]}')

# Check overall value distribution - are there extreme outliers?
print('\n=== VALUE DISTRIBUTION (EU-context) ===')
print(f'Mean: EUR {eu["value_eur"].mean():,.0f}')
print(f'Median: EUR {eu["value_eur"].median():,.0f}')
print(f'99.9th: EUR {eu["value_eur"].quantile(0.999):,.0f}')
print(f'Max: EUR {eu["value_eur"].max():,.0f}')
print(f'Total: EUR {eu["value_eur"].sum()/1e12:.1f}T')

# Count contracts > 1 billion EUR
mega = eu[eu['value_eur'] > 1e9]
print(f'\nContracts > EUR 1B: {len(mega):,} (total: EUR {mega["value_eur"].sum()/1e12:.1f}T)')
ultra = eu[eu['value_eur'] > 1e10]
print(f'Contracts > EUR 10B: {len(ultra):,} (total: EUR {ultra["value_eur"].sum()/1e12:.1f}T)')
giga = eu[eu['value_eur'] > 1e11]
print(f'Contracts > EUR 100B: {len(giga):,} (total: EUR {giga["value_eur"].sum()/1e12:.1f}T)')
