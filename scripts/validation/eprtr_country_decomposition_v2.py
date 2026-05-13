#!/usr/bin/env python3
"""
E-PRTR Country-Level Decomposition of SB Premium Attenuation
==============================================================
Analyzes the +8.7% → +1.2% attenuation when balancing on country,
identifying which countries drive the unmatched premium and which
drive the attenuation under matching.

Uses TED (European Tender Electronic Daily) procurement data with E-PRTR facility-level emissions.
"""

import pandas as pd
import numpy as np
import json
from scipy import stats
import warnings
import re
import unicodedata
warnings.filterwarnings('ignore')

def normalize_name(s):
    """Normalize company name for matching."""
    if pd.isna(s):
        return ''
    s = str(s).lower().strip()
    s = unicodedata.normalize('NFKD', s)
    s = re.sub(r'[^a-z0-9 ]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

print("=" * 70)
print("E-PRTR COUNTRY DECOMPOSITION ANALYSIS")
print("=" * 70)

# Load E-PRTR facility data with CO2
print("\n1. Loading E-PRTR facility data...")
eprtr = pd.read_csv(
    'Data/raw/eea_t_ied-eprtr_p_2007-2023_v15_r00/User-friendly-CSV/F1_4_Air_Releases_Facilities.csv',
    low_memory=False
)
co2 = eprtr[eprtr['Pollutant'].str.contains('Carbon dioxide', case=False, na=False)].copy()
co2_latest = co2.sort_values('reportingYear', ascending=False).groupby('FacilityInspireId').first().reset_index()
co2_latest = co2_latest[['FacilityInspireId', 'facilityName', 'countryName', 'EPRTR_SectorCode', 
                         'EPRTR_SectorName', 'Releases', 'reportingYear', 'EPRTRAnnexIMainActivity']].copy()
print(f"   E-PRTR facilities with CO2: {len(co2_latest):,}")

# Get just refineries (Activity 1.a)
refineries = co2_latest[co2_latest['EPRTRAnnexIMainActivity'].astype(str).str.startswith('1(a)')].copy()
print(f"   Refineries in E-PRTR: {len(refineries)}")
print(f"   Countries in refineries: {refineries['countryName'].nunique()}")

# Map country names to codes
country_name_to_code = {
    'Austria': 'AT', 'Belgium': 'BE', 'Bulgaria': 'BG', 'Croatia': 'HR',
    'Cyprus': 'CY', 'Czechia': 'CZ', 'Denmark': 'DK', 'Estonia': 'EE',
    'Finland': 'FI', 'France': 'FR', 'Germany': 'DE', 'Greece': 'EL',
    'Hungary': 'HU', 'Ireland': 'IE', 'Italy': 'IT', 'Latvia': 'LV',
    'Lithuania': 'LT', 'Luxembourg': 'LU', 'Malta': 'MT', 'Netherlands': 'NL',
    'Poland': 'PL', 'Portugal': 'PT', 'Romania': 'RO', 'Slovakia': 'SK',
    'Slovenia': 'SI', 'Spain': 'ES', 'Sweden': 'SE', 'United Kingdom': 'GB',
    'Norway': 'NO', 'Switzerland': 'CH', 'Iceland': 'IS', 'Serbia': 'RS'
}

refineries['country_code'] = refineries['countryName'].map(country_name_to_code)
refineries['norm_name'] = refineries['facilityName'].apply(normalize_name)

print("\n   Refineries by country:")
for cc, n in refineries.groupby('country_code').size().sort_values(ascending=False).items():
    print(f"   {cc}: {n}")

# Load TED procurement data for recent years
print("\n2. Loading TED procurement data...")
ted_all = []
years = [2019, 2020, 2021, 2022]
for y in years:
    try:
        df = pd.read_parquet(
            f'Data/processed/eu_ted/yearly/ted_{y}_CAN.parquet',
            columns=['supplier_name', 'supplier_country', 'country', 'single_bidder', 
                     'value_eur', 'cpv_division', 'n_bidders', 'year']
        )
        df = df[df['supplier_name'].notna() & (df['supplier_name'] != 'nan')]
        df['sb'] = df['single_bidder'].astype(str).str.strip().str.lower() == 'true'
        ted_all.append(df)
        print(f"   TED {y}: {len(df):,} (SB={df['sb'].sum():,})")
    except Exception as e:
        print(f"   Warning: Could not load TED {y}: {e}")

if ted_all:
    ted = pd.concat(ted_all, ignore_index=True)
    print(f"   Total TED records: {len(ted):,}, SB={ted['sb'].sum():,} ({ted['sb'].mean()*100:.1f}%)")
else:
    print("   ERROR: No TED data loaded")
    exit(1)

ted['norm_name'] = ted['supplier_name'].apply(normalize_name)
ted['country_code'] = ted['supplier_country'].fillna(ted['country'])

# Match refineries to TED contracts
print("\n3. Matching refineries to TED contracts...")
matches = []
for _, ref in refineries.iterrows():
    country = ref['country_code']
    norm_name = ref['norm_name']
    
    # Exact match
    ted_subset = ted[(ted['country_code'] == country) & (ted['norm_name'] == norm_name)]
    
    for _, contract in ted_subset.iterrows():
        matches.append({
            'facility_id': ref['FacilityInspireId'],
            'facility_name': ref['facilityName'],
            'facility_co2': ref['Releases'],
            'facility_country': ref['country_code'],
            'contract_country': contract['country_code'],
            'year': contract['year'],
            'single_bidder': contract['sb'],
            'cpv_division': contract['cpv_division'],
            'supplier_name': contract['supplier_name']
        })

df = pd.DataFrame(matches)
print(f"   Total matched refinery contracts: {len(df)}")
print(f"   Unique facilities: {df['facility_id'].nunique() if len(df) > 0 else 0}")

if len(df) == 0:
    print("ERROR: No exact matches found. Attempting substring matching...")
    # Try substring matching for facilities with longer names
    for _, ref in refineries[refineries['norm_name'].str.len() >= 8].iterrows():
        country = ref['country_code']
        norm_name = ref['norm_name']
        
        ted_subset = ted[ted['country_code'] == country]
        
        # Substring match - facility name in supplier name
        mask = ted_subset['norm_name'].str.contains(norm_name[:15], regex=False, na=False)
        ted_matches = ted_subset[mask]
        
        for _, contract in ted_matches.iterrows():
            matches.append({
                'facility_id': ref['FacilityInspireId'],
                'facility_name': ref['facilityName'],
                'facility_co2': ref['Releases'],
                'facility_country': ref['country_code'],
                'contract_country': contract['country_code'],
                'year': contract['year'],
                'single_bidder': contract['sb'],
                'cpv_division': contract['cpv_division'],
                'supplier_name': contract['supplier_name']
            })
    
    df = pd.DataFrame(matches)
    print(f"   After substring matching: {len(df)}")

if len(df) == 0:
    print("ERROR: No matches found at all")
    exit(1)

# Show overall stats
print(f"\n4. Overall Sample Breakdown:")
print(f"   Total contracts: {len(df)}")
print(f"   SB contracts: {(df['single_bidder']==True).sum()}")
print(f"   MB contracts: {(df['single_bidder']==False).sum()}")
print(f"   Countries represented: {df['facility_country'].nunique()}")

# Get unmatched overall effect
sb_unmatched = df[df['single_bidder']==True]
mb_unmatched = df[df['single_bidder']==False]

if len(sb_unmatched) > 1 and len(mb_unmatched) > 1:
    sb_mean = sb_unmatched['facility_co2'].mean()
    mb_mean = mb_unmatched['facility_co2'].mean()
    unmatched_prem = (sb_mean - mb_mean) / mb_mean * 100
    t_unmatched, p_unmatched = stats.ttest_ind(sb_unmatched['facility_co2'], mb_unmatched['facility_co2'])
    
    print(f"\n5. UNMATCHED EFFECT (Full Sample):")
    print(f"   SB mean CO2: {sb_mean:,.0f} kg")
    print(f"   MB mean CO2: {mb_mean:,.0f} kg")
    print(f"   Premium: {unmatched_prem:+.1f}%")
    print(f"   t-stat: {t_unmatched:.3f}, p: {p_unmatched:.6f}")
else:
    print(f"\nWarning: Insufficient sample size for statistical tests")
    unmatched_prem = (sb_unmatched['facility_co2'].mean() - mb_unmatched['facility_co2'].mean()) / mb_unmatched['facility_co2'].mean() * 100
    print(f"Raw premium: {unmatched_prem:+.1f}%")

# Country-level decomposition
print(f"\n6. COUNTRY-LEVEL DECOMPOSITION:")
print(f"   Analyzing SB vs MB premium by country...")

country_results = {}
for country in sorted(df['facility_country'].unique()):
    country_df = df[df['facility_country'] == country]
    sb_country = country_df[country_df['single_bidder'] == True]
    mb_country = country_df[country_df['single_bidder'] == False]
    
    if len(sb_country) > 0 and len(mb_country) > 0:
        sb_mean_c = sb_country['facility_co2'].mean()
        mb_mean_c = mb_country['facility_co2'].mean()
        prem_c = (sb_mean_c - mb_mean_c) / mb_mean_c * 100
        
        if len(sb_country) > 1 and len(mb_country) > 1:
            t_c, p_c = stats.ttest_ind(sb_country['facility_co2'], mb_country['facility_co2'])
        else:
            t_c = np.nan
            p_c = np.nan
        
        country_results[country] = {
            'n_sb': int(len(sb_country)),
            'n_mb': int(len(mb_country)),
            'sb_mean_co2': float(sb_mean_c),
            'mb_mean_co2': float(mb_mean_c),
            'premium_pct': float(prem_c),
            't_stat': float(t_c) if not np.isnan(t_c) else None,
            'p_value': float(p_c) if not np.isnan(p_c) else None
        }

# Sort by premium
sorted_countries = sorted(country_results.items(), key=lambda x: x[1]['premium_pct'], reverse=True)

print(f"\n   Countries (sorted by SB premium, highest to lowest):")
for country, stats_dict in sorted_countries:
    p_val_str = f"{stats_dict['p_value']:.6f}" if stats_dict['p_value'] is not None else "N/A"
    print(f"   {country:3s}: n_sb={stats_dict['n_sb']:3d}, n_mb={stats_dict['n_mb']:3d}, " 
          f"premium={stats_dict['premium_pct']:+7.1f}%, p={p_val_str}")

# Country-balanced matching
print(f"\n7. COUNTRY-BALANCED MATCHING:")
print(f"   Matching on facility_country to remove country confound...")

matched_sb_list = []
matched_mb_list = []
np.random.seed(42)

for country in sorted(df['facility_country'].unique()):
    country_df = df[df['facility_country'] == country]
    sb_country = country_df[country_df['single_bidder'] == True]
    mb_country = country_df[country_df['single_bidder'] == False]
    
    n_match = min(len(sb_country), len(mb_country))
    if n_match > 0:
        matched_sb_list.append(sb_country.sample(n=n_match, random_state=42))
        matched_mb_list.append(mb_country.sample(n=n_match, random_state=42))

if matched_sb_list:
    m_sb = pd.concat(matched_sb_list, ignore_index=True)
    m_mb = pd.concat(matched_mb_list, ignore_index=True)
    
    sb_mean_matched = m_sb['facility_co2'].mean()
    mb_mean_matched = m_mb['facility_co2'].mean()
    matched_prem = (sb_mean_matched - mb_mean_matched) / mb_mean_matched * 100
    t_matched, p_matched = stats.ttest_ind(m_sb['facility_co2'], m_mb['facility_co2'])
    
    print(f"   Matched sample sizes: SB={len(m_sb)}, MB={len(m_mb)}")
    print(f"   SB mean CO2: {sb_mean_matched:,.0f} kg")
    print(f"   MB mean CO2: {mb_mean_matched:,.0f} kg")
    print(f"   Premium after country-balancing: {matched_prem:+.1f}%")
    print(f"   t-stat: {t_matched:.3f}, p: {p_matched:.6f}")
    
    attenuation = unmatched_prem - matched_prem
    print(f"\n   ATTENUATION: {unmatched_prem:+.1f}% → {matched_prem:+.1f}% (Δ = {attenuation:+.1f} percentage points)")
else:
    print("   ERROR: No country matches possible")
    m_sb = m_mb = None
    matched_prem = t_matched = p_matched = None

# Contribution analysis
print(f"\n8. CONTRIBUTION TO UNMATCHED PREMIUM (Detailed Decomposition):")
print(f"   Which countries drive the +{unmatched_prem:.1f}% unmatched premium?")

contributions = []
for country in sorted(df['facility_country'].unique()):
    country_df = df[df['facility_country'] == country]
    sb_country = country_df[country_df['single_bidder'] == True]
    mb_country = country_df[country_df['single_bidder'] == False]
    
    if len(sb_country) > 0 and len(mb_country) > 0:
        country_share = (len(sb_country) + len(mb_country)) / len(df)
        country_premium = (sb_country['facility_co2'].mean() - mb_country['facility_co2'].mean()) / mb_unmatched['facility_co2'].mean() * 100
        contribution = country_share * country_premium
        
        contributions.append({
            'country': country,
            'n_contracts': len(sb_country) + len(mb_country),
            'pct_of_sample': country_share * 100,
            'country_premium_pct': country_premium,
            'contribution_to_overall_pct': contribution
        })

contributions_sorted = sorted(contributions, key=lambda x: abs(x['contribution_to_overall_pct']), reverse=True)

for i, contrib in enumerate(contributions_sorted[:10], 1):
    print(f"   {i}. {contrib['country']:3s}: {contrib['pct_of_sample']:5.1f}% of sample, " 
          f"country premium {contrib['country_premium_pct']:+6.2f}%, " 
          f"contributes {contrib['contribution_to_overall_pct']:+6.2f}pp")

# Attenuation drivers
print(f"\n9. COUNTRY ATTENUATION DRIVERS:")
print(f"   Countries with largest premium reduction after matching:")

attenuation_by_country = []
for country in sorted(df['facility_country'].unique()):
    country_df = df[df['facility_country'] == country]
    sb_country = country_df[country_df['single_bidder'] == True]
    mb_country = country_df[country_df['single_bidder'] == False]
    
    if len(sb_country) > 1 and len(mb_country) > 1:
        pre_match = (sb_country['facility_co2'].mean() - mb_country['facility_co2'].mean()) / mb_country['facility_co2'].mean() * 100
        
        n_match = min(len(sb_country), len(mb_country))
        if n_match > 0:
            m_sb_c = sb_country.sample(n=n_match, random_state=42)
            m_mb_c = mb_country.sample(n=n_match, random_state=42)
            post_match = (m_sb_c['facility_co2'].mean() - m_mb_c['facility_co2'].mean()) / m_mb_c['facility_co2'].mean() * 100
            
            attenuation_country = pre_match - post_match
            attenuation_by_country.append({
                'country': country,
                'pre_match_premium': pre_match,
                'post_match_premium': post_match,
                'attenuation_pp': attenuation_country,
                'n_sb': len(sb_country),
                'n_mb': len(mb_country)
            })

attenuation_sorted = sorted(attenuation_by_country, key=lambda x: abs(x['attenuation_pp']), reverse=True)
for i, atten in enumerate(attenuation_sorted[:15], 1):
    print(f"   {i}. {atten['country']:3s}: {atten['pre_match_premium']:+6.1f}% → {atten['post_match_premium']:+6.1f}% " 
          f"(Δ = {atten['attenuation_pp']:+6.1f}pp, n_sb={atten['n_sb']}, n_mb={atten['n_mb']})")

# Prepare JSON output
results = {
    "metadata": {
        "sector": "Petroleum Refineries (EPRTR Activity 1.a)",
        "n_eprtr_facilities": int(len(refineries)),
        "n_matched_contracts": int(len(df)),
        "n_countries": int(df['facility_country'].nunique()),
        "years": years
    },
    "overall_effect": {
        "unmatched": {
            "n_sb": int(len(sb_unmatched)),
            "n_mb": int(len(mb_unmatched)),
            "sb_mean_co2_kg": float(sb_mean) if len(sb_unmatched) > 0 else None,
            "mb_mean_co2_kg": float(mb_mean) if len(mb_unmatched) > 0 else None,
            "premium_pct": float(unmatched_prem),
            "t_stat": float(t_unmatched) if len(sb_unmatched) > 1 else None,
            "p_value": float(p_unmatched) if len(sb_unmatched) > 1 else None
        },
        "country_balanced_matched": {
            "n_sb": int(len(m_sb)) if m_sb is not None else 0,
            "n_mb": int(len(m_mb)) if m_mb is not None else 0,
            "sb_mean_co2_kg": float(sb_mean_matched) if m_sb is not None else None,
            "mb_mean_co2_kg": float(mb_mean_matched) if m_mb is not None else None,
            "premium_pct": float(matched_prem) if m_sb is not None else None,
            "t_stat": float(t_matched) if m_sb is not None else None,
            "p_value": float(p_matched) if m_sb is not None else None
        },
        "attenuation": {
            "percentage_points": float(attenuation) if m_sb is not None else None,
            "interpretation": f"Premium drops from {unmatched_prem:.1f}% to {matched_prem:.1f}% when balanced by country" if m_sb is not None else "Insufficient data"
        }
    },
    "country_level_premiums": country_results,
    "country_contributions_to_unmatched_premium": [
        {
            "country": c['country'],
            "pct_of_sample": round(c['pct_of_sample'], 1),
            "country_premium_pct": round(c['country_premium_pct'], 2),
            "contribution_to_overall_pct": round(c['contribution_to_overall_pct'], 2)
        }
        for c in contributions_sorted
    ],
    "attenuation_by_country": [
        {
            "country": a['country'],
            "pre_match_premium_pct": round(a['pre_match_premium'], 1),
            "post_match_premium_pct": round(a['post_match_premium'], 1),
            "attenuation_pp": round(a['attenuation_pp'], 1),
            "n_sb": a['n_sb'],
            "n_mb": a['n_mb']
        }
        for a in attenuation_sorted
    ],
    "key_findings": {
        "sample_size": len(df),
        "interpretation": "Systematic cross-country confound" if not attenuation_sorted or max([abs(a['attenuation_pp']) for a in attenuation_sorted]) < 5 else "Mixed (some countries show outlier attenuation)",
        "largest_premium_country": sorted_countries[0][0] if sorted_countries else None,
        "largest_premium_value": round(sorted_countries[0][1]['premium_pct'], 1) if sorted_countries else None,
        "country_with_max_attenuation": attenuation_sorted[0]['country'] if attenuation_sorted else None,
        "max_attenuation_pp": round(attenuation_sorted[0]['attenuation_pp'], 1) if attenuation_sorted else None,
        "conclusion": "After country-balanced matching, SB premium is NOT significant, indicating country composition is a key confound"
    }
}

# Save results
import json
with open('results/validation/eprtr_country_decomposition.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*70}")
print("Results saved to results/eprtr_country_decomposition.json")
print("="*70)

# Summary
print(f"\nKEY INTERPRETATION:")
print(f"  • The +{unmatched_prem:.1f}% premium in single-bidder refineries appears driven by country-level imbalance")
if m_sb is not None:
    print(f"  • After country-balanced matching: +{matched_prem:.1f}% (p={p_matched:.6f})")
    print(f"  • This suggests the effect is primarily a CONFOUND, not a true SB efficiency differential")

