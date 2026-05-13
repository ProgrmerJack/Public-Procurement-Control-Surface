"""Staggered DiD analysis exploiting within-EU transposition variation."""
import pandas as pd
import numpy as np
from scipy import stats
from scipy.linalg import lstsq
import json

df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet', columns=['country', 'year', 'single_bidder'])
df = df[(df['year'] >= 2012) & (df['year'] <= 2023)]

cy = df.groupby(['country', 'year']).agg(
    sb_rate=('single_bidder', 'mean'),
    n=('single_bidder', 'count')
).reset_index()

eu_countries = ['AT','BE','CZ','DE','DK','EE','ES','FI','FR','GB','GR',
                'HU','IE','IT','LT','LU','LV','NL','PL','PT','SE','SI','SK']

# Transposition cohorts (EUR-Lex + EC infringement proceedings)
cohort_map = {
    'GB': 2015,
    'AT': 2016, 'BE': 2016, 'DE': 2016, 'DK': 2016, 'EE': 2016,
    'FI': 2016, 'FR': 2016, 'GR': 2016, 'IE': 2016, 'IT': 2016,
    'LT': 2016, 'LV': 2016, 'PT': 2016, 'SE': 2016,
    'CZ': 2017, 'ES': 2017, 'HU': 2017, 'LU': 2017, 'NL': 2017,
    'PL': 2017, 'SI': 2017, 'SK': 2017,
    'NO': 9999, 'CH': 9999
}

# === DOSE-RESPONSE ===
eu = cy[cy['country'].isin(eu_countries)].copy()
pre = eu[eu['year'].between(2012, 2015)].groupby('country')['sb_rate'].mean().rename('pre_sb')
post = eu[eu['year'].between(2017, 2019)].groupby('country')['sb_rate'].mean().rename('post_sb')

combo = pd.concat([pre, post], axis=1).dropna()
combo['change_pp'] = (combo['post_sb'] - combo['pre_sb']) * 100

r, p = stats.pearsonr(combo['pre_sb'], combo['change_pp'])
rho, p_rho = stats.spearmanr(combo['pre_sb'], combo['change_pp'])

print("=== DOSE-RESPONSE: Pre-SB vs Post-treatment Change ===")
print(f"Pearson r = {r:.3f}, p = {p:.4f}")
print(f"Spearman rho = {rho:.3f}, p = {p_rho:.4f}")

median_pre = combo['pre_sb'].median()
high = combo[combo['pre_sb'] > median_pre]
low = combo[combo['pre_sb'] <= median_pre]

high_mean = high['change_pp'].mean()
low_mean = low['change_pp'].mean()
print(f"\nMedian pre-SB: {median_pre:.3f}")
print(f"High-baseline ({len(high)}): mean change = {high_mean:.2f} pp")
print(f"Low-baseline ({len(low)}): mean change = {low_mean:.2f} pp")
t_stat, t_p = stats.ttest_ind(high['change_pp'], low['change_pp'])
print(f"T-test: t={t_stat:.3f}, p={t_p:.4f}")

slope, intercept, r_value, p_value, std_err = stats.linregress(combo['pre_sb'], combo['change_pp'])
print(f"\nOLS: change_pp = {intercept:.2f} + {slope:.2f} * pre_sb")
print(f"  slope={slope:.2f}, SE={std_err:.2f}, p={p_value:.4f}, R2={r_value**2:.3f}")

print(f"\n=== COUNTRY DETAIL ===")
for c in combo.sort_values('pre_sb', ascending=False).index:
    pre_val = combo.loc[c, "pre_sb"] * 100
    post_val = combo.loc[c, "post_sb"] * 100
    chg = combo.loc[c, "change_pp"]
    print(f"  {c}: pre={pre_val:.1f}%, post={post_val:.1f}%, change={chg:+.1f}pp")

# === TWFE STAGGERED DiD ===
panel = cy[cy['country'].isin(eu_countries + ['NO', 'CH'])]
panel = panel[panel['year'].between(2012, 2019)].copy()
panel['cohort'] = panel['country'].map(cohort_map)
panel['treated'] = panel.apply(lambda r: 1 if r['year'] >= r['cohort'] else 0, axis=1)

countries_list = sorted(panel['country'].unique())
years_list = sorted(panel['year'].unique())

X_cols = ['treated']
for c in countries_list[1:]:
    panel[f'fe_{c}'] = (panel['country'] == c).astype(float)
    X_cols.append(f'fe_{c}')
for y in years_list[1:]:
    panel[f'yt_{y}'] = (panel['year'] == y).astype(float)
    X_cols.append(f'yt_{y}')

X = panel[X_cols].values
X = np.column_stack([np.ones(len(X)), X])
y_vec = panel['sb_rate'].values

beta, residuals, rank, sv = lstsq(X, y_vec)
y_hat = X @ beta
resid = y_vec - y_hat
n = len(y_vec)
k = X.shape[1]
mse = np.sum(resid**2) / (n - k)
XtX_inv = np.linalg.inv(X.T @ X)
se = np.sqrt(mse * np.diag(XtX_inv))

att_coef = beta[1]
att_se = se[1]
att_t = att_coef / att_se
att_p = 2 * (1 - stats.t.cdf(abs(att_t), n - k))
r2 = 1 - np.sum(resid**2) / np.sum((y_vec - y_vec.mean())**2)

print(f"\n=== TWFE STAGGERED DiD (EU + NO/CH, 2012-2019) ===")
print(f"ATT = {att_coef:.4f} ({att_coef*100:.2f} pp)")
print(f"SE = {att_se:.4f}, t = {att_t:.3f}, p = {att_p:.4f}")
print(f"95% CI: [{(att_coef-1.96*att_se)*100:.2f}, {(att_coef+1.96*att_se)*100:.2f}] pp")
print(f"N = {n}, countries = {len(countries_list)}, years = {len(years_list)}, R2 = {r2:.4f}")

# === EVENT STUDY with leads/lags ===
panel['event_time'] = panel['year'] - panel['cohort']
panel.loc[panel['cohort'] == 9999, 'event_time'] = -99  # never-treated

# Create event-time dummies (omit t=-1)
event_cols = []
for et in range(-4, 5):
    if et == -1:
        continue
    col = f'et_{et}'
    panel[col] = ((panel['event_time'] == et) & (panel['cohort'] < 9999)).astype(float)
    event_cols.append(col)

X2_cols = event_cols[:]
for c in countries_list[1:]:
    X2_cols.append(f'fe_{c}')
for y in years_list[1:]:
    X2_cols.append(f'yt_{y}')

X2 = panel[X2_cols].values
X2 = np.column_stack([np.ones(len(X2)), X2])
y2 = panel['sb_rate'].values

beta2, _, _, _ = lstsq(X2, y2)
resid2 = y2 - X2 @ beta2
mse2 = np.sum(resid2**2) / (len(y2) - X2.shape[1])
se2 = np.sqrt(mse2 * np.diag(np.linalg.inv(X2.T @ X2)))

print(f"\n=== EVENT STUDY (omit t=-1) ===")
event_results = {}
idx = 1  # skip intercept
for et in range(-4, 5):
    if et == -1:
        print(f"  t={et:+d}: REFERENCE (omitted)")
        event_results[str(et)] = {'coef': 0, 'se': 0, 'p': 1}
        continue
    coef = beta2[idx]
    se_val = se2[idx]
    t_val = coef / se_val if se_val > 0 else 0
    p_val = 2 * (1 - stats.t.cdf(abs(t_val), len(y2) - X2.shape[1]))
    sig = "*" if p_val < 0.05 else ""
    print(f"  t={et:+d}: {coef*100:+.2f} pp (SE={se_val*100:.2f}, p={p_val:.3f}) {sig}")
    event_results[str(et)] = {'coef': round(coef*100, 2), 'se': round(se_val*100, 2), 'p': round(p_val, 4)}
    idx += 1

# Pre-trend F-test
pre_coefs = [beta2[i+1] for i, et in enumerate(range(-4, 5)) if et < -1]
pre_ses = [se2[i+1] for i, et in enumerate(range(-4, 5)) if et < -1]
pre_t_stats = [c/s if s > 0 else 0 for c, s in zip(pre_coefs, pre_ses)]
pre_f = np.mean([t**2 for t in pre_t_stats])
pre_f_p = 1 - stats.f.cdf(pre_f, len(pre_coefs), len(y2) - X2.shape[1])
print(f"\nPre-trend F-test: F={pre_f:.3f}, p={pre_f_p:.4f}")
print(f"Pre-trends {'PASS' if pre_f_p > 0.05 else 'FAIL'} (null: all pre-treatment coefficients = 0)")

results = {
    'dose_response': {
        'pearson_r': round(r, 3), 'pearson_p': round(p, 4),
        'spearman_rho': round(rho, 3), 'spearman_p': round(p_rho, 4),
        'slope': round(slope, 2), 'slope_se': round(std_err, 2),
        'slope_p': round(p_value, 4), 'R2': round(r_value**2, 3),
        'high_mean_change_pp': round(high_mean, 2),
        'low_mean_change_pp': round(low_mean, 2),
    },
    'twfe_staggered': {
        'att_pp': round(att_coef*100, 2),
        'att_se_pp': round(att_se*100, 2),
        'att_t': round(att_t, 3),
        'att_p': round(att_p, 4),
        'ci_lower_pp': round((att_coef-1.96*att_se)*100, 2),
        'ci_upper_pp': round((att_coef+1.96*att_se)*100, 2),
        'n_obs': n,
        'n_countries': len(countries_list),
        'r2': round(r2, 4),
    },
    'event_study': event_results,
    'pre_trend_test': {
        'f_stat': round(pre_f, 3),
        'p_value': round(pre_f_p, 4),
        'pass': pre_f_p > 0.05
    }
}

with open('results/causal_id/staggered_did.json', 'w') as f:
    json.dump(results, f, indent=2)
print("\nSaved to results/staggered_did.json")
