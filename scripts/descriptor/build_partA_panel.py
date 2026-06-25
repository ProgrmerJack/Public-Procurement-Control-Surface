"""
Deterministic rebuild of the Part A competition panel + all Part A validation
statistics for the Scientific Data descriptor. Single source of truth: every
number in the descriptor's Technical Validation 1-2 is emitted here.

Reads the local harmonised TED yearly Contract-Award-Notice (CAN) parquet files
and the processed carbon extract, applies one documented recipe, and writes:
  competition_panel_country_cpv_month.parquet   (country x CPV-division x month)
  partA_validation.json                          (annual series, counts, contrasts)

RECIPE (fixed, documented in descriptor Methods):
  - universe: CAN files, EU/EEA reporting countries (GB/UK = different national
    population; CH = non-design) excluded;
  - de-duplicate to award level on (notice_id, award_id) (removes lot repetition);
  - observed-bid universe: keep awards with an observed offer count n_bidders>=1;
  - single_bidder := (n_bidders == 1); comp3 := (n_bidders >= 3);
  - monthly calendar from dispatch_date, which is reliably populated 2017-2020
    (the post-schema-change recovery window). 2015-2016 lack usable monthly dates
    in this harmonised layer and are not placed on the monthly panel.
  - cell rates are proportions, robust to any residual lot-expansion in counts.

The processed-extract contrast (the depressed single_bidder field, and the 2018
ingestion artifact) is computed from Data/processed/gprd_with_carbon.parquet.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
RESD = ROOT / "results" / "descriptor"; RESD.mkdir(parents=True, exist_ok=True)
YEARLY = ROOT / "Data" / "processed" / "eu_ted" / "yearly"
EXTRACT = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT_PANEL = RESD / "competition_panel_country_cpv_month.parquet"
OUT_JSON = RESD / "partA_validation.json"
EXCLUDE = {"GB", "CH", "UK"}
COLS = ["notice_id", "award_id", "country", "dispatch_date", "n_bidders", "cpv_division"]


def main():
    frames = []
    for yr in range(2015, 2021):
        d = pq.read_table(YEARLY / f"ted_{yr}_CAN.parquet", columns=COLS).to_pandas()
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    print(f"raw CAN rows 2015-2020: {len(df):,}")
    df = df[~df["country"].isin(EXCLUDE)]
    n_pre = len(df)
    df = df.drop_duplicates(subset=["notice_id", "award_id"])
    print(f"after EU/EEA filter + (notice,award) dedup: {len(df):,} (dropped {n_pre-len(df):,})")
    obs = df[df["n_bidders"].notna() & (df["n_bidders"] >= 1)].copy()
    obs["sb"] = (obs["n_bidders"] == 1).astype(float)
    obs["comp3"] = (obs["n_bidders"] >= 3).astype(float)
    dt = pd.to_datetime(obs["dispatch_date"], errors="coerce")
    obs = obs[dt.notna()].copy()
    obs["year"] = dt.dt.year
    obs["ym"] = dt.dt.year * 100 + dt.dt.month
    obs = obs[obs["year"].between(2017, 2020)].copy()   # reliably-dated window
    obs["cpv_division"] = obs["cpv_division"].astype(str)
    print(f"observed-bid, reliably-dated (2017-2020) award rows: {len(obs):,}")

    annual = obs.groupby("year")["sb"].mean().round(4)
    counts = obs.groupby("year").size()
    print("\nannual single-bidder rate (rebuild, dispatch-dated):")
    for y in range(2017, 2021):
        print(f"  {y}: sb_rate={annual.get(y)}  n_obs={int(counts.get(y, 0)):,}")
    overall = float(obs["sb"].mean())
    print(f"overall 2017-2020 rebuilt single-bidder rate: {overall:.4f}")

    panel = (obs.groupby(["country", "cpv_division", "ym"])
                .agg(n=("sb", "size"), sb_rate=("sb", "mean"), comp3_rate=("comp3", "mean"))
                .reset_index())
    panel.to_parquet(OUT_PANEL, index=False)
    print(f"panel rows (country x CPV x month): {len(panel):,} "
          f"({panel['country'].nunique()} countries, {panel['cpv_division'].nunique()} CPV divisions)")

    # ---- processed-extract contrast (the depressed field + 2018 artifact) ----
    ex = pq.read_table(EXTRACT, columns=["year", "country", "n_bidders", "single_bidder"]).to_pandas()
    ex_ted = ex[~ex["country"].isin(["CO", "GB"])]
    ex_full = ex_ted.groupby("year")["single_bidder"].mean().round(4)       # full coverage-imputed field
    ex_obs = (ex_ted[ex_ted["n_bidders"] >= 1].assign(sb=lambda d: (d["n_bidders"] == 1))
                .groupby("year")["sb"].mean().round(4))
    artifact_2018_rows = int((ex_ted["year"] == 2018).sum())               # the inflated 2018 vintage
    print(f"\nextract full-field single_bidder by year (depressed): "
          f"{ {int(k): float(v) for k, v in ex_full.loc[2015:2020].items()} }")
    print(f"extract observed-bidder single-bidder by year: "
          f"{ {int(k): float(v) for k, v in ex_obs.loc[2015:2020].items()} }")
    print(f"extract 2018 EU-context rows (artifact): {artifact_2018_rows:,}")

    out = {
        "recipe": "CAN 2015-2020; EU/EEA ex GB/CH/UK; dedup(notice,award); observed n_bidders>=1; "
                  "dispatch-dated monthly window 2017-2020",
        "rebuild_annual_single_bidder_rate": {str(y): float(annual.get(y)) for y in range(2017, 2021)},
        "rebuild_annual_observed_awards": {str(y): int(counts.get(y, 0)) for y in range(2017, 2021)},
        "rebuild_overall_single_bidder_rate_2017_2020": round(overall, 4),
        "panel_rows_country_cpv_month": int(len(panel)),
        "panel_n_countries": int(panel["country"].nunique()),
        "panel_n_cpv_divisions": int(panel["cpv_division"].nunique()),
        "extract_full_field_single_bidder_by_year": {str(int(k)): float(v) for k, v in ex_full.loc[2015:2020].items()},
        "extract_observed_single_bidder_by_year": {str(int(k)): float(v) for k, v in ex_obs.loc[2015:2020].items()},
        "extract_overall_full_field_single_bidder": round(float(ex_ted["single_bidder"].mean()), 4),
        "extract_2018_eu_context_rows_artifact": artifact_2018_rows,
        "official_2018_can_notices": 232989,
        "extract_2018_inflation_x": round(artifact_2018_rows / 232989, 1),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT_PANEL.name} and {OUT_JSON.name}")


if __name__ == "__main__":
    main()
