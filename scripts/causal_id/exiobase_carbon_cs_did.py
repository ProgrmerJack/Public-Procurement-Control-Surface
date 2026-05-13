#!/usr/bin/env python3
"""
EXIOBASE-Based Carbon-Gap Callaway & Sant'Anna DiD
===================================================
Formal C&S (2021) group-time ATT estimation for the primary carbon-gap claim.

Outcome: Country-year SB-minus-MB EXIOBASE carbon-intensity gap (kg CO₂e/USD)
         (already in the parquet as carbon_intensity_kg_usd)

Treatment: EU Directive 2014/24/EU staggered transposition (2016–2018 cohorts)
Control:   Norway (NO) + Switzerland (CH) — never-treated countries
           (Colombia excluded as non-comparable; GB = post-Brexit treated)

This directly formalizes the "66% narrowing" claim (pre=0.124, post=0.043 kg/USD)
with a proper C&S group-time ATT identification strategy, replacing the current
interrupted time series (ITS) which lacks a control group.

Reference:
    Callaway, B. & Sant'Anna, P.H.C. (2021). Difference-in-differences with
    multiple time periods. Journal of Econometrics, 225(2), 200-230.

Output: results/causal_id/exiobase_carbon_cs_did.json
"""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "results" / "causal_id"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Treatment cohort assignment ────────────────────────────────────────────────
# Based on EU Directive 2014/24/EU transposition year
# GB treated 2015 (pre-Brexit enforcement)
# 13 major economies: 2016 transposition
# Remaining: 2017 (3 countries), 2018 (ES, GR, LU)
COHORT_MAP = {
    "GB": 2015,
    "AT": 2016,
    "BE": 2016,
    "DE": 2016,
    "DK": 2016,
    "EE": 2016,
    "FI": 2016,
    "FR": 2016,
    "HU": 2016,
    "IE": 2016,
    "IT": 2016,
    "LT": 2016,
    "NL": 2016,
    "SE": 2016,
    "CZ": 2017,
    "LV": 2017,
    "PT": 2017,
    "SI": 2017,
    "SK": 2017,
    "PL": 2017,
    "ES": 2018,
    "GR": 2018,
    "LU": 2018,
}

NEVER_TREATED = {"NO", "CH"}
MIN_CONTRACTS = 20  # minimum SB and MB contracts per country-year cell
MAX_CI = 10.0  # outlier cap (carbon_intensity_kg_usd > 10 is unrealistic)


def load_panel() -> pd.DataFrame:
    """
    Load EXIOBASE-based country-year carbon gap panel.
    Returns panel with columns: country, year, gap, sb_mean, mb_mean,
    cohort, is_treated, is_control, post.
    """
    path = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"

    cols = ["country", "year", "single_bidder", "carbon_intensity_kg_usd"]
    table = pq.read_table(str(path), columns=cols)
    df = table.to_pandas()

    # Year filter
    df = df[df["year"].between(2012, 2023)].copy()

    # Drop unrealistic carbon intensities
    df = df[df["carbon_intensity_kg_usd"] > 0]
    df = df[df["carbon_intensity_kg_usd"] <= MAX_CI]
    df = df.dropna(subset=["carbon_intensity_kg_usd", "single_bidder"])

    # Exclude Colombia (not a comparator country) and Iceland (too small)
    df = df[~df["country"].isin({"CO", "IS"})]

    print(f"[INFO] Loaded {len(df):,} contracts (excl. CO, IS)")

    # Build country-year SB vs MB gap
    gaps = []
    for (country, year), grp in df.groupby(["country", "year"]):
        sb = grp[grp["single_bidder"] == True]["carbon_intensity_kg_usd"]
        mb = grp[grp["single_bidder"] == False]["carbon_intensity_kg_usd"]

        if len(sb) < MIN_CONTRACTS or len(mb) < MIN_CONTRACTS:
            continue

        sb_mean = float(sb.mean())
        mb_mean = float(mb.mean())
        gap = sb_mean - mb_mean  # positive → SB contracts go to higher-carbon sectors

        gaps.append(
            {
                "country": country,
                "year": int(year),
                "gap": gap,
                "sb_mean": sb_mean,
                "mb_mean": mb_mean,
                "n_sb": len(sb),
                "n_mb": len(mb),
            }
        )

    panel = pd.DataFrame(gaps)
    print(
        f"[INFO] Country-year cells: {len(panel)} (≥{MIN_CONTRACTS} SB & MB contracts each)"
    )

    # Add treatment structure
    panel["cohort"] = panel["country"].map(COHORT_MAP)
    panel["is_treated"] = panel["cohort"].notna()
    panel["is_control"] = panel["country"].isin(NEVER_TREATED)

    # For C&S, we need treatment to be a well-defined cohort or never-treated
    # Exclude countries that are neither treated nor control (e.g., CH and NO are control, rest EU are treated)
    panel = panel[panel["is_treated"] | panel["is_control"]].copy()

    panel["post"] = panel["year"] >= panel["cohort"].fillna(9999)
    panel["years_since"] = (panel["year"] - panel["cohort"].fillna(9999)).astype(float)

    return panel


def compute_att_gt(panel: pd.DataFrame, g: int, t: int) -> dict | None:
    """
    Compute ATT(g, t) for cohort g at calendar year t using never-treated controls.

    ATT(g, t) = E[ΔY(t, g-1) | G=g] - E[ΔY(t, g-1) | C]

    where ΔY(t, g-1) = Y(t) - Y(g-1), G=g is the treatment cohort,
    C is the never-treated group (NO, CH).
    """
    baseline = g - 1

    # Treatment group observations
    treat_t = panel[(panel["cohort"] == g) & (panel["year"] == t)]["gap"]
    treat_b = panel[(panel["cohort"] == g) & (panel["year"] == baseline)]["gap"]

    # Never-treated control observations
    ctrl_t = panel[(panel["is_control"]) & (panel["year"] == t)]["gap"]
    ctrl_b = panel[(panel["is_control"]) & (panel["year"] == baseline)]["gap"]

    if len(treat_t) == 0 or len(treat_b) == 0:
        return None
    if len(ctrl_t) == 0 or len(ctrl_b) == 0:
        return None

    delta_treat = float(treat_t.mean() - treat_b.mean())
    delta_ctrl = float(ctrl_t.mean() - ctrl_b.mean())
    att = delta_treat - delta_ctrl

    n_t = len(treat_t)
    n_b = len(treat_b)
    n_ct = len(ctrl_t)
    n_cb = len(ctrl_b)

    # Delta-method SE
    var = (
        treat_t.var(ddof=1) / n_t
        + treat_b.var(ddof=1) / n_b
        + (ctrl_t.var(ddof=1) / n_ct if n_ct > 1 else 0.0)
        + (ctrl_b.var(ddof=1) / n_cb if n_cb > 1 else 0.0)
    )
    se = float(np.sqrt(var)) if var > 0 else np.nan
    t_stat = att / se if (se > 0 and not np.isnan(se)) else np.nan
    df_dof = n_t + n_ct - 2
    p_value = (
        float(2 * stats.t.sf(abs(t_stat), df=df_dof))
        if not np.isnan(t_stat)
        else np.nan
    )

    return {
        "cohort": g,
        "year": t,
        "event_time": t - g,
        "att": round(att, 6),
        "se": round(se, 6) if not np.isnan(se) else None,
        "t_stat": round(t_stat, 4) if not np.isnan(t_stat) else None,
        "p_value": round(p_value, 6) if not np.isnan(p_value) else None,
        "delta_treat": round(delta_treat, 6),
        "delta_ctrl": round(delta_ctrl, 6),
        "n_treated": n_t,
        "n_control": n_ct,
        "pre_period": (t - g) < 0,
    }


def aggregate_att(gt_atts: list) -> dict:
    """
    Aggregate ATT: weighted average of post-treatment group-time ATTs.
    Weights = number of treated observations (n_treated).
    """
    post = [
        r
        for r in gt_atts
        if r is not None and not r["pre_period"] and r["att"] is not None
    ]
    if not post:
        return {"att": None, "se": None, "n_cells": 0}

    weights = np.array([r["n_treated"] for r in post], dtype=float)
    atts = np.array([r["att"] for r in post])
    ses = np.array([r["se"] if r["se"] is not None else np.nan for r in post])

    weights /= weights.sum()
    agg_att = float(np.sum(weights * atts))

    # Propagate SE via squared sum (assumes approximate independence)
    valid_ses = ~np.isnan(ses)
    if valid_ses.sum() > 0:
        agg_se = float(np.sqrt(np.sum((weights[valid_ses] * ses[valid_ses]) ** 2)))
    else:
        agg_se = np.nan

    t_stat = agg_att / agg_se if (agg_se > 0 and not np.isnan(agg_se)) else np.nan
    p_value = float(2 * stats.norm.sf(abs(t_stat))) if not np.isnan(t_stat) else np.nan

    return {
        "att": round(agg_att, 6),
        "se": round(agg_se, 6) if not np.isnan(agg_se) else None,
        "t_stat": round(float(t_stat), 4) if not np.isnan(t_stat) else None,
        "p_value": round(float(p_value), 6) if not np.isnan(p_value) else None,
        "ci_lower_95": round(agg_att - 1.96 * agg_se, 6)
        if not np.isnan(agg_se)
        else None,
        "ci_upper_95": round(agg_att + 1.96 * agg_se, 6)
        if not np.isnan(agg_se)
        else None,
        "n_cells": len(post),
        "n_cohorts": len(set(r["cohort"] for r in post)),
    }


def cluster_bootstrap(panel: pd.DataFrame, gt_atts: list, B: int = 500) -> dict:
    """
    Wild cluster bootstrap at country level for inference on aggregate ATT.
    """
    post = [
        r
        for r in gt_atts
        if r is not None and not r["pre_period"] and r["att"] is not None
    ]
    if not post:
        return {"p_value_boot": None, "ci_lower": None, "ci_upper": None}

    observed = np.mean([r["att"] for r in post])
    countries = list(panel["country"].unique())
    rng = np.random.default_rng(seed=42)
    boot_atts = []

    for _ in range(B):
        sampled = rng.choice(countries, size=len(countries), replace=True)
        boot_panel = pd.concat(
            [panel[panel["country"] == c] for c in sampled], ignore_index=True
        )

        boot_post = []
        for r in post:
            g, t = r["cohort"], r["year"]
            baseline = g - 1
            bt = boot_panel[(boot_panel["cohort"] == g) & (boot_panel["year"] == t)][
                "gap"
            ]
            bb = boot_panel[
                (boot_panel["cohort"] == g) & (boot_panel["year"] == baseline)
            ]["gap"]
            ct = boot_panel[(boot_panel["is_control"]) & (boot_panel["year"] == t)][
                "gap"
            ]
            cb = boot_panel[
                (boot_panel["is_control"]) & (boot_panel["year"] == baseline)
            ]["gap"]
            if all(len(x) > 0 for x in [bt, bb, ct, cb]):
                boot_post.append((bt.mean() - bb.mean()) - (ct.mean() - cb.mean()))

        if boot_post:
            boot_atts.append(np.mean(boot_post))

    boot_atts = np.array(boot_atts)
    boot_centered = boot_atts - np.mean(boot_atts)
    p_boot = float(np.mean(np.abs(boot_centered) >= np.abs(observed)))

    return {
        "p_value_boot": round(p_boot, 4),
        "ci_lower_95_boot": round(float(np.percentile(boot_atts, 2.5)), 6),
        "ci_upper_95_boot": round(float(np.percentile(boot_atts, 97.5)), 6),
        "n_bootstrap": B,
    }


def its_comparison(panel: pd.DataFrame) -> dict:
    """Compare ITS (no control) to DiD for transparency."""
    eu = panel[panel["is_treated"]]
    ctrl = panel[panel["is_control"]]

    eu_pre = eu[eu["year"] <= 2015]["gap"].values
    eu_post = eu[eu["year"] >= 2017]["gap"].values

    ctrl_pre = ctrl[ctrl["year"] <= 2015]["gap"].values
    ctrl_post = ctrl[ctrl["year"] >= 2017]["gap"].values

    eu_change = float(np.mean(eu_post) - np.mean(eu_pre))
    ctrl_change = (
        float(np.mean(ctrl_post) - np.mean(ctrl_pre)) if len(ctrl_post) > 0 else 0.0
    )
    did = eu_change - ctrl_change

    t_its, p_its = stats.ttest_ind(eu_post, eu_pre)

    pre_mean = float(np.mean(eu_pre))
    post_mean = float(np.mean(eu_post))
    pct_reduction = (
        (pre_mean - post_mean) / abs(pre_mean) * 100 if pre_mean != 0 else None
    )

    return {
        "its": {
            "pre_gap_mean": round(pre_mean, 6),
            "post_gap_mean": round(post_mean, 6),
            "eu_change": round(eu_change, 6),
            "pct_reduction": round(pct_reduction, 2) if pct_reduction else None,
            "t_stat": round(float(t_its), 4),
            "p_value": round(float(p_its), 6),
        },
        "control_trend": {
            "pre_gap_mean": round(float(np.mean(ctrl_pre)), 6)
            if len(ctrl_pre) > 0
            else None,
            "post_gap_mean": round(float(np.mean(ctrl_post)), 6)
            if len(ctrl_post) > 0
            else None,
            "change": round(ctrl_change, 6),
        },
        "did_simple": {
            "eu_change_minus_ctrl_change": round(did, 6),
            "note": "Simple 2x2 DiD — C&S group-time ATT above is the formal estimate",
        },
    }


def main():
    print("=" * 70)
    print("EXIOBASE Carbon-Gap C&S DiD")
    print("Outcome: Country-year SB minus MB EXIOBASE carbon intensity gap")
    print("Control: Norway (NO) + Switzerland (CH) [never-treated]")
    print("=" * 70)

    panel = load_panel()

    print(f"\n[Panel summary]")
    treated = sorted(panel[panel["is_treated"]]["country"].unique().tolist())
    controls = sorted(panel[panel["is_control"]]["country"].unique().tolist())
    print(f"  Treated countries: {treated}")
    print(f"  Control countries: {controls}")
    years = sorted(panel["year"].unique().tolist())
    print(f"  Years: {years[0]} – {years[-1]}")
    print(f"  Total cells: {len(panel)}")

    # ITS comparison first
    its = its_comparison(panel)
    print(f"\n[ITS comparison (EU vs itself, no control)]")
    print(f"  Pre-reform mean gap: {its['its']['pre_gap_mean']:.5f} kg/USD")
    print(f"  Post-reform mean gap: {its['its']['post_gap_mean']:.5f} kg/USD")
    print(f"  Change: {its['its']['pct_reduction']:.1f}% reduction")
    print(f"  ITS t={its['its']['t_stat']:.3f}, p={its['its']['p_value']:.5f}")
    print(
        f"  Control trend: {its['control_trend']['change']:+.5f} kg/USD (diffs it out)"
    )

    # Compute C&S group-time ATTs
    print("\n[Computing C&S group-time ATTs...]")
    cohorts = sorted([c for c in panel["cohort"].dropna().unique() if not pd.isna(c)])
    years_list = sorted(panel["year"].unique().tolist())

    gt_atts = []
    for g in cohorts:
        g = int(g)
        for t in years_list:
            t = int(t)
            if t < g - 3:  # allow 3 pre-treatment periods
                continue
            result = compute_att_gt(panel, g, t)
            if result is not None:
                gt_atts.append(result)
                pre_post = "PRE" if result["pre_period"] else "POST"
                sig = (
                    "***"
                    if result["p_value"] is not None and result["p_value"] < 0.001
                    else (
                        "**"
                        if result["p_value"] is not None and result["p_value"] < 0.01
                        else (
                            "*"
                            if result["p_value"] is not None
                            and result["p_value"] < 0.05
                            else ""
                        )
                    )
                )
                t_str = (
                    f"{result['t_stat']:.3f}" if result["t_stat"] is not None else "N/A"
                )
                p_str = (
                    f"{result['p_value']:.4f}"
                    if result["p_value"] is not None
                    else "N/A"
                )
                att_str = f"{result['att']:+.5f}"
                print(
                    f"  ATT({g},{t}) [e={t - g:+d}]: {att_str} kg/USD "
                    f"(t={t_str}, p={p_str}) {pre_post} {sig}"
                )

    # Aggregate ATT
    print("\n[Aggregate ATT (post-treatment, weighted by n_treated)]")
    agg = aggregate_att(gt_atts)
    if agg["att"] is not None:
        print(
            f"  ATT = {agg['att']:+.5f} kg/USD (SE={agg['se']}, t={agg['t_stat']}, p={agg['p_value']})"
        )
        print(f"  95% CI: [{agg['ci_lower_95']:.5f}, {agg['ci_upper_95']:.5f}]")

        # Express as % of pre-reform SB mean for manuscript
        sb_pre = its["its"]["pre_gap_mean"]
        if sb_pre != 0 and agg["att"] is not None:
            att_pct = agg["att"] / abs(sb_pre) * 100
            print(f"  ATT as % of pre-reform gap: {att_pct:+.1f}%")

    # Bootstrap
    print(f"\n[Cluster bootstrap (B=500, country-level clusters)]")
    boot = cluster_bootstrap(panel, gt_atts, B=500)
    print(f"  Bootstrap p = {boot['p_value_boot']}")
    print(
        f"  Bootstrap 95% CI: [{boot['ci_lower_95_boot']:.5f}, {boot['ci_upper_95_boot']:.5f}]"
    )

    # Event-study aggregation by event time
    event_agg = defaultdict(list)
    for r in gt_atts:
        if r is not None:
            event_agg[r["event_time"]].append(r["att"])
    event_study = {
        str(et): {
            "mean_att": round(float(np.mean(v)), 6),
            "se": round(float(np.std(v, ddof=1) / np.sqrt(len(v))), 6)
            if len(v) > 1
            else None,
            "n_cohorts": len(v),
            "pre_period": et < 0,
        }
        for et, v in sorted(event_agg.items())
    }

    print("\n[Event-study ATTs by event time]")
    for et, v in sorted(event_agg.items()):
        mean_v = np.mean(v)
        se_v = np.std(v, ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0
        pre_post = "PRE" if et < 0 else "POST"
        print(
            f"  Event {et:+d}: ATT = {mean_v:+.5f} ± {se_v:.5f} kg/USD ({pre_post}, n_cohorts={len(v)})"
        )

    # Pre-trend slope test
    pre_data = [
        (r["event_time"], r["att"])
        for r in gt_atts
        if r is not None and r["pre_period"] and r["att"] is not None
    ]
    if len(pre_data) >= 2:
        pre_et = np.array([x[0] for x in pre_data])
        pre_att = np.array([x[1] for x in pre_data])
        slope, intercept, r_val, p_slope, se_slope = stats.linregress(pre_et, pre_att)
        pre_trend = {
            "slope": round(float(slope), 6),
            "p_value": round(float(p_slope), 4),
            "r_squared": round(float(r_val**2), 4),
            "parallel_trends_supported": p_slope > 0.10,
        }
        print(f"\n[Pre-trend test]")
        print(f"  Slope: {slope:+.5f} kg/USD per year, p={p_slope:.4f}")
        print(
            f"  Parallel trends: {'SUPPORTED (p>0.10)' if p_slope > 0.10 else 'POTENTIAL VIOLATION (p<0.10)'}"
        )
    else:
        pre_trend = {"slope": None, "p_value": None, "parallel_trends_supported": None}

    # Save results
    results = {
        "specification": "Callaway_SantAnna_2021_EXIOBASE_Carbon_Gap_DiD",
        "outcome": "country_year_SB_minus_MB_EXIOBASE_carbon_intensity_gap_kg_per_usd",
        "treatment": "EU_Directive_2014_24_EU_staggered_transposition",
        "control_group": "Norway_CH_never_treated",
        "data_source": "EXIOBASE-derived carbon_intensity_kg_usd (gprd_with_carbon.parquet)",
        "panel_summary": {
            "n_cells": len(panel),
            "n_treated_countries": int(panel[panel["is_treated"]]["country"].nunique()),
            "n_control_countries": int(panel[panel["is_control"]]["country"].nunique()),
            "treated_countries": treated,
            "control_countries": controls,
            "cohorts": [int(c) for c in cohorts],
            "years": years_list,
        },
        "aggregate_att": agg,
        "bootstrap_inference": boot,
        "pre_trend_test": pre_trend,
        "event_study": event_study,
        "its_comparison": its,
        "group_time_atts": gt_atts,
        "methodology_notes": [
            "Outcome: country-year average carbon intensity gap (SB mean - MB mean) in kg CO2e/USD",
            "Carbon intensities from EXIOBASE (assigned to contracts by CPV/sector matching)",
            "Minimum 20 SB and 20 MB contracts per country-year cell",
            "C&S group-time ATT uses NO+CH as never-treated clean comparison group",
            "Aggregate ATT weighted by cohort size (n_treated contracts per cell)",
            "Pre-trend test: slope of pre-treatment ATT(g,t) vs event time",
            "Cluster bootstrap at country level (B=500) for inference",
            "This formalizes the '66% narrowing' ITS result with proper counterfactual",
        ],
    }

    out_path = RESULTS_DIR / "exiobase_carbon_cs_did.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n[SAVED] {out_path}")

    # Manuscript headline
    print("\n" + "=" * 70)
    print("MANUSCRIPT HEADLINE:")
    print(
        f"  ITS (existing): pre-gap = {its['its']['pre_gap_mean']:.5f}, post-gap = {its['its']['post_gap_mean']:.5f}"
    )
    print(
        f"  ITS: {its['its']['pct_reduction']:.1f}% reduction, p={its['its']['p_value']:.5f}"
    )
    if agg["att"] is not None:
        print(
            f"  C&S ATT: {agg['att']:+.5f} kg/USD (SE={agg['se']}, t={agg['t_stat']}, p={agg['p_value']})"
        )
        print(f"  C&S 95% CI: [{agg['ci_lower_95']:.5f}, {agg['ci_upper_95']:.5f}]")
        print(f"  Bootstrap p: {boot['p_value_boot']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
