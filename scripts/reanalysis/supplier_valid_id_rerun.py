"""
Supplier analyses on valid-ID contracts only (publication plan Item 6).

The audit showed 54.8% of contracts have an unusable supplier_id (the string
"nan" alone = 7.31M). Every supplier-level claim was computed on a pool dominated
by that placeholder. Here we re-run the two headline supplier claims on VALID-ID
contracts only and report whether they survive. Valid IDs are ~45% of contracts
and non-random (caveat stated).

Claims tested:
  - Relationship lock-in: 11+ repeat buyer-supplier transactions carry higher
    carbon than first-time awards (published +54.5%).
  - Within-supplier premium: suppliers active under both SB and MB regimes
    (published -0.87%, 39,410 firms).

Output: results/audit/supplier_valid_id_rerun.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "audit" / "supplier_valid_id_rerun.json"
PLACEHOLDERS = {"", "nan", "none", "null", "na", "n/a", "0", "1", "-", "unknown"}


def main():
    df = pq.read_table(PARQUET, columns=[
        "country", "supplier_id", "buyer_id", "single_bidder",
        "carbon_intensity_kg_usd"]).to_pandas()
    df = df[df.country != "CO"].dropna(subset=["carbon_intensity_kg_usd"])
    sid = df["supplier_id"].astype("string").str.strip().str.lower()
    valid = sid.notna() & ~sid.isin(PLACEHOLDERS) & (sid.str.len() > 2)
    full_n = len(df)
    df = df[valid].copy()
    res = {"valid_id_contracts": int(len(df)),
           "valid_id_frac": float(len(df) / full_n)}

    # ---- Relationship lock-in ----
    pair = df.groupby(["buyer_id", "supplier_id"]).size().rename("pair_n")
    df = df.merge(pair, on=["buyer_id", "supplier_id"], how="left")
    first = df[df.pair_n == 1]["carbon_intensity_kg_usd"]
    deep = df[df.pair_n >= 11]["carbon_intensity_kg_usd"]
    if len(first) > 5 and len(deep) > 5:
        t, p = stats.ttest_ind(deep, first, equal_var=False)
        res["relationship_lockin"] = {
            "first_time_mean": float(first.mean()),
            "deep_11plus_mean": float(deep.mean()),
            "premium_pct": float((deep.mean() - first.mean()) / first.mean() * 100),
            "n_first": int(len(first)), "n_deep": int(len(deep)),
            "t": float(t), "p": float(p),
            "published_value_pct": 54.5,
        }

    # ---- Within-supplier premium (paired SB vs MB by supplier) ----
    g = df.groupby("supplier_id")
    agg = g.agg(sb_mean=("carbon_intensity_kg_usd",
                         lambda x: x[df.loc[x.index, "single_bidder"]].mean()),
                mb_mean=("carbon_intensity_kg_usd",
                         lambda x: x[~df.loc[x.index, "single_bidder"]].mean()))
    agg = agg.dropna()
    if len(agg) > 10:
        diff = agg["sb_mean"] - agg["mb_mean"]
        t, p = stats.ttest_1samp(diff, 0)
        res["within_supplier"] = {
            "n_suppliers_both_regimes": int(len(agg)),
            "mean_sb_minus_mb": float(diff.mean()),
            "premium_pct": float(diff.mean() / agg["mb_mean"].mean() * 100),
            "t": float(t), "p": float(p),
            "published_value_pct": -0.87,
        }

    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print("SUPPLIER VALID-ID RERUN (Item 6)")
    print("=" * 60)
    print(f"  valid-ID contracts: {res['valid_id_contracts']:,} "
          f"({res['valid_id_frac']*100:.1f}% of EU-context)")
    if "relationship_lockin" in res:
        r = res["relationship_lockin"]
        print(f"\n  Relationship lock-in (11+ vs first-time): {r['premium_pct']:+.1f}% "
              f"(published +54.5%); t={r['t']:.1f}, p={r['p']:.2g}  "
              f"[n_deep={r['n_deep']:,}]")
    if "within_supplier" in res:
        w = res["within_supplier"]
        print(f"  Within-supplier premium: {w['premium_pct']:+.2f}% "
              f"(published -0.87%); {w['n_suppliers_both_regimes']:,} suppliers; "
              f"t={w['t']:.2f}, p={w['p']:.2g}")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
