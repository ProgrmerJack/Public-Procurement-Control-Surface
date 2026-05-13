"""Exact-match-only sensitivity analysis for E-PRTR facility-procurement matching.
Addresses editor concern: does the refinery +8.7% hold under Tier 1 (exact) matches only?
"""
import pandas as pd
import numpy as np
from scipy import stats
import re
import json

# Load E-PRTR data
eprtr = pd.read_csv('Data/raw/eea_t_ied-eprtr_p_2007-2023_v15_r00/User-friendly-CSV/F1_4_Air_Releases_Facilities.csv', low_memory=False)
eprtr_co2 = eprtr[(eprtr['Pollutant']=='Carbon dioxide (CO2)') & (eprtr['Releases'] > 0)]

# Load procurement data
proc = pd.read_parquet('Data/processed/gprd_master.parquet', columns=['supplier_name','supplier_country','single_bidder','sector'])
proc = proc[proc['supplier_name'].str.len() > 2].copy()

country_map = {
    'Austria':'AT','Belgium':'BE','Bulgaria':'BG','Croatia':'HR','Cyprus':'CY',
    'Czechia':'CZ','Czech Republic':'CZ','Denmark':'DK','Estonia':'EE','Finland':'FI',
    'France':'FR','Germany':'DE','Greece':'GR','Hungary':'HU','Ireland':'IE','Italy':'IT',
    'Latvia':'LV','Lithuania':'LT','Luxembourg':'LU','Malta':'MT','Netherlands':'NL',
    'Norway':'NO','Poland':'PL','Portugal':'PT','Romania':'RO','Slovakia':'SK','Slovenia':'SI',
    'Spain':'ES','Sweden':'SE','United Kingdom':'UK','Iceland':'IS','Liechtenstein':'LI',
    'Switzerland':'CH','Serbia':'RS'
}

eprtr_co2['country_code'] = eprtr_co2['countryName'].map(country_map)

def normalize_name(name):
    if pd.isna(name): return ''
    name = str(name).lower().strip()
    for suffix in [' gmbh',' ag',' ltd',' plc',' sa',' srl',' spa',' bv',' nv',' as',' ab',' oy',' se',' co.']:
        name = name.replace(suffix, '')
    name = re.sub(r'[^a-z0-9 ]', '', name)
    return ' '.join(name.split())

eprtr_co2['name_norm'] = eprtr_co2['facilityName'].apply(normalize_name)
proc['name_norm'] = proc['supplier_name'].apply(normalize_name)
proc['country_code'] = proc['supplier_country']

# E-PRTR facility-level aggregation
eprtr_fac = eprtr_co2.groupby(['country_code','name_norm','FacilityInspireId','EPRTRAnnexIMainActivity']).agg(
    mean_co2=('Releases','mean'),
    log_co2=('Releases', lambda x: np.log(x.mean()))
).reset_index()
eprtr_fac = eprtr_fac[eprtr_fac['name_norm'].str.len() > 2]

# TIER 1 ONLY: Exact merge on country + normalized name
matched = proc.merge(eprtr_fac, on=['country_code','name_norm'], how='inner')
n_fac = matched['FacilityInspireId'].nunique()
print(f'EXACT MATCH ONLY:')
print(f'  Matched contracts: {len(matched)}')
print(f'  Unique facilities: {n_fac}')

sb = matched[matched['single_bidder']==True]
mb = matched[matched['single_bidder']==False]
print(f'  SB: {len(sb)}, MB: {len(mb)}')

results = {'exact_match_only': {'n_contracts': len(matched), 'n_facilities': n_fac,
                                 'n_sb': len(sb), 'n_mb': len(mb)}}

def compute_premium(sb_data, mb_data, label):
    if len(sb_data) < 5 or len(mb_data) < 5:
        print(f'  {label}: insufficient data (SB={len(sb_data)}, MB={len(mb_data)})')
        return None
    prem = (sb_data['mean_co2'].mean() - mb_data['mean_co2'].mean()) / mb_data['mean_co2'].mean() * 100
    t, p = stats.ttest_ind(sb_data['mean_co2'], mb_data['mean_co2'], equal_var=False)
    print(f'  {label}: premium={prem:+.1f}% (t={t:.2f}, p={p:.4f}, SB={len(sb_data)}, MB={len(mb_data)})')
    return {'premium_pct': round(prem, 1), 't_stat': round(t, 2), 'p_value': round(p, 4),
            'n_sb': len(sb_data), 'n_mb': len(mb_data)}

# Overall
r = compute_premium(sb, mb, 'Overall')
if r: results['overall'] = r

# Energy sector
energy = matched[matched['EPRTRAnnexIMainActivity'].str.startswith('1(')]
r = compute_premium(energy[energy['single_bidder']==True], energy[energy['single_bidder']==False], 'Energy sector')
if r: results['energy'] = r

# Refineries 1(a)
ref = matched[matched['EPRTRAnnexIMainActivity']=='1(a)']
r = compute_premium(ref[ref['single_bidder']==True], ref[ref['single_bidder']==False], 'Refineries 1(a)')
if r: results['refineries_1a'] = r

# Thermal power 1(c)
tp = matched[matched['EPRTRAnnexIMainActivity']=='1(c)']
r = compute_premium(tp[tp['single_bidder']==True], tp[tp['single_bidder']==False], 'Thermal power 1(c)')
if r: results['thermal_power_1c'] = r

# Also test: controlling for facility size (log total CO2) in refineries
print('\n--- FACILITY-SIZE CONTROLLED REFINERY ANALYSIS ---')
ref_data = ref.copy()
if len(ref_data) > 20:
    ref_data['log_total_co2'] = np.log(ref_data['mean_co2'] + 1)
    # Split into size terciles
    median_co2 = ref_data['log_total_co2'].median()
    for label, subset_mask in [('below_median', ref_data['log_total_co2'] <= median_co2), 
                                ('above_median', ref_data['log_total_co2'] > median_co2)]:
        subset = ref_data[subset_mask]
        sb_s = subset[subset['single_bidder']==True]
        mb_s = subset[subset['single_bidder']==False]
        r = compute_premium(sb_s, mb_s, f'Refinery {label}')
        if r: results[f'refinery_{label}'] = r

# Save results
with open('results/robustness/exact_match_sensitivity.json', 'w') as f:
    json.dump(results, f, indent=2)
print('\nSaved results/exact_match_sensitivity.json')
