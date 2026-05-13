"""
Greece-exclusion robustness check for CS-DiD carbon intensity result.

Motivation: The 2018 cohort (GR, LU, SI) drives the carbon intensity ATT
(-0.165 kg/USD vs -0.015 for 2016 cohort). Greece's post-2010
deindustrialisation could confound the result. This script tests whether
the causal estimate survives Greece exclusion.

Three analyses:
  1. Carbon intensity CS-DiD excluding Greece (GR)
  2. Carbon intensity CS-DiD excluding entire 2018 cohort (GR, LU, SI)
  3. Single-bidder rate CS-DiD excluding Greece (GR)
"""

import json
import sys
import os

import pandas as pd
import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATA_PATH = r"Data\processed\gprd_with_carbon.parquet"
OUT_PATH = r"results\greece_exclusion_sensitivity.json"
N_BOOT = 500
RNG_SEED = 2024

# Cohort definitions per user specification (data uses 'GB' for UK)
COHORT_2016 = ['BG', 'DE', 'DK', 'EE', 'FI', 'FR', 'HU', 'IE', 'LT',
               'PL', 'PT', 'RO', 'GB']
COHORT_2017 = ['AT', 'BE', 'CZ', 'ES', 'IT', 'LV']
COHORT_2018 = ['GR', 'LU', 'SI']
NEVER_TREATED = ['NO', 'CH']
EXCLUDE_ALWAYS = ['CO']

COHORT_MAP = {}
for c in COHORT_2016:
    COHORT_MAP[c] = 2016
for c in COHORT_2017:
    COHORT_MAP[c] = 2017
for c in COHORT_2018:
    COHORT_MAP[c] = 2018
for c in NEVER_TREATED:
    COHORT_MAP[c] = 0  # never-treated sentinel


# ---------------------------------------------------------------------------
# Helper: build country-year panel
# ---------------------------------------------------------------------------
def build_panel(df, outcome_col, exclude_countries=None):
    """Collapse contract-level data to country-year means."""
    mask = ~df['country'].isin(EXCLUDE_ALWAYS)
    if exclude_countries:
        mask &= ~df['country'].isin(exclude_countries)
    # Keep only countries in our cohort universe
    valid = set(COHORT_MAP.keys())
    if exclude_countries:
        valid -= set(exclude_countries)
    mask &= df['country'].isin(valid)

    sub = df.loc[mask].copy()
    sub['year'] = sub['year'].astype(int)

    agg = sub.groupby(['country', 'year']).agg(
        outcome=(outcome_col, 'mean'),
        n=(outcome_col, 'count'),
    ).reset_index()
    agg['cohort'] = agg['country'].map(COHORT_MAP).fillna(-1).astype(int)
    # Drop countries that aren't in our map (shouldn't happen, but safety)
    agg = agg[agg['cohort'] >= 0]
    return agg


# ---------------------------------------------------------------------------
# Core CS-DiD estimator
# ---------------------------------------------------------------------------
def estimate_csdid(panel, n_boot=N_BOOT, seed=RNG_SEED):
    """
    Callaway & Sant'Anna (2021) group-time ATT estimation.
    Returns dict with group-time ATTs, cohort-level aggregates, and
    overall aggregate with bootstrap SEs.
    """
    never = panel[panel['cohort'] == 0]
    cohorts = sorted([c for c in panel['cohort'].unique() if c > 0])
    rng = np.random.default_rng(seed)

    gt_results = []

    for g in cohorts:
        treated = panel[panel['cohort'] == g]
        treated_countries = treated['country'].unique()
        control_countries = never['country'].unique()
        base_year = g - 1

        treated_base = treated[treated['year'] == base_year]
        control_base = never[never['year'] == base_year]
        if len(treated_base) == 0 or len(control_base) == 0:
            continue

        t_base_mean = np.average(treated_base['outcome'],
                                 weights=treated_base['n'])
        c_base_mean = np.average(control_base['outcome'],
                                 weights=control_base['n'])

        years_post = sorted(panel.loc[panel['year'] >= g, 'year'].unique())
        for t in years_post:
            treated_t = treated[treated['year'] == t]
            control_t = never[never['year'] == t]
            if len(treated_t) == 0 or len(control_t) == 0:
                continue

            t_mean = np.average(treated_t['outcome'],
                                weights=treated_t['n'])
            c_mean = np.average(control_t['outcome'],
                                weights=control_t['n'])
            att = (t_mean - t_base_mean) - (c_mean - c_base_mean)

            # Bootstrap SE: resample countries with replacement
            boot_atts = []
            for _ in range(n_boot):
                tc = rng.choice(treated_countries,
                                size=len(treated_countries), replace=True)
                cc = rng.choice(control_countries,
                                size=len(control_countries), replace=True)

                # treated base & post
                tb = [treated_base.loc[treated_base['country'] == c,
                      'outcome'].values[0]
                      for c in tc
                      if c in treated_base['country'].values]
                tp = [treated_t.loc[treated_t['country'] == c,
                      'outcome'].values[0]
                      for c in tc
                      if c in treated_t['country'].values]
                # control base & post
                cb = [control_base.loc[control_base['country'] == c,
                      'outcome'].values[0]
                      for c in cc
                      if c in control_base['country'].values]
                cp = [control_t.loc[control_t['country'] == c,
                      'outcome'].values[0]
                      for c in cc
                      if c in control_t['country'].values]

                if tb and tp and cb and cp:
                    b = (np.mean(tp) - np.mean(tb)) - \
                        (np.mean(cp) - np.mean(cb))
                    boot_atts.append(b)

            se = float(np.std(boot_atts)) if boot_atts else np.nan
            t_stat = att / se if se > 0 else np.nan
            dof = max(1, len(treated_countries) - 1)
            p_val = (2 * stats.t.sf(abs(t_stat), df=dof)
                     if not np.isnan(t_stat) else np.nan)

            gt_results.append({
                'cohort': int(g),
                'year': int(t),
                'event_time': int(t - g),
                'att': float(att),
                'se': float(se),
                't_stat': float(t_stat),
                'p_value': float(p_val),
                'n_treated_countries': int(len(treated_countries)),
                'treated_countries': sorted(treated_countries.tolist()),
            })

    if not gt_results:
        return {'group_time': [], 'by_cohort': {}, 'aggregate': None}

    gt_df = pd.DataFrame(gt_results)

    # --- Cohort-level aggregates ---
    by_cohort = {}
    for g in cohorts:
        cg = gt_df[gt_df['cohort'] == g]
        if cg.empty:
            continue
        c_att = float(cg['att'].mean())
        c_se = float(np.sqrt(np.mean(cg['se'] ** 2)))
        c_t = c_att / c_se if c_se > 0 else np.nan
        c_dof = max(1, len(cg) - 1)
        c_p = (2 * stats.t.sf(abs(c_t), df=c_dof)
               if not np.isnan(c_t) else np.nan)
        by_cohort[int(g)] = {
            'att': c_att,
            'se': c_se,
            't_stat': float(c_t),
            'p_value': float(c_p),
            'ci_lower': c_att - 1.96 * c_se,
            'ci_upper': c_att + 1.96 * c_se,
            'n_cells': int(len(cg)),
            'countries': sorted(
                cg['treated_countries'].iloc[0]) if len(cg) > 0 else [],
        }

    # --- Overall aggregate ATT (weighted by group size) ---
    weights = gt_df['n_treated_countries'].values.astype(float)
    agg_att = float(np.average(gt_df['att'], weights=weights))

    # Bootstrap the aggregate: resample group-time cells
    boot_agg = []
    rng2 = np.random.default_rng(seed + 1)
    for _ in range(n_boot):
        idx = rng2.choice(len(gt_df), size=len(gt_df), replace=True)
        w = weights[idx]
        boot_agg.append(float(np.average(gt_df['att'].values[idx],
                                         weights=w)))
    agg_se = float(np.std(boot_agg))
    agg_t = agg_att / agg_se if agg_se > 0 else np.nan
    agg_p = (2 * stats.norm.sf(abs(agg_t))
             if not np.isnan(agg_t) else np.nan)

    aggregate = {
        'att': agg_att,
        'se': agg_se,
        't_stat': float(agg_t),
        'p_value': float(agg_p),
        'ci_lower': agg_att - 1.96 * agg_se,
        'ci_upper': agg_att + 1.96 * agg_se,
        'n_cells': int(len(gt_df)),
        'n_cohorts': len(by_cohort),
    }

    return {
        'group_time': gt_results,
        'by_cohort': by_cohort,
        'aggregate': aggregate,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Loading data...")
    df = pd.read_parquet(
        DATA_PATH,
        columns=['country', 'year', 'single_bidder',
                 'carbon_intensity_kg_usd', 'value_eur'],
    )
    # single_bidder is boolean; cast to float for mean aggregation
    df['single_bidder'] = df['single_bidder'].astype(float)
    print(f"  {len(df):,} records, "
          f"{df['country'].nunique()} countries, "
          f"years {int(df['year'].min())}-{int(df['year'].max())}")

    results = {}

    # ==================================================================
    # Analysis 1: Carbon intensity, exclude Greece
    # ==================================================================
    print("\n" + "=" * 70)
    print("ANALYSIS 1: Carbon intensity CS-DiD — EXCLUDING GREECE (GR)")
    print("=" * 70)
    panel1 = build_panel(df, 'carbon_intensity_kg_usd',
                         exclude_countries=['GR'])
    print(f"  Panel: {panel1['country'].nunique()} countries, "
          f"{len(panel1)} country-year cells")
    print(f"  Cohorts present: "
          f"{sorted(c for c in panel1['cohort'].unique() if c > 0)}")

    res1 = estimate_csdid(panel1)
    _print_results("Carbon intensity (excl GR)", res1)
    results['carbon_excl_greece'] = res1

    # ==================================================================
    # Analysis 2: Carbon intensity, exclude entire 2018 cohort
    # ==================================================================
    print("\n" + "=" * 70)
    print("ANALYSIS 2: Carbon intensity CS-DiD — EXCLUDING 2018 COHORT "
          "(GR, LU, SI)")
    print("=" * 70)
    panel2 = build_panel(df, 'carbon_intensity_kg_usd',
                         exclude_countries=['GR', 'LU', 'SI'])
    print(f"  Panel: {panel2['country'].nunique()} countries, "
          f"{len(panel2)} country-year cells")
    print(f"  Cohorts present: "
          f"{sorted(c for c in panel2['cohort'].unique() if c > 0)}")

    res2 = estimate_csdid(panel2)
    _print_results("Carbon intensity (excl 2018 cohort)", res2)
    results['carbon_excl_2018_cohort'] = res2

    # ==================================================================
    # Analysis 3: Single-bidder rate, exclude Greece
    # ==================================================================
    print("\n" + "=" * 70)
    print("ANALYSIS 3: Single-bidder rate CS-DiD — EXCLUDING GREECE (GR)")
    print("=" * 70)
    panel3 = build_panel(df, 'single_bidder',
                         exclude_countries=['GR'])
    print(f"  Panel: {panel3['country'].nunique()} countries, "
          f"{len(panel3)} country-year cells")

    res3 = estimate_csdid(panel3)
    _print_results("Single-bidder rate (excl GR)", res3)
    results['singlebidder_excl_greece'] = res3

    # ==================================================================
    # Save
    # ==================================================================
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {OUT_PATH}")

    # ==================================================================
    # Summary table
    # ==================================================================
    print("\n" + "=" * 70)
    print("SUMMARY TABLE")
    print("=" * 70)
    fmt = "{:<45s} {:>10s} {:>8s} {:>8s} {:>22s}"
    print(fmt.format("Specification", "ATT", "SE", "p", "95% CI"))
    print("-" * 95)
    for label, key in [
        ("Carbon (excl GR)", 'carbon_excl_greece'),
        ("Carbon (excl 2018 cohort)", 'carbon_excl_2018_cohort'),
        ("Single-bidder (excl GR)", 'singlebidder_excl_greece'),
    ]:
        agg = results[key]['aggregate']
        if agg:
            print(fmt.format(
                label,
                f"{agg['att']:+.4f}",
                f"{agg['se']:.4f}",
                f"{agg['p_value']:.4f}",
                f"[{agg['ci_lower']:+.4f}, {agg['ci_upper']:+.4f}]",
            ))


def _print_results(title, res):
    """Pretty-print CS-DiD results to stdout."""
    agg = res['aggregate']
    if agg is None:
        print("  NO RESULTS (insufficient data)")
        return

    print(f"\n  Aggregate ATT = {agg['att']:+.6f}")
    print(f"  SE             = {agg['se']:.6f}")
    print(f"  t-stat         = {agg['t_stat']:.3f}")
    print(f"  p-value        = {agg['p_value']:.4f}")
    print(f"  95% CI         = [{agg['ci_lower']:+.6f}, "
          f"{agg['ci_upper']:+.6f}]")
    print(f"  Group-time cells = {agg['n_cells']}")

    print("\n  By cohort:")
    for g, c in sorted(res['by_cohort'].items()):
        sig = ("***" if c['p_value'] < 0.001
               else "**" if c['p_value'] < 0.01
               else "*" if c['p_value'] < 0.05 else "")
        print(f"    Cohort {g} ({', '.join(c['countries'])}): "
              f"ATT = {c['att']:+.6f} "
              f"(SE={c['se']:.6f}, p={c['p_value']:.4f}) {sig}")


if __name__ == '__main__':
    main()
