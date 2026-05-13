"""
Callaway & Sant'Anna (2021) with NOT-YET-TREATED comparison group.

This variant uses later EU cohorts as controls for earlier cohorts,
eliminating dependence on any external (non-EU) control countries.
This addresses the "thin control pool" limitation directly: if the
result holds without NO/CH, the external control pool is supplementary
rather than essential.

Comparison group:
  For cohort g at time t: control = all countries with cohort > t
  (i.e., countries that have not yet transposed Directive 2014/24/EU)

Output: results/causal_id/cs_not_yet_treated.json
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

# Define transposition cohorts (same as primary callaway_santanna.py)
transposition = {
    "GB": 2015,
    "DK": 2016, "FR": 2016, "DE": 2016, "HU": 2016, "IE": 2016,
    "LT": 2016, "NL": 2016, "PL": 2016, "PT": 2016, "RO": 2016,
    "SK": 2016, "FI": 2016, "SE": 2016, "EE": 2016,
    "AT": 2017, "BE": 2017, "BG": 2017, "CZ": 2017,
    "ES": 2017, "HR": 2017, "IT": 2017, "LV": 2017,
    "GR": 2018, "LU": 2018, "SI": 2018,
}

# ONLY EU treated countries — NO external controls
eu_countries = set(transposition.keys())
df = df[df["country"].isin(eu_countries)].copy()
df["cohort"] = df["country"].map(transposition).astype(int)

# Build country-year panel
cy = (
    df.groupby(["country", "year"])
    .agg(sb_rate=("single_bidder", "mean"), n=("single_bidder", "count"))
    .reset_index()
)
cy["cohort"] = cy["country"].map(transposition).astype(int)

cohorts = sorted(cy["cohort"].unique())
print("=" * 70)
print("CALLAWAY & SANT'ANNA (2021) — NOT-YET-TREATED COMPARISON GROUP")
print("=" * 70)
print(f"Treated countries: {', '.join(sorted(eu_countries))}")
print(f"External controls: NONE (purely within-EU identification)")
print(f"Comparison group: Not-yet-treated EU countries (cohort > t)")
print(f"Cohorts: {cohorts}")

all_atts = []

for g in cohorts:
    cohort_data = cy[cy["cohort"] == g]
    cohort_countries = sorted(cohort_data["country"].unique())
    base_year = g - 1

    print(f"\n--- Cohort {g} ({len(cohort_countries)} countries: {', '.join(cohort_countries)}) ---")

    # Treated baseline
    treated_base = cohort_data[cohort_data["year"] == base_year]
    if len(treated_base) == 0:
        print(f"  Skipping: no base year {base_year} data")
        continue
    treated_base_mean = np.average(treated_base["sb_rate"], weights=treated_base["n"])

    # Post-treatment periods
    for t in range(g, 2024):
        # NOT-YET-TREATED: countries whose cohort > t (not yet treated at time t)
        nyt_mask = cy["cohort"] > t
        control_pool = cy[nyt_mask]

        if len(control_pool) == 0:
            # No not-yet-treated countries left — cannot estimate
            continue

        control_base = control_pool[control_pool["year"] == base_year]
        control_t = control_pool[control_pool["year"] == t]
        treated_t = cohort_data[cohort_data["year"] == t]

        if len(treated_t) == 0 or len(control_base) == 0 or len(control_t) == 0:
            continue

        treated_t_mean = np.average(treated_t["sb_rate"], weights=treated_t["n"])
        control_base_mean = np.average(control_base["sb_rate"], weights=control_base["n"])
        control_t_mean = np.average(control_t["sb_rate"], weights=control_t["n"])

        # ATT(g,t) = (treated_t - treated_base) - (control_t - control_base)
        att = (treated_t_mean - treated_base_mean) - (control_t_mean - control_base_mean)

        # Bootstrap SE (country-level clustering)
        n_boot = 1000
        boot_atts = []
        rng = np.random.default_rng(42)

        nyt_countries = sorted(control_pool["country"].unique())

        for _ in range(n_boot):
            t_countries = rng.choice(cohort_countries, size=len(cohort_countries), replace=True)
            c_countries = rng.choice(nyt_countries, size=len(nyt_countries), replace=True)

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

            # Control (not-yet-treated)
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

            if (len(t_base_vals) > 0 and len(t_post_vals) > 0
                    and len(c_base_vals) > 0 and len(c_post_vals) > 0):
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
        n_nyt = len(nyt_countries)

        all_atts.append({
            "cohort": g,
            "year": t,
            "event_time": event_time,
            "att": att * 100,  # in pp
            "se": se * 100,
            "t_stat": t_stat,
            "p_value": p_val,
            "n_treated_countries": len(cohort_countries),
            "n_nyt_control_countries": n_nyt,
            "nyt_control_countries": sorted(nyt_countries) if n_nyt <= 15 else f"{n_nyt} countries",
            "pre_treatment": False,
        })

        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else ""
        print(
            f"  t={t} (e={event_time:+d}): ATT = {att * 100:+.2f} pp "
            f"(SE={se * 100:.2f}, p={p_val:.4f}) "
            f"[{n_nyt} nyt controls] {sig}"
        )

# Pre-treatment placebos
print("\n" + "=" * 70)
print("PRE-TREATMENT PLACEBOS (testing parallel trends)")
print("=" * 70)

for g in cohorts:
    cohort_data = cy[cy["cohort"] == g]
    cohort_countries = sorted(cohort_data["country"].unique())
    base_year = g - 1

    treated_base = cohort_data[cohort_data["year"] == base_year]
    if len(treated_base) == 0:
        continue
    treated_base_mean = np.average(treated_base["sb_rate"], weights=treated_base["n"])

    for t in range(2012, g):
        if t == base_year:
            continue

        nyt_mask = cy["cohort"] > t
        control_pool = cy[nyt_mask]
        if len(control_pool) == 0:
            continue

        control_base = control_pool[control_pool["year"] == base_year]
        control_t = control_pool[control_pool["year"] == t]
        treated_t = cohort_data[cohort_data["year"] == t]

        if len(treated_t) == 0 or len(control_base) == 0 or len(control_t) == 0:
            continue

        treated_t_mean = np.average(treated_t["sb_rate"], weights=treated_t["n"])
        control_base_mean = np.average(control_base["sb_rate"], weights=control_base["n"])
        control_t_mean = np.average(control_t["sb_rate"], weights=control_t["n"])

        att = (treated_t_mean - treated_base_mean) - (control_t_mean - control_base_mean)
        event_time = t - g

        all_atts.append({
            "cohort": g,
            "year": t,
            "event_time": event_time,
            "att": att * 100,
            "se": np.nan,
            "t_stat": np.nan,
            "p_value": np.nan,
            "n_treated_countries": len(cohort_countries),
            "n_nyt_control_countries": len(control_pool["country"].unique()),
            "pre_treatment": True,
        })

        print(f"  Cohort {g}, t={t} (e={event_time:+d}): ATT = {att * 100:+.2f} pp (no SE)")


# Aggregate ATT
print("\n" + "=" * 70)
print("AGGREGATE ATT (cohort-weighted, not-yet-treated controls)")
print("=" * 70)

att_df = pd.DataFrame(all_atts)
post_atts = att_df[(att_df["event_time"] >= 0) & (att_df["se"].notna())]

if len(post_atts) > 0:
    weights = post_atts["n_treated_countries"]
    agg_att = np.average(post_atts["att"], weights=weights)

    agg_se = np.sqrt(np.sum((weights * post_atts["se"]) ** 2)) / np.sum(weights)
    agg_t = agg_att / agg_se
    agg_p = 2 * stats.t.sf(abs(agg_t), df=len(post_atts) - 1)

    print(f"  Aggregate ATT = {agg_att:+.2f} pp")
    print(f"  SE = {agg_se:.2f}")
    print(f"  t = {agg_t:.2f}")
    print(f"  p = {agg_p:.6f}")
    print(f"  95% CI: [{agg_att - 1.96 * agg_se:.2f}, {agg_att + 1.96 * agg_se:.2f}]")
    print(f"  N (group-time cells) = {len(post_atts)}")

    # Equal-weight aggregation
    eq_att = post_atts["att"].mean()
    eq_se = post_atts["se"].mean() / np.sqrt(len(post_atts))
    eq_t = eq_att / eq_se
    eq_p = 2 * stats.t.sf(abs(eq_t), df=len(post_atts) - 1)
    print(f"\n  Equal-weight ATT = {eq_att:+.2f} pp (p={eq_p:.6f})")

    # By cohort
    print("\n  By cohort:")
    for g in cohorts:
        cohort_atts = post_atts[post_atts["cohort"] == g]
        if len(cohort_atts) > 0:
            c_att = cohort_atts["att"].mean()
            c_se = np.sqrt(np.mean(cohort_atts["se"] ** 2))
            c_t = c_att / c_se if c_se > 0 else np.nan
            c_p = 2 * stats.t.sf(abs(c_t), df=max(1, len(cohort_atts) - 1)) if not np.isnan(c_t) else np.nan
            n_nyt = cohort_atts["n_nyt_control_countries"].iloc[0]
            sig = "***" if c_p < 0.001 else "**" if c_p < 0.01 else "*" if c_p < 0.05 else ""
            print(f"    Cohort {g}: ATT = {c_att:+.2f} pp (SE={c_se:.2f}, p={c_p:.4f}) [{n_nyt} nyt controls] {sig}")

    # Event study
    print("\n  Event study (aggregated across cohorts):")
    for e in sorted(att_df["event_time"].unique()):
        event_cells = att_df[att_df["event_time"] == e]
        post_event = event_cells[event_cells["se"].notna()]
        if len(post_event) > 0:
            w = post_event["n_treated_countries"]
            e_att = np.average(post_event["att"], weights=w)
            e_se = np.sqrt(np.sum((w * post_event["se"]) ** 2)) / np.sum(w)
            sig = "**" if abs(e_att / e_se) > 2.58 else "*" if abs(e_att / e_se) > 1.96 else ""
            period = "PRE " if e < 0 else "POST"
            print(f"    e={e:+d} ({period}): ATT = {e_att:+.2f} pp (SE={e_se:.2f}) {sig}")
        elif len(event_cells) > 0:
            e_att = np.average(event_cells["att"], weights=event_cells["n_treated_countries"])
            print(f"    e={e:+d} (PRE ): ATT = {e_att:+.2f} pp (no SE)")

    # Comparison with primary (never-treated) estimate
    print("\n" + "=" * 70)
    print("COMPARISON WITH PRIMARY NEVER-TREATED ESTIMATE")
    print("=" * 70)
    print(f"  Never-treated (NO+CH) ATT:     -7.18 pp (from callaway_santanna.json)")
    print(f"  Not-yet-treated (EU-only) ATT:  {agg_att:+.2f} pp")
    print(f"  Equal-weight not-yet-treated:   {eq_att:+.2f} pp")
    diff = abs(agg_att - (-7.18))
    print(f"  Absolute difference:            {diff:.2f} pp")
    if agg_att < 0:
        print(f"  VERDICT: Same sign (negative) — result holds without external controls")
    else:
        print(f"  VERDICT: DIFFERENT SIGN — external controls may be essential")

# Save results
results = {
    "specification": "Callaway_SantAnna_NotYetTreated",
    "description": (
        "C&S 2021 with not-yet-treated comparison group. "
        "Uses ONLY within-EU timing variation — no external controls (NO, CH). "
        "This tests whether the main ATT depends on the thin external control pool."
    ),
    "comparison_group": "not_yet_treated_EU_cohorts",
    "external_controls_used": False,
    "sample": {
        "treated_countries": sorted(eu_countries),
        "n_treated": len(eu_countries),
        "control_type": "not_yet_treated",
        "note": "For cohort g at time t, control = EU countries with transposition year > t",
    },
    "group_time_atts": [
        {k: (float(v) if isinstance(v, (np.floating, float))
             else int(v) if isinstance(v, (np.integer, int))
             else bool(v) if isinstance(v, (np.bool_, bool))
             else v)
         for k, v in row.items() if k != "nyt_control_countries"}
        for _, row in att_df.iterrows()
    ],
    "aggregate": {
        "att_pp": float(agg_att),
        "se": float(agg_se),
        "t_stat": float(agg_t),
        "p_value": float(agg_p),
        "ci_lower": float(agg_att - 1.96 * agg_se),
        "ci_upper": float(agg_att + 1.96 * agg_se),
        "n_cells": int(len(post_atts)),
        "aggregation": "cohort_size_weighted",
    } if len(post_atts) > 0 else None,
    "equal_weight_aggregate": {
        "att_pp": float(eq_att),
        "se": float(eq_se),
        "t_stat": float(eq_t),
        "p_value": float(eq_p),
    } if len(post_atts) > 0 else None,
    "comparison_to_primary": {
        "primary_never_treated_att_pp": -7.18,
        "not_yet_treated_att_pp": float(agg_att),
        "same_sign": agg_att < 0,
        "difference_pp": float(abs(agg_att - (-7.18))),
    },
}

out_path = "results/causal_id/cs_not_yet_treated.json"
with open(out_path, "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nSaved to {out_path}")
