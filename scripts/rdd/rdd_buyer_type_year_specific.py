"""
Buyer-type-specific RDD at year-specific cutoffs (publication plan Item 4).

The dead fixed-EUR139k RDD failed because (i) the cutoff is revised biennially and
(ii) central vs sub-central authorities face different cutoffs and the final
parquet lacked buyer type. The HARMONIZED TED layer, however, carries `buyer_type`
and `contract_type`. We use them to run the legally-correct design:

  CENTRAL authorities (Central government, national agency, EU institution),
  supplies/services -> face the central cutoff (~EUR130-140k band, year-specific).
  SUB-CENTRAL authorities (regional agency, body governed by public law),
  supplies/services -> face the sub-central cutoff (~EUR200-215k band).

Falsification design:
  - Central buyers should show a bidder-count discontinuity AT the central cutoff
    and NO discontinuity at the (placebo) sub-central cutoff.
  - Sub-central buyers should show a discontinuity AT the sub-central cutoff and
    NONE at the (placebo) central cutoff.

The corrupted 2018 vintage is dropped throughout.

Output: results/rdd/rdd_buyer_type_year_specific.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from formal_rdd_estimator import local_linear_rdd, mse_optimal_bandwidth  # noqa

ROOT = Path(__file__).resolve().parents[2]
TED = ROOT / "Data" / "processed" / "eu_ted" / "eu_ted_harmonized.parquet"
OUT = ROOT / "results" / "rdd" / "rdd_buyer_type_year_specific.json"

CENTRAL = {2012: 130_000, 2013: 130_000, 2014: 134_000, 2015: 134_000,
           2016: 135_000, 2017: 135_000, 2018: 144_000, 2019: 144_000,
           2020: 139_000, 2021: 139_000, 2022: 140_000, 2023: 140_000}
SUBCENTRAL = {2012: 200_000, 2013: 200_000, 2014: 207_000, 2015: 207_000,
              2016: 209_000, 2017: 209_000, 2018: 221_000, 2019: 221_000,
              2020: 214_000, 2021: 214_000, 2022: 215_000, 2023: 215_000}
CENTRAL_BUYERS = {"Central government", "National agency", "EU institution"}
SUBCENTRAL_BUYERS = {"Regional agency", "Body governed by public law"}
PRIMARY_WINDOW = 0.10
GRID = np.round(np.arange(0.05, 0.31, 0.01), 4)


def rdd_on(sub, thresholds, label):
    d = sub.copy()
    d["thr"] = d["year"].map(thresholds)
    d = d.dropna(subset=["thr"])
    d["rv"] = np.log10(d["value_eur"]) - np.log10(d["thr"])
    d["above"] = (d["rv"] >= 0).astype(float)
    d = d.dropna(subset=["bidder_count"])
    if len(d) < 2000:
        return {"label": label, "n": int(len(d)), "insufficient": True}
    rv, y, a = d["rv"].values, d["bidder_count"].values, d["above"].values
    h = mse_optimal_bandwidth(rv, y, a)
    rp = local_linear_rdd(rv, y, a, PRIMARY_WINDOW)
    rm = local_linear_rdd(rv, y, a, h)
    grid = [g for g in (local_linear_rdd(rv, y, a, b) for b in GRID)
            if g["tau"] is not None]
    return {
        "label": label, "n": int(len(d)), "mse_bandwidth": h,
        "primary_pm010": {k: rp[k] for k in ("tau", "se", "t_stat", "p_value", "n_obs")},
        "mse_optimal": {k: rm[k] for k in ("tau", "se", "t_stat", "p_value", "n_obs")},
        "grid_n": len(grid),
        "grid_n_negative": sum(1 for g in grid if g["tau"] < 0),
        "grid_n_significant": sum(1 for g in grid if g["significant_005"]),
    }


def main():
    df = pq.read_table(TED, columns=[
        "country", "year", "buyer_type", "contract_type",
        "value_eur", "n_bidders"]).to_pandas()
    df["year"] = df["year"].astype("Int64")
    df = df[df.year.between(2012, 2023) & (df.year != 2018)]   # drop artifact
    df = df[df.value_eur > 0].dropna(subset=["value_eur"])
    df = df[df.contract_type.isin(["Supplies", "Services"])]
    p99 = df.n_bidders.quantile(0.99)
    df["bidder_count"] = df.n_bidders.clip(upper=p99)

    central = df[df.buyer_type.isin(CENTRAL_BUYERS)]
    subcentral = df[df.buyer_type.isin(SUBCENTRAL_BUYERS)]

    results = {"design": "buyer_type x year_specific cutoff RDD; 2018 dropped",
               "n_central": int(len(central)), "n_subcentral": int(len(subcentral)),
               "estimates": {}}
    runs = [
        ("central_at_CENTRAL_cutoff (predicted: jump)", central, CENTRAL),
        ("central_at_SUBCENTRAL_cutoff (placebo: null)", central, SUBCENTRAL),
        ("subcentral_at_SUBCENTRAL_cutoff (predicted: jump)", subcentral, SUBCENTRAL),
        ("subcentral_at_CENTRAL_cutoff (placebo: null)", subcentral, CENTRAL),
    ]
    for label, sub, thr in runs:
        r = rdd_on(sub, thr, label)
        results["estimates"][label] = r
        if r.get("insufficient"):
            print(f"{label}: insufficient N ({r['n']})"); continue
        p, m = r["primary_pm010"], r["mse_optimal"]
        print(f"\n{label}")
        print(f"  N={r['n']:,}  primary tau={p['tau']:+.3f} (p={p['p_value']:.4g})  "
              f"MSE tau={m['tau']:+.3f} (p={m['p_value']:.4g})  "
              f"grid {r['grid_n_negative']}/{r['grid_n']} neg, "
              f"{r['grid_n_significant']}/{r['grid_n']} sig")

    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
