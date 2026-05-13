"""
Minimal RDD Test - Reproduce Issue
==================================

Run just the carbon RDD analysis using the exact same code as run_causal_analysis.py
to see if we get -0.000397 or +0.003734.

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

# Import the exact functions from the original script
from run_causal_analysis import (
    load_analysis_data,
    run_rdd_analysis,
    optimal_bandwidth_ik,
    local_linear_regression
)

import numpy as np
import pandas as pd

print("=" * 70)
print("MINIMAL RDD TEST")
print("=" * 70)

# Load data using the same function
print("\nLoading data...")
df = load_analysis_data()
print(f"Loaded: {len(df):,} rows")

# Filter to analysis period
df = df[(df['year'] >= 2012) & (df['year'] <= 2023)]
print(f"Filtered 2012-2023: {len(df):,} rows")

# Run RDD using the exact same function
print("\nRunning RDD analysis...")
result = run_rdd_analysis(df, 'carbon_intensity_kg_usd')

print("\nResults from run_rdd_analysis():")
for key, value in result.items():
    if key != 'country':
        print(f"  {key}: {value}")

print("\n" + "=" * 70)
print("COMPARISON")
print("=" * 70)

print(f"\nFrom run_rdd_analysis function:")
print(f"  Estimate: {result.get('estimate', 'N/A')}")

print(f"\nFrom manual calculation (02_rdd_diagnostic.py):")
print(f"  Estimate: -0.000397")

print(f"\nFrom saved JSON (causal_analysis_results.json):")
print(f"  Estimate: +0.003734")

if abs(result.get('estimate', 0) - (-0.000397)) < 0.0001:
    print(f"\n✅ Function matches manual calculation (-0.000397)")
elif abs(result.get('estimate', 0) - 0.003734) < 0.0001:
    print(f"\n❌ Function matches saved JSON (+0.003734) - but manual calc is different!")
else:
    print(f"\n⚠️  Function gives DIFFERENT result: {result.get('estimate', 'N/A')}")
