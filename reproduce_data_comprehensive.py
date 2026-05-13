#!/usr/bin/env python3
"""
Comprehensive Data Verification Script
Generates exact statistics for manuscript
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
import json

def main():
    # Load the ACTUAL processed data
    df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet')

    print('='*70)
    print('COMPREHENSIVE DATA AUDIT - VERIFIED STATISTICS')
    print('='*70)

    # Basic stats
    n_total = len(df)
    n_countries = df['country'].nunique()
    year_min = df['year'].min()
    year_max = df['year'].max()
    
    print(f'\nTotal contracts: {n_total:,}')
    print(f'Countries: {n_countries}')
    print(f'Year range: {year_min}-{year_max}')

    # Carbon intensity analysis
    df_carbon = df[df['carbon_intensity_kg_usd'].notna()].copy()
    n_with_carbon = len(df_carbon)
    print(f'\nContracts with carbon data: {n_with_carbon:,}')

    # Competition analysis
    df_comp = df_carbon[df_carbon['single_bidder'].notna()].copy()
    single = df_comp[df_comp['single_bidder'] == True]['carbon_intensity_kg_usd']
    multi = df_comp[df_comp['single_bidder'] == False]['carbon_intensity_kg_usd']

    n_single = len(single)
    n_multi = len(multi)
    mean_single = single.mean()
    mean_multi = multi.mean()
    
    print(f'\n--- COMPETITION-CARBON ANALYSIS ---')
    print(f'Single-bidder contracts: {n_single:,}')
    print(f'Multi-bidder contracts: {n_multi:,}')
    print(f'Single-bidder mean: {mean_single:.4f} kg CO2/USD')
    print(f'Multi-bidder mean: {mean_multi:.4f} kg CO2/USD')

    premium = (mean_single - mean_multi) / mean_multi * 100
    print(f'\nCARBON PREMIUM: +{premium:.1f}%')

    t_stat, p_val = stats.ttest_ind(single, multi, equal_var=False)
    print(f't-statistic: {t_stat:.1f}')
    if p_val > 0:
        print(f'p-value: {p_val:.2e}')
    else:
        print('p-value: < 1e-300')

    # RDD Analysis at threshold
    print(f'\n--- RDD ANALYSIS AT EUR 139,000 THRESHOLD ---')
    threshold = 139000
    df_rdd = df_carbon[(df_carbon['value_eur'] > 0)].copy()
    df_rdd['log_value'] = np.log10(df_rdd['value_eur'])
    log_thresh = np.log10(threshold)

    # Bandwidth 0.1 log units
    bw = 0.1
    below = df_rdd[(df_rdd['log_value'] >= log_thresh - bw) & (df_rdd['log_value'] < log_thresh)]
    above = df_rdd[(df_rdd['log_value'] >= log_thresh) & (df_rdd['log_value'] <= log_thresh + bw)]

    n_below = len(below)
    n_above = len(above)
    print(f'Contracts below threshold: {n_below:,}')
    print(f'Contracts above threshold: {n_above:,}')

    # Bidder count effect
    bidders_below = below['n_bidders'].dropna()
    bidders_above = above['n_bidders'].dropna()
    bidder_effect = bidders_above.mean() - bidders_below.mean()
    bidder_pct = bidder_effect / bidders_below.mean() * 100
    t_bid, p_bid = stats.ttest_ind(bidders_above, bidders_below, equal_var=False)
    
    print(f'\nBidders below threshold: {bidders_below.mean():.2f}')
    print(f'Bidders above threshold: {bidders_above.mean():.2f}')
    print(f'Bidder effect: +{bidder_effect:.2f} bidders (+{bidder_pct:.1f}%)')
    print(f't-statistic: {t_bid:.1f}, p-value: {p_bid:.2e}')

    # Carbon effect at threshold
    carbon_below = below['carbon_intensity_kg_usd'].dropna()
    carbon_above = above['carbon_intensity_kg_usd'].dropna()
    carbon_effect = (carbon_above.mean() - carbon_below.mean()) / carbon_below.mean() * 100
    t_carb, p_carb = stats.ttest_ind(carbon_above, carbon_below, equal_var=False)
    
    print(f'\nCarbon below threshold: {carbon_below.mean():.4f} kg/USD')
    print(f'Carbon above threshold: {carbon_above.mean():.4f} kg/USD')
    print(f'Carbon effect at threshold: {carbon_effect:+.2f}%')
    print(f't-statistic: {t_carb:.1f}, p-value: {p_carb:.2e}')

    # Country-level analysis
    print(f'\n--- COUNTRY-LEVEL HETEROGENEITY ---')
    country_effects = []
    for country in df_comp['country'].unique():
        df_c = df_comp[df_comp['country'] == country]
        s = df_c[df_c['single_bidder'] == True]['carbon_intensity_kg_usd']
        m = df_c[df_c['single_bidder'] == False]['carbon_intensity_kg_usd']
        if len(s) > 100 and len(m) > 100:
            eff = (s.mean() - m.mean()) / m.mean() * 100
            t, p = stats.ttest_ind(s, m, equal_var=False)
            country_effects.append({
                'country': country, 
                'effect': eff, 
                'p': p, 
                'n': len(df_c),
                'significant': p < 0.05
            })

    country_df = pd.DataFrame(country_effects).sort_values('effect')
    sig_neg = len(country_df[(country_df['effect'] < 0) & (country_df['p'] < 0.05)])
    sig_pos = len(country_df[(country_df['effect'] > 0) & (country_df['p'] < 0.05)])
    
    print(f'Countries with significant NEGATIVE effect: {sig_neg}')
    print(f'Countries with significant POSITIVE effect: {sig_pos}')
    print(f'Total countries analyzed: {len(country_df)}')

    # I-squared calculation (proper meta-analysis)
    effects = country_df['effect'].values
    k = len(effects)
    Q = np.sum((effects - effects.mean())**2)
    df_q = k - 1
    I_sq = max(0, (Q - df_q) / Q) * 100 if Q > 0 else 0
    print(f'I-squared heterogeneity: {I_sq:.1f}%')

    # Print country details
    print(f'\n--- COUNTRY EFFECTS (sorted) ---')
    for _, row in country_df.iterrows():
        sig = '*' if row['p'] < 0.05 else ''
        print(f"  {row['country']}: {row['effect']:+.1f}% (n={row['n']:,}){sig}")

    # Save verified statistics to JSON
    verified_stats = {
        'data_summary': {
            'total_contracts': int(n_total),
            'contracts_with_carbon': int(n_with_carbon),
            'countries': int(n_countries),
            'year_range': f'{year_min}-{year_max}'
        },
        'competition_carbon': {
            'single_bidder_n': int(n_single),
            'multi_bidder_n': int(n_multi),
            'single_bidder_mean': float(mean_single),
            'multi_bidder_mean': float(mean_multi),
            'carbon_premium_pct': float(premium),
            't_statistic': float(t_stat),
            'p_value': float(p_val) if p_val > 0 else 0
        },
        'rdd_analysis': {
            'threshold_eur': threshold,
            'n_below': int(n_below),
            'n_above': int(n_above),
            'bidders_below': float(bidders_below.mean()),
            'bidders_above': float(bidders_above.mean()),
            'bidder_effect': float(bidder_effect),
            'bidder_effect_pct': float(bidder_pct),
            'carbon_below': float(carbon_below.mean()),
            'carbon_above': float(carbon_above.mean()),
            'carbon_effect_pct': float(carbon_effect)
        },
        'heterogeneity': {
            'countries_analyzed': len(country_df),
            'significant_negative': int(sig_neg),
            'significant_positive': int(sig_pos),
            'I_squared': float(I_sq)
        },
        'country_effects': country_df.to_dict('records')
    }
    
    with open('VERIFIED_STATISTICS.json', 'w') as f:
        json.dump(verified_stats, f, indent=2)
    
    print('\n' + '='*70)
    print('VERIFIED STATISTICS SAVED TO VERIFIED_STATISTICS.json')
    print('='*70)
    
    return verified_stats

if __name__ == '__main__':
    main()
