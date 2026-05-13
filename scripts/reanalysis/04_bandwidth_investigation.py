"""
Bandwidth Investigation - Why Different Sample Sizes?
=====================================================

The run_rdd_analysis() uses 74,959 obs, but my manual calc uses 948,631 obs.
Both claim to use bandwidth h=0.06877.

This script investigates why.

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

from run_causal_analysis import load_analysis_data, optimal_bandwidth_ik
import numpy as np
import pandas as pd

print("=" * 70)
print("BANDWIDTH INVESTIGATION")
print("=" * 70)

# Load full dataset
df = load_analysis_data()
df = df[(df['year'] >= 2012) & (df['year'] <= 2023)]
df = df.dropna(subset=['carbon_intensity_kg_usd', 'value_eur'])

print(f"\nFull dataset: {len(df):,} observations")

# Transform to log
Y = df['carbon_intensity_kg_usd'].values
X_eur = df['value_eur'].values
X_log = np.log10(X_eur + 1)

threshold = 139000
c_log = np.log10(threshold)

print(f"Threshold: €{threshold:,}")
print(f"Threshold (log10): {c_log:.6f}")

# Calculate bandwidth on FULL dataset
print("\n1. Calculating optimal bandwidth on FULL dataset...")
h_full = optimal_bandwidth_ik(Y, X_log, c_log)
print(f"   Bandwidth: {h_full:.6f}")

# Select window with this bandwidth
mask_full = (X_log >= c_log - h_full) & (X_log <= c_log + h_full)
n_in_window_full = mask_full.sum()
print(f"   Observations in window: {n_in_window_full:,}")

# Now try calculating bandwidth on a SUBSET near threshold
# (Maybe the function pre-filters?)
print("\n2. Trying different subsets...")

subsets = {
    '±0.5 log units': 0.5,
    '±1.0 log units': 1.0,
    '±0.3 log units': 0.3,
    '±0.2 log units': 0.2,
}

for name, window_size in subsets.items():
    mask_subset = (X_log >= c_log - window_size) & (X_log <= c_log + window_size)
    Y_subset = Y[mask_subset]
    X_subset = X_log[mask_subset]
    
    if len(X_subset) > 100:
        h_subset = optimal_bandwidth_ik(Y_subset, X_subset, c_log)
        
        # Count obs in THIS bandwidth
        mask_h = (X_subset >= c_log - h_subset) & (X_subset <= c_log + h_subset)
        n_h = mask_h.sum()
        
        print(f"\n   Subset {name}:")
        print(f"     Input: {len(X_subset):,} obs")
        print(f"     Bandwidth: {h_subset:.6f}")
        print(f"     In bandwidth: {n_h:,} obs")
        
        if abs(n_h - 74959) < 100:
            print(f"     ✅ MATCHES function output (74,959)")

# Check from saved results
print("\n3. From saved JSON:")
print(f"   Bandwidth: 0.06877020488792862")
print(f"   n_obs: 74,959")
print(f"   n_left: 40,095")
print(f"   n_right: 34,864")

# Try exact bandwidth from JSON
h_json = 0.06877020488792862
mask_json = (X_log >= c_log - h_json) & (X_log <= c_log + h_json)
print(f"\n4. Using exact JSON bandwidth on FULL dataset:")
print(f"   Observations in window: {mask_json.sum():,}")

#I think the issue is that optimal_bandwidth_ik is being called on a pre-filtered subset

# Let's check if there's any filtering I'm missing
print("\n5. Checking for additional filters...")

# Maybe it's filtering by country?
print(f"\n   Countries in dataset: {df['country'].nunique()}")
print(f"   Country counts (top 10):")
print(df['country'].value_counts().head(10))

# Maybe only EU countries for threshold analysis?
eu_countries = ['AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',  
                'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
                'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK']

df_eu = df[df['country'].isin(eu_countries)]
print(f"\n   EU countries only: {len(df_eu):,} obs")

if len(df_eu) > 0:
    Y_eu = df_eu['carbon_intensity_kg_usd'].values
    X_eu = np.log10(df_eu['value_eur'].values + 1)
    h_eu = optimal_bandwidth_ik(Y_eu, X_eu, c_log)
    mask_eu = (X_eu >= c_log - h_eu) & (X_eu <= c_log + h_eu)
    
    print(f"   Bandwidth on EU only: {h_eu:.6f}")
    print(f"   In bandwidth: {mask_eu.sum():,}")
    
    if abs(mask_eu.sum() - 74959) < 100:
        print(f"   ✅ MATCHES function output!")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
print("""
Need to determine:
1. What subset of data is run_rdd_analysis actually using?
2. Why does it have only 74,959 obs vs my 948,631?
3. Is there a pre-filter step I'm missing?
""")
