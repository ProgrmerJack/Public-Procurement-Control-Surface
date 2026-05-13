#!/usr/bin/env python3
"""
Generate final summary statistics for EU ETS within-sector analysis
"""

import json
import pandas as pd

# Load main results
with open('results/within_sector/eu_ets_within_sector_analysis.json') as f:
    data = json.load(f)

# Load detailed statistics
df_facility = pd.read_csv('results/csv/facility_level_sector_statistics.csv')
df_premiums = pd.read_csv('results/csv/procurement_premiums_by_sector.csv')

print("\n" + "="*90)
print(" "*25 + "EU ETS WITHIN-SECTOR ANALYSIS - FINAL SUMMARY")
print("="*90)

print("\n📍 DATA COVERAGE")
print("-"*90)
print(f"  • Facility-year records analyzed:        {data['data_summary']['total_facility_records']:>10,}")
print(f"  • Sector-country-year groups:           {data['data_summary']['sector_country_year_groups']:>10,}")
print(f"  • Countries covered:                    {data['data_summary']['countries']:>10}")
print(f"  • Industrial sectors:                   {data['data_summary']['sectors']:>10}")
print(f"  • Time period:                          {data['data_summary']['years']:>10}")
print(f"  • Average facilities per group:         {data['data_summary']['avg_facilities_per_group']:>10.1f}")

print("\n\n🎯 KEY METRIC 1: WITHIN-SECTOR VARIATION")
print("-"*90)
cv = data['within_sector_variation']['coefficient_of_variation']
print(f"  Coefficient of Variation (CV):")
print(f"    Mean:                                 {cv['mean']:>10.4f}")
print(f"    Median:                               {cv['median']:>10.4f}")
print(f"    Std Dev:                              {cv['std']:>10.4f}")
print(f"    Range:                                {cv['min']:>10.4f} to {cv['max']:>7.2f}")
print(f"\n  Interpretation: NOT ZERO. Actual variation is {cv['mean']:.2f}× the mean")

print("\n\n🎯 KEY METRIC 2: EMISSION INEQUALITY (P90/P10 RATIOS)")
print("-"*90)
ratio = data['within_sector_variation']['p90_p10_ratio']
print(f"  High vs Low Emitter Ratios:")
print(f"    Median ratio:                         {ratio['median']:>10.2f}×")
print(f"    Mean ratio:                           {ratio['mean']:>10.2f}×")
print(f"    Interquartile (25-75):                {ratio['p25']:>10.2f}× to {ratio['p75']:>7.2f}×")
print(f"\n  Interpretation: Top emitter is ~8.5× higher than bottom (not 1×)")

print("\n\n🎯 KEY METRIC 3: PROCUREMENT PREMIUM")
print("-"*90)
premium = data['procurement_premium']['p25_vs_p50_pct']
print(f"  Competitive Selection Scenario: P25 vs P50 (lower quartile vs median)")
print(f"    Median reduction:                     {premium['median']:>10.2f}%")
print(f"    Mean reduction:                       {premium['mean']:>10.2f}%")
print(f"    Interquartile (25-75):                {premium['p25']:>10.2f}% to {premium['p75']:>7.2f}%")
print(f"\n  Interpretation: Procurement achieves 43% within-sector reduction")

print("\n  More Aggressive Scenarios:")
p10_p50 = data['procurement_premium']['p10_vs_p50_pct']
p10_p90 = data['procurement_premium']['p10_vs_p90_pct']
print(f"    P10 vs P50 (median):                  {p10_p50['median']:>10.2f}%")
print(f"    P10 vs P90 (maximum):                 {p10_p90['median']:>10.2f}%")

print("\n\n⚡ KEY METRIC 4: EFFECT SIZE TELESCOPING")
print("-"*90)

exiobase_d = data['effect_sizes']['exiobase_200_sectors']['allocative_d']
eurostat_within_d = data['effect_sizes']['eurostat_648_sectors']['within_sector_effect']
eutl_d = data['effect_sizes']['eutl_facility_level']['effect_size_d_p25_vs_p50']['median']
amplification = data['effect_sizes']['eutl_facility_level']['amplification_vs_exiobase']

print(f"  Aggregation Level               d           Note")
print(f"  " + "-"*80)
print(f"  EXIOBASE (200 sectors)          {exiobase_d:8.4f}    Assumes 0% within-sector variation")
print(f"  Eurostat within (648 sectors)   {eurostat_within_d:8.4f}    Only 0.2% within-sector")
print(f"  EU ETS facility-level (actual)  {eutl_d:8.4f}    ← Reality with 43% procurement premium")
print(f"\n  Amplification Factor:           {amplification:8.1f}×")
print(f"\n  Interpretation: Facility-level effect is 4.6× larger than EXIOBASE!")

print("\n\n📊 TOP 5 HETEROGENEOUS SECTORS")
print("-"*90)
top_sectors = df_facility.nlargest(5, 'cv')[['sector', 'cv', 'p90_p10_ratio', 'gini', 'n_facilities']]
for idx, (_, row) in enumerate(top_sectors.iterrows(), 1):
    sector = row['sector'][:50] + "..." if len(row['sector']) > 50 else row['sector']
    print(f"\n  {idx}. {sector}")
    print(f"     CV: {row['cv']:8.3f}  |  P90/P10: {row['p90_p10_ratio']:8.1f}×  |  Gini: {row['gini']:7.3f}")

print("\n\n🔴 CRITICAL FINDINGS FOR MANUSCRIPT")
print("-"*90)

print("""
The assumption that EXIOBASE makes — identical carbon intensity within 
country-sector groups — is FUNDAMENTALLY WRONG:

1. REALITY:     Within-sector variation (CV) = 1.22 
   ASSUMPTION:  Within-sector variation = 0
   ERROR:       Unmeasured heterogeneity = 1.22

2. REALITY:     High emitters are 8.5× higher than low emitters
   ASSUMPTION:  All emitters identical (1× ratio)
   ERROR:       8.5× hidden variation

3. REALITY:     Procurement can select 25th percentile for 43% reduction
   ASSUMPTION:  No benefit from within-sector selection
   ERROR:       Missing 43% of accessible savings

4. REALITY:     Effect size should be d ≈ -0.37
   MEASURED:    EXIOBASE reports d = -0.08
   ERROR:       4.6× UNDERESTIMATE of procurement impact

This explains why:
  • Aggregated IO models underestimate procurement's carbon impact
  • Facility-level competition can drive deeper decarbonization
  • Specifying low-carbon suppliers is a major lever
  • Within-sector diversity creates procurement opportunities
""")

print("\n\n📁 ANALYSIS ARTIFACTS")
print("-"*90)
print("""
Core Results:
  ✓ eu_ets_within_sector_analysis.json
    → Effect size calculations
    → Summary statistics
    → Telescoping analysis

Detailed Data:
  ✓ facility_level_sector_statistics.csv
    → 5,999 rows (all sector-country-year groups)
    → CV, P90/P10, Gini, facilities, emissions stats

  ✓ procurement_premiums_by_sector.csv
    → 5,999 premium calculations
    → Multiple scenarios (P25 vs P50, P10 vs P50, etc.)

  ✓ top_20_sectors_by_heterogeneity.csv
    → Top 20 most heterogeneous sectors
    → Summary statistics

Documentation:
  ✓ EU_ETS_ANALYSIS_SUMMARY.md
    → Full interpretation for manuscript
    → Recommended language for limitations section
""")

print("\n" + "="*90)
print("Analysis complete. Results ready for manuscript integration.")
print("="*90 + "\n")
