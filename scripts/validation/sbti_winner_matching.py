"""
SBTi → Procurement Winner Matching Analysis
Match 14,366 SBTi companies to 2.1M unique procurement suppliers.
Test if competitive tenders actually SELECT SBTi-validated winners.
"""
import pandas as pd
import numpy as np
import json
import re
import unicodedata
from pathlib import Path

def normalize_name(name):
    """Aggressively normalize company names for matching."""
    if pd.isna(name) or not isinstance(name, str):
        return ""
    name = unicodedata.normalize('NFKD', name)
    name = name.encode('ascii', 'ignore').decode()
    name = name.upper().strip()
    # Remove common legal suffixes
    suffixes = [
        r'\bGMBH\b', r'\bAG\b', r'\bSA\b', r'\bSAS\b', r'\bSRL\b',
        r'\bLTD\b', r'\bLIMITED\b', r'\bPLC\b', r'\bINC\b', r'\bCORP\b',
        r'\bSE\b', r'\bNV\b', r'\bBV\b', r'\bOY\b', r'\bAB\b',
        r'\bSPA\b', r'\bSP\.?\s*Z\.?\s*O\.?\s*O\.?\b', r'\bAS\b',
        r'\bOOD\b', r'\bKFT\b', r'\bZRT\b', r'\bDOO\b',
        r'\bS\.?A\.?S\.?\b', r'\bS\.?R\.?L\.?\b', r'\bS\.?P\.?A\.?\b',
        r'\bS\.?A\.?\b', r'\bE\.?V\.?\b',
        r'\bGROUP\b', r'\bHOLDING\b', r'\bHOLDINGS\b',
        r'\b& CO\b', r'\bCO\.\b', r'\bCOMPANY\b',
    ]
    for s in suffixes:
        name = re.sub(s, '', name)
    name = re.sub(r'[^A-Z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def main():
    print("=" * 60)
    print("SBTi → PROCUREMENT WINNER MATCHING")
    print("=" * 60)

    # Load SBTi companies
    print("\nLoading SBTi data...")
    sbti = pd.read_csv('Data/external/sbti_companies.csv')
    print(f"  SBTi companies: {len(sbti):,}")
    sbti['name_norm'] = sbti['company_name'].apply(normalize_name)
    sbti['country_map'] = sbti['location'].map({
        'Germany': 'DE', 'France': 'FR', 'United Kingdom of Great Britain and Northern Ireland': 'GB',
        'Spain': 'ES', 'Italy': 'IT', 'Netherlands': 'NL', 'Belgium': 'BE',
        'Sweden': 'SE', 'Denmark': 'DK', 'Finland': 'FI', 'Austria': 'AT',
        'Ireland': 'IE', 'Poland': 'PL', 'Czech Republic': 'CZ', 'Czechia': 'CZ',
        'Portugal': 'PT', 'Greece': 'GR', 'Romania': 'RO', 'Hungary': 'HU',
        'Norway': 'NO', 'Switzerland': 'CH', 'Luxembourg': 'LU',
        'Slovakia': 'SK', 'Slovenia': 'SI', 'Lithuania': 'LT',
        'Latvia': 'LV', 'Estonia': 'EE', 'Croatia': 'HR',
        'Bulgaria': 'BG', 'Cyprus': 'CY', 'Malta': 'MT', 'Iceland': 'IS',
    })
    eu_sbti = sbti[sbti['country_map'].notna()].copy()
    print(f"  EU/EEA SBTi companies: {len(eu_sbti):,}")

    # Build SBTi lookup: normalized name → SBTi info
    sbti_lookup = {}
    for _, row in eu_sbti.iterrows():
        if row['name_norm']:
            key = (row['name_norm'], row['country_map'])
            sbti_lookup[key] = {
                'company': row['company_name'],
                'sector': row.get('sector', ''),
                'near_term_status': row.get('near_term_status', ''),
                'target_class': row.get('near_term_target_classification', ''),
            }

    # Also create name-only lookup for fuzzy matching
    sbti_names = {}
    for _, row in eu_sbti.iterrows():
        if row['name_norm'] and len(row['name_norm']) > 3:
            sbti_names[row['name_norm']] = row['country_map']

    print(f"  SBTi lookup entries (name+country): {len(sbti_lookup):,}")
    print(f"  SBTi name entries: {len(sbti_names):,}")

    # Load procurement data - EU context only
    print("\nLoading procurement data (EU context)...")
    cols = ['supplier_id', 'country', 'single_bidder', 'n_bidders',
            'cpv_division', 'exiobase_sector', 'carbon_intensity_kg_usd',
            'value_eur']
    df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet', columns=cols)
    df = df[df['country'] != 'CO'].copy()  # EU context
    print(f"  EU-context contracts: {len(df):,}")
    print(f"  Unique suppliers: {df['supplier_id'].nunique():,}")

    # Normalize supplier IDs for matching
    # Handle compound IDs (e.g., "SC 041252---9049658")
    print("\nNormalizing supplier names...")
    # Get unique suppliers
    suppliers = df[['supplier_id', 'country']].drop_duplicates()
    suppliers['name_norm'] = suppliers['supplier_id'].apply(normalize_name)

    # Match: exact name + country
    print("\nMatching SBTi companies to procurement suppliers...")
    matched_suppliers = set()
    match_details = []
    for _, row in suppliers.iterrows():
        key = (row['name_norm'], row['country'])
        if key in sbti_lookup:
            matched_suppliers.add(row['supplier_id'])
            match_details.append({
                'supplier_id': row['supplier_id'],
                'country': row['country'],
                'sbti_company': sbti_lookup[key]['company'],
                'sbti_sector': sbti_lookup[key]['sector'],
                'target_class': sbti_lookup[key]['target_class'],
            })

    # Also try name-only match (without country restriction)
    for _, row in suppliers.iterrows():
        if row['supplier_id'] not in matched_suppliers and row['name_norm'] in sbti_names:
            matched_suppliers.add(row['supplier_id'])
            match_details.append({
                'supplier_id': row['supplier_id'],
                'country': row['country'],
                'sbti_company': row['name_norm'],
                'sbti_sector': '',
                'target_class': 'name-only match',
            })

    print(f"  Matched SBTi suppliers: {len(matched_suppliers):,}")

    # Tag contracts
    df['sbti_winner'] = df['supplier_id'].isin(matched_suppliers)
    sbti_contracts = df[df['sbti_winner']].copy()
    non_sbti = df[~df['sbti_winner']].copy()

    print(f"  Contracts won by SBTi firms: {sbti_contracts.shape[0]:,} ({sbti_contracts.shape[0]/len(df)*100:.3f}%)")

    # KEY ANALYSIS: Are SBTi firms more likely to win competitive tenders?
    print("\n" + "=" * 60)
    print("KEY RESULT: SBTi Winner Selection by Competition Type")
    print("=" * 60)

    # Rate of SBTi winners in competitive vs single-bidder
    comp = df[df['single_bidder'] == False]
    sb = df[df['single_bidder'] == True]

    sbti_rate_comp = comp['sbti_winner'].mean()
    sbti_rate_sb = sb['sbti_winner'].mean()
    ratio = sbti_rate_comp / sbti_rate_sb if sbti_rate_sb > 0 else float('inf')

    print(f"  Competitive tenders: {sbti_rate_comp*100:.4f}% won by SBTi firms")
    print(f"  Single-bidder:       {sbti_rate_sb*100:.4f}% won by SBTi firms")
    print(f"  Ratio: {ratio:.2f}x")

    # Chi-squared test
    from scipy.stats import chi2_contingency
    contingency = pd.crosstab(df['single_bidder'], df['sbti_winner'])
    chi2, p_val, dof, expected = chi2_contingency(contingency)
    print(f"  Chi-squared: {chi2:.1f}, p = {p_val:.2e}")

    # By bidder count bins
    print("\n  By bidder count:")
    df['bidder_bin'] = pd.cut(df['n_bidders'].fillna(0), bins=[0, 1, 2, 5, 10, 100],
                               labels=['1 (SB)', '2', '3-5', '6-10', '11+'])
    for bin_label in ['1 (SB)', '2', '3-5', '6-10', '11+']:
        subset = df[df['bidder_bin'] == bin_label]
        if len(subset) > 0:
            rate = subset['sbti_winner'].mean()
            n = len(subset)
            print(f"    {bin_label}: {rate*100:.4f}% ({n:,} contracts)")

    # By sector (Dead Zone vs non-Dead Zone)
    # Dead Zone CPV divisions (from the paper)
    dz_cpvs = [24, 77, 65, 35, 15, 33, 14, 34, 31, 45, 44, 42, 39, 43, 9, 16, 37, 50, 51, 38, 41, 76]
    df['dead_zone'] = df['cpv_division'].isin(dz_cpvs)

    print("\n  Dead Zone sectors:")
    for dz_label, dz_val in [('Dead Zone', True), ('Non-Dead Zone', False)]:
        subset = df[df['dead_zone'] == dz_val]
        comp_sub = subset[subset['single_bidder'] == False]
        sb_sub = subset[subset['single_bidder'] == True]
        if len(comp_sub) > 0 and len(sb_sub) > 0:
            r_comp = comp_sub['sbti_winner'].mean()
            r_sb = sb_sub['sbti_winner'].mean()
            r = r_comp / r_sb if r_sb > 0 else float('inf')
            print(f"    {dz_label}: Comp={r_comp*100:.4f}% SB={r_sb*100:.4f}% Ratio={r:.2f}x")

    # Carbon intensity comparison
    print("\n  Carbon intensity of SBTi vs non-SBTi winners:")
    sbti_ci = df[df['sbti_winner']]['carbon_intensity_kg_usd'].mean()
    non_sbti_ci = df[~df['sbti_winner']]['carbon_intensity_kg_usd'].mean()
    diff_pct = (sbti_ci - non_sbti_ci) / non_sbti_ci * 100
    print(f"    SBTi winners: {sbti_ci:.4f} kg CO2/USD")
    print(f"    Non-SBTi:     {non_sbti_ci:.4f} kg CO2/USD")
    print(f"    Difference:   {diff_pct:+.1f}%")

    # Value-weighted analysis
    print("\n  Value-weighted SBTi selection:")
    for comp_label, comp_val in [('Competitive', False), ('Single-bidder', True)]:
        subset = df[df['single_bidder'] == comp_val]
        total_val = subset['value_eur'].sum()
        sbti_val = subset[subset['sbti_winner']]['value_eur'].sum()
        pct = sbti_val / total_val * 100 if total_val > 0 else 0
        print(f"    {comp_label}: {pct:.3f}% of value to SBTi firms (EUR {sbti_val/1e9:.2f}B / {total_val/1e9:.0f}B)")

    # Save results
    results = {
        'matching_summary': {
            'sbti_total': len(sbti),
            'sbti_eu': len(eu_sbti),
            'sbti_matched_to_suppliers': len(matched_suppliers),
            'contracts_with_sbti_winner': int(df['sbti_winner'].sum()),
            'total_eu_contracts': len(df),
            'match_rate_pct': len(matched_suppliers) / len(eu_sbti) * 100 if len(eu_sbti) > 0 else 0,
        },
        'selection_analysis': {
            'sbti_rate_competitive_pct': float(sbti_rate_comp * 100),
            'sbti_rate_single_bidder_pct': float(sbti_rate_sb * 100),
            'competitive_to_sb_ratio': float(ratio),
            'chi2': float(chi2),
            'p_value': float(p_val),
        },
        'carbon_comparison': {
            'sbti_winner_carbon_intensity': float(sbti_ci),
            'non_sbti_carbon_intensity': float(non_sbti_ci),
            'difference_pct': float(diff_pct),
        },
        'dead_zone_analysis': {},
        'sample_matches': match_details[:30],
    }

    # Dead zone details
    for dz_label, dz_val in [('dead_zone', True), ('non_dead_zone', False)]:
        subset = df[df['dead_zone'] == dz_val]
        comp_sub = subset[subset['single_bidder'] == False]
        sb_sub = subset[subset['single_bidder'] == True]
        results['dead_zone_analysis'][dz_label] = {
            'sbti_rate_competitive': float(comp_sub['sbti_winner'].mean()),
            'sbti_rate_sb': float(sb_sub['sbti_winner'].mean()),
            'ratio': float(comp_sub['sbti_winner'].mean() / sb_sub['sbti_winner'].mean()) if sb_sub['sbti_winner'].mean() > 0 else None,
            'n_contracts': len(subset),
        }

    out_path = Path('results/validation/sbti_winner_matching.json')
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

if __name__ == '__main__':
    main()
