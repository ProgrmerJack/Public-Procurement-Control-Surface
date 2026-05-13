import pyarrow.parquet as pq
import csv, collections
import numpy as np
from collections import defaultdict
from scipy import stats

# Load procurement data
table = pq.read_table('Data/processed/gprd_with_carbon.parquet',
    columns=['country','year','cpv_division','single_bidder','carbon_intensity_kg_usd'])
countries = table.column('country').to_pylist()
years = table.column('year').to_pylist()
cpvs_col = table.column('cpv_division').to_pylist()
sbs = table.column('single_bidder').to_pylist()
cis = table.column('carbon_intensity_kg_usd').to_pylist()
del table

non_eu = {'CO', 'CH', 'NO'}
gaps = defaultdict(lambda: {'sb_ci': [], 'mb_ci': []})

for i in range(len(countries)):
    c = countries[i]
    yr = years[i]
    ci = cis[i]
    sb = sbs[i]
    if yr is None or ci is None or sb is None: continue
    yr = int(yr)
    if yr < 2012 or yr > 2023: continue
    if ci <= 0 or ci > 10: continue
    key = (c, yr)
    if sb:
        gaps[key]['sb_ci'].append(ci)
    else:
        gaps[key]['mb_ci'].append(ci)

panel = []
for (c, yr), data in gaps.items():
    if len(data['sb_ci']) < 10 or len(data['mb_ci']) < 10:
        continue
    sb_mean = np.mean(data['sb_ci'])
    mb_mean = np.mean(data['mb_ci'])
    gap = sb_mean - mb_mean
    panel.append({
        'country': c, 'year': yr,
        'gap': gap, 'sb_mean': sb_mean, 'mb_mean': mb_mean,
        'is_eu': c not in non_eu,
        'is_control': c in {'CO', 'CH'},
        'post': yr >= 2017,
        'n_sb': len(data['sb_ci']), 'n_mb': len(data['mb_ci'])
    })

eu = [p for p in panel if p['is_eu']]
ctrl = [p for p in panel if p['is_control']]

eu_pre = [p['gap'] for p in eu if not p['post']]
eu_post = [p['gap'] for p in eu if p['post']]
ctrl_pre = [p['gap'] for p in ctrl if not p['post']]
ctrl_post = [p['gap'] for p in ctrl if p['post']]

print('=' * 60)
print('=== EXIOBASE Carbon Gap DiD (EU vs CO/CH) ===')
print(f'EU pre-reform: n={len(eu_pre)}, mean gap={np.mean(eu_pre):.5f}')
print(f'EU post-reform: n={len(eu_post)}, mean gap={np.mean(eu_post):.5f}')
print(f'Control pre-reform: n={len(ctrl_pre)}, mean gap={np.mean(ctrl_pre):.5f}')
print(f'Control post-reform: n={len(ctrl_post)}, mean gap={np.mean(ctrl_post):.5f}')
eu_change = np.mean(eu_post) - np.mean(eu_pre)
ctrl_change = np.mean(ctrl_post) - np.mean(ctrl_pre)
did = eu_change - ctrl_change
print(f'EU change: {eu_change:.5f}')
print(f'Control change: {ctrl_change:.5f}')
print(f'DiD estimate: {did:.5f}')

# CORRECT bootstrap p-value: proportion of bootstrap DiDs <= 0
np.random.seed(42)
all_obs = eu + ctrl
boot = []
for b in range(10000):
    idx = np.random.choice(len(all_obs), len(all_obs), replace=True)
    bp = [all_obs[i] for i in idx]
    ep = [p['gap'] for p in bp if p['is_eu'] and not p['post']]
    epo = [p['gap'] for p in bp if p['is_eu'] and p['post']]
    cp = [p['gap'] for p in bp if p['is_control'] and not p['post']]
    cpo = [p['gap'] for p in bp if p['is_control'] and p['post']]
    if ep and epo and cp and cpo:
        boot.append((np.mean(epo) - np.mean(ep)) - (np.mean(cpo) - np.mean(cp)))
boot = np.array(boot)
# Two-sided test: p = 2 * min(P(boot<=0), P(boot>=0))
p_below_zero = np.mean(boot <= 0)
p_above_zero = np.mean(boot >= 0)
p_correct = 2 * min(p_below_zero, p_above_zero)
print(f'Bootstrap (corrected) p: {p_correct:.6f}')
print(f'  P(boot <= 0) = {p_below_zero:.4f}')
print(f'  P(boot >= 0) = {p_above_zero:.4f}')
print(f'95%% CI: [{np.percentile(boot, 2.5):.5f}, {np.percentile(boot, 97.5):.5f}]')

print()
print('=' * 60)
print('=== Within-EU ITS ===')
t_val, p_val = stats.ttest_ind(eu_pre, eu_post)
print(f'Pre-reform gap: {np.mean(eu_pre):.5f} (n={len(eu_pre)})')
print(f'Post-reform gap: {np.mean(eu_post):.5f} (n={len(eu_post)})')
print(f'Change: {np.mean(eu_post) - np.mean(eu_pre):.5f}')
print(f't = {t_val:.3f}, p = {p_val:.6f}')

# Weighted ITS (weight by sqrt of total contracts)
w_eu_pre = [(p['gap'], np.sqrt(p['n_sb'] + p['n_mb'])) for p in eu if not p['post']]
w_eu_post = [(p['gap'], np.sqrt(p['n_sb'] + p['n_mb'])) for p in eu if p['post']]
w_pre_mean = np.average([x[0] for x in w_eu_pre], weights=[x[1] for x in w_eu_pre])
w_post_mean = np.average([x[0] for x in w_eu_post], weights=[x[1] for x in w_eu_post])
print(f'\nWeighted ITS:')
print(f'  Pre-reform weighted gap: {w_pre_mean:.5f}')
print(f'  Post-reform weighted gap: {w_post_mean:.5f}')
print(f'  Weighted change: {w_post_mean - w_pre_mean:.5f}')

# DZ analysis with proper cpv handling
print()
print('=' * 60)
print('=== Dead Zone Sectors (EU only) ===')
dz_cpv = {9, 14, 15, 24, 31, 33, 34, 35, 44, 45, 65, 77}
dz_gaps = defaultdict(lambda: {'sb_ci': [], 'mb_ci': []})
for i in range(len(countries)):
    c = countries[i]
    yr = years[i]
    ci = cis[i]
    sb = sbs[i]
    cpv = cpvs_col[i]
    if yr is None or ci is None or sb is None or cpv is None: continue
    try:
        cpv_int = int(float(cpv))
    except (ValueError, TypeError):
        continue
    yr = int(yr)
    if yr < 2012 or yr > 2023: continue
    if ci <= 0 or ci > 10: continue
    if cpv_int not in dz_cpv: continue
    if c in non_eu: continue
    key = (c, yr)
    if sb:
        dz_gaps[key]['sb_ci'].append(ci)
    else:
        dz_gaps[key]['mb_ci'].append(ci)

dz_panel = []
for (c, yr), data in dz_gaps.items():
    if len(data['sb_ci']) < 5 or len(data['mb_ci']) < 5:
        continue
    gap = np.mean(data['sb_ci']) - np.mean(data['mb_ci'])
    dz_panel.append({'gap': gap, 'post': yr >= 2017, 'year': yr, 'country': c})

dz_pre = [p['gap'] for p in dz_panel if not p['post']]
dz_post = [p['gap'] for p in dz_panel if p['post']]

if dz_pre and dz_post:
    print(f'DZ pre: n={len(dz_pre)}, mean gap={np.mean(dz_pre):.5f}')
    print(f'DZ post: n={len(dz_post)}, mean gap={np.mean(dz_post):.5f}')
    print(f'DZ change: {np.mean(dz_post) - np.mean(dz_pre):.5f}')
    t_val, p_val = stats.ttest_ind(dz_pre, dz_post)
    print(f'DZ t = {t_val:.3f}, p = {p_val:.6f}')
else:
    print(f'DZ pre: {len(dz_pre)}, DZ post: {len(dz_post)}')

# Now: Eurostat-based ITS (within-sector variation)
print()
print('=' * 60)
print('=== Eurostat-based Carbon ITS ===')

# Load Eurostat intensities
eurostat = {}
with open('Data/processed/eurostat_carbon_intensities.csv', 'r') as f:
    for row in csv.DictReader(f):
        try:
            intensity = float(row['intensity_kg_eur'])
        except (ValueError, TypeError):
            continue
        if intensity <= 0: continue
        key = (row['country'], row['nace'], int(float(row['year'])))
        eurostat[key] = intensity

# CPV-to-NACE crosswalk (simplified mapping)
cpv_to_nace = {
    '03': 'A03', '09': 'B', '14': 'B', '15': 'C10-C12',
    '18': 'C18', '22': 'C22', '24': 'C24', '31': 'C31_C32',
    '33': 'C33', '34': 'C29', '35': 'D35', '38': 'E37-E39',
    '41': 'M71', '42': 'M71', '43': 'M71', '44': 'F',
    '45': 'F', '48': 'J62_J63', '50': 'H49', '51': 'H51',
    '55': 'I', '60': 'H49', '63': 'J62_J63', '64': 'J58',
    '65': 'K64', '66': 'J61', '70': 'J62_J63', '71': 'M71',
    '72': 'M72', '73': 'M73', '75': 'Q86', '76': 'Q86',
    '77': 'N77', '79': 'N79', '80': 'N80', '85': 'O84',
    '90': 'R90-R92', '92': 'R90-R92', '98': 'S95'
}

# Map Eurostat countries (EL -> GR)
eu_code_map = {'EL': 'GR'}

# Build Eurostat-matched panel
e_gaps = defaultdict(lambda: {'sb_ci': [], 'mb_ci': []})
matched = 0
total = 0
for i in range(len(countries)):
    c = countries[i]
    yr = years[i]
    ci_exio = cis[i]
    sb = sbs[i]
    cpv = cpvs_col[i]
    if yr is None or sb is None or cpv is None: continue
    if c in non_eu: continue
    yr = int(yr)
    if yr < 2012 or yr > 2023: continue
    try:
        cpv_str = str(int(float(cpv))).zfill(2)
    except (ValueError, TypeError):
        continue
    
    nace = cpv_to_nace.get(cpv_str)
    if nace is None: continue
    
    # Map country code for Eurostat
    ec = {v: k for k, v in eu_code_map.items()}.get(c, c)
    # Also try: GR -> EL in Eurostat
    if c == 'GR':
        ec = 'EL'
    
    key = (ec, nace, yr)
    intensity = eurostat.get(key)
    if intensity is None:
        # Try without year
        for test_yr in range(yr-1, yr+2):
            intensity = eurostat.get((ec, nace, test_yr))
            if intensity: break
    if intensity is None: continue
    
    total += 1
    matched += 1
    ckey = (c, yr)
    if sb:
        e_gaps[ckey]['sb_ci'].append(intensity)
    else:
        e_gaps[ckey]['mb_ci'].append(intensity)

print(f'Eurostat matches: {matched} / {total}')

e_panel = []
for (c, yr), data in e_gaps.items():
    if len(data['sb_ci']) < 10 or len(data['mb_ci']) < 10:
        continue
    gap = np.mean(data['sb_ci']) - np.mean(data['mb_ci'])
    e_panel.append({'country': c, 'year': yr, 'gap': gap, 'post': yr >= 2017})

e_pre = [p['gap'] for p in e_panel if not p['post']]
e_post = [p['gap'] for p in e_panel if p['post']]

if e_pre and e_post:
    print(f'Eurostat pre: n={len(e_pre)}, mean gap={np.mean(e_pre):.5f}')
    print(f'Eurostat post: n={len(e_post)}, mean gap={np.mean(e_post):.5f}')
    print(f'Eurostat change: {np.mean(e_post) - np.mean(e_pre):.5f}')
    t_val, p_val = stats.ttest_ind(e_pre, e_post)
    print(f'Eurostat t = {t_val:.3f}, p = {p_val:.6f}')
else:
    print(f'Eurostat pre: {len(e_pre)}, post: {len(e_post)} - insufficient')

# Save all results
import json
results = {
    'exiobase_did': {
        'eu_pre_gap': float(np.mean(eu_pre)),
        'eu_post_gap': float(np.mean(eu_post)),
        'eu_change': float(eu_change),
        'ctrl_change': float(ctrl_change),
        'did_effect': float(did),
        'bootstrap_p': float(p_correct),
        'ci_lower': float(np.percentile(boot, 2.5)),
        'ci_upper': float(np.percentile(boot, 97.5)),
    },
    'within_eu_its': {
        'pre_gap': float(np.mean(eu_pre)),
        'post_gap': float(np.mean(eu_post)),
        'change': float(np.mean(eu_post) - np.mean(eu_pre)),
        't_stat': float(stats.ttest_ind(eu_pre, eu_post).statistic),
        'p_value': float(stats.ttest_ind(eu_pre, eu_post).pvalue),
    }
}
if dz_pre and dz_post:
    results['dead_zone_its'] = {
        'pre_gap': float(np.mean(dz_pre)),
        'post_gap': float(np.mean(dz_post)),
        'change': float(np.mean(dz_post) - np.mean(dz_pre)),
        't_stat': float(stats.ttest_ind(dz_pre, dz_post).statistic),
        'p_value': float(stats.ttest_ind(dz_pre, dz_post).pvalue),
    }

with open('results/causal_id/carbon_did_panel.json', 'w') as f:
    json.dump(results, f, indent=2)
print('\nResults saved to results/carbon_did_panel.json')
