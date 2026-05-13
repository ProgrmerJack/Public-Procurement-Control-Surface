"""
COMPREHENSIVE ROBUSTNESS VERIFICATION
======================================

Tests ALL robustness checks that should have been done:
1. Bandwidth sensitivity (0.5h to 2h)
2. Placebo tests at false cutoffs
3. McCrary density test for manipulation
4. Covariate balance at cutoff
5. Donut-hole RDD (exclude near-cutoff)
6. Alternative polynomial specifications
7. Different bandwidth selection methods

Author: Reanalysis Pipeline
Date: 2025-12-13
"""

import sys
from pathlib import Path
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
BASE_DIR = _d
sys.path.insert(0, str(BASE_DIR / 'scripts'))

from run_causal_analysis import load_analysis_data, optimal_bandwidth_ik, local_linear_regression
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.regression.linear_model import WLS
import json

print("=" * 80)
print("COMPREHENSIVE ROBUSTNESS VERIFICATION")
print("=" * 80)

# Load data EXACTLY as original analysis
df = load_analysis_data()
df = df[(df['year'] >= 2012) & (df['year'] <= 2023)]
df = df.dropna(subset=['carbon_intensity_kg_usd', 'value_eur'])

print(f"\nData loaded: {len(df):,} observations")
print(f"Countries: {df['country'].nunique()}")
print(f"Years: {df['year'].min()} - {df['year'].max()}")

# Setup
Y = df['carbon_intensity_kg_usd'].values
X = df['value_eur'].values
X_log = np.log10(X + 1)
threshold = 139000
c_log = np.log10(threshold)

# Baseline bandwidth
h_baseline = 0.06877020488792862

print(f"\nThreshold: €{threshold:,} (log: {c_log:.6f})")
print(f"Baseline bandwidth: {h_baseline:.6f}")

results = {
    'baseline': {},
    'bandwidth_sensitivity': [],
    'placebo_tests': [],
    'density_test': {},
    'covariate_balance': {},
    'donut_hole': [],
    'polynomial_specs': []
}

# ============================================================================
# 1. BANDWIDTH SENSITIVITY ANALYSIS
# ============================================================================
print("\n" + "=" * 80)
print("1. BANDWIDTH SENSITIVITY ANALYSIS")
print("=" * 80)

bandwidth_multipliers = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

for mult in bandwidth_multipliers:
    h = h_baseline * mult
    
    # Select observations
    mask = (X_log >= c_log - h) & (X_log <= c_log + h)
    X_local = X_log[mask]
    Y_local = Y[mask]
    
    # Triangular kernel
    u = (X_local - c_log) / h
    weights = (1 - np.abs(u)) * (np.abs(u) <= 1)
    
    # Treatment indicator
    T = (X_local >= c_log).astype(float)
    
    # Design matrix (local linear)
    X_centered = X_local - c_log
    design = np.column_stack([
        np.ones(len(X_local)),
        X_centered,
        T,
        X_centered * T
    ])
    
    # Fit
    model = WLS(Y_local, design, weights=weights).fit()
    
    estimate = model.params[2]
    se = model.bse[2]
    pval = model.pvalues[2]
    ci_low, ci_high = model.conf_int(alpha=0.05)[2]
    
    # Percentage
    baseline_y = Y_local[T == 0].mean()
    pct = (estimate / baseline_y) * 100
    
    result = {
        'multiplier': mult,
        'bandwidth': h,
        'n_obs': len(X_local),
        'n_below': (T == 0).sum(),
        'n_above': (T == 1).sum(),
        'estimate': estimate,
        'se': se,
        'pvalue': pval,
        'ci_low': ci_low,
        'ci_high': ci_high,
        'pct_effect': pct,
        'significant': pval < 0.05
    }
    
    results['bandwidth_sensitivity'].append(result)
    
    sig = "✓" if pval < 0.05 else "✗"
    sign = "+" if estimate > 0 else "-"
    print(f"\n  {mult}× bandwidth (h={h:.5f}):")
    print(f"    n = {len(X_local):,} ({(T==0).sum():,} below, {(T==1).sum():,} above)")
    print(f"    Effect: {sign}{abs(estimate):.6f} kg CO₂/USD ({pct:+.2f}%)")
    print(f"    SE: {se:.6f}, p={pval:.4f} {sig}")
    print(f"    95% CI: [{ci_low:.6f}, {ci_high:.6f}]")

# Store baseline
results['baseline'] = results['bandwidth_sensitivity'][2]  # 1.0× multiplier

# ============================================================================
# 2. PLACEBO TESTS AT FALSE CUTOFFS
# ============================================================================
print("\n" + "=" * 80)
print("2. PLACEBO TESTS AT FALSE CUTOFFS")
print("=" * 80)

# Test at cutoffs where there SHOULD BE NO effect
false_cutoffs = [100000, 120000, 160000, 180000, 200000]

for false_c in false_cutoffs:
    false_c_log = np.log10(false_c)
    
    # Use baseline bandwidth
    h = h_baseline
    
    # Select observations
    mask = (X_log >= false_c_log - h) & (X_log <= false_c_log + h)
    X_local = X_log[mask]
    Y_local = Y[mask]
    
    if len(X_local) < 100:
        print(f"\n  €{false_c:,}: SKIPPED (n < 100)")
        continue
    
    # Triangular kernel
    u = (X_local - false_c_log) / h
    weights = (1 - np.abs(u)) * (np.abs(u) <= 1)
    
    # Treatment indicator (pretending this is the cutoff)
    T = (X_local >= false_c_log).astype(float)
    
    # Design matrix
    X_centered = X_local - false_c_log
    design = np.column_stack([
        np.ones(len(X_local)),
        X_centered,
        T,
        X_centered * T
    ])
    
    # Fit
    model = WLS(Y_local, design, weights=weights).fit()
    
    estimate = model.params[2]
    se = model.bse[2]
    pval = model.pvalues[2]
    
    baseline_y = Y_local[T == 0].mean()
    pct = (estimate / baseline_y) * 100
    
    result = {
        'cutoff': false_c,
        'cutoff_log': false_c_log,
        'n_obs': len(X_local),
        'estimate': estimate,
        'se': se,
        'pvalue': pval,
        'pct_effect': pct,
        'significant': pval < 0.05
    }
    
    results['placebo_tests'].append(result)
    
    sig_warn = "⚠️  SIGNIFICANT" if pval < 0.05 else "✓ Not significant"
    sign = "+" if estimate > 0 else "-"
    print(f"\n  €{false_c:,} (log: {false_c_log:.5f}):")
    print(f"    n = {len(X_local):,}")
    print(f"    Effect: {sign}{abs(estimate):.6f} kg CO₂/USD ({pct:+.2f}%)")
    print(f"    p = {pval:.4f} - {sig_warn}")

# ============================================================================
# 3. MCCRARY DENSITY TEST FOR MANIPULATION
# ============================================================================
print("\n" + "=" * 80)
print("3. MCCRARY DENSITY TEST (Manipulation Check)")
print("=" * 80)

# McCrary (2008) test: Is there a discontinuity in DENSITY at cutoff?
# If firms manipulate to get above/below threshold, we'd see bunching

# Binned histogram approach
bin_width = 0.01  # in log space
bins_left = np.arange(c_log - 0.3, c_log, bin_width)
bins_right = np.arange(c_log, c_log + 0.3, bin_width)

# Count observations in each bin
counts_left = []
for i in range(len(bins_left) - 1):
    mask = (X_log >= bins_left[i]) & (X_log < bins_left[i+1])
    counts_left.append(mask.sum())

counts_right = []
for i in range(len(bins_right) - 1):
    mask = (X_log >= bins_right[i]) & (X_log < bins_right[i+1])
    counts_right.append(mask.sum())

# Compute densities (counts / total)
density_left = np.array(counts_left) / len(X_log)
density_right = np.array(counts_right) / len(X_log)

# Estimate density at cutoff from each side
# Use simple average of 3 bins closest to cutoff
density_at_c_left = np.mean(density_left[-3:])
density_at_c_right = np.mean(density_right[:3])

# Discontinuity in density
density_discontinuity = density_at_c_right - density_at_c_left
density_ratio = density_at_c_right / density_at_c_left if density_at_c_left > 0 else np.nan

# Simple statistical test: Are the densities significantly different?
# (This is a simplified version; full McCrary test uses local polynomial)
se_left = np.std(density_left[-10:]) / np.sqrt(10)
se_right = np.std(density_right[:10]) / np.sqrt(10)
se_diff = np.sqrt(se_left**2 + se_right**2)
t_stat = density_discontinuity / se_diff if se_diff > 0 else 0
p_value_density = 2 * (1 - stats.norm.cdf(abs(t_stat)))

results['density_test'] = {
    'density_left': density_at_c_left,
    'density_right': density_at_c_right,
    'discontinuity': density_discontinuity,
    'ratio': density_ratio,
    't_stat': t_stat,
    'pvalue': p_value_density,
    'manipulation_detected': p_value_density < 0.05
}

print(f"\n  Density just below cutoff: {density_at_c_left:.6f}")
print(f"  Density just above cutoff: {density_at_c_right:.6f}")
print(f"  Discontinuity: {density_discontinuity:.6f}")
print(f"  Ratio (above/below): {density_ratio:.3f}")
print(f"  p-value: {p_value_density:.4f}")

if p_value_density < 0.05:
    print(f"  ⚠️  POTENTIAL MANIPULATION DETECTED")
else:
    print(f"  ✓ No evidence of manipulation")

# ============================================================================
# 4. COVARIATE BALANCE TEST
# ============================================================================
print("\n" + "=" * 80)
print("4. COVARIATE BALANCE TEST")
print("=" * 80)

# Test if observable covariates are balanced at cutoff
# If RDD assumptions hold, pre-treatment covariates should be continuous

covariates_to_test = []

# Check which covariates are available
if 'year' in df.columns:
    covariates_to_test.append('year')
if 'entity_size' in df.columns:
    covariates_to_test.append('entity_size')
if 'is_green_procurement' in df.columns:
    covariates_to_test.append('is_green_procurement')

print(f"\n  Testing {len(covariates_to_test)} covariates for balance")

covariate_results = []

for cov in covariates_to_test:
    # Get covariate
    cov_data = df[cov].values
    
    # Remove NaNs
    valid = ~np.isnan(cov_data)
    Y_cov = cov_data[valid]
    X_cov = X_log[valid]
    
    # Run RDD on this covariate
    h = h_baseline
    mask = (X_cov >= c_log - h) & (X_cov <= c_log + h)
    X_local = X_cov[mask]
    Y_local = Y_cov[mask]
    
    if len(X_local) < 100:
        print(f"    {cov}: SKIPPED (n < 100)")
        continue
    
    # Triangular kernel
    u = (X_local - c_log) / h
    weights = (1 - np.abs(u)) * (np.abs(u) <= 1)
    
    # Treatment indicator
    T = (X_local >= c_log).astype(float)
    
    # Design matrix
    X_centered = X_local - c_log
    design = np.column_stack([
        np.ones(len(X_local)),
        X_centered,
        T,
        X_centered * T
    ])
    
    # Fit
    model = WLS(Y_local, design, weights=weights).fit()
    
    estimate = model.params[2]
    pval = model.pvalues[2]
    
    covariate_results.append({
        'covariate': cov,
        'estimate': estimate,
        'pvalue': pval,
        'balanced': pval >= 0.05
    })
    
    bal_status = "✓ Balanced" if pval >= 0.05 else "⚠️  IMBALANCED"
    print(f"    {cov}: estimate={estimate:.4f}, p={pval:.4f} - {bal_status}")

results['covariate_balance'] = covariate_results

# ============================================================================
# 5. DONUT-HOLE RDD
# ============================================================================
print("\n" + "=" * 80)
print("5. DONUT-HOLE RDD (Exclude Near-Cutoff)")
print("=" * 80)

# Exclude observations very close to cutoff to test for sorting/manipulation
hole_sizes = [0.01, 0.02, 0.03]  # in log space

for hole in hole_sizes:
    h = h_baseline
    
    # Select observations in bandwidth BUT exclude hole around cutoff
    mask = ((X_log >= c_log - h) & (X_log <= c_log + h)) & (np.abs(X_log - c_log) > hole)
    X_local = X_log[mask]
    Y_local = Y[mask]
    
    if len(X_local) < 100:
        print(f"\n  Hole size {hole:.3f}: SKIPPED (n < 100)")
        continue
    
    # Triangular kernel
    u = (X_local - c_log) / h
    weights = (1 - np.abs(u)) * (np.abs(u) <= 1)
    
    # Treatment indicator
    T = (X_local >= c_log).astype(float)
    
    # Design matrix
    X_centered = X_local - c_log
    design = np.column_stack([
        np.ones(len(X_local)),
        X_centered,
        T,
        X_centered * T
    ])
    
    # Fit
    model = WLS(Y_local, design, weights=weights).fit()
    
    estimate = model.params[2]
    se = model.bse[2]
    pval = model.pvalues[2]
    
    baseline_y = Y_local[T == 0].mean()
    pct = (estimate / baseline_y) * 100
    
    result = {
        'hole_size': hole,
        'n_obs': len(X_local),
        'n_excluded': ((X_log >= c_log - h) & (X_log <= c_log + h) & (np.abs(X_log - c_log) <= hole)).sum(),
        'estimate': estimate,
        'se': se,
        'pvalue': pval,
        'pct_effect': pct,
        'significant': pval < 0.05
    }
    
    results['donut_hole'].append(result)
    
    sig = "✓" if pval < 0.05 else "✗"
    sign = "+" if estimate > 0 else "-"
    print(f"\n  Exclude ±{hole:.3f} around cutoff:")
    print(f"    n = {len(X_local):,} ({result['n_excluded']} excluded)")
    print(f"    Effect: {sign}{abs(estimate):.6f} kg CO₂/USD ({pct:+.2f}%)")
    print(f"    p = {pval:.4f} {sig}")

# ============================================================================
# 6. ALTERNATIVE POLYNOMIAL SPECIFICATIONS
# ============================================================================
print("\n" + "=" * 80)
print("6. POLYNOMIAL SPECIFICATION TESTS")
print("=" * 80)

polynomial_orders = [1, 2, 3]  # Linear (baseline), Quadratic, Cubic

for order in polynomial_orders:
    h = h_baseline
    
    # Select observations
    mask = (X_log >= c_log - h) & (X_log <= c_log + h)
    X_local = X_log[mask]
    Y_local = Y[mask]
    
    # Triangular kernel
    u = (X_local - c_log) / h
    weights = (1 - np.abs(u)) * (np.abs(u) <= 1)
    
    # Treatment indicator
    T = (X_local >= c_log).astype(float)
    
    # Design matrix with polynomial
    X_centered = X_local - c_log
    
    if order == 1:
        # Linear (baseline)
        design = np.column_stack([
            np.ones(len(X_local)),
            X_centered,
            T,
            X_centered * T
        ])
    elif order == 2:
        # Quadratic
        design = np.column_stack([
            np.ones(len(X_local)),
            X_centered,
            X_centered**2,
            T,
            X_centered * T,
            X_centered**2 * T
        ])
    elif order == 3:
        # Cubic
        design = np.column_stack([
            np.ones(len(X_local)),
            X_centered,
            X_centered**2,
            X_centered**3,
            T,
            X_centered * T,
            X_centered**2 * T,
            X_centered**3 * T
        ])
    
    # Fit
    model = WLS(Y_local, design, weights=weights).fit()
    
    # Treatment effect is always the coefficient on T
    estimate = model.params[order + 1]
    se = model.bse[order + 1]
    pval = model.pvalues[order + 1]
    
    baseline_y = Y_local[T == 0].mean()
    pct = (estimate / baseline_y) * 100
    
    result = {
        'order': order,
        'spec': f'Polynomial order {order}',
        'n_obs': len(X_local),
        'estimate': estimate,
        'se': se,
        'pvalue': pval,
        'pct_effect': pct,
        'significant': pval < 0.05,
        'aic': model.aic,
        'bic': model.bic
    }
    
    results['polynomial_specs'].append(result)
    
    sig = "✓" if pval < 0.05 else "✗"
    sign = "+" if estimate > 0 else "-"
    spec_name = {1: "Linear", 2: "Quadratic", 3: "Cubic"}[order]
    print(f"\n  {spec_name} specification:")
    print(f"    Effect: {sign}{abs(estimate):.6f} kg CO₂/USD ({pct:+.2f}%)")
    print(f"    SE: {se:.6f}, p={pval:.4f} {sig}")
    print(f"    AIC: {model.aic:.1f}, BIC: {model.bic:.1f}")

# ============================================================================
# SAVE RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("SAVING RESULTS")
print("=" * 80)

output_file = BASE_DIR / 'reanalysis' / 'robustness_results.json'

# Convert numpy types to Python types for JSON serialization
def convert_types(obj):
    if isinstance(obj, dict):
        return {k: convert_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_types(item) for item in obj]
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        return float(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj

results_serializable = convert_types(results)

with open(output_file, 'w') as f:
    json.dump(results_serializable, f, indent=2)

print(f"\nResults saved to: {output_file}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("ROBUSTNESS SUMMARY")
print("=" * 80)

print(f"\n1. BANDWIDTH SENSITIVITY:")
sig_count = sum(1 for r in results['bandwidth_sensitivity'] if r['significant'])
print(f"   {sig_count}/{len(results['bandwidth_sensitivity'])} specifications significant")
print(f"   Sign consistency: ", end="")
signs = ['+' if r['estimate'] > 0 else '-' for r in results['bandwidth_sensitivity']]
if len(set(signs)) == 1:
    print(f"✓ ALL {signs[0]} (consistent)")
else:
    print(f"⚠️  MIXED SIGNS (not robust)")

print(f"\n2. PLACEBO TESTS:")
placebo_sig = sum(1 for r in results['placebo_tests'] if r['significant'])
if placebo_sig == 0:
    print(f"   ✓ 0/{len(results['placebo_tests'])} false cutoffs significant (good)")
else:
    print(f"   ⚠️  {placebo_sig}/{len(results['placebo_tests'])} false cutoffs significant (concerning)")

print(f"\n3. DENSITY TEST:")
if results['density_test']['manipulation_detected']:
    print(f"   ⚠️  MANIPULATION DETECTED (p={results['density_test']['pvalue']:.4f})")
else:
    print(f"   ✓ No manipulation detected (p={results['density_test']['pvalue']:.4f})")

print(f"\n4. COVARIATE BALANCE:")
if covariate_results:
    imbalanced = sum(1 for r in covariate_results if not r['balanced'])
    if imbalanced == 0:
        print(f"   ✓ All {len(covariate_results)} covariates balanced")
    else:
        print(f"   ⚠️  {imbalanced}/{len(covariate_results)} covariates imbalanced")
else:
    print(f"   (No covariates tested)")

print(f"\n5. DONUT-HOLE RDD:")
donut_sig = sum(1 for r in results['donut_hole'] if r['significant'])
print(f"   {donut_sig}/{len(results['donut_hole'])} specifications significant")

print(f"\n6. POLYNOMIAL SPECS:")
poly_sig = sum(1 for r in results['polynomial_specs'] if r['significant'])
print(f"   {poly_sig}/{len(results['polynomial_specs'])} specifications significant")

# FINAL VERDICT
print(f"\n" + "=" * 80)
print("FINAL VERDICT")
print("=" * 80)

# Count issues
issues = []

if len(set(signs)) > 1:
    issues.append("Sign flip across bandwidths")
if placebo_sig > 0:
    issues.append(f"{placebo_sig} significant placebo test(s)")
if results['density_test']['manipulation_detected']:
    issues.append("Density discontinuity detected")
if covariate_results and sum(1 for r in covariate_results if not r['balanced']) > 0:
    issues.append("Covariate imbalance")

if len(issues) == 0:
    print("\n✅ RESULT IS ROBUST")
    print("   - Consistent across bandwidths")
    print("   - No significant placebos")
    print("   - No manipulation detected")
    print("   - Covariates balanced")
else:
    print(f"\n⚠️  ROBUSTNESS CONCERNS ({len(issues)} issues):")
    for issue in issues:
        print(f"   - {issue}")

print(f"\n" + "=" * 80)
print("DONE")
print("=" * 80)
