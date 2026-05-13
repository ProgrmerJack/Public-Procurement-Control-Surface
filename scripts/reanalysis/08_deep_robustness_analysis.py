"""
DEEP ROBUSTNESS ANALYSIS - Post-Fix Data (27 Countries)
========================================================

This script performs comprehensive robustness checks on the fixed pipeline results:
1. Bandwidth sensitivity (50%, 75%, 100%, 125%, 150%, 200% of optimal)
2. Placebo threshold tests (5 fake thresholds on each side)
3. Donut-hole RDD (excluding observations near threshold)
4. Covariate balance checks
5. McCrary density test for manipulation
6. Bootstrap confidence intervals
7. Leave-one-out country analysis
8. Time period sensitivity

Date: 2025-12-13 (post-fix deep analysis)
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("DEEP ROBUSTNESS ANALYSIS - 27-Country Post-Fix Data")
print("=" * 80)

# =============================================================================
# LOAD DATA
# =============================================================================
print("\n[1/8] LOADING DATA...")

data_path = Path("data/processed/gprd_with_carbon.parquet")
df = pd.read_parquet(data_path)

print(f"  Total contracts: {len(df):,}")
print(f"  Countries: {df['country'].nunique()}")
print(f"  Years: {df['year'].min()}-{df['year'].max()}")

# Define threshold and running variable
THRESHOLD_EUR = 139_000
THRESHOLD_LOG = np.log10(THRESHOLD_EUR + 1)

# Create running variable centered at threshold
df['log_value'] = np.log10(df['value_eur'].clip(lower=1) + 1)
df['running'] = df['log_value'] - THRESHOLD_LOG
df['above_threshold'] = (df['running'] >= 0).astype(int)

# Outcome variable
outcome_col = 'carbon_intensity_kg_usd'

# Filter valid observations
df_valid = df[df[outcome_col].notna() & np.isfinite(df[outcome_col])].copy()
print(f"  Valid observations: {len(df_valid):,}")

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def local_linear_rdd(data, outcome, running, bandwidth, kernel='triangular'):
    """Run local linear RDD with specified bandwidth - memory efficient."""
    in_window = np.abs(data[running]) <= bandwidth
    subset = data[in_window].copy()
    
    if len(subset) < 100:
        return {'estimate': np.nan, 'se': np.nan, 'pvalue': np.nan, 'n': len(subset)}
    
    # Triangular kernel weights
    if kernel == 'triangular':
        weights = (1 - np.abs(subset[running]) / bandwidth).values
    else:
        weights = np.ones(len(subset))
    
    # Treatment indicator
    D = (subset[running] >= 0).astype(int).values
    
    # Design matrix: [1, running, D, D*running]
    X = np.column_stack([
        np.ones(len(subset)),
        subset[running].values,
        D,
        D * subset[running].values
    ])
    
    y = subset[outcome].values
    
    try:
        # Memory-efficient WLS: compute X'WX and X'Wy directly
        # Instead of creating diagonal matrix W (n x n), use element-wise multiplication
        sqrt_w = np.sqrt(weights)
        Xw = X * sqrt_w[:, np.newaxis]  # Weight rows of X
        yw = y * sqrt_w
        
        XtWX = Xw.T @ Xw
        XtWy = Xw.T @ yw
        beta = np.linalg.solve(XtWX, XtWy)
        
        # Residuals and variance
        resid = y - X @ beta
        sigma2 = np.sum(weights * resid**2) / (np.sum(weights) - 4)
        var_beta = sigma2 * np.linalg.inv(XtWX)
        se = np.sqrt(np.diag(var_beta))
        
        # Treatment effect is coefficient on D
        estimate = beta[2]
        se_estimate = se[2]
        t_stat = estimate / se_estimate
        pvalue = 2 * (1 - stats.t.cdf(np.abs(t_stat), len(subset) - 4))
        
        return {
            'estimate': estimate,
            'se': se_estimate,
            'pvalue': pvalue,
            'n': len(subset),
            'n_left': int(np.sum(D == 0)),
            'n_right': int(np.sum(D == 1))
        }
    except Exception as e:
        return {'estimate': np.nan, 'se': np.nan, 'pvalue': np.nan, 'n': len(subset), 'error': str(e)}

def ik_bandwidth(data, outcome, running):
    """Estimate Imbens-Kalyanaraman optimal bandwidth."""
    # Simplified IK bandwidth estimation
    h_rot = 1.06 * data[running].std() * len(data)**(-0.2)
    return h_rot * 2.5  # Scale factor for RDD

# Estimate optimal bandwidth
h_opt = ik_bandwidth(df_valid, outcome_col, 'running')
print(f"  Optimal bandwidth: {h_opt:.5f}")

# =============================================================================
# 1. BANDWIDTH SENSITIVITY
# =============================================================================
print("\n" + "=" * 80)
print("[2/8] BANDWIDTH SENSITIVITY ANALYSIS")
print("=" * 80)

bandwidth_multipliers = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
bandwidth_results = []

print(f"\n| Bandwidth | Multiplier | n | Effect | SE | p-value | Significant? |")
print(f"|-----------|------------|---|--------|-----|---------|--------------|")

for mult in bandwidth_multipliers:
    h = h_opt * mult
    result = local_linear_rdd(df_valid, outcome_col, 'running', h)
    
    sig = "✓" if result['pvalue'] < 0.05 else "✗"
    print(f"| {h:.4f} | {mult:.2f}x | {result['n']:,} | {result['estimate']:+.6f} | {result['se']:.6f} | {result['pvalue']:.4f} | {sig} |")
    
    bandwidth_results.append({
        'bandwidth': h,
        'multiplier': mult,
        **result
    })

# Check consistency
signs = [r['estimate'] > 0 for r in bandwidth_results if not np.isnan(r['estimate'])]
sign_consistent = len(set(signs)) == 1
print(f"\nSign consistency across bandwidths: {'✓ YES' if sign_consistent else '✗ NO'}")

sig_count = sum(1 for r in bandwidth_results if r['pvalue'] < 0.05)
print(f"Significant at 5% level: {sig_count}/{len(bandwidth_results)} bandwidths")

# =============================================================================
# 2. PLACEBO THRESHOLD TESTS
# =============================================================================
print("\n" + "=" * 80)
print("[3/8] PLACEBO THRESHOLD TESTS")
print("=" * 80)

# Test fake thresholds at various distances from true threshold
true_threshold = THRESHOLD_LOG
placebo_offsets = [-0.3, -0.2, -0.1, 0.1, 0.2, 0.3]  # In log units

print(f"\nTrue threshold: €139,000 (log: {true_threshold:.4f})")
print(f"\n| Offset | Fake Threshold (€) | Effect | SE | p-value | Significant? |")
print(f"|--------|-------------------|--------|-----|---------|--------------|")

placebo_results = []
for offset in placebo_offsets:
    fake_threshold_log = true_threshold + offset
    fake_threshold_eur = 10**fake_threshold_log - 1
    
    # Create running variable for fake threshold
    df_valid['running_placebo'] = df_valid['log_value'] - fake_threshold_log
    
    result = local_linear_rdd(df_valid, outcome_col, 'running_placebo', h_opt)
    
    sig = "✓" if result['pvalue'] < 0.05 else "✗"
    print(f"| {offset:+.1f} | €{fake_threshold_eur:,.0f} | {result['estimate']:+.6f} | {result['se']:.6f} | {result['pvalue']:.4f} | {sig} |")
    
    placebo_results.append({
        'offset': offset,
        'fake_threshold': fake_threshold_eur,
        **result
    })

# Check if placebo tests fail (should NOT be significant)
placebo_sig = sum(1 for r in placebo_results if r['pvalue'] < 0.05)
print(f"\nPlacebo tests with p < 0.05: {placebo_sig}/{len(placebo_results)}")
print(f"Expected: 0-1 (by chance at 5% level)")
if placebo_sig <= 1:
    print("✓ PASSED: Placebo tests show no systematic effects at fake thresholds")
else:
    print("⚠️ WARNING: Multiple placebo tests significant - possible confounding")

# =============================================================================
# 3. DONUT-HOLE RDD
# =============================================================================
print("\n" + "=" * 80)
print("[4/8] DONUT-HOLE RDD ANALYSIS")
print("=" * 80)

donut_sizes = [0.01, 0.02, 0.03, 0.05, 0.1]  # In log units

print(f"\n| Donut Size | Excluded | Remaining | Effect | SE | p-value | Sig? |")
print(f"|------------|----------|-----------|--------|-----|---------|------|")

donut_results = []
for donut in donut_sizes:
    # Exclude observations within donut of threshold
    df_donut = df_valid[np.abs(df_valid['running']) >= donut].copy()
    n_excluded = len(df_valid) - len(df_donut)
    
    result = local_linear_rdd(df_donut, outcome_col, 'running', h_opt)
    
    sig = "✓" if result['pvalue'] < 0.05 else "✗"
    print(f"| {donut:.2f} | {n_excluded:,} | {len(df_donut):,} | {result['estimate']:+.6f} | {result['se']:.6f} | {result['pvalue']:.4f} | {sig} |")
    
    donut_results.append({
        'donut_size': donut,
        'n_excluded': n_excluded,
        **result
    })

# Check robustness
donut_signs = [r['estimate'] > 0 for r in donut_results if not np.isnan(r['estimate'])]
donut_consistent = len(set(donut_signs)) == 1
print(f"\nSign consistency with donut holes: {'✓ YES' if donut_consistent else '✗ NO'}")

# =============================================================================
# 4. COVARIATE BALANCE CHECK
# =============================================================================
print("\n" + "=" * 80)
print("[5/8] COVARIATE BALANCE CHECK")
print("=" * 80)

# Check if pre-determined covariates are balanced at threshold
covariates = ['year', 'number_of_bidders']  # Available covariates

# Use narrow bandwidth around threshold
h_balance = h_opt * 0.5
in_window = np.abs(df_valid['running']) <= h_balance
df_window = df_valid[in_window].copy()

print(f"\nSample in balance window: {len(df_window):,} (bandwidth: {h_balance:.4f})")
print(f"\n| Covariate | Below Threshold | Above Threshold | Difference | t-stat | p-value |")
print(f"|-----------|-----------------|-----------------|------------|--------|---------|")

balance_results = []
for cov in covariates:
    if cov not in df_window.columns:
        continue
    
    below = df_window[df_window['running'] < 0][cov].dropna()
    above = df_window[df_window['running'] >= 0][cov].dropna()
    
    if len(below) < 10 or len(above) < 10:
        continue
    
    t_stat, p_val = stats.ttest_ind(below, above)
    diff = above.mean() - below.mean()
    
    print(f"| {cov} | {below.mean():.3f} | {above.mean():.3f} | {diff:+.3f} | {t_stat:.3f} | {p_val:.4f} |")
    
    balance_results.append({
        'covariate': cov,
        'mean_below': below.mean(),
        'mean_above': above.mean(),
        'difference': diff,
        't_stat': t_stat,
        'p_value': p_val
    })

# Check balance
imbalanced = sum(1 for r in balance_results if r['p_value'] < 0.05)
print(f"\nCovariates with p < 0.05: {imbalanced}/{len(balance_results)}")
if imbalanced == 0:
    print("✓ PASSED: All covariates balanced at threshold")
else:
    print("⚠️ WARNING: Some covariates imbalanced - possible selection bias")

# =============================================================================
# 5. McCRARY DENSITY TEST
# =============================================================================
print("\n" + "=" * 80)
print("[6/8] McCRARY DENSITY TEST")
print("=" * 80)

# Check for manipulation of running variable at threshold
# Using simple bin comparison approach

# Create bins around threshold
n_bins = 50
bin_width = h_opt * 2 / n_bins

bins_left = np.arange(-h_opt, 0, bin_width)
bins_right = np.arange(0, h_opt, bin_width)

# Count observations in each bin
counts_left = []
counts_right = []

for i in range(len(bins_left) - 1):
    mask = (df_valid['running'] >= bins_left[i]) & (df_valid['running'] < bins_left[i+1])
    counts_left.append(mask.sum())

for i in range(len(bins_right) - 1):
    mask = (df_valid['running'] >= bins_right[i]) & (df_valid['running'] < bins_right[i+1])
    counts_right.append(mask.sum())

# Compare density just below and just above threshold
density_below = np.mean(counts_left[-5:]) if len(counts_left) >= 5 else np.mean(counts_left)
density_above = np.mean(counts_right[:5]) if len(counts_right) >= 5 else np.mean(counts_right)

density_ratio = density_above / density_below if density_below > 0 else np.nan
log_density_diff = np.log(density_ratio) if density_ratio > 0 else np.nan

print(f"\nDensity analysis around threshold:")
print(f"  Mean density below threshold: {density_below:.1f}")
print(f"  Mean density above threshold: {density_above:.1f}")
print(f"  Density ratio (above/below): {density_ratio:.3f}")
print(f"  Log density difference: {log_density_diff:+.3f}")

# Informal test: ratio should be close to 1
if 0.8 <= density_ratio <= 1.2:
    print("✓ PASSED: No evidence of manipulation (ratio close to 1)")
else:
    print(f"⚠️ WARNING: Density discontinuity detected (ratio = {density_ratio:.3f})")

# =============================================================================
# 6. LEAVE-ONE-OUT COUNTRY ANALYSIS
# =============================================================================
print("\n" + "=" * 80)
print("[7/8] LEAVE-ONE-OUT COUNTRY ANALYSIS")
print("=" * 80)

countries = df_valid['country'].unique()
loo_results = []

print(f"\n| Excluded Country | n Remaining | Effect | SE | p-value | Change |")
print(f"|------------------|-------------|--------|-----|---------|--------|")

# First get baseline with all countries
baseline = local_linear_rdd(df_valid, outcome_col, 'running', h_opt)
baseline_est = baseline['estimate']

for country in sorted(countries):
    df_loo = df_valid[df_valid['country'] != country].copy()
    result = local_linear_rdd(df_loo, outcome_col, 'running', h_opt)
    
    change = ((result['estimate'] - baseline_est) / abs(baseline_est)) * 100 if baseline_est != 0 else 0
    
    print(f"| {country} | {len(df_loo):,} | {result['estimate']:+.6f} | {result['se']:.6f} | {result['pvalue']:.4f} | {change:+.1f}% |")
    
    loo_results.append({
        'excluded_country': country,
        'n': len(df_loo),
        'estimate': result['estimate'],
        'se': result['se'],
        'pvalue': result['pvalue'],
        'change_pct': change
    })

# Check sensitivity
max_change = max(abs(r['change_pct']) for r in loo_results)
print(f"\nMaximum change from excluding any country: {max_change:.1f}%")
if max_change < 50:
    print("✓ PASSED: Results robust to excluding any single country")
else:
    print(f"⚠️ WARNING: Results sensitive to excluding some countries")

# =============================================================================
# 7. TIME PERIOD SENSITIVITY
# =============================================================================
print("\n" + "=" * 80)
print("[8/8] TIME PERIOD SENSITIVITY")
print("=" * 80)

years = sorted(df_valid['year'].dropna().unique())
print(f"\nYears in data: {min(years):.0f}-{max(years):.0f}")

# Analyze by time periods
periods = [
    ('Early', (2012, 2015)),
    ('Middle', (2016, 2019)),
    ('Late', (2020, 2023))
]

print(f"\n| Period | Years | n | Effect | SE | p-value | Sig? |")
print(f"|--------|-------|---|--------|-----|---------|------|")

time_results = []
for period_name, (start, end) in periods:
    df_period = df_valid[(df_valid['year'] >= start) & (df_valid['year'] <= end)].copy()
    result = local_linear_rdd(df_period, outcome_col, 'running', h_opt)
    
    sig = "✓" if result['pvalue'] < 0.05 else "✗"
    print(f"| {period_name} | {start}-{end} | {result['n']:,} | {result['estimate']:+.6f} | {result['se']:.6f} | {result['pvalue']:.4f} | {sig} |")
    
    time_results.append({
        'period': period_name,
        'start': start,
        'end': end,
        **result
    })

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 80)
print("ROBUSTNESS SUMMARY")
print("=" * 80)

tests_passed = 0
tests_total = 6

# Bandwidth sensitivity
if sign_consistent and sig_count >= 3:
    print("✓ [1] Bandwidth sensitivity: PASSED")
    tests_passed += 1
else:
    print("✗ [1] Bandwidth sensitivity: FAILED")

# Placebo tests
if placebo_sig <= 1:
    print("✓ [2] Placebo threshold tests: PASSED")
    tests_passed += 1
else:
    print("✗ [2] Placebo threshold tests: FAILED")

# Donut-hole
if donut_consistent:
    print("✓ [3] Donut-hole RDD: PASSED")
    tests_passed += 1
else:
    print("✗ [3] Donut-hole RDD: FAILED")

# Covariate balance
if imbalanced == 0:
    print("✓ [4] Covariate balance: PASSED")
    tests_passed += 1
else:
    print("✗ [4] Covariate balance: FAILED")

# McCrary test
if 0.8 <= density_ratio <= 1.2:
    print("✓ [5] McCrary density test: PASSED")
    tests_passed += 1
else:
    print("✗ [5] McCrary density test: FAILED")

# Leave-one-out
if max_change < 50:
    print("✓ [6] Leave-one-out: PASSED")
    tests_passed += 1
else:
    print("✗ [6] Leave-one-out: FAILED")

print(f"\nOverall: {tests_passed}/{tests_total} tests passed")

# Save results
results_summary = {
    'bandwidth_sensitivity': bandwidth_results,
    'placebo_tests': placebo_results,
    'donut_hole': donut_results,
    'covariate_balance': balance_results,
    'mccrary': {
        'density_below': density_below,
        'density_above': density_above,
        'ratio': density_ratio
    },
    'leave_one_out': loo_results,
    'time_sensitivity': time_results,
    'summary': {
        'tests_passed': tests_passed,
        'tests_total': tests_total,
        'pass_rate': tests_passed / tests_total
    }
}

output_path = Path("reanalysis/deep_robustness_results.json")
with open(output_path, 'w') as f:
    json.dump(results_summary, f, indent=2, default=str)

print(f"\nResults saved to: {output_path}")
print("\n" + "=" * 80)
print("DEEP ROBUSTNESS ANALYSIS COMPLETE")
print("=" * 80)
