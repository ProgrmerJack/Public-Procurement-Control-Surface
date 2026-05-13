"""
Callaway & Sant'Anna leave-one-out for NEVER-TREATED CONTROLS.

Addresses R1-Severe reviewer concern: the primary specification uses both
Norway (NO) and Switzerland (CH) as never-treated comparators. Does the
C&S ATT depend on which control country anchors the counterfactual?

Three runs:
  1. Both NO + CH  (replication of primary)
  2. Norway only   (CH excluded)
  3. Switzerland only (NO excluded)

With only ONE control country the bootstrap is modified: the control side
is held deterministically fixed; uncertainty derives entirely from the
treated-country resampling. This is the principled approach when the
control pool is a singleton.

Results saved to: results/robustness/cs_loo_controls.json
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


def run_cs_loo(control_subset, label, n_boot=1000, seed=42):
    """
    C&S DiD restricted to the given control_subset.

    Bootstrap SE:
      - Multiple controls (len>=2): resample both treated AND control sides.
      - Single control  (len==1):  resample ONLY treated side; control is
        deterministic, so resampling it adds no uncertainty.
    """
    print(f"\n{'=' * 70}")
    print(f"C&S LOO: {label}")
    print(f"{'=' * 70}")

    analysis_countries = set(TRANSPOSITION) | set(control_subset)
    panel = df[df["country"].isin(analysis_countries)].copy()
    panel["cohort"] = panel["country"].map(TRANSPOSITION).fillna(0).astype(int)

    cy = (
        panel.groupby(["country", "year"])
        .agg(sb_rate=("single_bidder", "mean"), n=("single_bidder", "count"))
        .reset_index()
    )
    cy["cohort"] = cy["country"].map(TRANSPOSITION).fillna(0).astype(int)

    never_treated = cy[cy["cohort"] == 0]
    control_countries = np.array(sorted(never_treated["country"].unique()))
    cohorts = sorted(c for c in cy["cohort"].unique() if c > 0)
    single_ctrl = len(control_countries) == 1

    print(f"  Controls ({len(control_countries)}): {', '.join(control_countries)}")
    print(f"  Treated cohorts: {cohorts}")
    print(
        f"  Bootstrap mode: {'treated-only resampling' if single_ctrl else 'full resampling'}"
    )

    all_atts = []
    rng = np.random.default_rng(seed)

    for g in cohorts:
        cohort_data = cy[cy["cohort"] == g]
        cohort_countries = np.array(sorted(cohort_data["country"].unique()))
        base_year = g - 1

        tb_df = cohort_data[cohort_data["year"] == base_year]
        cb_df = never_treated[never_treated["year"] == base_year]

        if len(tb_df) == 0 or len(cb_df) == 0:
            continue

        tb_mean = np.average(tb_df["sb_rate"], weights=tb_df["n"])
        cb_mean = np.average(cb_df["sb_rate"], weights=cb_df["n"])

        for t in range(g, 2024):
            tp_df = cohort_data[cohort_data["year"] == t]
            cp_df = never_treated[never_treated["year"] == t]

            if len(tp_df) == 0 or len(cp_df) == 0:
                continue

            tp_mean = np.average(tp_df["sb_rate"], weights=tp_df["n"])
            cp_mean = np.average(cp_df["sb_rate"], weights=cp_df["n"])

            att = (tp_mean - tb_mean) - (cp_mean - cb_mean)

            # ── Bootstrap SE ─────────────────────────────────────────
            boot_atts = []
            for _ in range(n_boot):
                # Resample treated countries
                tc = rng.choice(
                    cohort_countries, size=len(cohort_countries), replace=True
                )

                # Resample controls only if >1 country available
                if single_ctrl:
                    # Control side is deterministic — no resampling adds variance
                    cb_vals = [
                        cb_df.loc[cb_df["country"] == c, "sb_rate"].values[0]
                        for c in control_countries
                        if c in cb_df["country"].values
                    ]
                    cp_vals = [
                        cp_df.loc[cp_df["country"] == c, "sb_rate"].values[0]
                        for c in control_countries
                        if c in cp_df["country"].values
                    ]
                else:
                    cc = rng.choice(
                        control_countries, size=len(control_countries), replace=True
                    )
                    cb_vals = [
                        cb_df.loc[cb_df["country"] == c, "sb_rate"].values[0]
                        for c in cc
                        if c in cb_df["country"].values
                    ]
                    cp_vals = [
                        cp_df.loc[cp_df["country"] == c, "sb_rate"].values[0]
                        for c in cc
                        if c in cp_df["country"].values
                    ]

                tb_vals = [
                    tb_df.loc[tb_df["country"] == c, "sb_rate"].values[0]
                    for c in tc
                    if c in tb_df["country"].values
                ]
                tp_vals = [
                    tp_df.loc[tp_df["country"] == c, "sb_rate"].values[0]
                    for c in tc
                    if c in tp_df["country"].values
                ]

                if tb_vals and tp_vals and cb_vals and cp_vals:
                    b = (np.mean(tp_vals) - np.mean(tb_vals)) - (
                        np.mean(cp_vals) - np.mean(cb_vals)
                    )
                    boot_atts.append(b)

            se = np.std(boot_atts) if len(boot_atts) >= 10 else np.nan
            t_stat = att / se if (se and se > 0) else np.nan
            df_deg = max(1, len(cohort_countries) - 1)
            p_val = (
                2 * stats.t.sf(abs(t_stat), df=df_deg)
                if not np.isnan(t_stat)
                else np.nan
            )

            event_time = t - g
            all_atts.append(
                {
                    "cohort": int(g),
                    "year": int(t),
                    "event_time": int(event_time),
                    "att": float(att * 100),
                    "se": float(se * 100) if not np.isnan(se) else None,
                    "t_stat": float(t_stat) if not np.isnan(t_stat) else None,
                    "p_value": float(p_val) if not np.isnan(p_val) else None,
                    "n_treated": int(len(cohort_countries)),
                    "n_control": int(len(control_countries)),
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
                f"  g={g}, t={t} (e={event_time:+d}): "
                f"ATT={att * 100:+.2f}pp "
                f"(SE={se * 100:.2f}, p={p_val:.3f}) {sig}"
            )

    # ── Aggregate ────────────────────────────────────────────────────
    att_df = pd.DataFrame(all_atts)
    post = att_df[(att_df["event_time"] >= 0) & att_df["se"].notna()].copy()

    agg = None
    if len(post) > 0:
        N = len(post)
        agg_att = post["att"].mean()
        agg_se = np.sqrt(np.sum(post["se"] ** 2)) / N
        agg_t = agg_att / agg_se if agg_se > 0 else np.nan
        agg_p = 2 * stats.t.sf(abs(agg_t), df=N - 1) if not np.isnan(agg_t) else np.nan

        print(f"\n  ── AGGREGATE ATT ({N} cells) ──")
        print(f"    ATT   = {agg_att:+.3f} pp")
        print(f"    SE    = {agg_se:.3f}")
        print(f"    t     = {agg_t:.3f}")
        print(f"    p     = {agg_p:.6f}")
        print(
            f"    95%CI = [{agg_att - 1.96 * agg_se:.3f}, "
            f"{agg_att + 1.96 * agg_se:.3f}] pp"
        )

        # Cohort-specific aggregates
        by_cohort = {}
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
            by_cohort[str(g)] = {
                "att_pp": float(c_att),
                "se_pp": float(c_se),
                "t_stat": float(c_t),
                "p_value": float(c_p),
                "n_cells": Ng,
            }

        agg = {
            "att_pp": float(agg_att),
            "se_pp": float(agg_se),
            "t_stat": float(agg_t),
            "p_value": float(agg_p),
            "ci_lower": float(agg_att - 1.96 * agg_se),
            "ci_upper": float(agg_att + 1.96 * agg_se),
            "n_cells": N,
            "by_cohort": by_cohort,
        }

    return {
        "label": label,
        "controls": list(control_subset),
        "bootstrap_mode": "treated-only" if single_ctrl else "full",
        "aggregate": agg,
        "group_time_atts": all_atts,
    }


# ══════════════════════════════════════════════════════════════════════
# Run three specifications
# ══════════════════════════════════════════════════════════════════════
primary = run_cs_loo(["NO", "CH"], "Both controls (primary; replication)", n_boot=1000)
norway_only = run_cs_loo(["NO"], "Norway only (exclude Switzerland)", n_boot=1000)
swiss_only = run_cs_loo(["CH"], "Switzerland only (exclude Norway)", n_boot=1000)

# ── Save ─────────────────────────────────────────────────────────────
output = {
    "description": (
        "C&S DiD leave-one-out for never-treated controls. "
        "Primary: both NO+CH. LOO-1: Norway only. LOO-2: Switzerland only. "
        "With a single control country the bootstrap resamples only the "
        "treated side (control side is deterministic)."
    ),
    "both_controls": primary,
    "norway_only": norway_only,
    "switzerland_only": swiss_only,
    "metadata": {
        "bootstrap_reps": 1000,
        "clustering": "country-level",
        "aggregation": "equal-weight across post (g,t) cells",
        "base_period": "g-1",
        "comparison": "never-treated",
        "single_ctrl_bootstrap": "treated-only resampling (control deterministic)",
    },
}

with open("results/robustness/cs_loo_controls.json", "w") as f:
    json.dump(output, f, indent=2, default=str)

print(f"\n{'=' * 70}")
print("SAVED: results/robustness/cs_loo_controls.json")
print(f"{'=' * 70}")

# ── Summary table ─────────────────────────────────────────────────────
print("\n── SUMMARY ──────────────────────────────────────────────────────")
print(
    f"{'Specification':<30} {'ATT (pp)':>10} {'SE':>6} {'p-value':>10} {'95% CI':>20}"
)
print("-" * 80)
for key, res in [
    ("Both (NO+CH)", primary),
    ("Norway only", norway_only),
    ("Switzerland only", swiss_only),
]:
    agg = res["aggregate"]
    if agg:
        ci = f"[{agg['ci_lower']:.2f}, {agg['ci_upper']:.2f}]"
        print(
            f"{key:<30} {agg['att_pp']:>10.3f} {agg['se_pp']:>6.3f} "
            f"{agg['p_value']:>10.4f} {ci:>20}"
        )
    else:
        print(f"{key:<30} {'N/A':>10}")
