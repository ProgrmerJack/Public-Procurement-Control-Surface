"""
CS-DiD Sensitivity Analyses for EU Directive 2014/24/EU

Three robustness checks requested by the editor:
  1. Excluding 2017 cohort → show aggregate ATT isn't artifact of null 2017
  2. Excluding calendar year 2018 → data anomaly year (~5.79M contracts)
  3. Carbon intensity as outcome → test whether directive affected portfolio carbon

Methodology follows Callaway & Sant'Anna (2021):
  ATT(g,t) = E[Y_{g,t} - Y_{g,g-1}] - E[Y_{ctrl,t} - Y_{ctrl,g-1}]
  Aggregate ATT = equal-weight mean across all post-treatment (g,t) cells
  SEs via country-level clustered bootstrap (500 reps)
"""

import json
import sys

sys.path.insert(0, ".")

import numpy as np
import pandas as pd
from scipy import stats

# ── Load data ────────────────────────────────────────────────────────
df = pd.read_parquet(
    "Data/processed/gprd_with_carbon.parquet",
    columns=["country", "year", "single_bidder", "carbon_intensity_kg_usd"],
)
df = df[df["year"].between(2012, 2023)].copy()

# ── Transposition years (identical to main analysis) ─────────────────
transposition = {
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

controls = ["NO", "CH"]
analysis_countries = set(transposition) | set(controls)
df = df[df["country"].isin(analysis_countries)].copy()

# ── Build country-year panel ─────────────────────────────────────────
cy = (
    df.groupby(["country", "year"])
    .agg(
        sb_rate=("single_bidder", "mean"),
        mean_carbon=("carbon_intensity_kg_usd", "mean"),
        n=("single_bidder", "count"),
    )
    .reset_index()
)
cy["cohort"] = cy["country"].map(transposition).fillna(0).astype(int)

print(
    f"Panel: {cy['country'].nunique()} countries, "
    f"years {cy['year'].min()}-{cy['year'].max()}, "
    f"{len(cy)} country-year cells"
)
print(
    f"Never-treated countries: {sorted(cy.loc[cy['cohort'] == 0, 'country'].unique())}"
)


# ── Core CS-DiD estimator ────────────────────────────────────────────
def run_cs_did(panel, outcome_col, label, n_boot=500, seed=42):
    """
    Callaway & Sant'Anna group-time ATT estimation.

    Returns dict with group_time_atts list and aggregate summary.
    ATTs for sb_rate are reported in percentage points;
    ATTs for mean_carbon are in kg CO2/USD.
    """
    is_rate = outcome_col == "sb_rate"
    scale = 100.0 if is_rate else 1.0
    unit = "pp" if is_rate else "kg CO2/USD"

    print(f"\n{'=' * 70}")
    print(f"CS-DiD: {label}")
    print(f"{'=' * 70}")

    never_treated = panel[panel["cohort"] == 0]
    control_countries = never_treated["country"].unique()
    cohorts = sorted([c for c in panel["cohort"].unique() if c > 0])

    print(f"  Cohorts: {cohorts}")
    print(
        f"  Never-treated ({len(control_countries)}): "
        f"{', '.join(sorted(control_countries))}"
    )
    print(f"  Outcome: {outcome_col} | Bootstrap: {n_boot} reps")

    all_atts = []
    rng = np.random.default_rng(seed)

    for g in cohorts:
        cohort_data = panel[panel["cohort"] == g]
        cohort_countries = cohort_data["country"].unique()
        base_year = g - 1

        print(
            f"\n  Cohort {g} ({len(cohort_countries)} countries: "
            f"{', '.join(sorted(cohort_countries))})"
        )

        treated_base = cohort_data[cohort_data["year"] == base_year]
        control_base = never_treated[never_treated["year"] == base_year]

        if len(treated_base) == 0 or len(control_base) == 0:
            print(f"    Skipping: no base-year {base_year} data")
            continue

        treated_base_mean = np.average(
            treated_base[outcome_col], weights=treated_base["n"]
        )
        control_base_mean = np.average(
            control_base[outcome_col], weights=control_base["n"]
        )

        for t in range(g, 2024):
            treated_t = cohort_data[cohort_data["year"] == t]
            control_t = never_treated[never_treated["year"] == t]

            if len(treated_t) == 0 or len(control_t) == 0:
                continue

            treated_t_mean = np.average(treated_t[outcome_col], weights=treated_t["n"])
            control_t_mean = np.average(control_t[outcome_col], weights=control_t["n"])

            att = (treated_t_mean - treated_base_mean) - (
                control_t_mean - control_base_mean
            )

            # Bootstrap SE (country-level clustering)
            boot_atts = []
            for _ in range(n_boot):
                tc = rng.choice(
                    cohort_countries, size=len(cohort_countries), replace=True
                )
                cc = rng.choice(
                    control_countries, size=len(control_countries), replace=True
                )

                tb = [
                    treated_base.loc[treated_base["country"] == c, outcome_col].values[
                        0
                    ]
                    for c in tc
                    if c in treated_base["country"].values
                ]
                tp = [
                    treated_t.loc[treated_t["country"] == c, outcome_col].values[0]
                    for c in tc
                    if c in treated_t["country"].values
                ]
                cb = [
                    control_base.loc[control_base["country"] == c, outcome_col].values[
                        0
                    ]
                    for c in cc
                    if c in control_base["country"].values
                ]
                cp = [
                    control_t.loc[control_t["country"] == c, outcome_col].values[0]
                    for c in cc
                    if c in control_t["country"].values
                ]

                if tb and tp and cb and cp:
                    b = (np.mean(tp) - np.mean(tb)) - (np.mean(cp) - np.mean(cb))
                    boot_atts.append(b)

            se = np.std(boot_atts) if boot_atts else np.nan
            t_stat = att / se if se > 0 else np.nan
            p_val = (
                2 * stats.t.sf(abs(t_stat), df=max(1, len(cohort_countries) - 1))
                if not np.isnan(t_stat)
                else np.nan
            )

            event_time = t - g
            all_atts.append(
                {
                    "cohort": int(g),
                    "year": int(t),
                    "event_time": int(event_time),
                    "att": float(att * scale),
                    "se": float(se * scale),
                    "t_stat": float(t_stat),
                    "p_value": float(p_val),
                    "n_treated_countries": int(len(cohort_countries)),
                    "n_control_countries": int(len(control_countries)),
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
                f"    t={t} (e={event_time:+d}): "
                f"ATT={att * scale:+.3f} {unit} "
                f"(SE={se * scale:.3f}, p={p_val:.3f}) {sig}"
            )

    # ── Aggregate ────────────────────────────────────────────────────
    att_df = pd.DataFrame(all_atts)
    post = att_df[att_df["event_time"] >= 0].copy()

    agg = None
    if len(post) > 0:
        N = len(post)
        agg_att = post["att"].mean()
        # SE under independence: sqrt(sum(se_i^2)) / N
        agg_se = np.sqrt(np.sum(post["se"] ** 2)) / N
        agg_t = agg_att / agg_se if agg_se > 0 else np.nan
        agg_p = 2 * stats.t.sf(abs(agg_t), df=N - 1) if not np.isnan(agg_t) else np.nan

        print(f"\n  ── AGGREGATE ATT (equal-weight, {N} cells) ──")
        print(f"    ATT   = {agg_att:+.3f} {unit}")
        print(f"    SE    = {agg_se:.3f}")
        print(f"    t     = {agg_t:.3f}")
        print(f"    p     = {agg_p:.6f}")
        print(
            f"    95%CI = [{agg_att - 1.96 * agg_se:.3f}, "
            f"{agg_att + 1.96 * agg_se:.3f}]"
        )

        agg = {
            "att": float(agg_att),
            "se": float(agg_se),
            "t_stat": float(agg_t),
            "p_value": float(agg_p),
            "ci_lower": float(agg_att - 1.96 * agg_se),
            "ci_upper": float(agg_att + 1.96 * agg_se),
            "n_cells": N,
            "unit": unit,
        }

        # By cohort
        by_cohort = {}
        print("\n  By cohort:")
        for g in cohorts:
            gc = post[post["cohort"] == g]
            if len(gc) == 0:
                continue
            Ng = len(gc)
            c_att = gc["att"].mean()
            c_se = np.sqrt(np.sum(gc["se"] ** 2)) / Ng
            c_t = c_att / c_se if c_se > 0 else np.nan
            c_p = (
                2 * stats.t.sf(abs(c_t), df=max(1, Ng - 1))
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
                f"    Cohort {g}: ATT={c_att:+.3f} {unit} "
                f"(SE={c_se:.3f}, p={c_p:.4f}) {sig}"
            )
            by_cohort[str(g)] = {
                "att": float(c_att),
                "se": float(c_se),
                "t_stat": float(c_t),
                "p_value": float(c_p),
                "n_cells": Ng,
            }
        agg["by_cohort"] = by_cohort

    return {"group_time_atts": all_atts, "aggregate": agg}


# ══════════════════════════════════════════════════════════════════════
# 1. Exclude 2017 cohort
# ══════════════════════════════════════════════════════════════════════
cohort_2017 = sorted(c for c, y in transposition.items() if y == 2017)
panel_no_c2017 = cy[~cy["country"].isin(cohort_2017)].copy()
res1 = run_cs_did(
    panel_no_c2017,
    "sb_rate",
    f"Excluding 2017 cohort ({', '.join(cohort_2017)})",
    n_boot=500,
)

# ══════════════════════════════════════════════════════════════════════
# 2. Exclude calendar year 2018
# ══════════════════════════════════════════════════════════════════════
panel_no_y2018 = cy[cy["year"] != 2018].copy()
res2 = run_cs_did(
    panel_no_y2018, "sb_rate", "Excluding calendar year 2018 from panel", n_boot=500
)

# ══════════════════════════════════════════════════════════════════════
# 3. Carbon intensity as outcome
# ══════════════════════════════════════════════════════════════════════
panel_carbon = cy[cy["mean_carbon"].notna()].copy()
res3 = run_cs_did(
    panel_carbon,
    "mean_carbon",
    "Portfolio carbon intensity (kg CO2/USD) as outcome",
    n_boot=500,
)

# ══════════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════════
output = {
    "sensitivity_1_exclude_2017_cohort": {
        "description": (
            "CS-DiD excluding 2017 cohort countries to confirm aggregate "
            "ATT is not an artifact of averaging with the null 2017 cohort"
        ),
        "excluded_countries": cohort_2017,
        **res1,
    },
    "sensitivity_2_exclude_year_2018": {
        "description": (
            "CS-DiD excluding calendar year 2018 from the panel "
            "(data anomaly year with ~5.79M contracts)"
        ),
        **res2,
    },
    "sensitivity_3_carbon_intensity": {
        "description": (
            "CS-DiD with portfolio carbon intensity (kg CO2/USD) "
            "as outcome variable instead of single-bidder rate"
        ),
        **res3,
    },
    "metadata": {
        "bootstrap_reps": 500,
        "clustering": "country-level",
        "aggregation": "equal-weight across (g,t) cells",
        "base_period": "g-1 (one period before treatment)",
        "comparison_group": "never-treated",
    },
}

with open("results/robustness/cs_did_sensitivity.json", "w") as f:
    json.dump(output, f, indent=2, default=str)

print(f"\n{'=' * 70}")
print("SAVED: results/cs_did_sensitivity.json")
print(f"{'=' * 70}")
