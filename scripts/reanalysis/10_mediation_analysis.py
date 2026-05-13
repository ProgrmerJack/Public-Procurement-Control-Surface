"""
MEDIATION ANALYSIS VERIFICATION
===============================

Manuscript claims that 67% of the carbon reduction is mediated through increased competition.
This script verifies whether competition actually mediates the effect.

The mediation pathway is:
  Transparency → Competition → Carbon Intensity

Manuscript claims:
- Competition (bidders) increases with transparency
- More competition → lower carbon intensity
- 67% of total effect is mediated through competition

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
print("MEDIATION ANALYSIS VERIFICATION")
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
mediator_col = 'n_bidders'  # Fixed column name
h_opt = 0.077

# Filter to RDD window
in_window = np.abs(df['running']) <= h_opt
df_rdd = df[in_window].copy()

print(f"\nSample in RDD window: {len(df_rdd):,}")
print(f"Below threshold: {(df_rdd['above_threshold'] == 0).sum():,}")
print(f"Above threshold: {(df_rdd['above_threshold'] == 1).sum():,}")

# =============================================================================
# 1. STEP 1: TOTAL EFFECT (c path)
# =============================================================================
print("\n" + "=" * 80)
print("[STEP 1] TOTAL EFFECT: Transparency → Carbon Intensity (c path)")
print("=" * 80)

# Check if columns exist
print(f"\nOutcome column '{outcome_col}' exists: {outcome_col in df_rdd.columns}")
print(f"Mediator column '{mediator_col}' exists: {mediator_col in df_rdd.columns}")

if mediator_col not in df_rdd.columns:
    print(f"\n⚠️ WARNING: '{mediator_col}' column not found!")
    print(f"Available columns: {list(df_rdd.columns)[:20]}...")
    
    # Search for similar columns
    bidder_cols = [c for c in df_rdd.columns if 'bid' in c.lower() or 'competitor' in c.lower() or 'offer' in c.lower()]
    print(f"Possible bidder-related columns: {bidder_cols}")

# Calculate kernel weights
weights = 1 - np.abs(df_rdd['running']) / h_opt

# Valid observations
valid_mask = df_rdd[outcome_col].notna() & np.isfinite(df_rdd[outcome_col])
df_valid = df_rdd[valid_mask].copy()
weights_valid = weights[valid_mask]

D = df_valid['above_threshold'].values
y = df_valid[outcome_col].values

# Total effect: regress outcome on treatment
X_total = np.column_stack([
    np.ones(len(df_valid)),
    df_valid['running'].values,
    D,
    D * df_valid['running'].values
])

try:
    sqrt_w = np.sqrt(weights_valid.values)
    Xw = X_total * sqrt_w[:, np.newaxis]
    yw = y * sqrt_w
    
    XtWX = Xw.T @ Xw
    XtWy = Xw.T @ yw
    beta_total = np.linalg.solve(XtWX, XtWy)
    
    resid = y - X_total @ beta_total
    sigma2 = np.sum(weights_valid.values * resid**2) / (np.sum(weights_valid.values) - 4)
    var_beta = sigma2 * np.linalg.inv(XtWX)
    se_total = np.sqrt(np.diag(var_beta))
    
    c_total = beta_total[2]
    se_c = se_total[2]
    t_c = c_total / se_c
    p_c = 2 * (1 - stats.t.cdf(np.abs(t_c), len(df_valid) - 4))
    
    print(f"\nTotal Effect (c):")
    print(f"  Estimate: {c_total:+.6f} kg CO₂/USD")
    print(f"  SE: {se_c:.6f}")
    print(f"  t-stat: {t_c:.3f}")
    print(f"  p-value: {p_c:.4f}")
    
    baseline = 0.31
    pct_total = (c_total / baseline) * 100
    print(f"  As percentage: {pct_total:+.2f}%")
    
except Exception as e:
    print(f"Error in total effect: {e}")
    c_total = np.nan
    pct_total = np.nan

# =============================================================================
# 2. STEP 2: EFFECT ON MEDIATOR (a path)
# =============================================================================
print("\n" + "=" * 80)
print("[STEP 2] EFFECT ON MEDIATOR: Transparency → Competition (a path)")
print("=" * 80)

if mediator_col in df_rdd.columns:
    # Valid observations with mediator
    valid_med = valid_mask & df_rdd[mediator_col].notna() & np.isfinite(df_rdd[mediator_col])
    df_med = df_rdd[valid_med].copy()
    weights_med = weights[valid_med]
    
    D_med = df_med['above_threshold'].values
    m = df_med[mediator_col].values
    
    print(f"\nMediator ({mediator_col}) statistics:")
    print(f"  n: {len(m):,}")
    print(f"  Mean: {np.mean(m):.3f}")
    print(f"  SD: {np.std(m):.3f}")
    print(f"  Below threshold mean: {df_med[df_med['above_threshold']==0][mediator_col].mean():.3f}")
    print(f"  Above threshold mean: {df_med[df_med['above_threshold']==1][mediator_col].mean():.3f}")
    
    # Regress mediator on treatment
    X_a = np.column_stack([
        np.ones(len(df_med)),
        df_med['running'].values,
        D_med,
        D_med * df_med['running'].values
    ])
    
    try:
        sqrt_w_med = np.sqrt(weights_med.values)
        Xw_a = X_a * sqrt_w_med[:, np.newaxis]
        mw = m * sqrt_w_med
        
        XtWX_a = Xw_a.T @ Xw_a
        XtWy_a = Xw_a.T @ mw
        beta_a = np.linalg.solve(XtWX_a, XtWy_a)
        
        resid_a = m - X_a @ beta_a
        sigma2_a = np.sum(weights_med.values * resid_a**2) / (np.sum(weights_med.values) - 4)
        var_beta_a = sigma2_a * np.linalg.inv(XtWX_a)
        se_a = np.sqrt(np.diag(var_beta_a))
        
        a_effect = beta_a[2]
        se_a_effect = se_a[2]
        t_a = a_effect / se_a_effect
        p_a = 2 * (1 - stats.t.cdf(np.abs(t_a), len(df_med) - 4))
        
        print(f"\nEffect on Mediator (a):")
        print(f"  Estimate: {a_effect:+.4f} bidders")
        print(f"  SE: {se_a_effect:.4f}")
        print(f"  t-stat: {t_a:.3f}")
        print(f"  p-value: {p_a:.4f}")
        
        pct_a = (a_effect / df_med[mediator_col].mean()) * 100
        print(f"  As percentage change: {pct_a:+.2f}%")
        
    except Exception as e:
        print(f"Error in a path: {e}")
        a_effect = np.nan
else:
    print(f"\nSkipping - mediator column not found")
    a_effect = np.nan

# =============================================================================
# 3. STEP 3: MEDIATOR → OUTCOME CONTROLLING FOR TREATMENT (b path)
# =============================================================================
print("\n" + "=" * 80)
print("[STEP 3] MEDIATOR → OUTCOME (b path, controlling for treatment)")
print("=" * 80)

if mediator_col in df_rdd.columns:
    # Valid observations with both mediator and outcome
    valid_both = valid_mask & df_rdd[mediator_col].notna() & np.isfinite(df_rdd[mediator_col])
    df_both = df_rdd[valid_both].copy()
    weights_both = weights[valid_both]
    
    D_both = df_both['above_threshold'].values
    y_both = df_both[outcome_col].values
    m_both = df_both[mediator_col].values
    
    # Regress outcome on treatment AND mediator
    X_b = np.column_stack([
        np.ones(len(df_both)),
        df_both['running'].values,
        D_both,
        D_both * df_both['running'].values,
        m_both,  # Add mediator
        m_both * D_both  # Interaction (optional)
    ])
    
    try:
        sqrt_w_both = np.sqrt(weights_both.values)
        Xw_b = X_b * sqrt_w_both[:, np.newaxis]
        yw_b = y_both * sqrt_w_both
        
        XtWX_b = Xw_b.T @ Xw_b
        XtWy_b = Xw_b.T @ yw_b
        beta_b = np.linalg.solve(XtWX_b, XtWy_b)
        
        resid_b = y_both - X_b @ beta_b
        sigma2_b = np.sum(weights_both.values * resid_b**2) / (np.sum(weights_both.values) - 6)
        var_beta_b = sigma2_b * np.linalg.inv(XtWX_b)
        se_b = np.sqrt(np.diag(var_beta_b))
        
        b_effect = beta_b[4]  # Coefficient on mediator
        se_b_effect = se_b[4]
        t_b = b_effect / se_b_effect
        p_b = 2 * (1 - stats.t.cdf(np.abs(t_b), len(df_both) - 6))
        
        c_prime = beta_b[2]  # Direct effect (controlling for mediator)
        se_c_prime = se_b[2]
        
        print(f"\nEffect of Mediator on Outcome (b):")
        print(f"  Estimate: {b_effect:+.6f} kg CO₂/USD per bidder")
        print(f"  SE: {se_b_effect:.6f}")
        print(f"  t-stat: {t_b:.3f}")
        print(f"  p-value: {p_b:.4f}")
        
        print(f"\nDirect Effect (c'):")
        print(f"  Estimate: {c_prime:+.6f} kg CO₂/USD")
        print(f"  SE: {se_c_prime:.6f}")
        
    except Exception as e:
        print(f"Error in b path: {e}")
        b_effect = np.nan
        c_prime = np.nan
else:
    print(f"\nSkipping - mediator column not found")
    b_effect = np.nan
    c_prime = np.nan

# =============================================================================
# 4. CALCULATE MEDIATION
# =============================================================================
print("\n" + "=" * 80)
print("[STEP 4] MEDIATION ANALYSIS")
print("=" * 80)

if not np.isnan(a_effect) and not np.isnan(b_effect) and not np.isnan(c_total):
    # Indirect effect = a * b
    indirect = a_effect * b_effect
    
    # Direct effect = c'
    direct = c_prime
    
    # Total = c
    total = c_total
    
    # Proportion mediated = (a * b) / c
    if abs(total) > 1e-10:
        prop_mediated = (indirect / total) * 100
    else:
        prop_mediated = np.nan
    
    print(f"\nMediation Decomposition:")
    print(f"  Total Effect (c): {total:+.6f}")
    print(f"  Direct Effect (c'): {direct:+.6f}")
    print(f"  Indirect Effect (a×b): {indirect:+.6f}")
    print(f"  Sum (c' + a×b): {direct + indirect:+.6f}")
    
    print(f"\nProportion Mediated:")
    print(f"  Actual: {prop_mediated:.1f}%")
    print(f"  Manuscript claims: 67%")
    
    deviation = abs(prop_mediated - 67) / 67 * 100
    print(f"  Deviation: {deviation:.1f}%")
    
    # Sobel test for significance of indirect effect
    se_indirect = np.sqrt(a_effect**2 * se_b_effect**2 + b_effect**2 * se_a_effect**2)
    z_sobel = indirect / se_indirect
    p_sobel = 2 * (1 - stats.norm.cdf(np.abs(z_sobel)))
    
    print(f"\nSobel Test for Indirect Effect:")
    print(f"  z-stat: {z_sobel:.3f}")
    print(f"  p-value: {p_sobel:.4f}")
    print(f"  Significant: {'YES' if p_sobel < 0.05 else 'NO'}")
    
else:
    print("\nCannot compute mediation - missing components")
    prop_mediated = np.nan
    indirect = np.nan

# =============================================================================
# 5. COMPARE TO MANUSCRIPT CLAIMS
# =============================================================================
print("\n" + "=" * 80)
print("[STEP 5] COMPARISON TO MANUSCRIPT CLAIMS")
print("=" * 80)

print(f"\nMANUSCRIPT CLAIMS:")
print(f"  1. Transparency increases competition")
print(f"  2. More competition reduces carbon intensity")
print(f"  3. 67% of effect mediated through competition")

print(f"\nACTUAL FINDINGS:")
if not np.isnan(a_effect):
    direction_a = "increases" if a_effect > 0 else "decreases"
    sig_a = "significant" if p_a < 0.05 else "NOT significant"
    print(f"  1. Transparency {direction_a} competition by {abs(a_effect):.2f} bidders ({sig_a})")
else:
    print(f"  1. Cannot assess - mediator data unavailable")

if not np.isnan(b_effect):
    direction_b = "more bidders → lower carbon" if b_effect < 0 else "more bidders → HIGHER carbon"
    sig_b = "significant" if p_b < 0.05 else "NOT significant"
    print(f"  2. {direction_b} ({sig_b})")
else:
    print(f"  2. Cannot assess - mediator data unavailable")

if not np.isnan(prop_mediated):
    print(f"  3. Actual proportion mediated: {prop_mediated:.1f}% (manuscript claims 67%)")
else:
    print(f"  3. Cannot assess mediation")

# =============================================================================
# 6. VERDICT
# =============================================================================
print("\n" + "=" * 80)
print("[VERDICT]")
print("=" * 80)

checks_passed = 0
checks_total = 3

if not np.isnan(a_effect):
    if a_effect > 0 and p_a < 0.05:
        print("✓ Check 1: Transparency increases competition")
        checks_passed += 1
    else:
        print("✗ Check 1: Transparency does NOT significantly increase competition")
else:
    print("? Check 1: Cannot assess")

if not np.isnan(b_effect):
    if b_effect < 0 and p_b < 0.05:
        print("✓ Check 2: More competition reduces carbon intensity")
        checks_passed += 1
    else:
        print("✗ Check 2: Competition does NOT significantly reduce carbon intensity")
else:
    print("? Check 2: Cannot assess")

if not np.isnan(prop_mediated):
    if 50 <= prop_mediated <= 80:
        print(f"✓ Check 3: Proportion mediated ({prop_mediated:.1f}%) close to claimed (67%)")
        checks_passed += 1
    else:
        print(f"✗ Check 3: Proportion mediated ({prop_mediated:.1f}%) far from claimed (67%)")
else:
    print("? Check 3: Cannot assess")

print(f"\nOverall: {checks_passed}/{checks_total} mediation claims validated")

# Save results
mediation_results = {
    'total_effect': {
        'estimate': float(c_total) if not np.isnan(c_total) else None,
        'pct': float(pct_total) if not np.isnan(pct_total) else None
    },
    'a_path': {
        'estimate': float(a_effect) if not np.isnan(a_effect) else None,
        'se': float(se_a_effect) if 'se_a_effect' in dir() else None,
        'pvalue': float(p_a) if 'p_a' in dir() else None
    },
    'b_path': {
        'estimate': float(b_effect) if not np.isnan(b_effect) else None,
        'se': float(se_b_effect) if 'se_b_effect' in dir() else None,
        'pvalue': float(p_b) if 'p_b' in dir() else None
    },
    'indirect_effect': float(indirect) if not np.isnan(indirect) else None,
    'direct_effect': float(c_prime) if not np.isnan(c_prime) else None,
    'proportion_mediated': float(prop_mediated) if not np.isnan(prop_mediated) else None,
    'manuscript_claim': 67,
    'checks_passed': checks_passed
}

output_path = Path("reanalysis/mediation_verification.json")
with open(output_path, 'w') as f:
    json.dump(mediation_results, f, indent=2)

print(f"\nResults saved to: {output_path}")
print("\n" + "=" * 80)
