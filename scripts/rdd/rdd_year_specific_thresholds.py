"""
Corrected RDD with year-specific EU thresholds (desk review M4).

The published design pooled 2012-2023 contracts around a single fixed cutoff of
EUR 139,000. But the EU central-government supplies/services threshold is revised
biennially and EUR 139,000 was operative for only two of the twelve sample years.
This script rebuilds the RDD by:

  1. Assigning each contract the OPERATIVE central-government supplies/services
     threshold for its award year.
  2. Excluding works contracts (CPV division 45), which face the ~EUR 5.35M works
     threshold, not the supplies/services band.
  3. Stacking the normalized log-distance to the year-specific cutoff and running
     the same local-linear (triangular kernel, HC2) estimator as the published
     design.

Honest limitations reported alongside:
  - The data contain no buyer-type field, so central- vs sub-central authorities
    cannot be separated. The supplies/services running variable therefore still
    mixes two legal cutoffs (central ~EUR 139k band and sub-central ~EUR 214k band).
    We test the sub-central band as a second candidate cutoff.
  - The old fixed EUR 139k cutoff (held only 2020-21) is run as a placebo: under a
    year-specific reality, a fixed-139k design should mostly capture noise outside
    those two years.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from formal_rdd_estimator import local_linear_rdd, mse_optimal_bandwidth  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "rdd" / "rdd_year_specific_thresholds.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

# EU central-government supplies/services thresholds (EUR), biennial revisions.
# Verified against European Commission delegated regulations / desk-review note.
CENTRAL_SUPPLIES_SERVICES = {
    2012: 130_000, 2013: 130_000, 2014: 134_000, 2015: 134_000,
    2016: 135_000, 2017: 135_000, 2018: 144_000, 2019: 144_000,
    2020: 139_000, 2021: 139_000, 2022: 140_000, 2023: 140_000,
}
# Sub-central authorities supplies/services thresholds (EUR).
SUBCENTRAL_SUPPLIES_SERVICES = {
    2012: 200_000, 2013: 200_000, 2014: 207_000, 2015: 207_000,
    2016: 209_000, 2017: 209_000, 2018: 221_000, 2019: 221_000,
    2020: 214_000, 2021: 214_000, 2022: 215_000, 2023: 215_000,
}
PRIMARY_WINDOW = 0.10
GRID = np.round(np.arange(0.05, 0.31, 0.01), 4)


def load():
    df = pd.read_parquet(PARQUET, columns=[
        "country", "year", "cpv_division", "value_eur",
        "n_bidders", "carbon_intensity_kg_usd"])
    df = df[df["country"] != "CO"].copy()
    df = df[df["value_eur"] > 0].dropna(subset=["value_eur"])
    df["year"] = df["year"].astype(int)
    df = df[df["year"].between(2012, 2023)]
    # Exclude works (CPV division 45) -> supplies/services band only
    df["cpv2"] = df["cpv_division"].astype(str).str.zfill(2)
    df["is_works"] = df["cpv2"] == "45"
    p99c = df["carbon_intensity_kg_usd"].quantile(0.99)
    df["carbon_intensity"] = df["carbon_intensity_kg_usd"].clip(upper=p99c)
    if df["n_bidders"].notna().any():
        p99b = df["n_bidders"].quantile(0.99)
        df["bidder_count"] = df["n_bidders"].clip(upper=p99b)
    return df


def run_design(df, thresholds, label, exclude_works=True):
    d = df.copy()
    if exclude_works:
        d = d[~d["is_works"]]
    d["thr"] = d["year"].map(thresholds)
    d = d.dropna(subset=["thr"])
    d["running_var"] = np.log10(d["value_eur"]) - np.log10(d["thr"])
    d["above"] = (d["running_var"] >= 0).astype(float)

    out = {"label": label, "n_total": int(len(d)),
           "exclude_works": exclude_works, "outcomes": {}}

    for outcome in ["bidder_count", "carbon_intensity"]:
        if outcome not in d.columns:
            continue
        sub = d.dropna(subset=[outcome])
        if len(sub) < 1000:
            continue
        rv = sub["running_var"].values
        y = sub[outcome].values
        dd = sub["above"].values
        h_mse = mse_optimal_bandwidth(rv, y, dd)
        r_primary = local_linear_rdd(rv, y, dd, PRIMARY_WINDOW)
        r_mse = local_linear_rdd(rv, y, dd, h_mse)
        grid = [local_linear_rdd(rv, y, dd, h) for h in GRID]
        grid = [g for g in grid if g["tau"] is not None]
        n_neg = sum(1 for g in grid if g["tau"] < 0)
        n_sig = sum(1 for g in grid if g["significant_005"])
        out["outcomes"][outcome] = {
            "n": int(len(sub)),
            "mse_bandwidth": h_mse,
            "primary_pm010": {k: r_primary[k] for k in
                              ("tau", "se", "t_stat", "p_value", "n_obs")},
            "mse_optimal": {k: r_mse[k] for k in
                            ("tau", "se", "t_stat", "p_value", "n_obs")},
            "grid_n": len(grid),
            "grid_n_negative": n_neg,
            "grid_n_significant": n_sig,
        }
    return out


def main():
    df = load()
    print(f"Loaded {len(df):,} EU-context contracts (2012-2023)")
    results = {"designs": {}}

    designs = [
        ("year_specific_central", CENTRAL_SUPPLIES_SERVICES, True),
        ("year_specific_subcentral", SUBCENTRAL_SUPPLIES_SERVICES, True),
        ("fixed_139k_placebo", {y: 139_000 for y in range(2012, 2024)}, True),
        ("fixed_139k_with_works", {y: 139_000 for y in range(2012, 2024)}, False),
    ]
    for label, thr, excl in designs:
        print(f"\n=== {label} ===")
        res = run_design(df, thr, label, exclude_works=excl)
        results["designs"][label] = res
        for oc, r in res["outcomes"].items():
            p = r["primary_pm010"]; m = r["mse_optimal"]
            print(f"  {oc}: primary tau={p['tau']} (p={p['p_value']}, N={p['n_obs']:,}) | "
                  f"MSE tau={m['tau']} (p={m['p_value']}) | "
                  f"grid {r['grid_n_negative']}/{r['grid_n']} neg, "
                  f"{r['grid_n_significant']}/{r['grid_n']} sig")

    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
