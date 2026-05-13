"""
FINAL DEFINITIVE TEST
====================

Load data EXACTLY as run_causal_analysis.py does, then manually
replicate the local linear RDD to see if we get +0.003734 or -0.000397.

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

from run_causal_analysis import load_analysis_data
import numpy as np
from statsmodels.regression.linear_model import WLS

print("=" * 70)
print("FINAL DEFINITIVE TEST - Exact Replication")
print("=" * 70)

# Load EXACTLY as the script does
df = load_analysis_data()
print(f"\n1. Loaded: {len(df):,} rows")

# Filter to 2012-2023
df = df[(df['year'] >= 2012) & (df['year'] <= 2023)]
print(f"2. Filtered to 2012-2023: {len(df):,} rows")

# Drop NAs (same as run_rdd_analysis does)
df = df.dropna(subset=['carbon_intensity_kg_usd', 'value_eur'])
print(f"3. Dropped NAs: {len(df):,} rows")

# Extract arrays
Y = df['carbon_intensity_kg_usd'].values
X = df['value_eur'].values

# Log transform
X_log = np.log10(X + 1)

# Cutoff
threshold = 139000
c_log = np.log10(threshold)

# Bandwidth from JSON
h = 0.06877020488792862

print(f"\n4. Threshold: €{threshold:,} (log: {c_log:.6f})")
print(f"5. Bandwidth: {h:.6f}")

# Select observations in bandwidth
mask = (X_log >= c_log - h) & (X_log <= c_log + h)
X_local = X_log[mask]
Y_local = Y[mask]

print(f"\n6. Observations in bandwidth: {len(X_local):,}")
print(f"   Below cutoff: {(X_local < c_log).sum():,}")
print(f"   Above cutoff: {(X_local >= c_log).sum():,}")

# Check if this matches JSON
if len(X_local) == 74959:
    print("   ✅ Matches JSON (74,959)")
else:
    print(f"   ❌ Does NOT match JSON (expected 74,959, got {len(X_local):,})")

# Manual local linear regression (EXACT replication)
print(f"\n7. Running local linear regression...")

# Triangular kernel weights
u = (X_local - c_log) / h
weights = (1 - np.abs(u)) * (np.abs(u) <= 1)

# Treatment indicator
T = (X_local >= c_log).astype(float)

# Design matrix
X_centered = X_local - c_log
design = np.column_stack([
    np.ones(len(X_local)),  # Intercept
    X_centered,              # Slope below
    T,                       # Treatment effect ← THIS IS WHAT WE CARE ABOUT
    X_centered * T           # Differential slope
])

# Fit WLS
model = WLS(Y_local, design, weights=weights).fit()

print(f"\n8. Regression results:")
print(f"   Intercept: {model.params[0]:.6f}")
print(f"   Slope below: {model.params[1]:.6f}")
print(f"   TREATMENT EFFECT: {model.params[2]:.6f}")
print(f"   Differential slope: {model.params[3]:.6f}")

print(f"\n9. Standard error: {model.bse[2]:.6f}")
print(f"10. P-value: {model.pvalues[2]:.6f}")

ci = model.conf_int(alpha=0.05)[2]
print(f"11. 95% CI: [{ci[0]:.6f}, {ci[1]:.6f}]")

# Compare to JSON
print(f"\n{'=' * 70}")
print("COMPARISON TO SAVED JSON")
print("=" * 70)

json_estimate = 0.0037344914810606227
json_se = 0.001800531290114446
json_p = 0.03807293865126511

print(f"\nManual calculation:")
print(f"  Estimate: {model.params[2]:.16f}")
print(f"  SE: {model.bse[2]:.16f}")
print(f"  P-value: {model.pvalues[2]:.16f}")

print(f"\nSaved JSON:")
print(f"  Estimate: {json_estimate:.16f}")
print(f"  SE: {json_se:.16f}")
print(f"  P-value: {json_p:.16f}")

print(f"\nDifferences:")
print(f"  Estimate diff: {model.params[2] - json_estimate:.16e}")
print(f"  SE diff: {model.bse[2] - json_se:.16e}")
print(f"  P-value diff: {model.pvalues[2] - json_p:.16e}")

if abs(model.params[2] - json_estimate) < 1e-10:
    print(f"\n✅ EXACT MATCH - Manual calculation reproduces JSON!")
elif abs(model.params[2] + json_estimate) < 1e-10:
    print(f"\n❌ OPPOSITE SIGNS - There's a sign flip somewhere!")
elif abs(model.params[2] - json_estimate) < 0.001:
    print(f"\n⚠️  CLOSE BUT NOT EXACT - Small numerical differences")
else:
    print(f"\n❌ DIFFERENT RESULTS - Something is wrong")

print(f"\n{'=' * 70}")
print("CONCLUSION")
print("=" * 70)

if abs(model.params[2] - json_estimate) < 1e-10:
    print("""
The manual calculation EXACTLY matches the saved JSON.

This means:
- The run_causal_analysis.py code is working correctly
- The +0.003734 result is what the data actually shows
- My earlier -0.000397 was from using the wrong data/window

However, the simple difference-in-means shows -0.43%.

This discrepancy means the LOCAL LINEAR REGRESSION (with weights and
trend controls) produces a DIFFERENT result than simple means.

This is POSSIBLE and indicates:
- Strong local trends near the cutoff
- Weighting matters (triangular kernel vs equal weight)
- The RDD is controlling for confounding trends

Whether +0.003734 or -0.000883 (simple diff) is more credible depends
on whether we trust the RDD assumptions (local linearity, weighting).
""")
else:
    print("""
The manual calculation does NOT match the JSON.

This suggests a BUG in either:
- The data loading process
- The RDD implementation
- The JSON saving process
- My replication attempt

Further investigation needed.
""")
