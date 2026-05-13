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
    is_eu = c not in non_eu and c != 'IS'
    is_control = c in {'CO', 'CH'}
    post = yr >= 2017
    panel.append({
        'country': c, 'year': yr,
        'gap': gap, 'sb_mean': sb_mean, 'mb_mean': mb_mean,
        'is_eu': is_eu, 'is_control': is_control, 'post': post,
        'n_sb': len(data['sb_ci']), 'n_mb': len(data['mb_ci'])
    })

eu = [p for p in panel if p['is_eu']]
ctrl = [p for p in panel if p['is_control']]

eu_pre = [p['gap'] for p in eu if not p['post']]
eu_post = [p['gap'] for p in eu if p['post']]
ctrl_pre = [p['gap'] for p in ctrl if not p['post']]
ctrl_post = [p['gap'] for p in ctrl if p['post']]

print('=== EXIOBASE Carbon Gap DiD (Panel) ===')
print(f'EU pre: n={len(eu_pre)}, mean gap={np.mean(eu_pre):.5f}')
print(f'EU post: n={len(eu_post)}, mean gap={np.mean(eu_post):.5f}')
n_ctrl_pre = len(ctrl_pre)
n_ctrl_post = len(ctrl_post)
print(f'Control pre: n={n_ctrl_pre}')
print(f'Control post: n={n_ctrl_post}')

if n_ctrl_pre > 0:
    print(f'Control pre mean: {np.mean(ctrl_pre):.5f}')
if n_ctrl_post > 0:
    print(f'Control post mean: {np.mean(ctrl_post):.5f}')

if ctrl_pre and ctrl_post:
    did = (np.mean(eu_post) - np.mean(eu_pre)) - (np.mean(ctrl_post) - np.mean(ctrl_pre))
    print(f'DiD effect: {did:.5f}')
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
    p_val = np.mean(np.abs(boot) >= np.abs(did))
    print(f'Bootstrap p: {p_val:.4f}')
    print(f'95%% CI: [{np.percentile(boot, 2.5):.5f}, {np.percentile(boot, 97.5):.5f}]')
else:
    # No controls - do within-EU only
    print('No control group observations, doing within-EU ITS only')

# Within-EU ITS
t_val, p_val = stats.ttest_ind(eu_pre, eu_post)
print(f'\n=== Within-EU ITS ===')
print(f'Pre mean gap: {np.mean(eu_pre):.5f} (n={len(eu_pre)})')
print(f'Post mean gap: {np.mean(eu_post):.5f} (n={len(eu_post)})')
print(f'Change: {np.mean(eu_post) - np.mean(eu_pre):.5f}')
print(f't = {t_val:.3f}, p = {p_val:.6f}')

# Year-by-year
yearly = defaultdict(list)
for p in eu:
    yearly[p['year']].append(p['gap'])
print(f'\n=== Year-by-year EU carbon gaps ===')
for yr in sorted(yearly.keys()):
    g = yearly[yr]
    print(f'{yr}: n={len(g)}, mean gap={np.mean(g):.5f}')

# Dead Zone sectors
dz_cpv = {9, 14, 15, 24, 31, 33, 34, 35, 44, 45, 65, 77}
dz_gaps = defaultdict(lambda: {'sb_ci': [], 'mb_ci': []})
for i in range(len(countries)):
    c = countries[i]
    yr = years[i]
    ci = cis[i]
    sb = sbs[i]
    cpv = cpvs_col[i]
    if yr is None or ci is None or sb is None or cpv is None: continue
    yr = int(yr)
    if yr < 2012 or yr > 2023: continue
    if ci <= 0 or ci > 10: continue
    if int(cpv) not in dz_cpv: continue
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
    dz_panel.append({'gap': gap, 'post': yr >= 2017, 'year': yr})

dz_pre = [p['gap'] for p in dz_panel if not p['post']]
dz_post = [p['gap'] for p in dz_panel if p['post']]
print(f'\n=== Dead Zone Sectors Only (EU) ===')
print(f'DZ pre: n={len(dz_pre)}, mean gap={np.mean(dz_pre):.5f}')
print(f'DZ post: n={len(dz_post)}, mean gap={np.mean(dz_post):.5f}')
print(f'DZ change: {np.mean(dz_post) - np.mean(dz_pre):.5f}')
t_val, p_val = stats.ttest_ind(dz_pre, dz_post)
print(f'DZ t = {t_val:.3f}, p = {p_val:.6f}')
