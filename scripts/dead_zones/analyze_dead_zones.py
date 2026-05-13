import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import json
from pathlib import Path

# Load the data
print("Loading data...")
df = pd.read_parquet("Data/processed/gprd_with_carbon.parquet")
print(f"Total records: {len(df)}")
print(f"Columns: {df.columns.tolist()}")
print(f"Countries: {df['country'].unique()}")

# Filter to EU context (exclude Colombia)
print("\nFiltering to EU context (excluding Colombia)...")
df_eu = df[df['country'] != 'CO'].copy()
print(f"Records after filtering: {len(df_eu)}")

# Extract CPV division (first 2 digits)
print("\nExtracting CPV divisions...")
df_eu['cpv_division'] = df_eu['cpv_code'].astype(str).str[:2]

# Group by CPV division
print("Grouping by CPV division...")
sector_metrics = []

for div in sorted(df_eu['cpv_division'].unique()):
    sector_data = df_eu[df_eu['cpv_division'] == div]
    
    # Compute metrics
    mean_carbon = sector_data['carbon_intensity_kg_usd'].mean()
    sb_rate = sector_data['single_bidder'].sum() / len(sector_data) if len(sector_data) > 0 else 0
    total_value = sector_data['value_eur'].sum()
    sb_value = sector_data[sector_data['single_bidder']]['value_eur'].sum()
    n_tenders = len(sector_data)
    n_sb_tenders = sector_data['single_bidder'].sum()
    
    sector_metrics.append({
        'cpv_division': div,
        'mean_carbon_intensity': mean_carbon,
        'single_bidder_rate': sb_rate,
        'total_value_eur': total_value,
        'sb_locked_value_eur': sb_value,
        'n_tenders': n_tenders,
        'n_sb_tenders': n_sb_tenders
    })

sector_df = pd.DataFrame(sector_metrics)
print(f"\nCPV divisions analyzed: {len(sector_df)}")
print(sector_df.head())

# Calculate baseline percentiles
baseline_carbon_pct = sector_df['mean_carbon_intensity'].quantile(0.67)
baseline_sb_pct = sector_df['single_bidder_rate'].quantile(0.50)

print(f"\nBaseline thresholds:")
print(f"  Carbon intensity (67th pct): {baseline_carbon_pct:.6f} kg CO2e/USD")
print(f"  Single-bidder rate (50th pct): {baseline_sb_pct:.4f}")

# Define threshold variations
carbon_percentiles = [0.50, 0.60, 0.67, 0.75, 0.80]
sb_percentiles = [0.25, 0.333, 0.50, 0.67, 0.75]

carbon_thresholds = {pct: sector_df['mean_carbon_intensity'].quantile(pct) 
                     for pct in carbon_percentiles}
sb_thresholds = {pct: sector_df['single_bidder_rate'].quantile(pct) 
                 for pct in sb_percentiles}

print(f"\nCarbon intensity thresholds (kg CO2e/USD):")
for pct, thresh in carbon_thresholds.items():
    print(f"  {pct*100:.0f}th pct: {thresh:.6f}")

print(f"\nSingle-bidder rate thresholds:")
for pct, thresh in sb_thresholds.items():
    print(f"  {pct*100:.1f}th pct: {thresh:.4f}")

# Sensitivity analysis
print("\n" + "="*80)
print("DEAD ZONE SENSITIVITY ANALYSIS")
print("="*80)

sensitivity_results = []
dead_zone_matrix = {}  # To track which sectors are dead zones across combinations

for carbon_pct, carbon_thresh in carbon_thresholds.items():
    for sb_pct, sb_thresh in sb_thresholds.items():
        # Identify dead zones
        dead_zones = sector_df[
            (sector_df['mean_carbon_intensity'] >= carbon_thresh) &
            (sector_df['single_bidder_rate'] >= sb_thresh)
        ].copy()
        
        n_dz = len(dead_zones)
        total_dz_value = dead_zones['total_value_eur'].sum()
        sb_locked_value = dead_zones['sb_locked_value_eur'].sum()
        
        combo_key = f"C{carbon_pct*100:.0f}_SB{sb_pct*100:.1f}"
        sensitivity_results.append({
            'combination': combo_key,
            'carbon_pct': carbon_pct,
            'carbon_threshold': carbon_thresh,
            'sb_pct': sb_pct,
            'sb_threshold': sb_thresh,
            'n_dead_zones': n_dz,
            'dead_zone_value_eur': total_dz_value,
            'sb_locked_value_eur': sb_locked_value,
            'dead_zone_sectors': dead_zones['cpv_division'].tolist() if n_dz > 0 else []
        })
        
        # Store dead zone sectors for this combination
        if n_dz > 0:
            dead_zone_matrix[combo_key] = set(dead_zones['cpv_division'].tolist())

sensitivity_df = pd.DataFrame(sensitivity_results)

print("\nSensitivity analysis summary (25 combinations):\n")
print(sensitivity_df[['combination', 'n_dead_zones', 'dead_zone_value_eur', 'sb_locked_value_eur']].to_string(index=False))

# Identify robust vs marginal sectors
print("\n" + "="*80)
print("ROBUST VS MARGINAL SECTOR CLASSIFICATION")
print("="*80)

n_combinations = len(sensitivity_results)
sector_robustness = {}

for sector in sector_df['cpv_division'].unique():
    appearances = sum(1 for combo_key in dead_zone_matrix 
                     if sector in dead_zone_matrix.get(combo_key, set()))
    sector_robustness[sector] = {
        'appearances': appearances,
        'robustness_pct': 100 * appearances / n_combinations
    }

# Classify sectors
always_dz = [s for s, v in sector_robustness.items() if v['appearances'] == n_combinations]
never_dz = [s for s, v in sector_robustness.items() if v['appearances'] == 0]
marginal_dz = [s for s, v in sector_robustness.items() 
               if 0 < v['appearances'] < n_combinations]

print(f"\nAlways Dead Zones ({len(always_dz)} sectors):")
if always_dz:
    for sector in sorted(always_dz):
        metrics = sector_df[sector_df['cpv_division'] == sector].iloc[0]
        print(f"  {sector}: Carbon={metrics['mean_carbon_intensity']:.6f}, SB_rate={metrics['single_bidder_rate']:.4f}")
else:
    print("  None - no sector qualifies as dead zone across all threshold combinations")

print(f"\nNever Dead Zones ({len(never_dz)} sectors):")
if len(never_dz) <= 10:
    for sector in sorted(never_dz):
        metrics = sector_df[sector_df['cpv_division'] == sector].iloc[0]
        print(f"  {sector}: Carbon={metrics['mean_carbon_intensity']:.6f}, SB_rate={metrics['single_bidder_rate']:.4f}")
else:
    print(f"  {len(never_dz)} sectors never qualify (carbon and/or SB rate too low)")

print(f"\nMarginal/Sensitive Dead Zones ({len(marginal_dz)} sectors):")
marginal_sorted = sorted(marginal_dz, 
                        key=lambda s: sector_robustness[s]['appearances'], 
                        reverse=True)
for sector in marginal_sorted[:15]:  # Show top 15
    v = sector_robustness[sector]
    metrics = sector_df[sector_df['cpv_division'] == sector].iloc[0]
    print(f"  {sector}: Carbon={metrics['mean_carbon_intensity']:.6f}, SB_rate={metrics['single_bidder_rate']:.4f}, DZ in {v['appearances']}/{n_combinations} combos ({v['robustness_pct']:.1f}%)")

# Composition effect: Spearman correlation between carbon and SB rate
print("\n" + "="*80)
print("COMPOSITION EFFECT: CARBON-SB CORRELATION")
print("="*80)

corr, pval = spearmanr(sector_df['mean_carbon_intensity'], 
                       sector_df['single_bidder_rate'])
print(f"\nSpearman correlation (Carbon Intensity vs Single-Bidder Rate):")
print(f"  rho = {corr:.4f}")
print(f"  p-value = {pval:.6f}")
print(f"  Significance: {'*** (p<0.001)' if pval < 0.001 else '** (p<0.01)' if pval < 0.01 else '* (p<0.05)' if pval < 0.05 else 'NS'}")

if corr > 0:
    print(f"  Interpretation: Positive correlation - high-carbon sectors tend to have higher SB rates")
elif corr < 0:
    print(f"  Interpretation: Negative correlation - high-carbon sectors tend to have lower SB rates")
else:
    print(f"  Interpretation: No correlation - carbon and SB rate are independent")

# Save comprehensive results to JSON
output_dir = Path("results")
output_dir.mkdir(parents=True, exist_ok=True)

results_json = {
    'metadata': {
        'analysis': 'Dead Zone Threshold Sensitivity Analysis',
        'dataset': 'gprd_with_carbon.parquet',
        'filtering': 'EU context (country != "CO")',
        'grouping_level': 'CPV division (2-digit)',
        'n_sectors': len(sector_df),
        'n_tenders': len(df_eu),
        'n_threshold_combinations': n_combinations
    },
    'baseline_thresholds': {
        'carbon_intensity_kg_usd': float(baseline_carbon_pct),
        'single_bidder_rate': float(baseline_sb_pct)
    },
    'percentile_thresholds': {
        'carbon_intensity': {str(int(pct*100)): float(val) for pct, val in carbon_thresholds.items()},
        'single_bidder_rate': {f"{int(pct*100)}" if pct == 0.50 else f"{pct*100:.1f}": float(val) 
                               for pct, val in sb_thresholds.items()}
    },
    'sector_metrics': sector_df.to_dict('records'),
    'sensitivity_analysis': sensitivity_results,
    'sector_robustness': {
        'always_dead_zones': {
            'count': len(always_dz),
            'sectors': sorted(always_dz),
            'details': [
                {
                    'cpv_division': s,
                    'mean_carbon_intensity': float(sector_df[sector_df['cpv_division']==s]['mean_carbon_intensity'].iloc[0]),
                    'single_bidder_rate': float(sector_df[sector_df['cpv_division']==s]['single_bidder_rate'].iloc[0])
                }
                for s in sorted(always_dz)
            ]
        },
        'marginal_dead_zones': {
            'count': len(marginal_dz),
            'sectors': [
                {
                    'cpv_division': s,
                    'appearances_out_of': [sector_robustness[s]['appearances'], n_combinations],
                    'robustness_pct': sector_robustness[s]['robustness_pct'],
                    'mean_carbon_intensity': float(sector_df[sector_df['cpv_division']==s]['mean_carbon_intensity'].iloc[0]),
                    'single_bidder_rate': float(sector_df[sector_df['cpv_division']==s]['single_bidder_rate'].iloc[0])
                }
                for s in sorted(marginal_dz, key=lambda x: sector_robustness[x]['appearances'], reverse=True)
            ]
        },
        'never_dead_zones': {
            'count': len(never_dz),
            'note': f"{len(never_dz)} sectors never qualify as dead zones"
        }
    },
    'composition_effect': {
        'spearman_rho': float(corr),
        'p_value': float(pval),
        'n_sectors': len(sector_df),
        'interpretation': 'Positive' if corr > 0 else 'Negative' if corr < 0 else 'No correlation',
        'statistical_significance': 'p<0.001' if pval < 0.001 else 'p<0.01' if pval < 0.01 else 'p<0.05' if pval < 0.05 else 'NS'
    }
}

# Save to JSON
output_file = output_dir / "dead_zone_sensitivity.json"
with open(output_file, 'w') as f:
    json.dump(results_json, f, indent=2)

print(f"\n✓ Results saved to {output_file}")
print(f"  File size: {output_file.stat().st_size / 1024:.1f} KB")
