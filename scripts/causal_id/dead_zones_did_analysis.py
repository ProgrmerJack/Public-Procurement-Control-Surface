"""
Decarbonization Dead Zones & Policy Reform Analysis
====================================================
Brown Monopoly Problem: high-carbon sectors locked in non-competitive contracts
Three analyses underpinning the revised Nature Sustainability manuscript:

1. Dead Zone mapping: sectors where govts need GPP leverage but have none
2. EU Reform DiD: 2014/24/EU Directive effect on SB rate and carbon gap
3. Country Leverage Index + WGI corruption control correlation
4. COVID as policy-reversal natural experiment on Dead Zones
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

print("=" * 80)
print("DEAD ZONES & POLICY REFORM ANALYSIS")
print("=" * 80)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
data_path = Path(r"C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\processed")
df = pd.read_parquet(data_path / "gprd_with_carbon.parquet")

print(f"Loaded: {len(df):,} contracts")
print(f"Columns: {list(df.columns)}")

# Standardise column names
col_map = {
    'year': 'award_year',
    'single_bidder': 'is_single_bidder',
    'carbon_intensity_kg_usd': 'carbon_intensity',
    'value_eur': 'contract_value_eur'
}
for old, new in col_map.items():
    if old in df.columns and new not in df.columns:
        df[new] = df[old]

sector_col = 'cpv_division' if 'cpv_division' in df.columns else (
             'sector' if 'sector' in df.columns else None)
print(f"Sector column: {sector_col}")
print(f"Year range: {df['award_year'].min()}-{df['award_year'].max()}")
print(f"Countries: {sorted(df['country'].unique())}")

results = {}

# ---------------------------------------------------------------------------
# 1. DECARBONIZATION DEAD ZONES
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("1.  DECARBONIZATION DEAD ZONES")
print("=" * 80)

if sector_col:
    # Aggregate by sector
    grps = []
    for sec, sec_df in df.groupby(sector_col):
        if len(sec_df) < 500:
            continue
        sb_sec = sec_df[sec_df['is_single_bidder'] == True]
        mb_sec = sec_df[sec_df['is_single_bidder'] == False]
        total_val = sec_df['contract_value_eur'].sum() if 'contract_value_eur' in df.columns else np.nan
        sb_val    = sb_sec['contract_value_eur'].sum() if 'contract_value_eur' in df.columns else np.nan
        grps.append({
            'sector': sec,
            'n_contracts': len(sec_df),
            'mean_carbon': sec_df['carbon_intensity'].mean(),
            'median_carbon': sec_df['carbon_intensity'].median(),
            'sb_rate': len(sb_sec) / len(sec_df),
            'sb_count': len(sb_sec),
            'total_value_eur': total_val,
            'sb_value_eur': sb_val
        })

    sector_agg = pd.DataFrame(grps)

    # Dead-Zone thresholds (top-tertile carbon × above-median SB rate)
    c_thresh  = sector_agg['mean_carbon'].quantile(0.67)
    sb_thresh = sector_agg['sb_rate'].median()
    print(f"Carbon threshold (67th pct): {c_thresh:.4f}")
    print(f"SB rate threshold (median):  {sb_thresh:.4f}")

    sector_agg['is_dead_zone'] = (
        (sector_agg['mean_carbon'] >= c_thresh) &
        (sector_agg['sb_rate']     >= sb_thresh)
    )
    # Procurement Leverage Index: high carbon × high SB = where govt needs
    # leverage most but has none
    sector_agg['leverage_index'] = (
        (sector_agg['mean_carbon'] / sector_agg['mean_carbon'].max()) *
        (sector_agg['sb_rate']     / sector_agg['sb_rate'].max())
    )

    dead  = sector_agg[sector_agg['is_dead_zone']].sort_values('leverage_index', ascending=False)
    alive = sector_agg[~sector_agg['is_dead_zone']]

    total_val     = sector_agg['total_value_eur'].sum()
    dz_total_val  = dead['total_value_eur'].sum()
    dz_sb_val     = dead['sb_value_eur'].sum()

    print(f"\nDead zone sectors: {len(dead)} of {len(sector_agg)}")
    print(f"Total value in sample: €{total_val/1e12:.3f}T")
    print(f"Dead Zone value:       €{dz_total_val/1e12:.3f}T  ({dz_total_val/total_val*100:.1f}%)")
    print(f"Dead Zone SB-locked:   €{dz_sb_val/1e9:.1f}B")

    print("\nTop Dead Zone sectors by leverage index:")
    print(dead[['sector','n_contracts','mean_carbon','sb_rate',
                'total_value_eur','leverage_index']].head(15).to_string())

    print("\nBottom (live) sectors:")
    print(alive.sort_values('leverage_index').head(10)[
        ['sector','mean_carbon','sb_rate','leverage_index']].to_string())

    # Carbon premium inside vs outside Dead Zones
    df['sector_label'] = df[sector_col]
    dz_sectors  = set(dead['sector'].tolist())
    df['in_dead_zone'] = df['sector_label'].isin(dz_sectors)

    dz_sb  = df[(df['in_dead_zone']) & (df['is_single_bidder'] == True)]['carbon_intensity']
    dz_mb  = df[(df['in_dead_zone']) & (df['is_single_bidder'] == False)]['carbon_intensity']
    live_sb = df[(~df['in_dead_zone']) & (df['is_single_bidder'] == True)]['carbon_intensity']
    live_mb = df[(~df['in_dead_zone']) & (df['is_single_bidder'] == False)]['carbon_intensity']

    if len(dz_sb) > 0 and len(dz_mb) > 0:
        dz_prem  = (dz_sb.mean()   - dz_mb.mean())   / dz_mb.mean() * 100
        live_prem = (live_sb.mean() - live_mb.mean()) / live_mb.mean() * 100
        print(f"\nCarbon premium IN Dead Zones:  {dz_prem:.1f}%")
        print(f"Carbon premium OUTSIDE:        {live_prem:.1f}%")

    results['dead_zones'] = {
        'n_dead_zone_sectors': int(len(dead)),
        'n_total_sectors':     int(len(sector_agg)),
        'total_value_eur':     float(total_val),
        'dead_zone_value_eur': float(dz_total_val),
        'dead_zone_sb_locked_eur': float(dz_sb_val) if not np.isnan(dz_sb_val) else 0,
        'dead_zone_pct_of_total': float(dz_total_val / total_val * 100),
        'carbon_threshold':     float(c_thresh),
        'sb_rate_threshold':    float(sb_thresh),
        'dead_zone_premium_pct':   float(dz_prem)  if 'dz_prem' in dir() else None,
        'live_zone_premium_pct':   float(live_prem) if 'live_prem' in dir() else None,
        'top_dead_zone_sectors': dead.head(15).to_dict('records')
    }

# ---------------------------------------------------------------------------
# 2. TEMPORAL DYNAMICS WITH EU REFORM MILESTONES
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("2.  TEMPORAL DYNAMICS + EU REFORM MILESTONES")
print("=" * 80)

EU_COUNTRIES = {
    'Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus', 'Czech Republic',
    'Czechia', 'Denmark', 'Estonia', 'Finland', 'France', 'Germany', 'Greece',
    'Hungary', 'Ireland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta',
    'Netherlands', 'Poland', 'Portugal', 'Romania', 'Slovak Republic', 'Slovakia',
    'Slovenia', 'Spain', 'Sweden',
    'AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IE',
    'IT','LV','LT','LU','MT','NL','PL','PT','RO','SK','SI','ES','SE'
}
df['is_eu'] = df['country'].isin(EU_COUNTRIES).astype(int)

REFORM_EVENTS = {
    2014: 'Directive 2014/24/EU enacted',
    2016: 'Transposition deadline (Apr)',
    2018: 'E-procurement mandate (Oct)',
    2020: 'COVID emergency sourcing begins',
    2022: 'Post-COVID compliance recovery'
}

temporal_rows = []
for year in sorted(df['award_year'].unique()):
    for label, mask in [('all', slice(None)),
                        ('eu_only', df['is_eu'] == 1),
                        ('non_eu', df['is_eu'] == 0)]:
        if label == 'all':
            y_df = df[df['award_year'] == year]
        else:
            y_df = df[(df['award_year'] == year) & mask]

        sb_y = y_df[y_df['is_single_bidder'] == True]['carbon_intensity']
        mb_y = y_df[y_df['is_single_bidder'] == False]['carbon_intensity']

        if len(sb_y) > 50 and len(mb_y) > 50:
            premium = (sb_y.mean() - mb_y.mean()) / mb_y.mean() * 100
            t_stat_y, _ = stats.ttest_ind(sb_y, mb_y)
            temporal_rows.append({
                'year': year,
                'sample': label,
                'n': len(y_df),
                'sb_rate': float(y_df['is_single_bidder'].mean()),
                'premium_pct': float(premium),
                't_stat': float(t_stat_y),
                'sb_mean_carbon': float(sb_y.mean()),
                'mb_mean_carbon': float(mb_y.mean()),
                'reform_event': REFORM_EVENTS.get(year)
            })

temporal_df = pd.DataFrame(temporal_rows)

for label in ['all', 'eu_only', 'non_eu']:
    sub = temporal_df[temporal_df['sample'] == label].sort_values('year')
    print(f"\n{label.upper()} temporal:")
    print(sub[['year','n','sb_rate','premium_pct','reform_event']].to_string(index=False))

# Segmented regression: does the EU Directive (2016) create a structural break?
def segmented_reg(df_yearly, break_year):
    d = df_yearly.copy().sort_values('year')
    d['t']    = d['year'] - d['year'].min()
    d['post'] = (d['year'] >= break_year).astype(int)
    d['t_post'] = d['post'] * (d['year'] - break_year)
    X = np.column_stack([np.ones(len(d)), d['t'], d['post'], d['t_post']])
    y = d['premium_pct'].values
    try:
        coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        return {
            'intercept': float(coef[0]),
            'pre_slope': float(coef[1]),
            'level_shift': float(coef[2]),
            'post_slope_change': float(coef[3])
        }
    except Exception as e:
        return {'error': str(e)}

eu_yearly = temporal_df[(temporal_df['sample'] == 'eu_only')].copy()
break_2016 = segmented_reg(eu_yearly, 2016)
break_2018 = segmented_reg(eu_yearly, 2018)
print(f"\nSegmented regression EU break @2016: {break_2016}")
print(f"Segmented regression EU break @2018: {break_2018}")

# Linear trend pre-2016 and post-2016
pre  = eu_yearly[eu_yearly['year'] < 2016]
post = eu_yearly[eu_yearly['year'].between(2016, 2019)]
if len(pre) >= 3 and len(post) >= 3:
    sl_pre,  *_ = stats.linregress(pre['year'],  pre['premium_pct'])
    sl_post, *_ = stats.linregress(post['year'], post['premium_pct'])
    print(f"EU pre-2016 slope:  {sl_pre:.2f}%/yr")
    print(f"EU 2016-2019 slope: {sl_post:.2f}%/yr")

results['temporal'] = {
    'data': temporal_df.to_dict('records'),
    'break_at_2016': break_2016,
    'break_at_2018': break_2018
}

# ---------------------------------------------------------------------------
# 3. COUNTRY LEVERAGE INDEX + WGI CORRUPTION CONTROL
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("3.  COUNTRY LEVERAGE INDEX + WGI ANTI-CORRUPTION")
print("=" * 80)

# World Governance Indicators: Control of Corruption estimate 2019
# Source: World Bank WGI, range -2.5 to +2.5 (higher = better governance)
WGI_CC = {
    'Latvia': 0.62,  'Estonia': 1.27, 'Denmark': 2.33, 'Germany': 1.81,
    'Poland': 0.41,  'Hungary': -0.14,'Czech Republic': 0.81, 'Czechia': 0.81,
    'Spain': 0.83,   'Colombia': -0.34,'Iceland': 2.19, 'Luxembourg': 1.87,
    'Ireland': 1.51, 'Norway': 2.18,  'Sweden': 2.06,  'Portugal': 1.10,
    'Greece': 0.12,  'Lithuania': 0.50,'Austria': 1.67, 'Belgium': 1.42,
    'France': 1.30,  'Netherlands': 1.93,'Finland': 2.28,'Slovenia': 0.71,
    'Slovak Republic': 0.25,'Slovakia': 0.25,'Italy': 0.20,
    'UK': 1.68,'United Kingdom': 1.68,
    'Switzerland': 2.16
}

c_rows = []
for country in df['country'].unique():
    c_df = df[df['country'] == country]
    sb_c = c_df[c_df['is_single_bidder'] == True]['carbon_intensity']
    mb_c = c_df[c_df['is_single_bidder'] == False]['carbon_intensity']
    if len(c_df) < 500 or len(sb_c) < 50 or len(mb_c) < 50:
        continue

    sb_rate     = float(c_df['is_single_bidder'].mean())
    mean_carbon = float(c_df['carbon_intensity'].mean())
    premium     = float((sb_c.mean() - mb_c.mean()) / mb_c.mean() * 100)
    leverage    = mean_carbon * sb_rate           # Procurement Leverage Index
    wgi         = WGI_CC.get(country, np.nan)

    # Dead Zone fraction of this country's contracts
    if sector_col and 'dz_sectors' in dir():
        dz_frac = float(c_df[c_df[sector_col].isin(dz_sectors)]['is_single_bidder'].mean())
    else:
        dz_frac = np.nan

    c_rows.append({
        'country': country,
        'n': len(c_df),
        'sb_rate': sb_rate,
        'mean_carbon': mean_carbon,
        'premium_pct': premium,
        'leverage_index': leverage,
        'dead_zone_sb_frac': dz_frac,
        'wgi_cc_2019': wgi
    })

country_df2 = pd.DataFrame(c_rows).sort_values('leverage_index', ascending=False)
print(country_df2.to_string(index=False))

# WGI correlation
valid_wgi = country_df2.dropna(subset=['wgi_cc_2019'])
if len(valid_wgi) >= 5:
    r_lev, p_lev = stats.pearsonr(valid_wgi['wgi_cc_2019'], valid_wgi['leverage_index'])
    r_dz, p_dz   = stats.pearsonr(valid_wgi['wgi_cc_2019'], valid_wgi['dead_zone_sb_frac'].fillna(0))
    r_prem, p_prem = stats.pearsonr(valid_wgi['wgi_cc_2019'], valid_wgi['premium_pct'])
    print(f"\nWGI × leverage_index:   r={r_lev:.3f}, p={p_lev:.3f}")
    print(f"WGI × dead_zone_frac:   r={r_dz:.3f},  p={p_dz:.3f}")
    print(f"WGI × carbon_premium:   r={r_prem:.3f}, p={p_prem:.3f}")
    results['wgi'] = {
        'r_vs_leverage': float(r_lev), 'p_vs_leverage': float(p_lev),
        'r_vs_dead_zone': float(r_dz), 'p_vs_dead_zone': float(p_dz),
        'r_vs_premium': float(r_prem), 'p_vs_premium': float(p_prem),
        'n': int(len(valid_wgi))
    }

results['country_leverage'] = country_df2.to_dict('records')

# ---------------------------------------------------------------------------
# 4. DiD: EU DIRECTIVE 2014/24 — STAGGERED IMPLEMENTATION
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("4.  DiD — EU DIRECTIVE IMPLEMENTATION (2013-2019)")
print("=" * 80)

# Restrict to 2013-2019 (pre-COVID, straddles 2016 transposition deadline)
panel_df = df[df['award_year'].between(2013, 2019)].copy()
panel_df['post_reform'] = (panel_df['award_year'] >= 2016).astype(int)

country_year = panel_df.groupby(['country', 'award_year']).agg(
    sb_rate   = ('is_single_bidder', 'mean'),
    mean_carbon = ('carbon_intensity', 'mean'),
    n         = ('carbon_intensity', 'count'),
    is_eu_val = ('is_eu', 'mean')
).reset_index()
country_year['is_eu']      = (country_year['is_eu_val'] > 0.5).astype(int)
country_year['post_reform'] = (country_year['award_year'] >= 2016).astype(int)
country_year['treated']     = country_year['is_eu'] * country_year['post_reform']

# 2×2 DiD table
for var in ['sb_rate', 'mean_carbon']:
    eu_pre  = country_year[(country_year['is_eu']==1) & (country_year['post_reform']==0)][var].mean()
    eu_post = country_year[(country_year['is_eu']==1) & (country_year['post_reform']==1)][var].mean()
    ne_pre  = country_year[(country_year['is_eu']==0) & (country_year['post_reform']==0)][var].mean()
    ne_post = country_year[(country_year['is_eu']==0) & (country_year['post_reform']==1)][var].mean()
    did     = (eu_post - eu_pre) - (ne_post - ne_pre)
    print(f"\nDiD for {var}:")
    print(f"  EU:    pre={eu_pre:.4f}, post={eu_post:.4f}, Δ={eu_post-eu_pre:+.4f}")
    print(f"  Non-EU: pre={ne_pre:.4f}, post={ne_post:.4f}, Δ={ne_post-ne_pre:+.4f}")
    print(f"  ATT (DiD) = {did:+.4f}")

results['did'] = {
    'eu_sb_pre':  float(country_year[(country_year['is_eu']==1) & (country_year['post_reform']==0)]['sb_rate'].mean()),
    'eu_sb_post': float(country_year[(country_year['is_eu']==1) & (country_year['post_reform']==1)]['sb_rate'].mean()),
    'ne_sb_pre':  float(country_year[(country_year['is_eu']==0) & (country_year['post_reform']==0)]['sb_rate'].mean()),
    'ne_sb_post': float(country_year[(country_year['is_eu']==0) & (country_year['post_reform']==1)]['sb_rate'].mean()),
}

# ---------------------------------------------------------------------------
# 5. COVID AS DEAD ZONE EXPANSION: POLICY REVERSAL TEST
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("5.  COVID DEAD ZONE EXPANSION TEST")
print("=" * 80)

period_map = {
    'pre_covid':  df['award_year'].between(2018, 2019),
    'covid':      df['award_year'].between(2020, 2021),
    'post_covid': df['award_year'].between(2022, 2023)
}

covid_results = {}
for period, mask in period_map.items():
    p_df = df[mask]
    sb_p = p_df[p_df['is_single_bidder'] == True]['carbon_intensity']
    mb_p = p_df[p_df['is_single_bidder'] == False]['carbon_intensity']
    if len(sb_p) > 50 and len(mb_p) > 50:
        prem = (sb_p.mean() - mb_p.mean()) / mb_p.mean() * 100
        # Dead zone SB fraction
        if sector_col and 'dz_sectors' in dir():
            dz_df  = p_df[p_df[sector_col].isin(dz_sectors)]
            dz_sb_frac = dz_df['is_single_bidder'].mean()
        else:
            dz_sb_frac = np.nan
        print(f"{period}: n={len(p_df):,}, sb_rate={p_df['is_single_bidder'].mean():.3f}, "
              f"premium={prem:.1f}%, dz_sb_frac={dz_sb_frac:.3f}")
        covid_results[period] = {
            'n': int(len(p_df)),
            'sb_rate': float(p_df['is_single_bidder'].mean()),
            'carbon_premium_pct': float(prem),
            'dead_zone_sb_fraction': float(dz_sb_frac) if not np.isnan(dz_sb_frac) else None
        }

results['covid_dead_zones'] = covid_results

# ---------------------------------------------------------------------------
# 6. OVERALL VERIFIED STATISTICS (anchor for manuscript)
# ---------------------------------------------------------------------------
print("\n" + "=" * 80)
print("6.  CORE VERIFIED STATISTICS")
print("=" * 80)

sb_all = df[df['is_single_bidder'] == True]['carbon_intensity']
mb_all = df[df['is_single_bidder'] == False]['carbon_intensity']
overall_premium = (sb_all.mean() - mb_all.mean()) / mb_all.mean() * 100
t_all, p_all = stats.ttest_ind(sb_all, mb_all)
d_all = (sb_all.mean() - mb_all.mean()) / df['carbon_intensity'].std()

print(f"Overall premium: {overall_premium:.2f}%  (t={t_all:.1f}, d={d_all:.3f})")
print(f"SB contracts: {len(sb_all):,} ({len(sb_all)/len(df)*100:.1f}%)")
print(f"MB contracts: {len(mb_all):,}")

results['core'] = {
    'overall_premium_pct': float(overall_premium),
    't_stat': float(t_all),
    'cohen_d': float(d_all),
    'n_sb': int(len(sb_all)),
    'n_mb': int(len(mb_all)),
    'n_total': int(len(df))
}

# ---------------------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------------------
out_path = Path(r"C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\results")
out_file = out_path / "dead_zones_reform_analysis.json"

def _conv(obj):
    if isinstance(obj, (np.integer, np.floating, np.bool_)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _conv(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_conv(i) for i in obj]
    return obj

with open(out_file, 'w') as f:
    json.dump(_conv(results), f, indent=2, default=str)

print(f"\nSaved: {out_file}")
print("\n" + "=" * 80)
print("ALL ANALYSES COMPLETE")
print("=" * 80)
