import pyarrow.parquet as pq
import csv, collections
import numpy as np
from scipy import stats

# CPV to NACE mapping (standard concordance)
CPV_NACE = {
    '3': 'A01',   # Agricultural products
    '9': 'B',     # Petroleum products (Mining)
    '14': 'B',    # Mining/quarrying
    '15': 'A',    # Food/beverages (Agriculture)
    '16': 'A',    # Agricultural machinery
    '18': 'C13-C15',  # Clothing/textiles
    '19': 'C16',  # Leather (Wood)
    '22': 'C17',  # Printed matter (Paper)
    '24': 'C20',  # Chemical products
    '30': 'C26',  # Office/computer equipment
    '31': 'C27',  # Electrical machinery
    '32': 'J61',  # Radio/TV/telecom
    '33': 'C21',  # Medical equipment -> Pharma
    '34': 'C29',  # Transport equipment
    '35': 'M71',  # Security/defence -> Prof services
    '37': 'C28',  # Musical instruments -> Machinery
    '38': 'M72',  # Lab equipment -> R&D
    '39': 'C22',  # Furniture -> Rubber/plastic
    '41': 'E36',  # Collected water
    '42': 'C20',  # Industrial chemicals
    '43': 'D',    # Electricity/energy
    '44': 'F',    # Construction structures
    '45': 'F',    # Construction work
    '48': 'J62_J63',  # Software
    '50': 'H49',  # Repair/maintenance -> Transport
    '51': 'F',    # Construction installation
    '55': 'I',    # Hotel/restaurant
    '60': 'H49',  # Transport services
    '63': 'H52',  # Transport support
    '64': 'N80-N82',  # Sports/recreation -> Admin
    '65': 'O',    # Public admin
    '66': 'K64',  # Financial services
    '70': 'J62_J63',  # IT services
    '71': 'M71',  # Architectural/engineering
    '72': 'M72',  # R&D
    '73': 'M72',  # Research -> R&D
    '75': 'O',    # Public admin services
    '76': 'M74_M75',  # Natural resource services
    '77': 'N77',  # Rental services
    '79': 'N79',  # Travel agency
    '80': 'P',    # Education
    '85': 'Q86',  # Health services
    '90': 'E37-E39',  # Sewage/waste
    '92': 'R',    # Recreation/culture
    '98': 'R',    # Other community
}

# Load data
table = pq.read_table('Data/processed/gprd_with_carbon.parquet',
    columns=['country','year','cpv_division','single_bidder','carbon_intensity_kg_usd'])
countries = table.column('country').to_pylist()
years = table.column('year').to_pylist()
cpvs = table.column('cpv_division').to_pylist()
sb = table.column('single_bidder').to_pylist()

# Load Eurostat
eurostat = {}
with open('Data/processed/eurostat_carbon_intensities.csv') as f:
    for row in csv.DictReader(f):
        try:
            eurostat[(row['country'], row['nace'], row['year'])] = float(row['intensity_kg_eur'])
        except:
            pass
print(f'Eurostat: {len(eurostat)} entries')

# Treatment groups
early_treat = {'AT','BE','BG','CY','DK','FI','FR','DE','HU','IE','IT','LT','RO'}
late_treat = {'CZ','EE','HR','LV','NL','PL'}
all_eu_treat = early_treat | late_treat | {'ES','GR','IS','LU','MT','PT','SE','SI','SK','UK'}
non_treat = {'NO','CH'}

# Match contracts
cy_data = collections.defaultdict(lambda: {'sb_ci':[],'mb_ci':[]})
matched = 0

for i in range(len(countries)):
    c = countries[i]
    if not c or c == 'CO':
        continue
    y = years[i]
    if not y or y < 2012 or y > 2023:
        continue
    cpv = cpvs[i]
    if not cpv:
        continue
    s = sb[i]
    if s is None:
        continue
    
    cpv_str = str(int(cpv)) if isinstance(cpv, float) else str(cpv)
    nace = CPV_NACE.get(cpv_str)
    if not nace:
        continue
    
    yr_str = str(int(y))
    ci = eurostat.get((c, nace, yr_str))
    if ci is None:
        for ty in [str(int(y)-1), str(int(y)+1), str(int(y)-2)]:
            ci = eurostat.get((c, nace, ty))
            if ci is not None:
                break
    if ci is None:
        continue
    
    matched += 1
    key = (c, int(y))
    if s:
        cy_data[key]['sb_ci'].append(ci)
    else:
        cy_data[key]['mb_ci'].append(ci)

print(f'Matched contracts: {matched}')
print(f'Country-year cells: {len(cy_data)}')

# === AGGREGATE CARBON DiD ===
print('\n=== AGGREGATE CARBON DiD (EUROSTAT) ===')
treat_gaps = {}
for (c, y), data in cy_data.items():
    if len(data['sb_ci']) < 10 or len(data['mb_ci']) < 10:
        continue
    gap = np.mean(data['sb_ci']) - np.mean(data['mb_ci'])
    if c in all_eu_treat:
        if c not in treat_gaps:
            treat_gaps[c] = {'pre':[], 'post':[]}
        if y <= 2015:
            treat_gaps[c]['pre'].append(gap)
        elif y >= 2017:
            treat_gaps[c]['post'].append(gap)

all_pre = [g for d in treat_gaps.values() for g in d['pre']]
all_post = [g for d in treat_gaps.values() for g in d['post']]
change = np.mean(all_post) - np.mean(all_pre)
t, p = stats.ttest_ind(all_post, all_pre)
print(f'Pre: mean={np.mean(all_pre):.4f} (n={len(all_pre)})')
print(f'Post: mean={np.mean(all_post):.4f} (n={len(all_post)})')
print(f'Change: {change:.4f}, t={t:.3f}, p={p:.4f}')

# LOO
print('\n=== LOO ROBUSTNESS ===')
loo = {}
for exc in sorted(treat_gaps.keys()):
    pre_l = [g for c, d in treat_gaps.items() if c != exc for g in d['pre']]
    post_l = [g for c, d in treat_gaps.items() if c != exc for g in d['post']]
    if pre_l and post_l:
        ch = np.mean(post_l) - np.mean(pre_l)
        t_l, p_l = stats.ttest_ind(post_l, pre_l)
        loo[exc] = (ch, t_l, p_l)

neg = sum(1 for v in loo.values() if v[0] < 0)
sig = sum(1 for v in loo.values() if v[2] < 0.05)
print(f'{neg}/{len(loo)} negative, {sig}/{len(loo)} significant (p<0.05)')

for c, (v, t, p) in sorted(loo.items(), key=lambda x: x[1][0])[:5]:
    print(f'  Excl {c}: {v:.4f} t={t:.3f} p={p:.4f}')
print('  ...')
for c, (v, t, p) in sorted(loo.items(), key=lambda x: x[1][0])[-5:]:
    print(f'  Excl {c}: {v:.4f} t={t:.3f} p={p:.4f}')

# Key countries
for key_c in ['GR', 'DE', 'FR', 'IT', 'PL', 'UK']:
    if key_c in loo:
        v, t, p = loo[key_c]
        print(f'  KEY: Excl {key_c}: {v:.4f} t={t:.3f} p={p:.4f}')

# === STAGGERED ===
print('\n=== STAGGERED CARBON DiD (EUROSTAT) ===')
pe, poe, pl, pol = [], [], [], []
for (c, y), data in cy_data.items():
    if len(data['sb_ci']) < 10 or len(data['mb_ci']) < 10:
        continue
    gap = np.mean(data['sb_ci']) - np.mean(data['mb_ci'])
    if c in early_treat:
        if y <= 2015: pe.append(gap)
        elif y >= 2017: poe.append(gap)
    elif c in late_treat:
        if y <= 2015: pl.append(gap)
        elif y >= 2017: pol.append(gap)

if pe and poe and pl and pol:
    sd = (np.mean(poe)-np.mean(pe)) - (np.mean(pol)-np.mean(pl))
    print(f'Early: pre={np.mean(pe):.4f}, post={np.mean(poe):.4f}')
    print(f'Late: pre={np.mean(pl):.4f}, post={np.mean(pol):.4f}')
    print(f'Staggered DiD: {sd:.4f}')
    
    # Bootstrap
    rng = np.random.default_rng(42)
    boots = []
    for _ in range(5000):
        b = (np.mean(rng.choice(poe,len(poe)))-np.mean(rng.choice(pe,len(pe)))) - \
            (np.mean(rng.choice(pol,len(pol)))-np.mean(rng.choice(pl,len(pl))))
        boots.append(b)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    p_boot = 2*min(np.mean(np.array(boots)>=0), np.mean(np.array(boots)<=0))
    print(f'95% CI: [{lo:.4f}, {hi:.4f}], p_boot={p_boot:.4f}')

# === DZ-RESTRICTED (EUROSTAT) ===
print('\n=== DEAD ZONE CARBON DiD (EUROSTAT) ===')
dz_cpvs = {'9','14','24','33','34','63'}
dz_treat = {}
for (c, y), data in cy_data.items():
    cpv_in_dz = False
    # Need to re-check -- this aggregated data doesn't split by CPV
    # Let me do it differently
    pass

# Actually need to re-collect DZ-specific data
dz_cy = collections.defaultdict(lambda: {'sb_ci':[],'mb_ci':[]})
for i in range(len(countries)):
    c = countries[i]
    if not c or c == 'CO': continue
    y = years[i]
    if not y or y < 2012 or y > 2023: continue
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
    if c not in all_eu_treat: continue
    key = (c, int(y))
    if s: dz_cy[key]['sb_ci'].append(ci)
    else: dz_cy[key]['mb_ci'].append(ci)

dz_pre, dz_post = [], []
dz_by_c = {}
for (c, y), data in dz_cy.items():
    if len(data['sb_ci']) < 5 or len(data['mb_ci']) < 5: continue
    gap = np.mean(data['sb_ci']) - np.mean(data['mb_ci'])
    if c not in dz_by_c: dz_by_c[c] = {'pre':[], 'post':[]}
    if y <= 2015:
        dz_pre.append(gap)
        dz_by_c[c]['pre'].append(gap)
    elif y >= 2017:
        dz_post.append(gap)
        dz_by_c[c]['post'].append(gap)

if dz_pre and dz_post:
    ch = np.mean(dz_post) - np.mean(dz_pre)
    t_dz, p_dz = stats.ttest_ind(dz_post, dz_pre)
    print(f'DZ pre={np.mean(dz_pre):.4f} (n={len(dz_pre)}), post={np.mean(dz_post):.4f} (n={len(dz_post)})')
    print(f'DZ change: {ch:.4f}, t={t_dz:.3f}, p={p_dz:.4f}')
    
    neg_dz = 0
    for exc in dz_by_c:
        p_l = [g for c2, d in dz_by_c.items() if c2 != exc for g in d['pre']]
        po_l = [g for c2, d in dz_by_c.items() if c2 != exc for g in d['post']]
        if p_l and po_l:
            if np.mean(po_l) - np.mean(p_l) < 0: neg_dz += 1
    print(f'DZ LOO: {neg_dz}/{len(dz_by_c)} negative')
else:
    print('Insufficient DZ data for DiD')
