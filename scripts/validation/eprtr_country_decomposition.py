#!/usr/bin/env python3
"""
E-PRTR Country-Level Decomposition of SB Premium Attenuation
==============================================================
Analyzes the +8.7% → +1.2% attenuation when balancing on country,
identifying which countries drive the unmatched premium and which
drive the attenuation under matching.
"""

import pandas as pd
import numpy as np
import json
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

print("=" * 70)
print("E-PRTR COUNTRY DECOMPOSITION ANALYSIS")
print("=" * 70)

# Load E-PRTR facility data with CO2
print("\n1. Loading E-PRTR facility data...")
eprtr = pd.read_csv(
    'Data/raw/eea_t_ied-eprtr_p_2007-2023_v15_r00/User-friendly-CSV/F1_4_Air_Releases_Facilities.csv',
    low_memory=False
)
co2 = eprtr[eprtr['Pollutant'] == 'Carbon dioxide (CO2 - Air)'].copy()
co2['Releases'] = pd.to_numeric(co2['Releases'], errors='coerce')
co2 = co2.dropna(subset=['Releases'])
co2_fac = co2.groupby('FacilityInspireId').agg(
    mean_co2=('Releases', 'mean'),
    name=('facilityName', 'first'),
    country=('countryName', 'first'),
    activity=('EPRTRAnnexIMainActivity', 'first')
).reset_index()

# Get just refineries (Activity 1.a)
refineries = co2_fac[co2_fac['activity'].str.startswith('1.(a)')].copy()
print(f"   Refineries in E-PRTR: {len(refineries)}")
print(f"   Countries in refineries: {refineries['country'].nunique()}")

# Load procurement data
print("\n2. Loading procurement data...")
proc = pd.read_parquet(
    'Data/processed/gprd_with_carbon.parquet',
    columns=['country', 'year', 'single_bidder', 'carbon_intensity_kg_usd', 'value_eur', 'contractorName']
)
print(f"   Total procurement records: {len(proc)}")

# Match refineries to procurement contracts
print("\n3. Matching refineries to procurement contracts...")
matches = []
proc['name_upper'] = proc['contractorName'].fillna('').str.upper().str.strip()
proc_name_set = set(proc['name_upper'].unique())

for _, fac in refineries.iterrows():
    name_upper = str(fac['name']).upper().strip()
    if name_upper in proc_name_set:
        fac_contracts = proc[proc['name_upper'] == name_upper]
        for _, c in fac_contracts.iterrows():
            matches.append({
                'facility_id': fac['FacilityInspireId'],
                'facility_name': fac['name'],
                'facility_co2': fac['mean_co2'],
                'facility_country': fac['country'],
                'contract_country': c['country'],
                'year': c['year'],
                'single_bidder': c['single_bidder'],
                'carbon_intensity': c['carbon_intensity_kg_usd'],
                'value_eur': c['value_eur']
            })

df = pd.DataFrame(matches)
print(f"   Total matched refinery contracts: {len(df)}")
print(f"   Unique facilities: {df['facility_id'].nunique()}")

if len(df) == 0:
    print("ERROR: No matches found")
    exit(1)

# Map country names to codes for better readability
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

df['facility_country_code'] = df['facility_country'].map(country_name_to_code).fillna(df['facility_country'])

# Show overall stats first
print(f"\n4. Overall Sample Breakdown:")
print(f"   SB contracts: {(df['single_bidder']==True).sum()}")
print(f"   MB contracts: {(df['single_bidder']==False).sum()}")
print(f"   Countries represented: {df['facility_country_code'].nunique()}")

# Get unmatched overall effect
sb_unmatched = df[df['single_bidder']==True]
mb_unmatched = df[df['single_bidder']==False]
sb_mean = sb_unmatched['facility_co2'].mean()
mb_mean = mb_unmatched['facility_co2'].mean()
unmatched_prem = (sb_mean - mb_mean) / mb_mean * 100
t_unmatched, p_unmatched = stats.ttest_ind(sb_unmatched['facility_co2'], mb_unmatched['facility_co2'])

print(f"\n5. UNMATCHED EFFECT (Full Sample):")
print(f"   SB mean CO2: {sb_mean:,.0f} kg")
print(f"   MB mean CO2: {mb_mean:,.0f} kg")
print(f"   Premium: {unmatched_prem:+.1f}%")
print(f"   t-stat: {t_unmatched:.3f}, p: {p_unmatched:.4f}")

# Now do country-level matching and decomposition
print(f"\n6. COUNTRY-LEVEL DECOMPOSITION:")
print(f"   Analyzing SB vs MB premium by country...")

country_results = {}
for country in sorted(df['facility_country_code'].unique()):
    country_df = df[df['facility_country_code'] == country]
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
    p_val_str = f"{stats_dict['p_value']:.4f}" if stats_dict['p_value'] is not None else "N/A"
    print(f"   {country:3s}: n_sb={stats_dict['n_sb']:3d}, n_mb={stats_dict['n_mb']:3d}, " 
          f"premium={stats_dict['premium_pct']:+7.1f}%, p={p_val_str}")

# Now do country-balanced matching
print(f"\n7. COUNTRY-BALANCED MATCHING:")
print(f"   Matching on facility_country to remove country confound...")

matched_sb_list = []
matched_mb_list = []
np.random.seed(42)

for country in sorted(df['facility_country_code'].unique()):
    country_df = df[df['facility_country_code'] == country]
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
    print(f"   t-stat: {t_matched:.3f}, p: {p_matched:.4f}")
    
    attenuation = unmatched_prem - matched_prem
    print(f"\n   ATTENUATION: {unmatched_prem:+.1f}% → {matched_prem:+.1f}% (Δ = {attenuation:+.1f} percentage points)")
else:
    print("   ERROR: No country matches possible")
    m_sb = m_mb = None

# Calculate contribution to unmatched premium by country
print(f"\n8. CONTRIBUTION TO UNMATCHED PREMIUM (Detailed Decomposition):")
print(f"   Which countries drive the +{unmatched_prem:.1f}% unmatched premium?")

# For each country, compute its contribution to the overall SB-MB difference
contributions = []
for country in sorted(df['facility_country_code'].unique()):
    country_df = df[df['facility_country_code'] == country]
    sb_country = country_df[country_df['single_bidder'] == True]
    mb_country = country_df[country_df['single_bidder'] == False]
    
    if len(sb_country) > 0 and len(mb_country) > 0:
        # Contribution = (country share of total) * (country premium)
        country_share = (len(sb_country) + len(mb_country)) / len(df)
        country_premium = (sb_country['facility_co2'].mean() - mb_country['facility_co2'].mean()) / mb_mean * 100
        contribution = country_share * country_premium
        
        contributions.append({
            'country': country,
            'n_contracts': len(sb_country) + len(mb_country),
            'pct_of_sample': country_share * 100,
            'country_premium_pct': country_premium,
            'contribution_to_overall_pct': contribution
        })

# Sort by contribution (absolute value)
contributions_sorted = sorted(contributions, key=lambda x: abs(x['contribution_to_overall_pct']), reverse=True)

for i, contrib in enumerate(contributions_sorted[:10], 1):
    print(f"   {i}. {contrib['country']:3s}: {contrib['pct_of_sample']:5.1f}% of sample, " 
          f"country premium {contrib['country_premium_pct']:+6.2f}%, " 
          f"contributes {contrib['contribution_to_overall_pct']:+6.2f}pp")

# Identify which country(ies) drive the attenuation
print(f"\n9. COUNTRY ATTENUATION DRIVERS:")
print(f"   Under country-matching, {country_results.copy().__len__()} countries become balanced.")
print(f"   Countries with largest premium reduction after matching:")

attenuation_by_country = []
for country in sorted(df['facility_country_code'].unique()):
    # Get pre-match premium
    country_df = df[df['facility_country_code'] == country]
    sb_country = country_df[country_df['single_bidder'] == True]
    mb_country = country_df[country_df['single_bidder'] == False]
    
    if len(sb_country) > 1 and len(mb_country) > 1:
        pre_match = (sb_country['facility_co2'].mean() - mb_country['facility_co2'].mean()) / mb_country['facility_co2'].mean() * 100
        
        # Get matched premium for this country
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
for i, atten in enumerate(attenuation_sorted[:10], 1):
    print(f"   {i}. {atten['country']:3s}: {atten['pre_match_premium']:+6.1f}% → {atten['post_match_premium']:+6.1f}% " 
          f"(Δ = {atten['attenuation_pp']:+6.1f}pp, n_sb={atten['n_sb']}, n_mb={atten['n_mb']})")

# Prepare comprehensive JSON output
results = {
    "metadata": {
        "sector": "Petroleum Refineries (EPRTR Activity 1.a)",
        "n_eprtr_facilities": int(len(refineries)),
        "n_matched_contracts": int(len(df)),
        "n_countries": int(df['facility_country_code'].nunique())
    },
    "overall_effect": {
        "unmatched": {
            "n_sb": int(len(sb_unmatched)),
            "n_mb": int(len(mb_unmatched)),
            "sb_mean_co2_kg": float(sb_mean),
            "mb_mean_co2_kg": float(mb_mean),
            "premium_pct": float(unmatched_prem),
            "t_stat": float(t_unmatched),
            "p_value": float(p_unmatched)
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
            "interpretation": f"Premium drops from {unmatched_prem:.1f}% to {matched_prem:.1f}% when balanced by country"
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
        "outlier_or_systematic": "Systematic cross-country confound" if max([abs(a['attenuation_pp']) for a in attenuation_sorted]) < 5 else "Possible outlier country",
        "largest_premium_country": sorted_countries[0][0] if sorted_countries else None,
        "largest_premium_value": sorted_countries[0][1]['premium_pct'] if sorted_countries else None,
        "country_with_max_attenuation": attenuation_sorted[0]['country'] if attenuation_sorted else None,
        "max_attenuation_pp": round(attenuation_sorted[0]['attenuation_pp'], 1) if attenuation_sorted else None
    }
}

# Save results
with open('results/validation/eprtr_country_decomposition.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*70}")
print("Results saved to results/eprtr_country_decomposition.json")
print("="*70)

# Summary interpretation
print(f"\nKEY INTERPRETATION:")
print(f"  • The +{unmatched_prem:.1f}% premium in single-bidder refineries is driven by country-level imbalance")
print(f"  • After country-balanced matching: +{matched_prem:.1f}% (p={p_matched:.4f}), suggesting the effect")
print(f"    is primarily a CONFOUND, not a true SB efficiency effect")

max_atten = max([a['attenuation_pp'] for a in attenuation_sorted], default=0)
min_atten = min([a['attenuation_pp'] for a in attenuation_sorted], default=0)
print(f"  • Attenuation magnitude ranges from {min_atten:.1f}pp to {max_atten:.1f}pp across countries")
print(f"  • This {'suggests a SINGLE OUTLIER' if max_atten > 5 else 'indicates SYSTEMATIC confound across countries'}")

