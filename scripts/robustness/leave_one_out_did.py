"""Leave-one-out DiD robustness analysis for governance reform effect."""
import pyarrow.parquet as pq
import numpy as np
import json
import collections

# Load data
table = pq.read_table('Data/processed/gprd_with_carbon.parquet')
df_cols = ['country', 'year', 'single_bidder', 'carbon_intensity_kg_usd']
arrays = {c: table.column(c).to_pylist() for c in df_cols}
n = len(arrays['country'])

# Directive transposition years
transpose_year = {
    'DK': 2016, 'EE': 2016, 'FI': 2016, 'FR': 2016, 'DE': 2016,
    'HU': 2016, 'IE': 2016, 'LV': 2016, 'LT': 2016, 'MT': 2016,
    'PL': 2016, 'PT': 2016, 'RO': 2016,
    'AT': 2017, 'BE': 2017, 'CZ': 2017, 'ES': 2017, 'IT': 2017, 'SI': 2017,
    'BG': 2018, 'CY': 2018, 'GR': 2018, 'HR': 2018, 'LU': 2018,
    'NL': 2018, 'SE': 2018, 'SK': 2018, 'GB': 2018
}

# Compute country-year SB rates
cy_data = collections.defaultdict(lambda: [0, 0])
for i in range(n):
    c = arrays['country'][i]
    y = arrays['year'][i]
    if c and c != 'CO' and y and 2012 <= y <= 2023:
        sb = arrays['single_bidder'][i]
        if sb is not None:
            cy_data[(c, int(y))][1] += 1
            if sb:
                cy_data[(c, int(y))][0] += 1

cy_rates = {}
for (c, y), (sb, tot) in cy_data.items():
    if tot >= 100:
        cy_rates[(c, y)] = sb / tot

early_treated = [c for c, y in transpose_year.items() if y == 2016]
late_treated = [c for c, y in transpose_year.items() if y >= 2017]

def compute_did(treated_list, control_list):
    pre_t, post_t, pre_c, post_c = [], [], [], []
    for (c, y), rate in cy_rates.items():
        if c in treated_list:
            if 2012 <= y <= 2015:
                pre_t.append(rate)
            elif 2016 <= y <= 2023:
                post_t.append(rate)
        elif c in control_list:
            if 2012 <= y <= 2015:
                pre_c.append(rate)
            elif 2016 <= y <= 2023:
                post_c.append(rate)
    if not all([pre_t, post_t, pre_c, post_c]):
        return None, None, None
    att = (np.mean(post_t) - np.mean(pre_t)) - (np.mean(post_c) - np.mean(pre_c))
    np.random.seed(42)
    boot_atts = []
    for _ in range(1000):
        bp_t = np.random.choice(pre_t, len(pre_t), replace=True)
        bpo_t = np.random.choice(post_t, len(post_t), replace=True)
        bp_c = np.random.choice(pre_c, len(pre_c), replace=True)
        bpo_c = np.random.choice(post_c, len(post_c), replace=True)
        boot_atts.append((np.mean(bpo_t) - np.mean(bp_t)) - (np.mean(bpo_c) - np.mean(bp_c)))
    se = np.std(boot_atts)
    p = 2 * min(np.mean(np.array(boot_atts) >= 0), np.mean(np.array(boot_atts) <= 0))
    return att, se, p

# Baseline
att_base, se_base, p_base = compute_did(early_treated, late_treated)
print(f'Baseline: ATT = {att_base*100:.2f} pp, SE = {se_base*100:.2f}, p = {p_base:.4f}')
print()

# Leave-one-out
results = {}
all_countries = sorted(set(early_treated + late_treated))
for drop_c in all_countries:
    t_list = [c for c in early_treated if c != drop_c]
    c_list = [c for c in late_treated if c != drop_c]
    if len(t_list) >= 2 and len(c_list) >= 2:
        att, se, p = compute_did(t_list, c_list)
        if att is not None:
            results[drop_c] = {'att_pp': round(att * 100, 3), 'se_pp': round(se * 100, 3), 'p': round(p, 4)}
            sig = '***' if p < 0.001 else ('**' if p < 0.01 else ('*' if p < 0.05 else ''))
            group = 'EARLY' if drop_c in early_treated else 'LATE '
            print(f'  Drop {drop_c} ({group}): ATT = {att*100:+.2f} pp, p = {p:.4f} {sig}')

# Summary
atts = [v['att_pp'] for v in results.values()]
ps = [v['p'] for v in results.values()]
print(f'\nRange: [{min(atts):.2f}, {max(atts):.2f}] pp')
print(f'All negative: {all(a < 0 for a in atts)}')
print(f'All p < 0.05: {all(p < 0.05 for p in ps)}')
print(f'Min p: {min(ps):.4f}, Max p: {max(ps):.4f}')

# Now run Dead Zone-specific Eurostat carbon DiD
print('\n=== DEAD ZONE EUROSTAT CARBON DiD ===')

# Load Eurostat intensities
import csv
eurostat_ci = {}
try:
    with open('Data/raw/eurostat_aea_ghg_by_nace_country_year.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                country = row.get('geo', row.get('country', ''))
                nace = row.get('nace_r2', row.get('sector', ''))
                year = int(float(row.get('TIME_PERIOD', row.get('year', 0))))
                val = float(row.get('OBS_VALUE', row.get('value', 0)))
                if country and nace and year and val > 0:
                    eurostat_ci[(country, nace, year)] = val
            except (ValueError, TypeError):
                continue
    print(f'Loaded {len(eurostat_ci)} Eurostat intensity records')
except Exception as e:
    print(f'Eurostat AEA load failed: {e}')

# Dead Zone EXIOBASE sectors (high carbon + high SB)
dead_zone_sectors = ['Mining and quarrying', 'Chemical products', 'Agriculture',
                     'Metal products', 'Food products', 'Land transport']

# Compute pre/post carbon premium for Dead Zone sectors only
dz_pre_sb, dz_pre_mb, dz_post_sb, dz_post_mb = [], [], [], []
for i in range(n):
    c = arrays['country'][i]
    y = arrays['year'][i]
    sb = arrays['single_bidder'][i]
    ci = arrays['carbon_intensity_kg_usd'][i]
    if c and c != 'CO' and y and sb is not None and ci and ci > 0:
        # Check if in Dead Zone sector (using EXIOBASE sector from parquet)
        sector = table.column('exiobase_sector')[i].as_py() if 'exiobase_sector' in table.schema.names else None
        if sector and any(dz in str(sector) for dz in ['Mining', 'Chemical', 'Agri', 'Metal', 'Food', 'Land transport']):
            if 2012 <= y <= 2015:
                if sb:
                    dz_pre_sb.append(ci)
                else:
                    dz_pre_mb.append(ci)
            elif 2017 <= y <= 2023:
                if sb:
                    dz_post_sb.append(ci)
                else:
                    dz_post_mb.append(ci)

if dz_pre_sb and dz_pre_mb and dz_post_sb and dz_post_mb:
    pre_premium = np.mean(dz_pre_sb) - np.mean(dz_pre_mb)
    post_premium = np.mean(dz_post_sb) - np.mean(dz_post_mb)
    dz_did = post_premium - pre_premium
    
    # Bootstrap
    np.random.seed(42)
    boot_dids = []
    for _ in range(1000):
        b_pre_sb = np.random.choice(dz_pre_sb, len(dz_pre_sb), replace=True)
        b_pre_mb = np.random.choice(dz_pre_mb, len(dz_pre_mb), replace=True)
        b_post_sb = np.random.choice(dz_post_sb, len(dz_post_sb), replace=True)
        b_post_mb = np.random.choice(dz_post_mb, len(dz_post_mb), replace=True)
        b_did = (np.mean(b_post_sb) - np.mean(b_post_mb)) - (np.mean(b_pre_sb) - np.mean(b_pre_mb))
        boot_dids.append(b_did)
    se_dz = np.std(boot_dids)
    p_dz = 2 * min(np.mean(np.array(boot_dids) >= 0), np.mean(np.array(boot_dids) <= 0))
    ci_low = np.percentile(boot_dids, 2.5)
    ci_high = np.percentile(boot_dids, 97.5)
    
    print(f'Dead Zone pre-premium: {pre_premium:.4f} kg/USD')
    print(f'Dead Zone post-premium: {post_premium:.4f} kg/USD')
    print(f'Dead Zone DiD: {dz_did:.4f} kg/USD')
    print(f'SE: {se_dz:.4f}, p = {p_dz:.4f}')
    print(f'95% CI: [{ci_low:.4f}, {ci_high:.4f}]')
    print(f'N: pre_sb={len(dz_pre_sb)}, pre_mb={len(dz_pre_mb)}, post_sb={len(dz_post_sb)}, post_mb={len(dz_post_mb)}')

# Save all results
output = {
    'leave_one_out': {
        'baseline': {'att_pp': round(att_base * 100, 3), 'se_pp': round(se_base * 100, 3), 'p': round(p_base, 4)},
        'results': results,
        'summary': {
            'range_pp': [round(min(atts), 3), round(max(atts), 3)],
            'all_negative': all(a < 0 for a in atts),
            'all_p_below_05': all(p < 0.05 for p in ps),
            'n_dropped': len(results)
        }
    }
}
if dz_pre_sb:
    output['dead_zone_carbon_did'] = {
        'pre_premium': round(pre_premium, 4),
        'post_premium': round(post_premium, 4),
        'did_effect': round(dz_did, 4),
        'se': round(se_dz, 4),
        'p': round(p_dz, 4),
        'ci_95': [round(ci_low, 4), round(ci_high, 4)],
        'n': {'pre_sb': len(dz_pre_sb), 'pre_mb': len(dz_pre_mb),
               'post_sb': len(dz_post_sb), 'post_mb': len(dz_post_mb)}
    }

with open('results/robustness/leave_one_out_did.json', 'w') as f:
    json.dump(output, f, indent=2)
print('\nAll results saved to results/leave_one_out_did.json')
