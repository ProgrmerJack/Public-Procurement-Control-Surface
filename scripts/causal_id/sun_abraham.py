"""
Sun & Abraham (2021) Interaction-Weighted (IW) Estimator.

Third causal specification alongside TWFE and Callaway & Sant'Anna.

Method:
  Sun & Abraham (2021) show that the conventional TWFE estimator under
  staggered adoption computes a weighted average of cohort×event-time effects
  δ_{g,l} where the weights can be negative (contaminating already-treated units
  serve as implicit controls). The interaction-weighted (IW) estimator corrects
  this by:
    1. Estimating cohort-specific ATT_{g,l} using only clean comparators
       (never-treated or not-yet-treated — in our case, only never-treated NO/CH)
    2. Averaging δ_{g,l} using cohort-size weights (share of treated units in
       cohort g at event time l)

  The SA aggregate ATT = Σ_g Σ_{l≥0} ω_{g,l} × δ_{g,l}
  where ω_{g,l} = (n_g × n_{l,g}) / Σ_{g',l'≥0} (n_{g'} × n_{l',g'})
  and n_g = number of countries in cohort g, n_{l,g} = 1 for balanced panel.

  With balanced panel and equal cohort sizes, SA ≈ simple average of ATT(g,t).
  The key distinction from TWFE: no "contaminated" comparisons (never uses
  already-treated units as controls).

  This specification is mathematically equivalent to C&S with the "equal"
  weighting scheme. Small differences from the primary C&S ATT (-7.18 pp)
  would reflect weighting scheme differences; agreement confirms robustness.

Expected result:
  ATT should fall between TWFE (-0.71 pp, biased) and the cohort-size-weighted
  C&S aggregate. Proximity to C&S ATT confirms TWFE's attenuation is due to
  heterogeneous treatment effects, not data problems.

References:
  Sun, L. & Abraham, S. (2021). Estimating dynamic treatment effects in event
  studies with heterogeneous treatment effects. Journal of Econometrics, 225(2).

Results saved to: results/causal_id/sun_abraham.json
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


def run_sun_abraham():
    """
    Sun & Abraham (2021) IW estimator.

    For each cohort g, estimate cohort-specific ATT_{g,l} for each
    post-treatment event time l ≥ 0 using:
      ATT(g, l) = (Y_{g, g+l} - Y_{g, g-1}) - (Y_{control, g+l} - Y_{control, g-1})

    Aggregate with cohort-size weights:
      SAIW = Σ_{g,l≥0} (n_g / N_total) × (1 / T_g) × ATT(g, l)
    where T_g = number of observed post-treatment periods for cohort g.

    Bootstrap: country-level cluster resampling of treated side;
    control side (only 2 countries) resampled as in primary analysis.
    """
    print("=" * 70)
    print("SUN & ABRAHAM (2021) INTERACTION-WEIGHTED ESTIMATOR")
    print("=" * 70)

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

    # Step 1: Estimate cohort×event-time ATTs
    cohort_event_atts = []  # list of (g, l, att, n_g, se)
    cohort_sizes = {}  # n_g = number of countries in cohort g

    for g in cohorts:
        cohort_data = cy[cy["cohort"] == g]
        cohort_countries = cohort_data["country"].unique()
        n_g = len(cohort_countries)
        cohort_sizes[g] = n_g
        base_year = g - 1  # standard SA base period

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

        for t in range(g, 2024):
            l = t - g  # event time (0-indexed: l=0 is first post-treatment year)

            treated_t = cohort_data[cohort_data["year"] == t]
            control_t = never_treated[never_treated["year"] == t]

            if len(treated_t) == 0 or len(control_t) == 0:
                continue

            treated_t_mean = np.average(treated_t["sb_rate"], weights=treated_t["n"])
            control_t_mean = np.average(control_t["sb_rate"], weights=control_t["n"])

            att_gl = (treated_t_mean - treated_base_mean) - (
                control_t_mean - control_base_mean
            )

            # Bootstrap SE
            rng = np.random.default_rng(RNG_SEED + l)
            boot_atts = []
            for _ in range(N_BOOT):
                t_c = rng.choice(
                    cohort_countries, size=len(cohort_countries), replace=True
                )
                c_c = rng.choice(
                    control_countries, size=len(control_countries), replace=True
                )

                tb = [
                    treated_base[treated_base["country"] == c]["sb_rate"].values[0]
                    for c in t_c
                    if c in treated_base["country"].values
                ]
                tp = [
                    treated_t[treated_t["country"] == c]["sb_rate"].values[0]
                    for c in t_c
                    if c in treated_t["country"].values
                ]
                cb = [
                    control_base[control_base["country"] == c]["sb_rate"].values[0]
                    for c in c_c
                    if c in control_base["country"].values
                ]
                cp = [
                    control_t[control_t["country"] == c]["sb_rate"].values[0]
                    for c in c_c
                    if c in control_t["country"].values
                ]

                if tb and tp and cb and cp:
                    boot_atts.append(
                        (np.mean(tp) - np.mean(tb)) - (np.mean(cp) - np.mean(cb))
                    )

            se = np.std(boot_atts) if boot_atts else np.nan

            cohort_event_atts.append(
                {
                    "cohort": g,
                    "event_time": l,
                    "calendar_year": t,
                    "att": att_gl,
                    "se": se,
                    "n_g": n_g,
                }
            )

    if not cohort_event_atts:
        return {"error": "no cohort-event ATTs computed"}

    att_df = pd.DataFrame(cohort_event_atts)

    # Step 2: Sun-Abraham interaction-weighted aggregation
    # ω_{g,l} ∝ n_g (cohort size weight) — identical to primary C&S weighting
    # This directly implements the IW estimator: weight each δ_{g,l} by cohort size
    weights = att_df["n_g"].values.astype(float)
    sa_att_pp = float(np.average(att_df["att"].values, weights=weights)) * 100

    # Aggregate SE (weighted, matching primary analysis)
    agg_se = (
        float(
            np.sqrt(np.nansum((weights * att_df["se"].values) ** 2)) / np.sum(weights)
        )
        * 100
    )

    z_stat = sa_att_pp / agg_se if agg_se > 0 else np.nan
    p_val = 2 * stats.norm.sf(abs(z_stat))
    ci_lower = sa_att_pp - 1.96 * agg_se
    ci_upper = sa_att_pp + 1.96 * agg_se

    print(f"\n  SA Aggregate ATT = {sa_att_pp:.3f} pp")
    print(f"  SE               = {agg_se:.3f} pp")
    print(f"  95% CI           = [{ci_lower:.3f}, {ci_upper:.3f}]")
    print(f"  p-value          = {p_val:.2e}")
    print(f"  N cohort×time    = {len(att_df)}")

    # Per-cohort averages
    by_cohort = []
    for g, grp in att_df.groupby("cohort"):
        by_cohort.append(
            {
                "cohort": int(g),
                "n_countries": int(grp["n_g"].iloc[0]),
                "att_pp": round(grp["att"].mean() * 100, 3),
                "n_event_times": len(grp),
            }
        )

    # Event-study profile (average across cohorts at each event time)
    by_event_time = []
    for l, grp in att_df.groupby("event_time"):
        by_event_time.append(
            {
                "event_time": int(l),
                "att_pp": round(grp["att"].mean() * 100, 3),
                "n_cohorts": len(grp),
            }
        )

    return {
        "estimator": "Sun-Abraham (2021) Interaction-Weighted",
        "aggregate": {
            "att_pp": round(sa_att_pp, 3),
            "se_pp": round(agg_se, 3),
            "ci_lower": round(ci_lower, 3),
            "ci_upper": round(ci_upper, 3),
            "p_value": float(p_val),
            "n_cohort_event_cells": len(att_df),
        },
        "by_cohort": by_cohort,
        "event_study": by_event_time,
        "weighting_scheme": "cohort-size (n_g / N_total), equal weight over event times within cohort",
        "controls": CONTROLS,
        "total_treated_countries": int(sum(cohort_sizes.values())),
    }


if __name__ == "__main__":
    result = run_sun_abraham()

    print("\n" + "=" * 70)
    print("SUN-ABRAHAM vs PRIMARY C&S COMPARISON")
    print("=" * 70)
    cs_att = -7.176  # primary C&S aggregate ATT
    twfe_att = -0.71  # conventional TWFE ATT
    sa_att = result.get("aggregate", {}).get("att_pp", float("nan"))
    print(
        f"  TWFE ATT:         {twfe_att:.2f} pp  (attenuated by heterogeneous effects)"
    )
    print(f"  Sun-Abraham ATT:  {sa_att:.3f} pp  (this study, interaction-weighted)")
    print(f"  C&S ATT:          {cs_att:.3f} pp  (primary specification)")
    print(f"  TWFE attenuation: {sa_att - twfe_att:.3f} pp vs SA")
    print(f"  SA-C&S agreement: {abs(sa_att - cs_att):.3f} pp difference")

    # Save results
    out_path = Path("results/causal_id/sun_abraham.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nResults saved to {out_path}")
