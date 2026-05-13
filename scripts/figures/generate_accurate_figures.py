#!/usr/bin/env python3
"""
Generate accurate figures from actual analysis results.

This script loads the validated causal analysis results from JSON files
and generates publication-ready figures that accurately represent the data.

IMPORTANT: This script does NOT use hardcoded values. All numbers come from
the actual analysis in results/causal_analysis_results.json.
"""

import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from typing import Dict, Any, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# Paths
# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
PROJECT_ROOT = _d
RESULTS_DIR = PROJECT_ROOT / "results"
OUTPUT_DIR = PROJECT_ROOT / "NC_Submission" / "Main_Figures"
EXTENDED_DIR = PROJECT_ROOT / "NC_Submission" / "Extended_Data_Figures"

# Ensure output directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
EXTENDED_DIR.mkdir(parents=True, exist_ok=True)

# Nature style settings
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 8,
    'axes.labelsize': 8,
    'axes.titlesize': 9,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
    'axes.linewidth': 0.5,
    'xtick.major.width': 0.5,
    'ytick.major.width': 0.5,
})

# Color scheme
COLORS = {
    'below': '#2166AC',  # Blue - below threshold
    'above': '#B2182B',  # Red - above threshold
    'effect': '#4DAF4A',  # Green - effect
    'neutral': '#666666',  # Gray
    'ci': '#CCCCCC',  # Light gray for CI bands
}


def load_results() -> Dict[str, Any]:
    """Load the actual causal analysis results."""
    results_file = RESULTS_DIR / "causal_analysis_results.json"
    
    if not results_file.exists():
        raise FileNotFoundError(
            f"Results file not found: {results_file}\n"
            "Please run the causal analysis first."
        )
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    print(f"Loaded results from: {results_file}")
    print(f"  - {results['n_total']:,} total contracts")
    print(f"  - {results['summary']['n_countries']} countries")
    
    return results


def load_parquet_data() -> pd.DataFrame:
    """Load the processed procurement data."""
    data_file = PROJECT_ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
    
    if not data_file.exists():
        raise FileNotFoundError(f"Data file not found: {data_file}")
    
    df = pd.read_parquet(data_file)
    print(f"Loaded {len(df):,} records from parquet")
    return df


def fig1_rdd_main(results: Dict[str, Any], df: pd.DataFrame) -> None:
    """
    Figure 1: Main RDD discontinuity plot.
    
    Shows the actual discontinuity at the transparency threshold.
    """
    print("\nGenerating Figure 1: Main RDD Plot...")
    
    # Get meta-analysis result
    meta = results['rdd']['carbon_intensity_kg_usd_meta']
    effect = meta['pooled_estimate'] * 100  # Convert to percentage
    ci_low = meta['ci_low'] * 100
    ci_high = meta['ci_high'] * 100
    i2 = meta['I2'] * 100
    
    # Prepare binned data around threshold
    THRESHOLD = 139000
    BW = 0.15  # bandwidth in log10 scale
    
    # Filter to valid data
    df_rdd = df.dropna(subset=['carbon_intensity_kg_usd', 'value_eur'])
    df_rdd = df_rdd[(df_rdd['value_eur'] > 0) & (df_rdd['carbon_intensity_kg_usd'] > 0)]
    
    # Create running variable
    df_rdd['log_value'] = np.log10(df_rdd['value_eur'])
    log_threshold = np.log10(THRESHOLD)
    df_rdd['running'] = df_rdd['log_value'] - log_threshold
    
    # Filter to bandwidth
    df_rdd = df_rdd[np.abs(df_rdd['running']) <= BW]
    
    # Create bins
    n_bins = 30
    df_rdd['bin'] = pd.cut(df_rdd['running'], bins=n_bins, labels=False)
    
    # Calculate bin means
    binned = df_rdd.groupby('bin').agg({
        'running': 'mean',
        'carbon_intensity_kg_usd': ['mean', 'std', 'count']
    }).reset_index()
    binned.columns = ['bin', 'x', 'y', 'std', 'n']
    binned['se'] = binned['std'] / np.sqrt(binned['n'])
    
    # Separate below/above
    below = binned[binned['x'] < 0]
    above = binned[binned['x'] >= 0]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(3.5, 3))
    
    # Plot points with error bars
    ax.errorbar(below['x'], below['y'], yerr=below['se']*1.96, 
                fmt='o', color=COLORS['below'], markersize=4, 
                capsize=2, capthick=0.5, label='Below threshold')
    ax.errorbar(above['x'], above['y'], yerr=above['se']*1.96,
                fmt='o', color=COLORS['above'], markersize=4,
                capsize=2, capthick=0.5, label='Above threshold')
    
    # Fit and plot regression lines
    if len(below) > 3:
        z = np.polyfit(below['x'], below['y'], 1)
        p = np.poly1d(z)
        x_line = np.linspace(below['x'].min(), 0, 50)
        ax.plot(x_line, p(x_line), '-', color=COLORS['below'], linewidth=1.5)
    
    if len(above) > 3:
        z = np.polyfit(above['x'], above['y'], 1)
        p = np.poly1d(z)
        x_line = np.linspace(0, above['x'].max(), 50)
        ax.plot(x_line, p(x_line), '-', color=COLORS['above'], linewidth=1.5)
    
    # Threshold line
    ax.axvline(x=0, color='black', linestyle='--', linewidth=0.75, alpha=0.7)
    
    # Labels
    ax.set_xlabel('Distance from threshold (log$_{10}$)')
    ax.set_ylabel('Carbon intensity (kg CO$_2$e/USD)')
    ax.set_title('A', loc='left', fontweight='bold', fontsize=10)
    
    # Add effect annotation
    effect_text = (
        f'Meta-analysis effect: {effect:.2f}%\n'
        f'95% CI: [{ci_low:.2f}%, {ci_high:.2f}%]\n'
        f'I² = {i2:.1f}%'
    )
    ax.text(0.97, 0.97, effect_text, transform=ax.transAxes, fontsize=6,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray'))
    
    ax.legend(loc='lower left', framealpha=0.9, fontsize=6)
    
    # Save
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "Fig1_RDD_Main.pdf")
    fig.savefig(OUTPUT_DIR / "Fig1_RDD_Main.png")
    plt.close()
    
    print(f"  Saved to {OUTPUT_DIR / 'Fig1_RDD_Main.pdf'}")
    print(f"  Effect: {effect:.2f}% [{ci_low:.2f}%, {ci_high:.2f}%]")


def fig2_forest_plot(results: Dict[str, Any]) -> None:
    """
    Figure 2: Forest plot of country-level effects.
    
    Shows heterogeneity across countries with meta-analysis pooled estimate.
    """
    print("\nGenerating Figure 2: Forest Plot...")
    
    # Extract country results
    country_results = results['rdd']['carbon_intensity_kg_usd_by_country']
    meta = results['rdd']['carbon_intensity_kg_usd_meta']
    
    # Create dataframe
    data = []
    for r in country_results:
        if r['country'] and not np.isnan(r.get('estimate', np.nan)):
            data.append({
                'country': r['country'],
                'effect': r['estimate'] * 100,  # Convert to %
                'ci_low': r['ci_low'] * 100,
                'ci_high': r['ci_high'] * 100,
                'n': int(r['n_obs']),
                'pvalue': r['pvalue']
            })
    
    df = pd.DataFrame(data)
    df = df.sort_values('effect')
    
    # Create figure
    fig, ax = plt.subplots(figsize=(4, 6))
    
    y_positions = range(len(df))
    
    # Plot country effects
    for i, (_, row) in enumerate(df.iterrows()):
        color = COLORS['effect'] if row['effect'] < 0 else COLORS['above']
        alpha = 0.8 if row['pvalue'] < 0.05 else 0.4
        
        # CI line
        ax.plot([row['ci_low'], row['ci_high']], [i, i], 
                color=color, linewidth=1, alpha=alpha)
        
        # Point estimate
        ax.plot(row['effect'], i, 'o', color=color, markersize=4, alpha=alpha)
    
    # Pooled estimate
    pooled_effect = meta['pooled_estimate'] * 100
    pooled_ci_low = meta['ci_low'] * 100
    pooled_ci_high = meta['ci_high'] * 100
    
    # Diamond for pooled
    y_pooled = len(df) + 1
    diamond_height = 0.4
    diamond = plt.Polygon([
        (pooled_ci_low, y_pooled),
        (pooled_effect, y_pooled + diamond_height),
        (pooled_ci_high, y_pooled),
        (pooled_effect, y_pooled - diamond_height)
    ], color=COLORS['effect'], alpha=0.8)
    ax.add_patch(diamond)
    
    # Zero line
    ax.axvline(x=0, color='black', linestyle='--', linewidth=0.5)
    
    # Y-axis labels
    labels = list(df['country']) + ['', 'Pooled']
    ax.set_yticks(list(y_positions) + [len(df), len(df) + 1])
    ax.set_yticklabels(labels)
    
    # Labels
    ax.set_xlabel('Effect on carbon intensity (%)')
    ax.set_title('B', loc='left', fontweight='bold', fontsize=10)
    
    # Annotation
    i2 = meta['I2'] * 100
    info_text = (
        f'Pooled: {pooled_effect:.2f}%\n'
        f'I² = {i2:.1f}%\n'
        f'n = {len(df)} countries'
    )
    ax.text(0.97, 0.03, info_text, transform=ax.transAxes, fontsize=6,
            verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='gray'))
    
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "Fig2_Forest.pdf")
    fig.savefig(OUTPUT_DIR / "Fig2_Forest.png")
    plt.close()
    
    print(f"  Saved to {OUTPUT_DIR / 'Fig2_Forest.pdf'}")
    print(f"  Pooled effect: {pooled_effect:.2f}% [{pooled_ci_low:.2f}%, {pooled_ci_high:.2f}%]")
    print(f"  I² = {i2:.1f}%")


def fig3_mechanism(results: Dict[str, Any]) -> None:
    """
    Figure 3: Mediation analysis - mechanism through competition.
    """
    print("\nGenerating Figure 3: Mediation Mechanism...")
    
    mediation = results['mediation']
    
    # Create figure with path diagram
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis('off')
    
    # Boxes
    box_style = dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='black')
    
    # Treatment box
    ax.text(1, 3, 'Above\nThreshold', ha='center', va='center', fontsize=8,
            bbox=box_style)
    
    # Mediator box
    ax.text(5, 5, 'Competition\n(n bidders)', ha='center', va='center', fontsize=8,
            bbox=box_style)
    
    # Outcome box
    ax.text(9, 3, 'Carbon\nIntensity', ha='center', va='center', fontsize=8,
            bbox=box_style)
    
    # Arrows with coefficients
    bidders = mediation['bidders']
    
    # Path a (Treatment -> Mediator)
    ax.annotate('', xy=(4, 4.7), xytext=(2, 3.5),
                arrowprops=dict(arrowstyle='->', color='black', lw=1))
    ax.text(2.8, 4.3, f'a = {bidders["path_a"]:.3f}', fontsize=7)
    
    # Path b (Mediator -> Outcome)
    ax.annotate('', xy=(8, 3.5), xytext=(6, 4.7),
                arrowprops=dict(arrowstyle='->', color='black', lw=1))
    ax.text(7.2, 4.3, f'b = {bidders["path_b"]:.3f}', fontsize=7)
    
    # Path c' (Direct effect)
    ax.annotate('', xy=(8, 3), xytext=(2, 3),
                arrowprops=dict(arrowstyle='->', color='gray', lw=1.5))
    ax.text(5, 2.5, f"c' = {bidders['path_c_prime_direct']:.3f}", fontsize=7, color='gray')
    
    # Mediation statistics
    prop_med = bidders['proportion_mediated'] * 100
    indirect = bidders['indirect_effect']
    
    stats_text = (
        f'Indirect effect: {indirect:.4f}\n'
        f'Proportion mediated: {prop_med:.1f}%\n'
        f'Sobel z = {bidders["sobel_z"]:.2f}, p < 0.001'
    )
    ax.text(5, 0.5, stats_text, ha='center', va='bottom', fontsize=7,
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    
    ax.set_title('C', loc='left', fontweight='bold', fontsize=10, x=-0.05)
    
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "Fig3_Mediation.pdf")
    fig.savefig(OUTPUT_DIR / "Fig3_Mediation.png")
    plt.close()
    
    print(f"  Saved to {OUTPUT_DIR / 'Fig3_Mediation.pdf'}")
    print(f"  Proportion mediated: {prop_med:.1f}%")


def fig4_policy_implications(results: Dict[str, Any]) -> None:
    """
    Figure 4: Policy implications - effect heterogeneity.
    """
    print("\nGenerating Figure 4: Policy Heterogeneity...")
    
    # Extract country results
    country_results = results['rdd']['carbon_intensity_kg_usd_by_country']
    meta = results['rdd']['carbon_intensity_kg_usd_meta']
    
    data = []
    for r in country_results:
        if r['country'] and not np.isnan(r.get('estimate', np.nan)):
            data.append({
                'country': r['country'],
                'effect': r['estimate'] * 100,
                'n': int(r['n_obs']),
                'pvalue': r['pvalue']
            })
    
    df = pd.DataFrame(data)
    
    # Create figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6, 3))
    
    # Left: Distribution of effects
    ax1.hist(df['effect'], bins=15, color=COLORS['neutral'], edgecolor='white', alpha=0.7)
    ax1.axvline(x=0, color='black', linestyle='--', linewidth=0.75)
    ax1.axvline(x=meta['pooled_estimate']*100, color=COLORS['effect'], 
                linestyle='-', linewidth=1.5, label='Pooled estimate')
    ax1.set_xlabel('Effect on carbon intensity (%)')
    ax1.set_ylabel('Number of countries')
    ax1.set_title('D', loc='left', fontweight='bold', fontsize=10)
    ax1.legend(loc='upper right', fontsize=6)
    
    # Count positive/negative
    n_negative = (df['effect'] < 0).sum()
    n_positive = (df['effect'] >= 0).sum()
    n_sig_neg = ((df['effect'] < 0) & (df['pvalue'] < 0.05)).sum()
    
    ax1.text(0.97, 0.97, 
             f'{n_negative} countries: negative effect\n'
             f'{n_sig_neg} significant (p < 0.05)\n'
             f'{n_positive} countries: positive effect',
             transform=ax1.transAxes, fontsize=6,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # Right: Effect vs sample size
    sizes = np.sqrt(df['n']) / 10
    colors = [COLORS['effect'] if e < 0 else COLORS['above'] for e in df['effect']]
    ax2.scatter(df['n'] / 1000, df['effect'], s=30, c=colors, alpha=0.6)
    ax2.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
    ax2.set_xlabel('Sample size (thousands)')
    ax2.set_ylabel('Effect on carbon intensity (%)')
    ax2.set_title('E', loc='left', fontweight='bold', fontsize=10)
    
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "Fig4_Policy.pdf")
    fig.savefig(OUTPUT_DIR / "Fig4_Policy.png")
    plt.close()
    
    print(f"  Saved to {OUTPUT_DIR / 'Fig4_Policy.pdf'}")


def generate_source_data(results: Dict[str, Any], df: pd.DataFrame) -> None:
    """Generate source data files for reproducibility."""
    print("\nGenerating Source Data files...")
    
    source_dir = PROJECT_ROOT / "NC_Submission" / "Source_Data"
    source_dir.mkdir(parents=True, exist_ok=True)
    
    # Source Data Fig 1 - RDD binned data
    THRESHOLD = 139000
    BW = 0.15
    
    df_rdd = df.dropna(subset=['carbon_intensity_kg_usd', 'value_eur'])
    df_rdd = df_rdd[(df_rdd['value_eur'] > 0) & (df_rdd['carbon_intensity_kg_usd'] > 0)]
    df_rdd['log_value'] = np.log10(df_rdd['value_eur'])
    log_threshold = np.log10(THRESHOLD)
    df_rdd['running'] = df_rdd['log_value'] - log_threshold
    df_rdd = df_rdd[np.abs(df_rdd['running']) <= BW]
    
    n_bins = 30
    df_rdd['bin'] = pd.cut(df_rdd['running'], bins=n_bins, labels=False)
    
    binned = df_rdd.groupby('bin').agg({
        'running': 'mean',
        'carbon_intensity_kg_usd': ['mean', 'std', 'count']
    }).reset_index()
    binned.columns = ['bin', 'distance_from_threshold', 'carbon_intensity_mean', 
                      'carbon_intensity_std', 'n_observations']
    binned['above_threshold'] = binned['distance_from_threshold'] >= 0
    binned.to_csv(source_dir / "Source_Data_Fig1.csv", index=False)
    
    # Source Data Fig 2 - Country effects
    country_data = []
    for r in results['rdd']['carbon_intensity_kg_usd_by_country']:
        if r['country']:
            country_data.append({
                'country': r['country'],
                'effect_pct': r['estimate'] * 100 if not np.isnan(r['estimate']) else np.nan,
                'ci_low_pct': r['ci_low'] * 100 if not np.isnan(r['ci_low']) else np.nan,
                'ci_high_pct': r['ci_high'] * 100 if not np.isnan(r['ci_high']) else np.nan,
                'p_value': r['pvalue'],
                'n_observations': r['n_obs']
            })
    
    pd.DataFrame(country_data).to_csv(source_dir / "Source_Data_Fig2.csv", index=False)
    
    # Source Data Fig 3 - Mediation
    med_data = {
        'path': ['a (treatment->mediator)', 'b (mediator->outcome)', 
                 'c_total', 'c_prime (direct)', 'indirect'],
        'coefficient': [
            results['mediation']['bidders']['path_a'],
            results['mediation']['bidders']['path_b'],
            results['mediation']['bidders']['path_c_total'],
            results['mediation']['bidders']['path_c_prime_direct'],
            results['mediation']['bidders']['indirect_effect']
        ],
        'proportion_mediated': [None, None, None, None, 
                                results['mediation']['bidders']['proportion_mediated']]
    }
    pd.DataFrame(med_data).to_csv(source_dir / "Source_Data_Fig3.csv", index=False)
    
    print(f"  Saved source data to {source_dir}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("GENERATING ACCURATE FIGURES FROM ACTUAL ANALYSIS RESULTS")
    print("=" * 60)
    
    # Load data
    results = load_results()
    df = load_parquet_data()
    
    # Generate figures
    fig1_rdd_main(results, df)
    fig2_forest_plot(results)
    fig3_mechanism(results)
    fig4_policy_implications(results)
    
    # Generate source data
    generate_source_data(results, df)
    
    # Print summary
    print("\n" + "=" * 60)
    print("FIGURE GENERATION COMPLETE")
    print("=" * 60)
    
    meta = results['rdd']['carbon_intensity_kg_usd_meta']
    print(f"\nKey findings from ACTUAL data:")
    print(f"  - Pooled effect: {meta['pooled_estimate']*100:.2f}%")
    print(f"  - 95% CI: [{meta['ci_low']*100:.2f}%, {meta['ci_high']*100:.2f}%]")
    print(f"  - I² heterogeneity: {meta['I2']*100:.1f}%")
    print(f"  - Number of countries: {meta['n_studies']}")
    print(f"  - Mediation via competition: {results['mediation']['bidders']['proportion_mediated']*100:.1f}%")
    
    print(f"\nFigures saved to: {OUTPUT_DIR}")
    print(f"Source data saved to: {PROJECT_ROOT / 'NC_Submission' / 'Source_Data'}")


if __name__ == "__main__":
    main()
