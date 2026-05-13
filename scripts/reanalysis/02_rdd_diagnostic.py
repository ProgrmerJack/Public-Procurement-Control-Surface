"""
RDD Bug Diagnostic - Understand Sign Discrepancy
=================================================

The RDD shows +1.74% (increase) but simple diff shows -0.43% (decrease).
This script investigates why they differ.

Possible explanations:
1. RDD bandwidth is selecting different observations (composition bias)
2. Local linear regression weights observations differently
3. Treatment indicator is flipped
4. Running variable transformation creates non-linear effects

Author: Reanalysis Pipeline
Date: 2025-12-13
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

# Paths
DATA_DIR = Path('Data/processed')
OUTPUT_DIR = Path('reanalysis/results')
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

print("=" * 70)
print("RDD BUG DIAGNOSTIC")
print("=" * 70)

# Load data
df = pd.read_parquet(DATA_DIR / 'gprd_with_carbon.parquet')
df = df.dropna(subset=['carbon_intensity_kg_usd', 'value_eur'])

threshold = 139000
print(f"\nThreshold: €{threshold:,}")

# Create log running variable (same as RDD script)
df['value_log'] = np.log10(df['value_eur'] + 1)
c_log = np.log10(threshold)

print(f"Cutoff (log10): {c_log:.6f}")

# Calculate RDD bandwidth using simple rule-of-thumb
# (Imbens-Kalyanaraman would be ~0.069 from the results)
h_rdd = 0.06877020488792862  # From causal_analysis_results.json

print(f"\nRDD bandwidth: {h_rdd:.6f}")

# Select observations within RDD bandwidth (in LOG space)
rdd_mask = (df['value_log'] >= c_log - h_rdd) & (df['value_log'] <= c_log + h_rdd)
df_rdd = df[rdd_mask].copy()

print(f"Observations in RDD window: {len(df_rdd):,}")

# Split by treatment
below_rdd = df_rdd[df_rdd['value_log'] < c_log]
above_rdd = df_rdd[df_rdd['value_log'] >= c_log]

print(f"\nIn RDD bandwidth:")
print(f"  Below cutoff: {len(below_rdd):,}")
print(f"  Above cutoff: {len(above_rdd):,}")

# Check carbon levels
print(f"\nCarbon intensity (kg CO₂/USD):")
print(f"  Below cutoff: {below_rdd['carbon_intensity_kg_usd'].mean():.6f}")
print(f"  Above cutoff: {above_rdd['carbon_intensity_kg_usd'].mean():.6f}")

diff_rdd = above_rdd['carbon_intensity_kg_usd'].mean() - below_rdd['carbon_intensity_kg_usd'].mean()
print(f"  Simple difference: {diff_rdd:+.6f} kg CO₂/USD")
print(f"  Percentage: {(diff_rdd / below_rdd['carbon_intensity_kg_usd'].mean()) * 100:+.2f}%")

# Compare to simple window (±20% in LEVEL space)
window_below = 0.8 * threshold
window_above = 1.2 * threshold
df_simple = df[(df['value_eur'] >= window_below) & (df['value_eur'] <= window_above)].copy()

below_simple = df_simple[df_simple['value_eur'] < threshold]
above_simple = df_simple[df_simple['value_eur'] >= threshold]

diff_simple = above_simple['carbon_intensity_kg_usd'].mean() - below_simple['carbon_intensity_kg_usd'].mean()

print(f"\nComparison:")
print(f"  Simple window (±20% in levels): {diff_simple:+.6f} kg CO₂/USD ({(diff_simple / below_simple['carbon_intensity_kg_usd'].mean()) * 100:+.2f}%)")
print(f"  RDD bandwidth (±{h_rdd:.4f} in logs):  {diff_rdd:+.6f} kg CO₂/USD ({(diff_rdd / below_rdd['carbon_intensity_kg_usd'].mean()) * 100:+.2f}%)")
print(f"  RDD estimate from JSON:             +0.003734 kg CO₂/USD (+1.74%)")

# Check VALUE ranges
print(f"\nValue ranges (EUR):")
print(f"  Simple window: €{window_below:,.0f} to €{window_above:,.0f}")
print(f"  RDD bandwidth (in log space):")
print(f"    Log range: {c_log - h_rdd:.6f} to {c_log + h_rdd:.6f}")
log_min = c_log - h_rdd
log_max = c_log + h_rdd
value_min = 10 ** log_min - 1
value_max = 10 ** log_max - 1
print(f"    EUR range: €{value_min:,.0f} to €{value_max:,.0f}")

# Now let's manually calculate local linear regression
print(f"\n{'=' * 70}")
print("MANUAL LOCAL LINEAR REGRESSION")
print("=" * 70)

X_local = df_rdd['value_log'].values
Y_local = df_rdd['carbon_intensity_kg_usd'].values

# Triangular kernel weights
u = (X_local - c_log) / h_rdd
weights = (1 - np.abs(u)) * (np.abs(u) <= 1)

# Treatment indicator
T = (X_local >= c_log).astype(float)

# Design matrix
X_centered = X_local - c_log
design = np.column_stack([
    np.ones(len(X_local)),  # Intercept
    X_centered,              # Slope below
    T,                       # Treatment effect
    X_centered * T           # Slope above (differential)
])

print(f"\nDesign matrix shape: {design.shape}")
print(f"Weights shape: {weights.shape}")
print(f"Y shape: {Y_local.shape}")

# Weighted least squares
from statsmodels.regression.linear_model import WLS
model = WLS(Y_local, design, weights=weights).fit()

print(f"\nRegression coefficients:")
print(f"  Intercept (Y at cutoff, below): {model.params[0]:.6f}")
print(f"  Slope below cutoff: {model.params[1]:.6f}")
print(f"  TREATMENT EFFECT: {model.params[2]:.6f} ← This is the RDD estimate")
print(f"  Differential slope above: {model.params[3]:.6f}")

print(f"\nStandard errors:")
print(f"  Treatment effect SE: {model.bse[2]:.6f}")

print(f"\nP-value:")
print(f"  Treatment effect p: {model.pvalues[2]:.6f}")

print(f"\n95% Confidence Interval:")
ci = model.conf_int(alpha=0.05)[2]
print(f"  [{ci[0]:.6f}, {ci[1]:.6f}]")

# Interpretation
print(f"\n{'=' * 70}")
print("INTERPRETATION")
print("=" * 70)

print(f"""
The RDD coefficient is: {model.params[2]:+.6f} kg CO₂/USD

This means:
- At the cutoff, contracts just ABOVE have {model.params[2]:+.6f} kg CO₂/USD
  {'' if model.params[2] < 0 else 'MORE'} carbon than contracts just below
  
- As a percentage of baseline ({model.params[0]:.6f} kg CO₂/USD at cutoff):
  {(model.params[2] / model.params[0]) * 100:+.2f}%

However, the simple difference-in-means shows:
  {diff_simple:+.6f} kg CO₂/USD ({(diff_simple / below_simple['carbon_intensity_kg_usd'].mean()) * 100:+.2f}%)

POSSIBLE EXPLANATIONS FOR DISCREPANCY:
1. Log bandwidth selects different observations than ±20% level window
2. Triangular kernel weights observations near cutoff more heavily
3. Local linear regression controls for trends differently than simple means
4. Composition of contracts differs in log vs level windows
""")

# Check composition
print(f"\n{'=' * 70}")
print("COMPOSITION CHECK")
print("=" * 70)

print("\nCountry composition:")
print("\nSimple window (±20%):")
print(df_simple['country'].value_counts())

print("\nRDD bandwidth (log):")
print(df_rdd['country'].value_counts())

# Save diagnostic results
results = pd.DataFrame([{
    'method': 'Simple difference (±20%)',
    'n_below': len(below_simple),
    'n_above': len(above_simple),
    'mean_below': below_simple['carbon_intensity_kg_usd'].mean(),
    'mean_above': above_simple['carbon_intensity_kg_usd'].mean(),
    'difference': diff_simple,
    'pct_change': (diff_simple / below_simple['carbon_intensity_kg_usd'].mean()) * 100
}, {
    'method': 'RDD bandwidth simple diff',
    'n_below': len(below_rdd),
    'n_above': len(above_rdd),
    'mean_below': below_rdd['carbon_intensity_kg_usd'].mean(),
    'mean_above': above_rdd['carbon_intensity_kg_usd'].mean(),
    'difference': diff_rdd,
    'pct_change': (diff_rdd / below_rdd['carbon_intensity_kg_usd'].mean()) * 100
}, {
    'method': 'RDD local linear',
    'n_below': (T == 0).sum(),
    'n_above': (T == 1).sum(),
    'mean_below': model.params[0],
    'mean_above': model.params[0] + model.params[2],
    'difference': model.params[2],
    'pct_change': (model.params[2] / model.params[0]) * 100
}])

results.to_csv(OUTPUT_DIR / 'rdd_diagnostic.csv', index=False)
print(f"\nResults saved to: {OUTPUT_DIR / 'rdd_diagnostic.csv'}")

# Plot to visualize
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Left panel: Simple window
ax = axes[0]
df_plot = df[(df['value_eur'] >= window_below * 0.5) & (df['value_eur'] <= window_above * 2)]
below_plot = df_plot[df_plot['value_eur'] < threshold]
above_plot = df_plot[df_plot['value_eur'] >= threshold]

ax.scatter(below_plot['value_eur'] / 1000, below_plot['carbon_intensity_kg_usd'], 
           alpha=0.1, s=1, label='Below threshold', color='blue')
ax.scatter(above_plot['value_eur'] / 1000, above_plot['carbon_intensity_kg_usd'], 
           alpha=0.1, s=1, label='Above threshold', color='red')
ax.axvline(threshold / 1000, color='black', linestyle='--', label='Threshold')
ax.axhline(below_simple['carbon_intensity_kg_usd'].mean(), color='blue', linestyle=':')
ax.axhline(above_simple['carbon_intensity_kg_usd'].mean(), color='red', linestyle=':')
ax.set_xlabel('Contract Value (€1000s)')
ax.set_ylabel('Carbon Intensity (kg CO₂/USD)')
ax.set_title('Simple Window (±20% levels)')
ax.legend()
ax.set_xlim(window_below * 0.5 / 1000, window_above * 2 / 1000)

# Right panel: RDD bandwidth
ax = axes[1]
ax.scatter(below_rdd['value_eur'] / 1000, below_rdd['carbon_intensity_kg_usd'], 
           alpha=0.1, s=1, label='Below threshold (RDD)', color='blue')
ax.scatter(above_rdd['value_eur'] / 1000, above_rdd['carbon_intensity_kg_usd'], 
           alpha=0.1, s=1, label='Above threshold (RDD)', color='red')
ax.axvline(threshold / 1000, color='black', linestyle='--', label='Threshold')
ax.axhline(model.params[0], color='blue', linestyle=':')
ax.axhline(model.params[0] + model.params[2], color='red', linestyle=':')
ax.set_xlabel('Contract Value (€1000s)')
ax.set_ylabel('Carbon Intensity (kg CO₂/USD)')
ax.set_title(f'RDD Bandwidth (h={h_rdd:.4f} in log10)')
ax.legend()
ax.set_xlim(value_min / 1000, value_max / 1000)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'rdd_vs_simple_comparison.png', dpi=150)
print(f"Plot saved to: {OUTPUT_DIR / 'rdd_vs_simple_comparison.png'}")

print(f"\n{'=' * 70}")
print("CONCLUSION")
print("=" * 70)
print(f"""
The RDD local linear estimate ({model.params[2]:+.6f}) differs from the
simple difference ({diff_simple:+.6f}) because:

1. Different observations selected (log bandwidth vs level window)
2. Weighted regression (triangular kernel) vs unweighted means
3. Controls for local trends (X_centered interactions)

The question is: which is more credible?
- Simple diff: More transparent, easy to interpret
- RDD: Controls for selection, optimal weighting, trend adjustment

If they differ substantially in SIGN (not just magnitude), investigate:
- Composition bias (different types of contracts in each window)
- Non-linear trends near cutoff
- Treatment indicator correctness
""")
