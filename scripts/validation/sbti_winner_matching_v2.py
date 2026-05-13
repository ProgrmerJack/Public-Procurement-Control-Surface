"""
Enhanced SBTi → Procurement Winner Matching using supplier_name from gprd_master.
Also runs within-supplier competition-mode analysis.
"""
import pandas as pd
import numpy as np
import json
import re
import unicodedata
from pathlib import Path
from scipy.stats import chi2_contingency, ttest_ind

def normalize_name(name):
    if pd.isna(name) or not isinstance(name, str):
        return ""
    name = unicodedata.normalize('NFKD', name)
    name = name.encode('ascii', 'ignore').decode()
    name = name.upper().strip()
    suffixes = [
        r'\bGMBH\b', r'\bAG\b', r'\bS\.?A\.?\b', r'\bSAS\b', r'\bSRL\b',
        r'\bLTD\b', r'\bLIMITED\b', r'\bPLC\b', r'\bINC\b', r'\bCORP\b',
        r'\bSE\b', r'\bN\.?V\.?\b', r'\bB\.?V\.?\b', r'\bOY\b', r'\bAB\b',
        r'\bS\.?P\.?A\.?\b', r'\bSP\s*Z\s*O\s*O\b', r'\bA\.?S\.?\b',
        r'\bGROUP\b', r'\bHOLDING\b', r'\bHOLDINGS\b',
        r'\b&\s*CO\b', r'\bCO\.\b', r'\bCOMPANY\b',
        r'\bE\.?V\.?\b', r'\bKG\b', r'\bOHG\b',
    ]
    for s in suffixes:
        name = re.sub(s, '', name)
    name = re.sub(r'[^A-Z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def main():
    print("=" * 60)
    print("ENHANCED SBTi MATCHING (using supplier_name)")
    print("=" * 60)

    # Load SBTi
    print("\nLoading SBTi data...")
    sbti = pd.read_csv('Data/external/sbti_companies.csv')
    print(f"  Total SBTi companies: {len(sbti):,}")
    sbti['name_norm'] = sbti['company_name'].apply(normalize_name)
    # Build set of normalized names (at least 4 chars to avoid false matches)
    sbti_names = set(n for n in sbti['name_norm'] if len(n) >= 4)
    # Build name → info lookup
    sbti_info = {}
    for _, row in sbti.iterrows():
        n = row['name_norm']
        if len(n) >= 4:
            sbti_info[n] = {
                'company': row['company_name'],
                'sector': str(row.get('sector', '')),
                'status': str(row.get('near_term_status', '')),
            }
    print(f"  Unique normalized SBTi names: {len(sbti_names):,}")

    # Load procurement supplier_name from gprd_master
    print("\nLoading supplier_name from gprd_master (this may take a few minutes)...")
    cols = ['supplier_id', 'supplier_name', 'country', 'single_bidder',
            'cpv_division', 'carbon_intensity_kg_usd', 'value_eur', 'year']
    df = pd.read_parquet('Data/processed/gprd_master.parquet', columns=cols)

    # Filter to EU context (exclude CO)
    df = df[df['country'] != 'CO'].copy()
    print(f"  EU-context contracts: {len(df):,}")
    print(f"  With supplier_name: {df['supplier_name'].notna().sum():,}")
    print(f"  Unique supplier_names: {df['supplier_name'].nunique():,}")

    # Normalize supplier names
    print("\nNormalizing supplier names...")
    unique_suppliers = df[['supplier_name', 'country']].drop_duplicates()
    unique_suppliers = unique_suppliers[unique_suppliers['supplier_name'].notna()]
    unique_suppliers['name_norm'] = unique_suppliers['supplier_name'].apply(normalize_name)
    print(f"  Unique supplier name-country pairs: {len(unique_suppliers):,}")

    # Exact match on normalized names
    print("\nMatching...")
    matched_names = unique_suppliers[unique_suppliers['name_norm'].isin(sbti_names)]['supplier_name'].unique()
    matched_set = set(matched_names)
    print(f"  Exact name matches: {len(matched_set):,}")

    # Show sample matches
    print("\n  Sample matches:")
    for name in list(matched_set)[:15]:
        norm = normalize_name(name)
        info = sbti_info.get(norm, {})
        print(f"    {name} → {info.get('company', '?')} [{info.get('sector', '')}]")

    # Tag contracts
    df['sbti_winner'] = df['supplier_name'].isin(matched_set)
    n_sbti = df['sbti_winner'].sum()
    print(f"\n  Contracts won by SBTi firms: {n_sbti:,} ({n_sbti/len(df)*100:.3f}%)")

    if n_sbti < 50:
        print("\n  Too few matches for robust analysis. Trying substring matching...")
        # Try matching where SBTi name is a substring of supplier_name
        df['name_norm'] = df['supplier_name'].apply(normalize_name)
        # Only check names > 6 chars to avoid false positives
        long_sbti = [n for n in sbti_names if len(n) > 6]
        print(f"  Trying {len(long_sbti)} SBTi names as substrings...")

        from collections import defaultdict
        substring_matches = set()
        # Build a set of unique normalized procurement names
        unique_proc_names = set(df['name_norm'].dropna().unique())
        print(f"  Against {len(unique_proc_names):,} unique procurement names...")

        # For each SBTi name, check if it appears in any procurement name
        for sbti_n in long_sbti:
            for proc_n in unique_proc_names:
                if sbti_n in proc_n or proc_n in sbti_n:
                    # Find original names
                    orig_names = df[df['name_norm'] == proc_n]['supplier_name'].unique()
                    for on in orig_names:
                        substring_matches.add(on)

        if len(substring_matches) > len(matched_set):
            print(f"  Substring matches: {len(substring_matches):,}")
            matched_set = matched_set | substring_matches
            df['sbti_winner'] = df['supplier_name'].isin(matched_set)
            n_sbti = df['sbti_winner'].sum()
            print(f"  Total contracts with SBTi winners: {n_sbti:,}")

    # KEY ANALYSIS
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    comp = df[df['single_bidder'] == False]
    sb = df[df['single_bidder'] == True]

    sbti_rate_comp = comp['sbti_winner'].mean() if len(comp) > 0 else 0
    sbti_rate_sb = sb['sbti_winner'].mean() if len(sb) > 0 else 0
    ratio = sbti_rate_comp / sbti_rate_sb if sbti_rate_sb > 0 else float('inf')

    print(f"\n  SBTi winner rate in competitive: {sbti_rate_comp*100:.4f}%")
    print(f"  SBTi winner rate in SB:          {sbti_rate_sb*100:.4f}%")
    print(f"  Ratio (comp/SB): {ratio:.2f}x")

    # Chi-squared
    if n_sbti > 0:
        tab = pd.crosstab(df['single_bidder'], df['sbti_winner'])
        chi2, p, _, _ = chi2_contingency(tab)
        print(f"  Chi2={chi2:.1f}, p={p:.2e}")

    # Carbon intensity
    if n_sbti > 0:
        ci_sbti = df[df['sbti_winner']]['carbon_intensity_kg_usd'].mean()
        ci_non = df[~df['sbti_winner']]['carbon_intensity_kg_usd'].mean()
        diff = (ci_sbti - ci_non) / ci_non * 100
        print(f"\n  Carbon intensity:")
        print(f"    SBTi winners:     {ci_sbti:.4f} kg/USD")
        print(f"    Non-SBTi winners: {ci_non:.4f} kg/USD")
        print(f"    Difference: {diff:+.1f}%")

    # Temporal trend (SBTi firms growing over time?)
    if n_sbti > 50:
        print("\n  Temporal trend of SBTi winner selection:")
        for yr in sorted(df['year'].dropna().unique()):
            yr_df = df[df['year'] == yr]
            rate = yr_df['sbti_winner'].mean() * 100
            n = yr_df['sbti_winner'].sum()
            if n > 0:
                print(f"    {int(yr)}: {rate:.4f}% ({n:,} contracts)")

    # Save
    results = {
        'matching': {
            'sbti_companies': len(sbti),
            'unique_sbti_names_normalized': len(sbti_names),
            'matched_supplier_names': len(matched_set),
            'total_sbti_contracts': int(n_sbti),
            'eu_context_contracts': len(df),
        },
        'selection': {
            'sbti_rate_competitive_pct': float(sbti_rate_comp * 100),
            'sbti_rate_sb_pct': float(sbti_rate_sb * 100),
            'ratio': float(ratio),
        },
    }
    if n_sbti > 0:
        results['carbon'] = {
            'ci_sbti': float(ci_sbti),
            'ci_non_sbti': float(ci_non),
            'diff_pct': float(diff),
        }

    with open('results/validation/sbti_winner_matching_v2.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to results/sbti_winner_matching_v2.json")

if __name__ == '__main__':
    main()
