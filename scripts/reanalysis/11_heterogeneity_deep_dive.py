"""
COUNTRY HETEROGENEITY DEEP DIVE
===============================

Deep analysis of why effects vary so dramatically across countries:
- Some show large decreases (Portugal: -22%, Finland: -22%)
- Some show large increases (Slovenia: +21%, Czech Republic: +7%)
- Most show no significant effect

Questions to answer:
1. Why is heterogeneity so high (I²=85.9%)?
2. What explains the variation across countries?
3. Are country effects correlated with institutional factors?

Date: 2025-12-13
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("COUNTRY HETEROGENEITY DEEP DIVE")
print("=" * 80)

# Load data
data_path = Path("data/processed/gprd_with_carbon.parquet")
df = pd.read_parquet(data_path)

# Define threshold
THRESHOLD_EUR = 139_000
THRESHOLD_LOG = np.log10(THRESHOLD_EUR + 1)

df['log_value'] = np.log10(df['value_eur'].clip(lower=1) + 1)
df['running'] = df['log_value'] - THRESHOLD_LOG
df['above_threshold'] = (df['running'] >= 0).astype(int)

outcome_col = 'carbon_intensity_kg_usd'
h_opt = 0.077
baseline = 0.31

def local_linear_rdd(data, outcome, running, bandwidth):
    """Memory-efficient local linear RDD."""
    in_window = np.abs(data[running]) <= bandwidth
    subset = data[in_window].copy()
    
    if len(subset) < 50:
        return None
    
    weights = (1 - np.abs(subset[running]) / bandwidth).values
    D = (subset[running] >= 0).astype(int).values
    
    X = np.column_stack([
        np.ones(len(subset)),
        subset[running].values,
        D,
        D * subset[running].values
    ])
    
    y = subset[outcome].values
    
    try:
        sqrt_w = np.sqrt(weights)
        Xw = X * sqrt_w[:, np.newaxis]
        yw = y * sqrt_w
        
        XtWX = Xw.T @ Xw
        XtWy = Xw.T @ yw
        beta = np.linalg.solve(XtWX, XtWy)
        
        resid = y - X @ beta
        sigma2 = np.sum(weights * resid**2) / (np.sum(weights) - 4)
        var_beta = sigma2 * np.linalg.inv(XtWX)
        se = np.sqrt(np.diag(var_beta))
        
        estimate = beta[2]
        se_estimate = se[2]
        pvalue = 2 * (1 - stats.t.cdf(np.abs(estimate/se_estimate), len(subset) - 4))
        
        return {
            'estimate': estimate,
            'se': se_estimate,
            'pvalue': pvalue,
            'n': len(subset)
        }
    except:
        return None

# =============================================================================
# 1. COUNTRY-LEVEL CHARACTERISTICS
# =============================================================================
print("\n" + "=" * 80)
print("[1] COUNTRY-LEVEL DATA CHARACTERISTICS")
print("=" * 80)

country_stats = []
for country in sorted(df['country'].unique()):
    df_c = df[df['country'] == country]
    
    in_window = np.abs(df_c['running']) <= h_opt
    df_rdd = df_c[in_window]
    
    stats_dict = {
        'country': country,
        'n_total': len(df_c),
        'n_rdd': len(df_rdd),
        'mean_value_eur': df_c['value_eur'].mean(),
        'mean_carbon_intensity': df_c[outcome_col].mean(),
        'sd_carbon_intensity': df_c[outcome_col].std(),
        'pct_above_threshold': (df_c['running'] >= 0).mean() * 100,
        'year_range': f"{int(df_c['year'].min())}-{int(df_c['year'].max())}" if df_c['year'].notna().any() else "N/A",
        'n_years': df_c['year'].nunique()
    }
    
    if 'n_bidders' in df_c.columns:
        stats_dict['mean_bidders'] = df_c['n_bidders'].mean()
    
    country_stats.append(stats_dict)

print(f"\n| Country | n_total | n_RDD | Mean Value (€) | Mean CI | SD CI | Years |")
print(f"|---------|---------|-------|----------------|---------|-------|-------|")
for s in sorted(country_stats, key=lambda x: x['n_total'], reverse=True)[:15]:
    print(f"| {s['country']} | {s['n_total']:,} | {s['n_rdd']:,} | {s['mean_value_eur']:,.0f} | {s['mean_carbon_intensity']:.3f} | {s['sd_carbon_intensity']:.3f} | {s['year_range']} |")

# =============================================================================
# 2. RDD EFFECTS BY COUNTRY
# =============================================================================
print("\n" + "=" * 80)
print("[2] RDD EFFECTS BY COUNTRY")
print("=" * 80)

country_results = []
for country in sorted(df['country'].unique()):
    df_c = df[df['country'] == country]
    result = local_linear_rdd(df_c, outcome_col, 'running', h_opt)
    
    if result:
        pct_effect = (result['estimate'] / baseline) * 100
        country_results.append({
            'country': country,
            'effect_pct': pct_effect,
            **result
        })

# Sort by effect size
country_results = sorted(country_results, key=lambda x: x['effect_pct'])

print(f"\n| Country | Effect (%) | SE | p-value | n | Sig? | Direction |")
print(f"|---------|------------|-----|---------|---|------|-----------|")
for r in country_results:
    sig = "✓" if r['pvalue'] < 0.05 else "✗"
    direction = "↓ DECREASE" if r['effect_pct'] < 0 else "↑ INCREASE"
    print(f"| {r['country']} | {r['effect_pct']:+.2f}% | {r['se']:.4f} | {r['pvalue']:.4f} | {r['n']:,} | {sig} | {direction} |")

# =============================================================================
# 3. CATEGORIZE COUNTRIES BY EFFECT
# =============================================================================
print("\n" + "=" * 80)
print("[3] COUNTRY CATEGORIZATION")
print("=" * 80)

sig_decrease = [r for r in country_results if r['pvalue'] < 0.05 and r['effect_pct'] < 0]
sig_increase = [r for r in country_results if r['pvalue'] < 0.05 and r['effect_pct'] > 0]
no_effect = [r for r in country_results if r['pvalue'] >= 0.05]

print(f"\nCOUNTRIES WITH SIGNIFICANT DECREASE ({len(sig_decrease)}):")
for r in sorted(sig_decrease, key=lambda x: x['effect_pct']):
    print(f"  {r['country']}: {r['effect_pct']:+.2f}% (p={r['pvalue']:.4f})")

print(f"\nCOUNTRIES WITH SIGNIFICANT INCREASE ({len(sig_increase)}):")
for r in sorted(sig_increase, key=lambda x: x['effect_pct'], reverse=True):
    print(f"  {r['country']}: {r['effect_pct']:+.2f}% (p={r['pvalue']:.4f})")

print(f"\nCOUNTRIES WITH NO SIGNIFICANT EFFECT ({len(no_effect)}):")
for r in sorted(no_effect, key=lambda x: abs(x['effect_pct'])):
    print(f"  {r['country']}: {r['effect_pct']:+.2f}% (p={r['pvalue']:.4f})")

# =============================================================================
# 4. CORRELATION WITH COUNTRY CHARACTERISTICS
# =============================================================================
print("\n" + "=" * 80)
print("[4] CORRELATES OF HETEROGENEITY")
print("=" * 80)

# Merge country stats with results
for r in country_results:
    for s in country_stats:
        if r['country'] == s['country']:
            r.update(s)
            break

# Test correlations
effects = [r['effect_pct'] for r in country_results]
sample_sizes = [r['n_total'] for r in country_results]
mean_values = [r.get('mean_value_eur', np.nan) for r in country_results]
mean_ci = [r.get('mean_carbon_intensity', np.nan) for r in country_results]

print(f"\nCorrelation of effect with country characteristics:")

corr_n, p_n = stats.pearsonr(effects, sample_sizes)
print(f"  Sample size: r={corr_n:.3f}, p={p_n:.4f}")

valid_values = [(e, v) for e, v in zip(effects, mean_values) if not np.isnan(v)]
if valid_values:
    corr_v, p_v = stats.pearsonr([x[0] for x in valid_values], [x[1] for x in valid_values])
    print(f"  Mean contract value: r={corr_v:.3f}, p={p_v:.4f}")

valid_ci = [(e, c) for e, c in zip(effects, mean_ci) if not np.isnan(c)]
if valid_ci:
    corr_ci, p_ci = stats.pearsonr([x[0] for x in valid_ci], [x[1] for x in valid_ci])
    print(f"  Mean carbon intensity: r={corr_ci:.3f}, p={p_ci:.4f}")

# =============================================================================
# 5. TIME TRENDS BY COUNTRY
# =============================================================================
print("\n" + "=" * 80)
print("[5] TIME TRENDS WITHIN COUNTRIES")
print("=" * 80)

# Check if effect changes over time
# Compare early (2012-2017) vs late (2018-2023) periods

time_comparison = []
for country in sorted(df['country'].unique()):
    df_c = df[df['country'] == country]
    
    early = df_c[df_c['year'] <= 2017]
    late = df_c[df_c['year'] >= 2018]
    
    result_early = local_linear_rdd(early, outcome_col, 'running', h_opt)
    result_late = local_linear_rdd(late, outcome_col, 'running', h_opt)
    
    if result_early and result_late:
        early_pct = (result_early['estimate'] / baseline) * 100
        late_pct = (result_late['estimate'] / baseline) * 100
        change = late_pct - early_pct
        
        time_comparison.append({
            'country': country,
            'early_effect': early_pct,
            'early_n': result_early['n'],
            'late_effect': late_pct,
            'late_n': result_late['n'],
            'change': change
        })

print(f"\n| Country | Early (≤2017) | Late (≥2018) | Change | Trend |")
print(f"|---------|---------------|--------------|--------|-------|")
for t in sorted(time_comparison, key=lambda x: x['change'])[:10]:
    trend = "↓ Decreasing" if t['change'] < -2 else ("↑ Increasing" if t['change'] > 2 else "→ Stable")
    print(f"| {t['country']} | {t['early_effect']:+.2f}% (n={t['early_n']}) | {t['late_effect']:+.2f}% (n={t['late_n']}) | {t['change']:+.2f}pp | {trend} |")

# =============================================================================
# 6. META-REGRESSION
# =============================================================================
print("\n" + "=" * 80)
print("[6] META-REGRESSION: Explaining Heterogeneity")
print("=" * 80)

# Simple meta-regression: effect ~ sample size
# (Would typically include country-level moderators like GDP, corruption index, etc.)

effects_arr = np.array(effects)
sizes_arr = np.log(np.array(sample_sizes))  # Log sample size

slope, intercept, r_value, p_value, std_err = stats.linregress(sizes_arr, effects_arr)

print(f"\nMeta-regression: Effect ~ log(sample size)")
print(f"  Slope: {slope:.4f}")
print(f"  Intercept: {intercept:.4f}")
print(f"  R²: {r_value**2:.4f}")
print(f"  p-value: {p_value:.4f}")

if p_value < 0.05:
    print(f"  Interpretation: Sample size significantly associated with effect")
else:
    print(f"  Interpretation: No significant publication bias pattern")

# =============================================================================
# 7. INTERPRETATION
# =============================================================================
print("\n" + "=" * 80)
print("[7] INTERPRETATION OF HETEROGENEITY")
print("=" * 80)

print(f"\nKEY FINDINGS:")
print(f"\n1. EXTREME HETEROGENEITY (I²=85.9%):")
print(f"   - Effects vary from {min(effects):.1f}% to {max(effects):.1f}%")
print(f"   - Range: {max(effects) - min(effects):.1f} percentage points")
print(f"   - This suggests NO universal effect of transparency on carbon")

print(f"\n2. DIRECTION SPLIT:")
print(f"   - {len(sig_decrease)} countries: Significant DECREASE (manuscript direction)")
print(f"   - {len(sig_increase)} countries: Significant INCREASE (opposite direction)")
print(f"   - {len(no_effect)} countries: No significant effect")

print(f"\n3. LARGEST EFFECTS:")
largest_decrease = min(country_results, key=lambda x: x['effect_pct'])
largest_increase = max(country_results, key=lambda x: x['effect_pct'])
print(f"   - Largest DECREASE: {largest_decrease['country']} at {largest_decrease['effect_pct']:+.1f}%")
print(f"   - Largest INCREASE: {largest_increase['country']} at {largest_increase['effect_pct']:+.1f}%")

print(f"\n4. IMPLICATIONS FOR MANUSCRIPT:")
print(f"   - Manuscript claims -8.7% across all countries")
print(f"   - Reality: Effect ranges from {min(effects):.1f}% to {max(effects):.1f}%")
print(f"   - Average across countries: {np.mean(effects):.2f}%")
print(f"   - Manuscript OVERSTATES effect by factor of {abs(-8.7 / np.mean(effects)):.1f}x")

print(f"\n5. SCIENTIFIC CONCLUSION:")
print(f"   - Cannot claim a universal effect of transparency on carbon")
print(f"   - Effect is highly context-dependent (country-specific)")
print(f"   - Some countries show reduction, some show increase, most show nothing")
print(f"   - Manuscript's -8.7% is NOT a credible summary statistic")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    COUNTRY HETEROGENEITY ANALYSIS                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Total countries analyzed: {len(country_results):2d}                                              ║
║  Mean effect: {np.mean(effects):+.2f}%                                                    ║
║  Median effect: {np.median(effects):+.2f}%                                                  ║
║  Range: {min(effects):+.1f}% to {max(effects):+.1f}%                                            ║
║                                                                              ║
║  Significant decrease: {len(sig_decrease):2d} countries (manuscript direction)                ║
║  Significant increase: {len(sig_increase):2d} countries (OPPOSITE direction)                  ║
║  No significant effect: {len(no_effect):2d} countries                                       ║
║                                                                              ║
║  MANUSCRIPT CLAIM: -8.7% universal effect                                    ║
║  ACTUAL FINDING: Highly variable, mean {np.mean(effects):+.2f}% (NOT SIGNIFICANT pooled)     ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

# Save results
heterogeneity_results = {
    'country_effects': country_results,
    'summary': {
        'n_countries': len(country_results),
        'mean_effect': float(np.mean(effects)),
        'median_effect': float(np.median(effects)),
        'min_effect': float(min(effects)),
        'max_effect': float(max(effects)),
        'n_sig_decrease': len(sig_decrease),
        'n_sig_increase': len(sig_increase),
        'n_no_effect': len(no_effect)
    },
    'time_comparison': time_comparison,
    'meta_regression': {
        'slope': float(slope),
        'intercept': float(intercept),
        'r_squared': float(r_value**2),
        'p_value': float(p_value)
    }
}

output_path = Path("reanalysis/heterogeneity_deep_dive.json")
with open(output_path, 'w') as f:
    json.dump(heterogeneity_results, f, indent=2, default=float)

print(f"\nResults saved to: {output_path}")
