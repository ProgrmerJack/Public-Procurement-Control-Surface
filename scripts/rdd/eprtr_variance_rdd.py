import pandas as pd
import numpy as np
from scipy import stats
import json
import warnings
warnings.filterwarnings('ignore')

print('=' * 70)
print('E-PRTR WITHIN-SECTOR VARIANCE ANALYSIS')
print('=' * 70)

eprtr = pd.read_csv('Data/raw/eea_t_ied-eprtr_p_2007-2023_v15_r00/User-friendly-CSV/F1_4_Air_Releases_Facilities.csv', low_memory=False)
co2 = eprtr[eprtr['Pollutant'].str.contains('Carbon dioxide', case=False, na=False)].copy()

print(f'CO2 records: {len(co2):,}, Facilities: {co2["FacilityInspireId"].nunique():,}')
recent = co2[co2['reportingYear'] >= 2018].copy()
print(f'Recent (2018+): {len(recent):,}')

names = {1:'Energy',2:'Metals',3:'Minerals',4:'Chemicals',5:'Waste',6:'Paper',7:'Livestock',8:'Food',9:'Other'}
sector_results = {}
print('\nWITHIN-SECTOR CO2 VARIANCE:')
print(f'{"Sector":>20} | {"N":>6} | {"Mean_t":>12} | {"Std_t":>12} | {"CV":>5} | {"P90/P10":>8}')
for sc in sorted(recent['EPRTR_SectorCode'].dropna().unique()):
    sc = int(sc)
    data = recent[recent['EPRTR_SectorCode']==sc]['Releases']
    if len(data)<20: continue
    cv = data.std()/data.mean() if data.mean()>0 else 0
    p10 = max(data.quantile(0.10),1)
    p90 = data.quantile(0.90)
    nm = names.get(sc,f'S{sc}')
    print(f'{nm:>20} | {len(data):>6} | {data.mean():>12,.0f} | {data.std():>12,.0f} | {cv:>5.2f} | {p90/p10:>7.1f}x')
    sector_results[nm] = dict(n=int(len(data)), mean=float(data.mean()), std=float(data.std()), cv=float(cv), p90_p10=float(p90/p10))

# Country-sector groups
cs = []
for (c,s), g in recent.groupby(['countryName','EPRTR_SectorCode']):
    v = g['Releases']
    if len(v)>=3:
        cs.append(dict(country=c, sector=int(s), n=len(v), cv=v.std()/v.mean() if v.mean()>0 else 0, std=float(v.std())))
cs_df = pd.DataFrame(cs)
nz = (cs_df['std']>0).sum()
print(f'\nCOUNTRY-SECTOR GROUPS (n>=3): {len(cs_df)}')
print(f'With nonzero variance: {nz}/{len(cs_df)} ({nz/len(cs_df)*100:.1f}%)')
print(f'Mean within-country-sector CV: {cs_df["cv"].mean():.2f}')
print(f'\n*** EXIOBASE: within-country-sector std = EXACTLY 0.0000 ***')
print(f'*** E-PRTR: within-country-sector std = {cs_df["std"].mean():,.0f} tonnes CO2 ***')

# Variance decomposition
print('\nVARIANCE DECOMPOSITION (within vs between country):')
decomp = {}
for sc in sorted(recent['EPRTR_SectorCode'].dropna().unique()):
    sc = int(sc)
    sd = recent[recent['EPRTR_SectorCode']==sc]
    if len(sd)<50: continue
    bw = sd.groupby('countryName')['Releases'].mean().var()
    wi = sd.groupby('countryName')['Releases'].var().dropna().mean()
    tot = bw+wi if (bw+wi)>0 else 1
    nm = names.get(sc,f'S{sc}')
    print(f'  {nm:>15}: within={wi/tot*100:.1f}%, between={bw/tot*100:.1f}%')
    decomp[nm] = dict(within_pct=float(wi/tot*100), between_pct=float(bw/tot*100))

# Now load procurement and do sector-interaction RDD
print('\n' + '='*70)
print('E-PRTR x RDD SECTOR INTERACTION')
print('='*70)

proc = pd.read_parquet('Data/processed/gprd_with_carbon.parquet')
eu = proc[proc['country']!='CO'].copy()
rdd = eu[(eu['value_eur']>=80000)&(eu['value_eur']<=200000)].copy()
rdd['above'] = (rdd['value_eur']>=139000).astype(int)
print(f'RDD zone contracts: {len(rdd):,}')

# Map CPV to E-PRTR sectors
cpv_eprtr = {9:1, 31:1, 65:1, 14:2, 44:3, 45:3, 24:4, 33:4, 90:5, 22:6, 3:7, 15:8, 71:9, 79:9}
cpv_cv = {}
for cpv, eprtr_s in cpv_eprtr.items():
    nm = names.get(eprtr_s)
    if nm in sector_results:
        cpv_cv[str(cpv).zfill(2)] = sector_results[nm]['cv']

rdd['eprtr_cv'] = rdd['cpv_division'].map(cpv_cv)
matched = rdd.dropna(subset=['eprtr_cv','carbon_intensity_kg_usd'])
print(f'Matched to E-PRTR sectors: {len(matched):,} ({len(matched)/len(rdd)*100:.1f}%)')

if len(matched) > 1000:
    med_cv = matched['eprtr_cv'].median()
    matched['high_var'] = (matched['eprtr_cv'] > med_cv).astype(int)
    
    rdd_results = {}
    for label, sub in [('HIGH variance sectors', matched[matched['high_var']==1]),
                        ('LOW variance sectors', matched[matched['high_var']==0]),
                        ('ALL matched', matched)]:
        ab = sub[sub['above']==1]['carbon_intensity_kg_usd']
        bl = sub[sub['above']==0]['carbon_intensity_kg_usd']
        if len(ab)>100 and len(bl)>100:
            diff = ab.mean()-bl.mean()
            pct = diff/bl.mean()*100 if bl.mean()>0 else 0
            t,p = stats.ttest_ind(ab, bl, equal_var=False)
            d = diff/np.sqrt((ab.var()+bl.var())/2) if (ab.var()+bl.var())>0 else 0
            print(f'\n  {label}:')
            print(f'    N_below={len(bl):,}, N_above={len(ab):,}')
            print(f'    Below mean: {bl.mean():.4f}, Above mean: {ab.mean():.4f}')
            print(f'    Diff: {pct:+.2f}%, t={t:.2f}, p={p:.6f}, d={d:.4f}')
            rdd_results[label] = dict(n_below=int(len(bl)), n_above=int(len(ab)), below_mean=float(bl.mean()), above_mean=float(ab.mean()), pct_diff=float(pct), t=float(t), p=float(p), d=float(d))

    # Regression with interaction
    try:
        import statsmodels.api as sm
        reg = matched.copy()
        reg['running'] = reg['value_eur']-139000
        reg['cv_std'] = (reg['eprtr_cv']-reg['eprtr_cv'].mean())/reg['eprtr_cv'].std()
        reg['above_x_cv'] = reg['above']*reg['cv_std']
        X = sm.add_constant(reg[['above','running','cv_std','above_x_cv']])
        y = reg['carbon_intensity_kg_usd']
        model = sm.OLS(y, X).fit(cov_type='HC1')
        print('\n  Interaction regression:')
        for var in ['above','cv_std','above_x_cv']:
            print(f'    {var}: coef={model.params[var]:.6f}, t={model.tvalues[var]:.3f}, p={model.pvalues[var]:.4f}')
        rdd_results['interaction'] = dict(
            above_coef=float(model.params['above']), above_p=float(model.pvalues['above']),
            cv_coef=float(model.params['cv_std']), cv_p=float(model.pvalues['cv_std']),
            interaction_coef=float(model.params['above_x_cv']), interaction_p=float(model.pvalues['above_x_cv']),
            r2=float(model.rsquared)
        )
    except Exception as e:
        print(f'  Regression error: {e}')

# Save all results
output = dict(
    sector_variance=sector_results,
    country_sector=dict(total_groups=len(cs_df), nonzero_variance=int(nz), mean_cv=float(cs_df['cv'].mean())),
    variance_decomposition=decomp,
    rdd_interaction=rdd_results if 'rdd_results' in dir() else {}
)
with open('results/rdd/eprtr_within_sector_variance.json','w') as f:
    json.dump(output, f, indent=2)
print('\nSaved to results/eprtr_within_sector_variance.json')
print('\n*** KEY FINDINGS ***')
print(f'1. E-PRTR proves massive within-sector CO2 variation (mean CV={cs_df["cv"].mean():.2f})')
print(f'2. {nz}/{len(cs_df)} country-sector groups have nonzero variance')
print(f'3. EXIOBASE captures 0% of within-sector variation by construction')
