"""
Bridge analysis: Compare EXIOBASE premium on the full sample vs the Eurostat-matchable subsample.
If EXIOBASE premium is similar on both, the Eurostat strengthening is due to measurement
granularity, not sample selection.

Also runs the Eurostat within-sector analysis with FDR correction (per critic).
"""
import pandas as pd
import numpy as np
import json

print("=" * 60)
print("BRIDGE ANALYSIS: EXIOBASE full vs Eurostat-matchable subsample")
print("=" * 60)

print("\nLoading gprd_with_carbon.parquet...")
df = pd.read_parquet("Data/processed/gprd_with_carbon.parquet",
                     columns=['country', 'single_bidder', 'carbon_intensity_kg_usd',
                              'cpv_division', 'year', 'exiobase_sector'])
print(f"  Total rows: {len(df):,}")

eu = df[df['country'] != 'CO'].copy()
print(f"  EU-context: {len(eu):,}")

eurostat_ci = pd.read_csv("Data/processed/eurostat_carbon_intensities.csv")
print(f"  Eurostat CI rows: {len(eurostat_ci):,}")

# Build CPV-to-NACE crosswalk
cpv_to_nace = {
    '01': 'A', '02': 'A', '03': 'A',
    '09': 'B', '14': 'B',
    '15': 'C10-C12',
    '18': 'C13-C15',
    '19': 'C16',
    '22': 'C17',
    '24': 'C20',
    '33': 'C21',
    '25': 'C22',
    '44': 'C23',
    '34': 'C24',
    '43': 'C25',
    '30': 'C26', '32': 'C26', '48': 'C26',
    '31': 'C27',
    '42': 'C28', '38': 'C28', '16': 'C28',
    '29': 'C22',
    '35': 'D',
    '65': 'E',
    '45': 'F',
    '60': 'H', '63': 'H',
    '55': 'I',
    '64': 'J', '72': 'J',
    '66': 'K',
    '70': 'L',
    '71': 'M', '73': 'M', '79': 'M',
    '77': 'A', '37': 'A',
    '50': 'N', '90': 'N', '92': 'N',
    '80': 'O',
    '39': 'P',
    '85': 'Q',
    '98': 'N',
}

eu['cpv_div_str'] = eu['cpv_division'].astype(str).str.zfill(2)
eu['nace'] = eu['cpv_div_str'].map(cpv_to_nace)

# Build set of valid Eurostat keys
eurostat_keys = set()
for _, row in eurostat_ci.iterrows():
    eurostat_keys.add((row['country'], row['nace'], int(row['year'])))

print("\nChecking Eurostat matchability...")
eu_nace_notna = eu[eu['nace'].notna()].copy()
eu_nace_notna['ekey'] = list(zip(eu_nace_notna['country'], eu_nace_notna['nace'],
                                  eu_nace_notna['year'].astype(int)))
eu_nace_notna['eurostat_matchable'] = eu_nace_notna['ekey'].isin(eurostat_keys)

n_matchable = eu_nace_notna['eurostat_matchable'].sum()
n_total = len(eu)
print(f"  Eurostat-matchable: {n_matchable:,} / {n_total:,} = {100*n_matchable/n_total:.1f}%")

# ============================================================
# BRIDGE TEST
# ============================================================
print("\n" + "=" * 60)
print("EXIOBASE PREMIUM COMPARISON")
print("=" * 60)

def calc_premium(data, label):
    sb = data[data['single_bidder'] == True]['carbon_intensity_kg_usd']
    mb = data[data['single_bidder'] == False]['carbon_intensity_kg_usd']
    sb_mean = sb.mean()
    mb_mean = mb.mean()
    premium = (sb_mean - mb_mean) / mb_mean * 100
    d = (sb_mean - mb_mean) / data['carbon_intensity_kg_usd'].std()
    print(f"  {label}:")
    print(f"    N = {len(data):,} (SB={len(sb):,}, MB={len(mb):,})")
    print(f"    SB mean = {sb_mean:.4f}, MB mean = {mb_mean:.4f}")
    print(f"    Premium = {premium:.2f}%,  d = {d:.4f}")
    return {'n': int(len(data)), 'n_sb': int(len(sb)), 'n_mb': int(len(mb)),
            'sb_mean': round(float(sb_mean), 4), 'mb_mean': round(float(mb_mean), 4),
            'premium_pct': round(float(premium), 2), 'cohens_d': round(float(d), 4)}

r_full = calc_premium(eu, "EXIOBASE on FULL EU-context sample")
print()
matchable_df = eu_nace_notna[eu_nace_notna['eurostat_matchable']]
r_match = calc_premium(matchable_df, "EXIOBASE on Eurostat-MATCHABLE subsample")
print()
unmatch_df = eu[~eu.index.isin(matchable_df.index)]
r_unmatch = calc_premium(unmatch_df, "EXIOBASE on NON-matchable subsample")

diff = abs(r_full['premium_pct'] - r_match['premium_pct'])
print(f"\n  Premium difference (full vs matchable): {diff:.2f} pp")
conclusion = 'measurement_granularity' if diff < 2 else 'possible_sample_selection'
print(f"  --> {conclusion.upper()}")

# ============================================================
# Eurostat premium on matchable subsample
# ============================================================
print("\n" + "=" * 60)
print("EUROSTAT PREMIUM ON MATCHABLE SUBSAMPLE")
print("=" * 60)

matchable_merged = matchable_df.copy()
matchable_merged['year_int'] = matchable_merged['year'].astype(int)
eurostat_ci['year_int'] = eurostat_ci['year'].astype(int)
matchable_merged = matchable_merged.merge(
    eurostat_ci[['country', 'nace', 'year_int', 'intensity_kg_eur']],
    on=['country', 'nace', 'year_int'], how='left')

matched_with_ci = matchable_merged[matchable_merged['intensity_kg_eur'].notna()]
print(f"  Contracts with Eurostat CI: {len(matched_with_ci):,}")

sb_euro = matched_with_ci[matched_with_ci['single_bidder'] == True]['intensity_kg_eur']
mb_euro = matched_with_ci[matched_with_ci['single_bidder'] == False]['intensity_kg_eur']
euro_premium = (sb_euro.mean() - mb_euro.mean()) / mb_euro.mean() * 100
euro_d = (sb_euro.mean() - mb_euro.mean()) / matched_with_ci['intensity_kg_eur'].std()
print(f"  SB mean (Eurostat) = {sb_euro.mean():.4f}")
print(f"  MB mean (Eurostat) = {mb_euro.mean():.4f}")
print(f"  Eurostat premium = {euro_premium:.2f}%")
print(f"  Eurostat d = {euro_d:.4f}")

# ============================================================
# Within-sector analysis with FDR correction
# ============================================================
print("\n" + "=" * 60)
print("EUROSTAT WITHIN-SECTOR ANALYSIS (FDR-corrected)")
print("=" * 60)

from scipy.stats import ttest_ind, binomtest

groups = matched_with_ci.groupby(['country', 'nace'])
within_results = []

for (country, nace), grp in groups:
    sb_vals = grp[grp['single_bidder'] == True]['intensity_kg_eur']
    mb_vals = grp[grp['single_bidder'] == False]['intensity_kg_eur']
    if len(sb_vals) >= 5 and len(mb_vals) >= 5:
        combined_std = pd.concat([sb_vals, mb_vals]).std()
        if combined_std > 0:
            t, p = ttest_ind(sb_vals, mb_vals, equal_var=False)
            prem = (sb_vals.mean() - mb_vals.mean()) / mb_vals.mean() * 100 if mb_vals.mean() != 0 else 0
            within_results.append({
                'country': country, 'nace': nace,
                'n_sb': len(sb_vals), 'n_mb': len(mb_vals),
                'premium_pct': prem, 't': t, 'p': p
            })

within_df = pd.DataFrame(within_results)
n_tests = len(within_df)
print(f"  Groups tested: {n_tests}")

# BH FDR correction
within_df_sorted = within_df.sort_values('p').reset_index(drop=True)
within_df_sorted['rank'] = range(1, n_tests + 1)
within_df_sorted['bh_threshold'] = within_df_sorted['rank'] / n_tests * 0.05
within_df_sorted['sig_bh'] = within_df_sorted['p'] <= within_df_sorted['bh_threshold']

n_sig_raw = int((within_df['p'] < 0.05).sum())
n_sig_fdr = int(within_df_sorted['sig_bh'].sum())

sig_raw = within_df[within_df['p'] < 0.05]
n_neg_raw = int((sig_raw['premium_pct'] < 0).sum())
n_pos_raw = int((sig_raw['premium_pct'] > 0).sum())

sig_fdr = within_df_sorted[within_df_sorted['sig_bh']]
n_neg_fdr = int((sig_fdr['premium_pct'] < 0).sum())
n_pos_fdr = int((sig_fdr['premium_pct'] > 0).sum())

n_neg_all = int((within_df['premium_pct'] < 0).sum())
n_pos_all = int((within_df['premium_pct'] > 0).sum())
sign_test = binomtest(n_neg_all, n_neg_all + n_pos_all, 0.5)

print(f"\n  Raw p < 0.05: {n_sig_raw}/{n_tests} ({100*n_sig_raw/n_tests:.1f}%)")
print(f"    Negative: {n_neg_raw}, Positive: {n_pos_raw}, Ratio: {n_neg_raw/max(n_pos_raw,1):.1f}:1")
print(f"\n  FDR-corrected (BH q < 0.05): {n_sig_fdr}/{n_tests} ({100*n_sig_fdr/n_tests:.1f}%)")
print(f"    Negative: {n_neg_fdr}, Positive: {n_pos_fdr}, Ratio: {n_neg_fdr/max(n_pos_fdr,1):.1f}:1")
print(f"\n  Sign test (all groups): {n_neg_all} negative vs {n_pos_all} positive")
print(f"    Binomial p = {sign_test.pvalue:.2e}")

within_df['weight'] = within_df['n_sb'] + within_df['n_mb']
wtd_premium = float(np.average(within_df['premium_pct'], weights=within_df['weight']))
print(f"\n  Weighted within-sector premium: {wtd_premium:.3f}%")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print("BRIDGE ANALYSIS SUMMARY TABLE")
print("=" * 60)
print(f"{'Measure':<40} {'N':>12} {'Premium':>10} {'d':>8}")
print("-" * 72)
print(f"{'EXIOBASE (full EU-context)':<40} {r_full['n']:>12,} {r_full['premium_pct']:>9.2f}% {r_full['cohens_d']:>8.4f}")
print(f"{'EXIOBASE (Eurostat-matchable subset)':<40} {r_match['n']:>12,} {r_match['premium_pct']:>9.2f}% {r_match['cohens_d']:>8.4f}")
print(f"{'EXIOBASE (non-matchable subset)':<40} {r_unmatch['n']:>12,} {r_unmatch['premium_pct']:>9.2f}% {r_unmatch['cohens_d']:>8.4f}")
print(f"{'Eurostat (matchable subset)':<40} {len(matched_with_ci):>12,} {euro_premium:>9.2f}% {euro_d:>8.4f}")

results = {
    'bridge_analysis': {
        'exiobase_full': r_full,
        'exiobase_matchable': r_match,
        'exiobase_non_matchable': r_unmatch,
        'eurostat_matchable': {
            'n': int(len(matched_with_ci)),
            'sb_mean': round(float(sb_euro.mean()), 4),
            'mb_mean': round(float(mb_euro.mean()), 4),
            'premium_pct': round(float(euro_premium), 2),
            'cohens_d': round(float(euro_d), 4)
        },
        'premium_difference_full_vs_matchable': round(float(diff), 2),
        'conclusion': conclusion
    },
    'within_sector_fdr': {
        'n_groups': n_tests,
        'n_sig_raw': n_sig_raw,
        'n_sig_fdr': n_sig_fdr,
        'n_neg_raw': n_neg_raw,
        'n_pos_raw': n_pos_raw,
        'neg_pos_ratio_raw': round(n_neg_raw / max(n_pos_raw, 1), 1),
        'n_neg_fdr': n_neg_fdr,
        'n_pos_fdr': n_pos_fdr,
        'neg_pos_ratio_fdr': round(n_neg_fdr / max(n_pos_fdr, 1), 1),
        'sign_test_n_neg': n_neg_all,
        'sign_test_n_pos': n_pos_all,
        'sign_test_p': float(sign_test.pvalue),
        'weighted_within_premium_pct': round(wtd_premium, 3)
    }
}

with open('results/mechanism/bridge_analysis.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to results/bridge_analysis.json")
