"""
Callaway & Sant'Anna DiD — Anticipation Parameter Sensitivity.

Tests whether allowing 1 period of anticipatory compliance changes the ATT.

Background:
  EU Directive 2014/24/EU was formally proposed in December 2011 and adopted
  in April 2014 with a two-year transposition deadline (April 2016). The full
  2012-2014 pre-period therefore overlaps the legislative announcement window.
  If firms anticipate governance reform and begin compliance early, the
  standard anticipation=0 specification (using g-1 as base period) may absorb
  anticipatory treatment into the pre-trend, making the primary ATT a
  CONSERVATIVE lower bound.

  With anticipation=1, period g-1 is treated as the first post-treatment period
  (firms anticipated treatment one year early), and the base period shifts to g-2.
  If ATT(anticipation=1) is more negative than ATT(anticipation=0), this confirms
  the primary ATT is conservative and that pre-trends reflect anticipatory
  compliance rather than parallel-trends violations.

Specifications:
  - anticipation=0: base period = g-1 (primary specification)
  - anticipation=1: base period = g-2 (one-year anticipation allowed)

Results saved to: results/robustness/cs_anticipation_sensitivity.json
"""

import json
import sys

sys.path.insert(0, ".")

import numpy as np
import pandas as pd
from scipy import stats
from pathlib import Path

# ── Load data ────────────────────────────────────────────────────────
df = pd.read_parquet(
    "Data/processed/gprd_with_carbon.parquet",
    columns=["country", "year", "single_bidder"],
)
df = df[df["year"].between(2012, 2023)].copy()

# ── Transposition years (identical to primary analysis) ──────────────
TRANSPOSITION = {
    "GB": 2015,
    "DK": 2016,
    "FR": 2016,
    "DE": 2016,
    "HU": 2016,
    "IE": 2016,
    "LT": 2016,
    "NL": 2016,
    "PL": 2016,
    "PT": 2016,
    "RO": 2016,
    "SK": 2016,
    "FI": 2016,
    "SE": 2016,
    "EE": 2016,
    "AT": 2017,
    "BE": 2017,
    "BG": 2017,
    "CZ": 2017,
    "ES": 2017,
    "HR": 2017,
    "IT": 2017,
    "LV": 2017,
    "GR": 2018,
    "LU": 2018,
    "SI": 2018,
}
CONTROLS = ["NO", "CH"]
N_BOOT = 1000
RNG_SEED = 42


def run_cs_with_anticipation(anticipation: int = 0, label: str = "") -> dict:
    """
    Run C&S DiD with specified anticipation parameter.

    anticipation=0: base period = g-1 (standard)
    anticipation=1: base period = g-2 (1-year anticipation allowed)

    The base period is shifted back by `anticipation` years. Periods
    [g - anticipation, ..., g-1] are treated as the first post-periods
    when anticipation > 0.
    """
    print(f"\n{'=' * 70}")
    print(f"C&S DiD — anticipation={anticipation}  [{label}]")
    print(f"{'=' * 70}")

    analysis_countries = set(TRANSPOSITION) | set(CONTROLS)
    panel = df[df["country"].isin(analysis_countries)].copy()
    panel["cohort"] = panel["country"].map(TRANSPOSITION).fillna(0).astype(int)

    cy = (
        panel.groupby(["country", "year"])
        .agg(sb_rate=("single_bidder", "mean"), n=("single_bidder", "count"))
        .reset_index()
    )
    cy["cohort"] = cy["country"].map(TRANSPOSITION).fillna(0).astype(int)

    never_treated = cy[cy["cohort"] == 0]
    cohorts = sorted(c for c in cy["cohort"].unique() if c > 0)
    control_countries = np.array(sorted(never_treated["country"].unique()))

    all_atts = []

    for g in cohorts:
        cohort_data = cy[cy["cohort"] == g]
        cohort_countries = cohort_data["country"].unique()

        # Shift base period back by anticipation years
        base_year = g - 1 - anticipation

        # With anticipation>0, post-treatment starts at g-anticipation
        post_start = g - anticipation

        if base_year < 2012:
            print(
                f"  Cohort {g}: skipped (base year {base_year} before data start 2012)"
            )
            continue

        treated_base = cohort_data[cohort_data["year"] == base_year]
        control_base = never_treated[never_treated["year"] == base_year]

        if len(treated_base) == 0 or len(control_base) == 0:
            print(f"  Cohort {g}: skipped (no data at base year {base_year})")
            continue

        treated_base_mean = np.average(
            treated_base["sb_rate"], weights=treated_base["n"]
        )
        control_base_mean = np.average(
            control_base["sb_rate"], weights=control_base["n"]
        )

        for t in range(post_start, 2024):
            treated_t = cohort_data[cohort_data["year"] == t]
            control_t = never_treated[never_treated["year"] == t]

            if len(treated_t) == 0 or len(control_t) == 0:
                continue

            treated_t_mean = np.average(treated_t["sb_rate"], weights=treated_t["n"])
            control_t_mean = np.average(control_t["sb_rate"], weights=control_t["n"])

            # ATT(g,t) = (treated_t - treated_base) - (control_t - control_base)
            att = (treated_t_mean - treated_base_mean) - (
                control_t_mean - control_base_mean
            )

            # Bootstrap SE (country-level clustering)
            rng = np.random.default_rng(RNG_SEED)
            boot_atts = []
            for _ in range(N_BOOT):
                t_countries = rng.choice(
                    cohort_countries, size=len(cohort_countries), replace=True
                )
                c_countries = rng.choice(
                    control_countries, size=len(control_countries), replace=True
                )

                t_base_vals = [
                    treated_base[treated_base["country"] == c]["sb_rate"].values[0]
                    for c in t_countries
                    if c in treated_base["country"].values
                ]
                t_post_vals = [
                    treated_t[treated_t["country"] == c]["sb_rate"].values[0]
                    for c in t_countries
                    if c in treated_t["country"].values
                ]
                c_base_vals = [
                    control_base[control_base["country"] == c]["sb_rate"].values[0]
                    for c in c_countries
                    if c in control_base["country"].values
                ]
                c_post_vals = [
                    control_t[control_t["country"] == c]["sb_rate"].values[0]
                    for c in c_countries
                    if c in control_t["country"].values
                ]

                if not (t_base_vals and t_post_vals and c_base_vals and c_post_vals):
                    continue

                b_att = (np.mean(t_post_vals) - np.mean(t_base_vals)) - (
                    np.mean(c_post_vals) - np.mean(c_base_vals)
                )
                boot_atts.append(b_att)

            se = np.std(boot_atts) if boot_atts else np.nan
            n_cells = len(cohort_countries)

            all_atts.append(
                {
                    "cohort": g,
                    "year": t,
                    "att": att,
                    "se": se,
                    "n_countries": n_cells,
                    "base_year": base_year,
                    "post_start": post_start,
                }
            )

    if not all_atts:
        return {"error": "no ATT cells computed"}

    att_df = pd.DataFrame(all_atts)

    # Cohort-size-weighted aggregation (matches primary callaway_santanna.py)
    weights = att_df["n_countries"].values.astype(float)
    att_pp = float(np.average(att_df["att"].values, weights=weights)) * 100
    # Weighted aggregate SE
    agg_se = (
        float(
            np.sqrt(np.nansum((weights * att_df["se"].values) ** 2)) / np.sum(weights)
        )
        * 100
    )
    n_cells = len(att_df)

    z_stat = att_pp / agg_se if agg_se > 0 else np.nan
    p_val = 2 * stats.norm.sf(abs(z_stat))
    ci_lower = att_pp - 1.96 * agg_se
    ci_upper = att_pp + 1.96 * agg_se

    print(f"\n  Aggregate ATT = {att_pp:.3f} pp")
    print(f"  SE            = {agg_se:.3f} pp")
    print(f"  95% CI        = [{ci_lower:.3f}, {ci_upper:.3f}]")
    print(f"  p-value       = {p_val:.2e}")
    print(f"  N cells       = {n_cells}")

    # Per-cohort averages
    by_cohort = []
    for g, grp in att_df.groupby("cohort"):
        by_cohort.append(
            {
                "cohort": int(g),
                "att_pp": round(grp["att"].mean() * 100, 3),
                "n_periods": len(grp),
            }
        )

    return {
        "anticipation": anticipation,
        "label": label,
        "aggregate": {
            "att_pp": round(att_pp, 3),
            "se_pp": round(agg_se, 3),
            "ci_lower": round(ci_lower, 3),
            "ci_upper": round(ci_upper, 3),
            "p_value": float(p_val),
            "n_cells": n_cells,
        },
        "by_cohort": by_cohort,
    }


if __name__ == "__main__":
    results = {}

    # Specification 1: anticipation=0 (primary, replication check)
    results["anticipation_0"] = run_cs_with_anticipation(
        anticipation=0, label="Primary specification — no anticipation (base: g-1)"
    )

    # Specification 2: anticipation=1 (one-year early compliance allowed)
    results["anticipation_1"] = run_cs_with_anticipation(
        anticipation=1, label="Anticipation=1 — base period g-2, post from g-1"
    )

    # Comparison summary
    att0 = results["anticipation_0"]["aggregate"]["att_pp"]
    att1 = results["anticipation_1"]["aggregate"]["att_pp"]
    direction = (
        "more negative (primary ATT is CONSERVATIVE lower bound)"
        if att1 < att0
        else "less negative (primary ATT unchanged or more extreme)"
    )
    results["comparison"] = {
        "att_anticipation_0": att0,
        "att_anticipation_1": att1,
        "difference_pp": round(att1 - att0, 3),
        "interpretation": direction,
    }

    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)
    print(f"  ATT (anticipation=0): {att0:.3f} pp")
    print(f"  ATT (anticipation=1): {att1:.3f} pp")
    print(f"  Difference:          {att1 - att0:.3f} pp")
    print(f"  Interpretation:       {direction}")

    # Save results
    out_path = Path("results/robustness/cs_anticipation_sensitivity.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")
