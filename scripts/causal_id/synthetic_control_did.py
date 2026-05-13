"""
Synthetic Control Method for DiD Robustness — Addresses thin-comparator concern.
Creates a synthetic EU counterfactual from donor pool (NO, CH, UK pre-2020, CO).
Also runs permutation/placebo tests for inference.
"""
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy import stats
import json

# Load contract-level data
print("Loading data...")
df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet',
                     columns=['country', 'year', 'single_bidder', 'carbon_intensity_kg_usd'])
df = df.rename(columns={'year': 'award_year'})
df['award_year'] = df['award_year'].astype(int)
df = df[df['award_year'].between(2012, 2023)].copy()
print(f"Loaded {len(df):,} contracts, {df['country'].nunique()} countries")

# Country classifications
EU_COUNTRIES = {'AT','BE','BG','CY','CZ','DE','DK','EE','ES','FI','FR','GR',
                'HR','HU','IE','IT','LT','LU','LV','MT','NL','PL','PT','RO',
                'SE','SI','SK'}
DONOR_POOL = {'NO', 'CH', 'GB'}  # UK pre-2020 only
# Colombia excluded from donors (too different: 0.7% SB rate, hydro economy)

# Build country-year panel
panel = df.groupby(['country', 'award_year']).agg(
    sb_rate=('single_bidder', 'mean'),
    n=('single_bidder', 'count')
).reset_index()

# Compute EU aggregate (weighted by contract count)
eu_panel = panel[panel['country'].isin(EU_COUNTRIES)].copy()
eu_agg = eu_panel.groupby('award_year').apply(
    lambda g: pd.Series({
        'sb_rate': np.average(g['sb_rate'], weights=g['n']),
        'n': g['n'].sum()
    })
).reset_index()
eu_agg['country'] = 'EU_AGG'

# Get individual donor country panels
donor_panels = {}
for c in DONOR_POOL:
    cp = panel[panel['country'] == c].copy()
    if c == 'GB':
        cp = cp[cp['award_year'] <= 2019]  # UK pre-Brexit only
    if len(cp) > 0:
        donor_panels[c] = cp
        print(f"  Donor {c}: {len(cp)} years, SB range {cp['sb_rate'].min():.3f}-{cp['sb_rate'].max():.3f}")

# Pre-treatment: 2012-2015; Treatment: 2016+
PRE_YEARS = [2012, 2013, 2014, 2015]
POST_YEARS = [2017, 2018, 2019, 2020, 2021, 2022, 2023]  # 2016 excluded as transition

# Build matrices for synthetic control
eu_pre = eu_agg[eu_agg['award_year'].isin(PRE_YEARS)].set_index('award_year')['sb_rate']
eu_post = eu_agg[eu_agg['award_year'].isin(POST_YEARS)].set_index('award_year')['sb_rate']

# Donor pre-treatment matrix
donor_pre = {}
donor_post = {}
valid_donors = []
for c, cp in donor_panels.items():
    pre = cp[cp['award_year'].isin(PRE_YEARS)].set_index('award_year')['sb_rate']
    post = cp[cp['award_year'].isin(POST_YEARS)].set_index('award_year')['sb_rate']
    if len(pre) >= 3:  # Need at least 3 pre-treatment years
        donor_pre[c] = pre
        donor_post[c] = post
        valid_donors.append(c)

print(f"\nValid donors: {valid_donors}")
print(f"EU pre-treatment SB rates: {eu_pre.to_dict()}")
for c in valid_donors:
    print(f"  {c} pre-treatment: {donor_pre[c].to_dict()}")

# ==========================================
# Synthetic Control: Find weights
# ==========================================
# Minimize pre-treatment RMSE between EU and weighted donor combination
# Allow intercept shift (demeaned SC) to handle level differences

def sc_objective(params, eu_vals, donor_matrix, use_intercept=True):
    """Objective: minimize pre-treatment gap between EU and synthetic control."""
    n_donors = donor_matrix.shape[1]
    if use_intercept:
        weights = params[:n_donors]
        intercept = params[n_donors]
    else:
        weights = params
        intercept = 0
    
    synthetic = donor_matrix @ weights + intercept
    return np.sum((eu_vals - synthetic) ** 2)

# Align years
common_pre_years = sorted(set(eu_pre.index))
donor_matrix_pre = np.column_stack([
    donor_pre[c].reindex(common_pre_years).values for c in valid_donors
])
eu_vals_pre = eu_pre.reindex(common_pre_years).values

# Method 1: Standard SC (convex weights, no intercept)
n_donors = len(valid_donors)
# Constraints: weights sum to 1, each weight >= 0
constraints_std = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
bounds_std = [(0, 1)] * n_donors
x0_std = np.ones(n_donors) / n_donors

res_std = minimize(sc_objective, x0_std, args=(eu_vals_pre, donor_matrix_pre, False),
                   bounds=bounds_std, constraints=constraints_std, method='SLSQP')

print(f"\n=== STANDARD SYNTHETIC CONTROL ===")
print(f"Weights: {dict(zip(valid_donors, res_std.x))}")
print(f"Pre-treatment RMSE: {np.sqrt(res_std.fun / len(common_pre_years)):.4f}")

# Method 2: Demeaned SC (allows intercept to handle level gap)
bounds_dm = [(0, 1)] * n_donors + [(-0.5, 0.5)]  # weights + intercept
constraints_dm = [{'type': 'eq', 'fun': lambda p: np.sum(p[:n_donors]) - 1}]
x0_dm = list(np.ones(n_donors) / n_donors) + [0.1]

res_dm = minimize(sc_objective, x0_dm, args=(eu_vals_pre, donor_matrix_pre, True),
                  bounds=bounds_dm, constraints=constraints_dm, method='SLSQP')

dm_weights = res_dm.x[:n_donors]
dm_intercept = res_dm.x[n_donors]
print(f"\n=== DEMEANED SYNTHETIC CONTROL ===")
print(f"Weights: {dict(zip(valid_donors, dm_weights))}")
print(f"Intercept (level shift): {dm_intercept:.4f}")
print(f"Pre-treatment RMSE: {np.sqrt(res_dm.fun / len(common_pre_years)):.4f}")

# ==========================================
# Compute post-treatment gaps
# ==========================================
common_post_years = sorted(set(eu_post.index))

# For post-treatment, only use donors that have data
for method_name, weights, intercept in [
    ("Standard SC", res_std.x, 0),
    ("Demeaned SC", dm_weights, dm_intercept)
]:
    print(f"\n--- {method_name}: Post-treatment gaps ---")
    gaps = {}
    for year in common_post_years:
        eu_val = eu_post.get(year, np.nan)
        donor_vals = []
        for i, c in enumerate(valid_donors):
            val = donor_post[c].get(year, np.nan)
            if np.isnan(val):
                val = donor_post[c].iloc[-1] if len(donor_post[c]) > 0 else np.nan
            donor_vals.append(val)
        
        if not any(np.isnan(donor_vals)):
            synthetic_val = np.dot(weights, donor_vals) + intercept
            gap = eu_val - synthetic_val
            gaps[year] = {'eu': eu_val, 'synthetic': synthetic_val, 'gap': gap}
            print(f"  {year}: EU={eu_val:.4f}, Synthetic={synthetic_val:.4f}, Gap={gap:+.4f} ({gap*100:+.1f} pp)")
    
    if gaps:
        avg_gap = np.mean([g['gap'] for g in gaps.values()])
        print(f"  Average post-treatment gap: {avg_gap:+.4f} ({avg_gap*100:+.1f} pp)")

# ==========================================
# Permutation test (placebo inference)
# ==========================================
print("\n=== PERMUTATION/PLACEBO TEST ===")
# For each donor country, pretend IT is the treated unit
# and the remaining donors + EU are the controls
# The true EU gap should be larger than all placebos

all_countries_panel = {}
for c in valid_donors:
    cp = panel[panel['country'] == c]
    if c == 'GB':
        cp = cp[cp['award_year'] <= 2019]
    all_countries_panel[c] = cp.set_index('award_year')['sb_rate']

# Add EU aggregate
all_countries_panel['EU_AGG'] = eu_agg.set_index('award_year')['sb_rate']

# True EU effect: pre-post change in gap vs donors
eu_pre_mean = eu_pre.mean()
eu_post_mean = eu_post.mean()
donor_pre_means = {c: donor_pre[c].mean() for c in valid_donors}

# Simple DiD-style: (EU_post - EU_pre) - avg(donor_post - donor_pre)
donor_changes = []
for c in valid_donors:
    post_vals = donor_post[c]
    if len(post_vals) > 0:
        change = post_vals.mean() - donor_pre[c].mean()
        donor_changes.append(change)
        print(f"  {c}: pre={donor_pre[c].mean():.4f}, post={post_vals.mean():.4f}, change={change:+.4f}")

eu_change = eu_post_mean - eu_pre_mean
avg_donor_change = np.mean(donor_changes)
true_did = eu_change - avg_donor_change
print(f"\n  EU: pre={eu_pre_mean:.4f}, post={eu_post_mean:.4f}, change={eu_change:+.4f}")
print(f"  Avg donor change: {avg_donor_change:+.4f}")
print(f"  TRUE DiD effect: {true_did:+.4f} ({true_did*100:+.1f} pp)")

# Placebo: for each individual EU country, compute its "effect"
print("\n=== WITHIN-EU PLACEBO DISTRIBUTION ===")
eu_country_effects = {}
for c in EU_COUNTRIES:
    cp = panel[panel['country'] == c]
    pre = cp[cp['award_year'].isin(PRE_YEARS)]['sb_rate']
    post = cp[cp['award_year'].isin(POST_YEARS)]['sb_rate']
    if len(pre) >= 2 and len(post) >= 2:
        effect = (post.mean() - pre.mean())
        eu_country_effects[c] = effect

# How many EU countries show negative effects (reduction in SB)?
negative = sum(1 for v in eu_country_effects.values() if v < 0)
total = len(eu_country_effects)
print(f"  EU countries with negative change (SB decreased): {negative}/{total}")
print(f"  Mean EU country effect: {np.mean(list(eu_country_effects.values()))*100:+.1f} pp")
print(f"  Median EU country effect: {np.median(list(eu_country_effects.values()))*100:+.1f} pp")

# Sort by effect
sorted_effects = sorted(eu_country_effects.items(), key=lambda x: x[1])
print(f"  Largest decreases: {[(c, f'{v*100:+.1f}pp') for c, v in sorted_effects[:5]]}")
print(f"  Largest increases: {[(c, f'{v*100:+.1f}pp') for c, v in sorted_effects[-5:]]}")

# Save results
results = {
    'synthetic_control': {
        'standard': {
            'weights': dict(zip(valid_donors, [round(w, 4) for w in res_std.x])),
            'pre_rmse': round(np.sqrt(res_std.fun / len(common_pre_years)), 4)
        },
        'demeaned': {
            'weights': dict(zip(valid_donors, [round(w, 4) for w in dm_weights])),
            'intercept': round(dm_intercept, 4),
            'pre_rmse': round(np.sqrt(res_dm.fun / len(common_pre_years)), 4)
        }
    },
    'true_did_effect_pp': round(true_did * 100, 2),
    'eu_countries_with_decrease': negative,
    'eu_countries_total': total,
    'mean_eu_country_effect_pp': round(np.mean(list(eu_country_effects.values())) * 100, 2),
    'country_effects': {c: round(v * 100, 2) for c, v in eu_country_effects.items()}
}

with open('results/causal_id/synthetic_control_did.json', 'w') as f:
    json.dump(results, f, indent=2)
print("\nSaved results/synthetic_control_did.json")
