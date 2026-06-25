"""
Fix 1 (foundation): rebuild a country x month single-bidding panel from the LOCAL
harmonized TED yearly Contract-Award-Notice files, which retain day-level dispatch
dates and observed bidder counts for 2012-2016 (contrary to the degraded final
extract). This dissolves the "sub-annual dates missing before 2017" claim.

Coverage-stable universe: contracts with an OBSERVED bidder count (n_bidders>=1),
GB/CH excluded (different source / not in EU-timing design), EU+Norway kept.
De-duplication: collapse to one row per (notice_id, award_id) to avoid lot-level
repetition inflating counts. Timing from dispatch_date (100% populated all years).

Outputs:
  Data/processed/ted_country_month_panel.parquet  (country x month outcomes)
  results/causal_id/monthly_panel_summary.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
YEARLY = ROOT / "Data" / "processed" / "eu_ted" / "yearly"
OUTP = ROOT / "Data" / "processed" / "ted_country_month_panel.parquet"
OUTJ = ROOT / "results" / "causal_id" / "monthly_panel_summary.json"

EXCLUDE = {"GB", "CH", "UK"}          # different source / non-design
COLS = ["notice_id", "award_id", "lot_number", "country", "dispatch_date",
        "award_date", "n_bidders", "single_bidder", "cpv_division",
        "value_eur", "estimated_value_eur", "is_framework"]


def main():
    frames = []
    for yr in range(2012, 2024):
        f = YEARLY / f"ted_{yr}_CAN.parquet"
        if not f.exists():
            continue
        d = pq.read_table(f, columns=COLS).to_pandas()
        frames.append(d)
        print(f"  {yr}: {len(d):,}")
    df = pd.concat(frames, ignore_index=True)
    print(f"raw CAN rows 2012-2023: {len(df):,}")

    df = df[~df["country"].isin(EXCLUDE)]
    # de-duplicate to award level (lots repeat the award/bidder count)
    before = len(df)
    df = df.drop_duplicates(subset=["notice_id", "award_id"])
    print(f"after country filter + dedup on (notice_id,award_id): {len(df):,} (dropped {before-len(df):,})")

    # coverage-stable: observed bidder count
    df = df[df["n_bidders"].notna() & (df["n_bidders"] >= 1)].copy()
    df["sb"] = (df["n_bidders"] == 1).astype(float)
    df["comp3"] = (df["n_bidders"] >= 3).astype(float)
    # monthly timing from dispatch_date
    dt = pd.to_datetime(df["dispatch_date"], errors="coerce")
    df = df[dt.notna()].copy()
    df["ym"] = dt.dt.year * 12 + (dt.dt.month - 1)
    df["year"] = dt.dt.year
    df = df[df["year"].between(2012, 2023)]
    print(f"coverage-stable observed-bidder rows: {len(df):,}")

    panel = (df.groupby(["country", "ym"])
               .agg(sb_rate=("sb", "mean"),
                    comp3_rate=("comp3", "mean"),
                    mean_bidders=("n_bidders", lambda s: s.clip(upper=s.quantile(0.99)).mean()),
                    n=("sb", "size")).reset_index())
    panel["year"] = 2012 + panel["ym"] // 12
    panel["month"] = panel["ym"] % 12 + 1
    panel.to_parquet(OUTP)

    summary = {
        "n_award_rows_used": int(len(df)),
        "n_country_month_cells": int(len(panel)),
        "countries": sorted(panel["country"].unique().tolist()),
        "n_countries": int(panel["country"].nunique()),
        "months_span": [int(panel["ym"].min()), int(panel["ym"].max())],
        "median_cell_n": int(panel["n"].median()),
        "cells_ge_50": int((panel["n"] >= 50).sum()),
        "sb_rate_by_year": df.groupby("year")["sb"].mean().round(3).to_dict(),
    }
    OUTJ.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\ncountry-month cells: {len(panel):,} over {panel['country'].nunique()} countries")
    print(f"months span: {panel['ym'].min()}..{panel['ym'].max()} "
          f"({(panel['ym'].max()-panel['ym'].min()+1)} months)")
    print(f"cells with n>=50: {(panel['n']>=50).sum():,}")
    print("SB rate by year:", summary["sb_rate_by_year"])
    print(f"Saved panel -> {OUTP}")


if __name__ == "__main__":
    main()
