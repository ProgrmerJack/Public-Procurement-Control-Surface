import pandas as pd
import numpy as np
from scipy import stats
import json, re, unicodedata, warnings
warnings.filterwarnings('ignore')

print('='*70)
print('E-PRTR x TED FIRM-LEVEL MATCHING (FIXED)')
print('='*70)

eprtr = pd.read_csv('Data/raw/eea_t_ied-eprtr_p_2007-2023_v15_r00/User-friendly-CSV/F1_4_Air_Releases_Facilities.csv', low_memory=False)
co2 = eprtr[eprtr['Pollutant'].str.contains('Carbon dioxide', case=False, na=False)].copy()
co2_latest = co2.sort_values('reportingYear',ascending=False).groupby('FacilityInspireId').first().reset_index()
co2_latest = co2_latest[['FacilityInspireId','facilityName','countryName','EPRTR_SectorCode','EPRTR_SectorName','Releases','reportingYear']].copy()
print(f'E-PRTR facilities with CO2: {len(co2_latest):,}')

def norm(s):
    if pd.isna(s): return ''
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFKD',s)
    s = re.sub(r'[^a-z0-9 ]','',s)
    s = re.sub(r'\s+',' ',s).strip()
    return s

co2_latest['norm_name'] = co2_latest['facilityName'].apply(norm)
country_map = {'Austria':'AT','Belgium':'BE','Bulgaria':'BG','Croatia':'HR','Cyprus':'CY','Czechia':'CZ',
    'Denmark':'DK','Estonia':'EE','Finland':'FI','France':'FR','Germany':'DE','Greece':'EL',
    'Hungary':'HU','Ireland':'IE','Italy':'IT','Latvia':'LV','Lithuania':'LT','Luxembourg':'LU',
    'Malta':'MT','Netherlands':'NL','Poland':'PL','Portugal':'PT','Romania':'RO','Slovakia':'SK',
    'Slovenia':'SI','Spain':'ES','Sweden':'SE','United Kingdom':'GB','Norway':'NO','Switzerland':'CH',
    'Iceland':'IS','Serbia':'RS'}
co2_latest['country_code'] = co2_latest['countryName'].map(country_map)

# Load TED CAN data
years = [2019,2020,2021,2022]
ted_all = []
for y in years:
    df = pd.read_parquet(f'Data/processed/eu_ted/yearly/ted_{y}_CAN.parquet',
        columns=['supplier_name','supplier_country','country','single_bidder','value_eur','cpv_division','n_bidders'])
    df['year'] = y
    df = df[df['supplier_name'].notna() & (df['supplier_name']!='nan')]
    # Fix single_bidder: string 'True'/'False' -> boolean
    df['sb'] = df['single_bidder'].astype(str).str.strip().str.lower() == 'true'
    ted_all.append(df)
    print(f'  TED {y}: {len(df):,} (SB={df["sb"].sum():,})')
ted = pd.concat(ted_all,ignore_index=True)
print(f'Total: {len(ted):,}, SB={ted["sb"].sum():,} ({ted["sb"].mean()*100:.1f}%)')

ted['norm_name'] = ted['supplier_name'].apply(norm)
ted['country_code'] = ted['supplier_country'].fillna(ted['country'])

# EXACT MATCH
merged = ted.merge(co2_latest[['country_code','norm_name','Releases','EPRTR_SectorCode','EPRTR_SectorName','facilityName']],
    on=['country_code','norm_name'], how='inner')
n_fac = merged['facilityName'].nunique()
n_ctr = merged['country_code'].nunique()
print(f'\nExact matches: {len(merged):,} contracts, {n_fac} facilities, {n_ctr} countries')

# SUBSTRING MATCH (for names >= 8 chars)
if n_fac < 500:
    eprtr_sub = co2_latest[co2_latest['norm_name'].str.len()>=8].copy()
    ted_sub = ted[~ted.index.isin(merged.index)].copy()
    ted_sub = ted_sub[ted_sub['norm_name'].str.len()>=8]
    # Build a dict of eprtr names per country
    eprtr_by_country = {}
    for _, row in eprtr_sub.iterrows():
        cc = row['country_code']
        if cc not in eprtr_by_country:
            eprtr_by_country[cc] = []
        eprtr_by_country[cc].append(row)
    
    sub_matches = []
    print('Running substring matching...')
    for cc in eprtr_by_country:
        ted_cc = ted_sub[ted_sub['country_code']==cc]
        if len(ted_cc)==0: continue
        for erow in eprtr_by_country[cc]:
            en = erow['norm_name']
            mask = ted_cc['norm_name'].str.contains(en, regex=False, na=False) | \
                   ted_cc['norm_name'].apply(lambda x: en in x if isinstance(x,str) else False)
            hits = ted_cc[mask].copy()
            if len(hits) > 0:
                hits['Releases'] = erow['Releases']
                hits['EPRTR_SectorCode'] = erow['EPRTR_SectorCode']
                hits['EPRTR_SectorName'] = erow['EPRTR_SectorName']
                hits['facilityName'] = erow['facilityName']
                sub_matches.append(hits)
    
    if sub_matches:
        sub_df = pd.concat(sub_matches, ignore_index=True)
        merged = pd.concat([merged, sub_df], ignore_index=True)
        print(f'Substring matches: {len(sub_df):,} additional')
        print(f'Total: {len(merged):,} contracts, {merged["facilityName"].nunique()} facilities')

# ANALYSIS
sb = merged[merged['sb']==True]
mb = merged[merged['sb']==False]
print(f'\nSB contracts: {len(sb):,}, MB contracts: {len(mb):,}')

results = {}
if len(sb)>30 and len(mb)>30:
    sb_co2 = sb['Releases']; mb_co2 = mb['Releases']
    prem = (sb_co2.mean()-mb_co2.mean())/mb_co2.mean()*100
    t,p = stats.ttest_ind(sb_co2, mb_co2, equal_var=False)
    d = (sb_co2.mean()-mb_co2.mean())/np.sqrt((sb_co2.var()+mb_co2.var())/2)
    print(f'\nOVERALL:')
    print(f'  SB mean: {sb_co2.mean():,.0f}, MB mean: {mb_co2.mean():,.0f}')
    print(f'  Premium: {prem:+.1f}%, t={t:.2f}, p={p:.6f}, d={d:.4f}')
    results['overall'] = dict(n_sb=int(len(sb)), n_mb=int(len(mb)), premium_pct=round(prem,1), t=round(float(t),3), p=round(float(p),6), d=round(float(d),4))

    # Within-sector
    print('\nWITHIN SECTOR:')
    sector_res = {}
    names = {1:'Energy',2:'Metals',3:'Minerals',4:'Chemicals',5:'Waste',6:'Paper',7:'Livestock',8:'Food',9:'Other'}
    for sc in sorted(merged['EPRTR_SectorCode'].dropna().unique()):
        sc = int(sc)
        sub = merged[merged['EPRTR_SectorCode']==sc]
        ss = sub[sub['sb']==True]['Releases']; sm = sub[sub['sb']==False]['Releases']
        if len(ss)>10 and len(sm)>10:
            pr = (ss.mean()-sm.mean())/sm.mean()*100 if sm.mean()>0 else 0
            tt,pp = stats.ttest_ind(ss, sm, equal_var=False)
            nm = names.get(sc,f'S{sc}')
            print(f'  {nm:>15}: premium={pr:+.1f}%, t={tt:.2f}, p={pp:.4f}, n_sb={len(ss)}, n_mb={len(sm)}')
            sector_res[nm] = dict(premium_pct=round(pr,1), t=round(float(tt),3), p=round(float(pp),6), n_sb=int(len(ss)), n_mb=int(len(sm)))
    results['within_sector'] = sector_res

    # Within-country
    print('\nWITHIN COUNTRY:')
    country_res = {}
    for cc in sorted(merged['country_code'].unique()):
        sub = merged[merged['country_code']==cc]
        sc = sub[sub['sb']==True]['Releases']; mc = sub[sub['sb']==False]['Releases']
        if len(sc)>20 and len(mc)>20:
            pr = (sc.mean()-mc.mean())/mc.mean()*100 if mc.mean()>0 else 0
            tt,pp = stats.ttest_ind(sc, mc, equal_var=False)
            print(f'  {cc}: premium={pr:+.1f}%, t={tt:.2f}, p={pp:.4f}, n_sb={len(sc)}, n_mb={len(mc)}')
            country_res[cc] = dict(premium_pct=round(pr,1), t=round(float(tt),3), p=round(float(pp),6), n_sb=int(len(sc)), n_mb=int(len(mc)))
    results['within_country'] = country_res

    # Within-country-within-sector
    print('\nWITHIN COUNTRY x SECTOR:')
    cs_res = []
    for (cc,sc), grp in merged.groupby(['country_code','EPRTR_SectorCode']):
        ss = grp[grp['sb']==True]['Releases']; sm = grp[grp['sb']==False]['Releases']
        if len(ss)>5 and len(sm)>5:
            pr = (ss.mean()-sm.mean())/sm.mean()*100 if sm.mean()>0 else 0
            cs_res.append(dict(country=cc, sector=int(sc), premium_pct=pr, n_sb=len(ss), n_mb=len(sm)))
    if cs_res:
        cs_df = pd.DataFrame(cs_res)
        wmean = np.average(cs_df['premium_pct'], weights=cs_df['n_sb']+cs_df['n_mb'])
        pos = (cs_df['premium_pct']>0).sum()
        print(f'  {len(cs_df)} groups tested, {pos} positive, weighted mean premium: {wmean:+.1f}%')
        results['within_country_sector'] = dict(n_groups=len(cs_df), n_positive=int(pos), weighted_mean=round(float(wmean),1))

with open('results/validation/ted_eprtr_matching.json','w') as f:
    json.dump(results, f, indent=2)
print('\nSaved results/ted_eprtr_matching.json')
