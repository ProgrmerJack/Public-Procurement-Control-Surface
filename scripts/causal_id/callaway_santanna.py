"""
Callaway & Sant'Anna (2021) group-time ATT estimation.
Uses the staggered transposition of EU Directive 2014/24/EU
to estimate cohort-specific treatment effects.

This addresses the leading methodological critique: standard TWFE
produces biased estimates under heterogeneous treatment effects.
"""

import json
import sys

sys.path.insert(0, ".")

import pandas as pd
import numpy as np
from scipy import stats

# Load data
df = pd.read_parquet(
    "Data/processed/gprd_with_carbon.parquet",
    columns=["country", "year", "single_bidder"],
)
df = df[df["year"].between(2012, 2023)].copy()

# Define country groups and transposition years
# Source: EUR-Lex transposition dates
transposition = {
    "GB": 2015,  # Early adopter; harmonized data use GB for the UK
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

# Non-EU controls. Colombia and Iceland are excluded from the primary DiD
# panel; Colombia is an explicitly reported sensitivity check, while Iceland
# is outside the EU member-state treatment group.
controls = ["NO", "CH"]
analysis_countries = set(transposition) | set(controls)
df = df[df["country"].isin(analysis_countries)].copy()

# Assign cohort (transposition year) or 0 for never-treated
df["cohort"] = df["country"].map(transposition).fillna(0).astype(int)

# Get country-year panel
cy = (
    df.groupby(["country", "year"])
    .agg(sb_rate=("single_bidder", "mean"), n=("single_bidder", "count"))
    .reset_index()
)
cy["cohort"] = cy["country"].map(transposition).fillna(0).astype(int)

# Manual Callaway & Sant'Anna-style estimation
# For each cohort g, estimate ATT(g,t) for each post-treatment period t
# using the never-treated group as comparison
# ATT(g,t) = E[Y_{g,t} - Y_{g,g-1}] - E[Y_{never,t} - Y_{never,g-1}]

never_treated = cy[cy["cohort"] == 0]

cohorts = sorted([c for c in cy["cohort"].unique() if c > 0])
print("=" * 70)
print("CALLAWAY & SANT'ANNA (2021) GROUP-TIME ATT ESTIMATION")
print("=" * 70)
print(
    f"Treated countries: {', '.join(sorted(cy.loc[cy['cohort'] > 0, 'country'].unique()))}"
)
print(f"Never-treated controls: {', '.join(sorted(never_treated['country'].unique()))}")

all_atts = []

for g in cohorts:
    cohort_data = cy[cy["cohort"] == g]
    cohort_countries = cohort_data["country"].unique()

    # Pre-treatment base period: g-1
    base_year = g - 1

    print(
        f"\n--- Cohort {g} ({len(cohort_countries)} countries: {', '.join(sorted(cohort_countries))}) ---"
    )

    # Get base period means
    treated_base = cohort_data[cohort_data["year"] == base_year]
    control_base = never_treated[never_treated["year"] == base_year]

    if len(treated_base) == 0 or len(control_base) == 0:
        print(f"  Skipping: no base year {base_year} data")
        continue

    treated_base_mean = np.average(treated_base["sb_rate"], weights=treated_base["n"])
    control_base_mean = np.average(control_base["sb_rate"], weights=control_base["n"])

    for t in range(g, 2024):
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

        # Bootstrap SE (simple version: country-level clustering)
        n_boot = 1000
        boot_atts = []
        rng = np.random.default_rng(42)

        for _ in range(n_boot):
            # Resample countries within each group
            t_countries = rng.choice(
                cohort_countries, size=len(cohort_countries), replace=True
            )
            c_countries = rng.choice(
                never_treated["country"].unique(),
                size=len(never_treated["country"].unique()),
                replace=True,
            )

            # Treated
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

            # Control
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

            if (
                len(t_base_vals) > 0
                and len(t_post_vals) > 0
                and len(c_base_vals) > 0
                and len(c_post_vals) > 0
            ):
                b_att = (np.mean(t_post_vals) - np.mean(t_base_vals)) - (
                    np.mean(c_post_vals) - np.mean(c_base_vals)
                )
                boot_atts.append(b_att)

        se = np.std(boot_atts) if len(boot_atts) > 0 else np.nan
        t_stat = att / se if se > 0 else np.nan
        p_val = (
            2 * stats.t.sf(abs(t_stat), df=max(1, len(cohort_countries) - 1))
            if not np.isnan(t_stat)
            else np.nan
        )

        event_time = t - g
        all_atts.append(
            {
                "cohort": g,
                "year": t,
                "event_time": event_time,
                "att": att * 100,  # in pp
                "se": se * 100,
                "t_stat": t_stat,
                "p_value": p_val,
                "n_treated_countries": len(cohort_countries),
                "n_control_countries": len(never_treated["country"].unique()),
            }
        )

        sig = (
            "***"
            if p_val < 0.001
            else "**"
            if p_val < 0.01
            else "*"
            if p_val < 0.05
            else ""
        )
        print(
            f"  t={t} (e={event_time:+d}): ATT = {att * 100:+.2f} pp (SE={se * 100:.2f}, p={p_val:.3f}) {sig}"
        )

# Also estimate pre-treatment placebos for each cohort
print("\n" + "=" * 70)
print("PRE-TREATMENT PLACEBOS (testing parallel trends)")
print("=" * 70)

for g in cohorts:
    cohort_data = cy[cy["cohort"] == g]
    cohort_countries = cohort_data["country"].unique()
    base_year = g - 1

    treated_base = cohort_data[cohort_data["year"] == base_year]
    control_base = never_treated[never_treated["year"] == base_year]

    if len(treated_base) == 0 or len(control_base) == 0:
        continue

    treated_base_mean = np.average(treated_base["sb_rate"], weights=treated_base["n"])
    control_base_mean = np.average(control_base["sb_rate"], weights=control_base["n"])

    for t in range(2012, g):
        if t == base_year:
            continue
        treated_t = cohort_data[cohort_data["year"] == t]
        control_t = never_treated[never_treated["year"] == t]

        if len(treated_t) == 0 or len(control_t) == 0:
            continue

        treated_t_mean = np.average(treated_t["sb_rate"], weights=treated_t["n"])
        control_t_mean = np.average(control_t["sb_rate"], weights=control_t["n"])

        att = (treated_t_mean - treated_base_mean) - (
            control_t_mean - control_base_mean
        )
        event_time = t - g

        all_atts.append(
            {
                "cohort": g,
                "year": t,
                "event_time": event_time,
                "att": att * 100,
                "se": np.nan,
                "t_stat": np.nan,
                "p_value": np.nan,
                "n_treated_countries": len(cohort_countries),
                "n_control_countries": len(never_treated["country"].unique()),
                "pre_treatment": True,
            }
        )

# Aggregate ATT across cohorts (weighted by number of countries)
print("\n" + "=" * 70)
print("AGGREGATE ATT (cohort-weighted)")
print("=" * 70)

att_df = pd.DataFrame(all_atts)
post_atts = att_df[(att_df["event_time"] >= 0) & (att_df["se"].notna())]

if len(post_atts) > 0:
    # Weight by number of treated countries
    weights = post_atts["n_treated_countries"]
    agg_att = np.average(post_atts["att"], weights=weights)

    # Aggregate SE (conservative: assume independence across cohort-time cells)
    agg_se = np.sqrt(np.sum((weights * post_atts["se"]) ** 2)) / np.sum(weights)
    agg_t = agg_att / agg_se
    agg_p = 2 * stats.t.sf(abs(agg_t), df=len(post_atts) - 1)

    print(f"  Aggregate ATT = {agg_att:+.2f} pp")
    print(f"  SE = {agg_se:.2f}")
    print(f"  t = {agg_t:.2f}")
    print(f"  p = {agg_p:.4f}")
    print(f"  95% CI: [{agg_att - 1.96 * agg_se:.2f}, {agg_att + 1.96 * agg_se:.2f}]")
    print(f"  N (group-time cells) = {len(post_atts)}")

    # Also by cohort
    print("\n  By cohort:")
    for g in cohorts:
        cohort_atts = post_atts[post_atts["cohort"] == g]
        if len(cohort_atts) > 0:
            c_att = cohort_atts["att"].mean()
            c_se = np.sqrt(np.mean(cohort_atts["se"] ** 2))
            c_t = c_att / c_se if c_se > 0 else np.nan
            c_p = (
                2 * stats.t.sf(abs(c_t), df=max(1, len(cohort_atts) - 1))
                if not np.isnan(c_t)
                else np.nan
            )
            sig = (
                "***"
                if c_p < 0.001
                else "**"
                if c_p < 0.01
                else "*"
                if c_p < 0.05
                else ""
            )
            print(
                f"    Cohort {g}: ATT = {c_att:+.2f} pp (SE={c_se:.2f}, p={c_p:.3f}) {sig}"
            )

# Event study aggregation
print("\n" + "=" * 70)
print("EVENT STUDY (aggregated across cohorts by event time)")
print("=" * 70)

for e in range(-4, 8):
    event_cells = att_df[att_df["event_time"] == e]
    post_event = event_cells[event_cells["se"].notna()]
    if len(post_event) > 0:
        w = post_event["n_treated_countries"]
        e_att = np.average(post_event["att"], weights=w)
        e_se = np.sqrt(np.sum((w * post_event["se"]) ** 2)) / np.sum(w)
        sig = "*" if abs(e_att / e_se) > 1.96 else ""
        period = "PRE " if e < 0 else "POST"
        print(f"  e={e:+d} ({period}): ATT = {e_att:+.2f} pp (SE={e_se:.2f}) {sig}")
    elif len(event_cells) > 0:
        e_att = np.average(
            event_cells["att"], weights=event_cells["n_treated_countries"]
        )
        print(f"  e={e:+d} (PRE ): ATT = {e_att:+.2f} pp (no SE)")

# Save results
results = {
    "sample": {
        "treated_countries": sorted(cy.loc[cy["cohort"] > 0, "country"].unique()),
        "never_treated_countries": sorted(never_treated["country"].unique()),
        "excluded_from_primary": ["CO", "IS"],
        "years": [2012, 2023],
    },
    "group_time_atts": [
        {
            k: (
                float(v)
                if isinstance(v, (np.floating, float))
                else int(v)
                if isinstance(v, (np.integer, int))
                else bool(v)
                if isinstance(v, (np.bool_, bool))
                else v
            )
            for k, v in row.items()
        }
        for _, row in att_df.iterrows()
    ],
    "aggregate": {
        "att": float(agg_att),
        "se": float(agg_se),
        "t_stat": float(agg_t),
        "p_value": float(agg_p),
        "ci_lower": float(agg_att - 1.96 * agg_se),
        "ci_upper": float(agg_att + 1.96 * agg_se),
        "n_cells": int(len(post_atts)),
    }
    if len(post_atts) > 0
    else None,
}

with open("results/causal_id/callaway_santanna.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print("\nSaved to results/callaway_santanna.json")
