import pyarrow.parquet as pq
import csv, collections
import numpy as np
from scipy import stats

CPV_NACE = {
    '3': 'A01', '9': 'B', '14': 'B', '15': 'A', '24': 'C20', '33': 'C21',
    '34': 'C29', '42': 'C20', '44': 'F', '45': 'F',
}

table = pq.read_table('Data/processed/gprd_with_carbon.parquet',
    columns=['country','year','cpv_division','single_bidder','carbon_intensity_kg_usd'])
countries = table.column('country').to_pylist()
years = table.column('year').to_pylist()
cpvs = table.column('cpv_division').to_pylist()
sb = table.column('single_bidder').to_pylist()
ci_col = table.column('carbon_intensity_kg_usd').to_pylist()

all_eu = {'AT','BE','BG','CY','CZ','DK','EE','ES','FI','FR','DE','GR','HR','HU',
          'IE','IS','IT','LT','LU','LV','MT','NL','PL','PT','RO','SE','SI','SK','UK'}
dz_cpvs = {'9','14','24','33','34','63'}

eurostat = {}
with open('Data/processed/eurostat_carbon_intensities.csv') as f:
    for row in csv.DictReader(f):
        try:
            eurostat[(row['country'], row['nace'], row['year'])] = float(row['intensity_kg_eur'])
        except: pass

# EUROSTAT pre-trend
cy_gaps = collections.defaultdict(lambda: {'sb':[], 'mb':[]})
for i in range(len(countries)):
    c = countries[i]
    if not c or c not in all_eu: continue
    y = years[i]
    if not y or y < 2012 or y > 2015: continue
    cpv = cpvs[i]
    if not cpv: continue
    s = sb[i]
    if s is None: continue
    cpv_str = str(int(cpv)) if isinstance(cpv, float) else str(cpv)
    if cpv_str not in dz_cpvs: continue
    nace = CPV_NACE.get(cpv_str)
    if not nace: continue
    yr_str = str(int(y))
    ci = eurostat.get((c, nace, yr_str))
    if ci is None:
        for ty in [str(int(y)-1), str(int(y)+1)]:
            ci = eurostat.get((c, nace, ty))
            if ci: break
    if ci is None: continue
    key = (c, int(y))
    if s: cy_gaps[key]['sb'].append(ci)
    else: cy_gaps[key]['mb'].append(ci)

year_gaps = collections.defaultdict(list)
for (c, y), data in cy_gaps.items():
    if len(data['sb']) >= 5 and len(data['mb']) >= 5:
        gap = np.mean(data['sb']) - np.mean(data['mb'])
        year_gaps[y].append(gap)

print('=== DEAD ZONE PRE-TREND (EUROSTAT) ===')
for y in sorted(year_gaps.keys()):
    gaps = year_gaps[y]
    print(f'  {y}: mean gap = {np.mean(gaps):.4f}, n={len(gaps)}')

all_y, all_g = [], []
for y in sorted(year_gaps.keys()):
    for g in year_gaps[y]:
        all_y.append(y)
        all_g.append(g)
slope, intercept, r, p, se = stats.linregress(all_y, all_g)
print(f'Linear trend: slope={slope:.5f}, p={p:.4f}, r={r:.4f}')
if p > 0.05:
    print('=> NO significant pre-trend (parallel trends supported)')
else:
    print('=> WARNING: significant pre-trend')

# EXIOBASE pre-trend
cy_ex = collections.defaultdict(lambda: {'sb':[], 'mb':[]})
for i in range(len(countries)):
    c = countries[i]
    if not c or c not in all_eu: continue
    y = years[i]
    if not y or y < 2012 or y > 2015: continue
    cpv = cpvs[i]
    if not cpv: continue
    s = sb[i]
    if s is None: continue
    ci = ci_col[i]
    if ci is None: continue
    cpv_str = str(int(cpv)) if isinstance(cpv, float) else str(cpv)
    if cpv_str not in dz_cpvs: continue
    key = (c, int(y))
    if s: cy_ex[key]['sb'].append(ci)
    else: cy_ex[key]['mb'].append(ci)

year_gaps_ex = collections.defaultdict(list)
for (c, y), data in cy_ex.items():
    if len(data['sb']) >= 5 and len(data['mb']) >= 5:
        gap = np.mean(data['sb']) - np.mean(data['mb'])
        year_gaps_ex[y].append(gap)

print('\n=== DEAD ZONE PRE-TREND (EXIOBASE) ===')
for y in sorted(year_gaps_ex.keys()):
    gaps = year_gaps_ex[y]
    print(f'  {y}: mean gap = {np.mean(gaps):.4f}, n={len(gaps)}')

all_ye, all_ge = [], []
for y in sorted(year_gaps_ex.keys()):
    for g in year_gaps_ex[y]:
        all_ye.append(y)
        all_ge.append(g)
slope_e, _, r_e, p_e, _ = stats.linregress(all_ye, all_ge)
print(f'Linear trend: slope={slope_e:.5f}, p={p_e:.4f}')
if p_e > 0.05:
    print('=> NO significant pre-trend (parallel trends supported)')
else:
    print('=> WARNING: significant pre-trend')
