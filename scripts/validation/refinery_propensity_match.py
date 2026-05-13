"""Propensity-matched refinery analysis to address SB/MB sample imbalance."""
import pandas as pd
import numpy as np
import json
from scipy import stats

# Load E-PRTR data
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

# Load procurement
proc = pd.read_parquet(
    'Data/processed/gprd_with_carbon.parquet',
    columns=['country', 'year', 'single_bidder', 'carbon_intensity_kg_usd', 'value_eur', 'contractorName']
)

# Focus on refineries: Activity 1(a)
refineries = co2_fac[co2_fac['activity'].str.startswith('1.(a)')].copy()
print(f"Refineries in E-PRTR: {len(refineries)}")
print(f"Countries: {refineries['country'].nunique()}")

# Match to procurement (exact match on name)
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
print(f"Total matched refinery contracts: {len(df)}")

if len(df) == 0:
    # Try substring matching for refineries
    print("No exact matches. Trying substring matching...")
    for _, fac in refineries.iterrows():
        name_upper = str(fac['name']).upper().strip()
        if len(name_upper) < 5:
            continue
        mask = proc['name_upper'].str.contains(name_upper[:20], na=False, regex=False)
        fac_contracts = proc[mask]
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
    print(f"After substring matching: {len(df)}")

if len(df) == 0:
    print("No refinery matches found at all.")
    # Save null results
    results = {"status": "no_matches", "note": "No refinery facilities matched to procurement contracts"}
    with open('results/validation/refinery_propensity_match.json', 'w') as f:
        json.dump(results, f, indent=2)
    exit(0)

sb = df[df['single_bidder'] == True]
mb = df[df['single_bidder'] == False]
print(f"SB: {len(sb)}, MB: {len(mb)}")

# APPROACH 1: Country-year matched subsample
print("\n=== APPROACH 1: Country-Year Propensity Matching ===")
matched_sb_list = []
matched_mb_list = []
np.random.seed(42)

for (country, year), group in df.groupby(['facility_country', 'year']):
    g_sb = group[group['single_bidder'] == True]
    g_mb = group[group['single_bidder'] == False]
    n_match = min(len(g_sb), len(g_mb))
    if n_match > 0:
        matched_sb_list.append(g_sb.sample(n=n_match, random_state=42))
        matched_mb_list.append(g_mb.sample(n=n_match, random_state=42))

if matched_sb_list:
    m_sb = pd.concat(matched_sb_list)
    m_mb = pd.concat(matched_mb_list)
    print(f"Matched pairs: SB={len(m_sb)}, MB={len(m_mb)}")

    sb_co2 = m_sb['facility_co2'].mean()
    mb_co2 = m_mb['facility_co2'].mean()
    premium_matched = (sb_co2 - mb_co2) / mb_co2 * 100
    t_matched, p_matched = stats.ttest_ind(m_sb['facility_co2'], m_mb['facility_co2'])
    
    print(f"SB mean CO2: {sb_co2:,.0f} kg")
    print(f"MB mean CO2: {mb_co2:,.0f} kg")
    print(f"Premium: {premium_matched:+.1f}%")
    print(f"t={t_matched:.3f}, p={p_matched:.4f}")
else:
    print("No country-year matches possible")
    premium_matched = None
    t_matched = None
    p_matched = None

# APPROACH 2: Unmatched full sample (for comparison)
print("\n=== APPROACH 2: Unmatched Full Sample ===")
all_sb_co2 = sb['facility_co2'].mean()
all_mb_co2 = mb['facility_co2'].mean()
all_prem = (all_sb_co2 - all_mb_co2) / all_mb_co2 * 100
t_all, p_all = stats.ttest_ind(sb['facility_co2'], mb['facility_co2'])
print(f"SB: {len(sb)}, MB: {len(mb)}")
print(f"SB mean: {all_sb_co2:,.0f}, MB mean: {all_mb_co2:,.0f}")
print(f"Premium: {all_prem:+.1f}%, t={t_all:.3f}, p={p_all:.4f}")

# APPROACH 3: Welch t-test (handles unequal variance + size)
print("\n=== APPROACH 3: Welch t-test (unequal variance) ===")
t_welch, p_welch = stats.ttest_ind(sb['facility_co2'], mb['facility_co2'], equal_var=False)
print(f"Welch t={t_welch:.3f}, p={p_welch:.4f}")

# APPROACH 4: Bootstrap confidence interval
print("\n=== APPROACH 4: Bootstrap CI ===")
n_boot = 10000
boot_premiums = []
for _ in range(n_boot):
    sb_boot = sb['facility_co2'].sample(n=len(sb), replace=True)
    mb_boot = mb['facility_co2'].sample(n=len(mb), replace=True)
    boot_prem = (sb_boot.mean() - mb_boot.mean()) / mb_boot.mean() * 100
    boot_premiums.append(boot_prem)

boot_premiums = np.array(boot_premiums)
ci_low = np.percentile(boot_premiums, 2.5)
ci_high = np.percentile(boot_premiums, 97.5)
print(f"Bootstrap premium: {np.mean(boot_premiums):+.1f}% (95% CI: {ci_low:+.1f}% to {ci_high:+.1f}%)")

# APPROACH 5: Mann-Whitney U (non-parametric)
print("\n=== APPROACH 5: Mann-Whitney U (non-parametric) ===")
u_stat, p_mw = stats.mannwhitneyu(sb['facility_co2'], mb['facility_co2'], alternative='greater')
print(f"U={u_stat:.0f}, p={p_mw:.4f}")

# Save results
results = {
    "n_refineries_eprtr": int(len(refineries)),
    "n_matched_contracts": int(len(df)),
    "n_sb": int(len(sb)),
    "n_mb": int(len(mb)),
    "unmatched": {
        "sb_mean_co2": float(all_sb_co2),
        "mb_mean_co2": float(all_mb_co2),
        "premium_pct": float(all_prem),
        "t_stat": float(t_all),
        "p_value": float(p_all),
        "welch_t": float(t_welch),
        "welch_p": float(p_welch)
    },
    "country_year_matched": {
        "n_sb": int(len(m_sb)) if matched_sb_list else 0,
        "n_mb": int(len(m_mb)) if matched_sb_list else 0,
        "premium_pct": float(premium_matched) if premium_matched else None,
        "t_stat": float(t_matched) if t_matched else None,
        "p_value": float(p_matched) if p_matched else None
    },
    "bootstrap": {
        "mean_premium": float(np.mean(boot_premiums)),
        "ci_low_95": float(ci_low),
        "ci_high_95": float(ci_high)
    },
    "mann_whitney": {
        "U": float(u_stat),
        "p_value": float(p_mw)
    }
}

with open('results/validation/refinery_propensity_match.json', 'w') as f:
    json.dump(results, f, indent=2)
print("\nResults saved to results/refinery_propensity_match.json")
