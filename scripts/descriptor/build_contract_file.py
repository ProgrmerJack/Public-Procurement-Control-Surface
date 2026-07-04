"""
Deterministic rebuild of the flagship contract file ted_awards_2012_2023.parquet
from the raw yearly TED contract-award-notice (CAN) parquet layer.

WHY: the previously deposited file was the harmonised extract, which carried a
mislabeled multi-year 2018 ingestion batch (~5.16M rows for one dispatch year)
and lot-row duplication. The named "ted_YYYY_CAN.parquet" files are *ingestion
batches*, not notice years: e.g. the 2018 file contains notices dispatched in
2023. Correct de-duplication is therefore: union ALL batch files, de-duplicate on
(notice_id, award_id), and assign each award's year from its dispatch_date. The
2018 artifact then disappears by construction (2018 -> ~674k awards, in line with
neighbours), exactly as it already does for the competition panel.

FIXES vs the old file (all at source, no re-download; the yearly parquets are the
already-parsed monthly packages):
  1. 2018 vintage        -> eliminated by dispatch-year + (notice_id,award_id) dedup.
  2. placeholder identity -> winner_name from the source supplier name field
     (~85% coverage) replaces reliance on supplier_id (~25% populated, junk text).
  3. value inflation      -> value_eur is the awarded field; an is_framework flag is
     added so framework/DPS ceiling values can be excluded. Residual (framework
     ceilings, extreme outliers) is documented, not silently "corrected".

Non-TED sources (Colombia SECOP, UK Contracts Finder) are carried over UNCHANGED
from the previous deposit: their issues are documented and are not what this fixes.

Carbon weight is reused VERBATIM from the previously validated deposit (rho=0.82 vs
Eurostat): a 1:1 cpv_division -> carbon_kg_per_usd map, default 0.20 for unmapped.

Output: deposit/procurement_awards_2012_2023.parquet + results/descriptor/contract_file_stats.json
(the file is a 48% plurality TED plus flagged SECOP/UK, hence the source-neutral name; `source`
distinguishes the layers, and `single_bidder` is null-safe: NULL where n_bidders is null/0).
"""
import json
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[2]
YEARLY = ROOT / "Data" / "processed" / "eu_ted" / "yearly"
DEP = ROOT / "deposit"
OLD = DEP / "ted_awards_2012_2023.OLD.parquet"      # pristine prior deposit: SECOP/UK + validated carbon map
OUT = DEP / "procurement_awards_2012_2023.parquet"  # renamed: file is a 48% plurality TED, not majority
TMP = DEP / "_rebuild.parquet"
RESD = ROOT / "results" / "descriptor"; RESD.mkdir(parents=True, exist_ok=True)
STATS = RESD / "contract_file_stats.json"
EXCLUDE = ("GB", "CH", "UK")


def main():
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    yearly_glob = str(YEARLY / "ted_*_CAN.parquet").replace("\\", "/")
    old = str(OLD).replace("\\", "/")

    # validated cpv -> carbon map (INT key) from the previous deposit's TED rows
    con.execute(f"""
        CREATE TEMP TABLE carbonmap AS
        SELECT DISTINCT TRY_CAST(cpv_division AS INT) AS cpv, carbon_kg_per_usd AS carbon
        FROM read_parquet('{old}')
        WHERE source='TED' AND TRY_CAST(cpv_division AS INT) IS NOT NULL
    """)

    # clean, de-duplicated, dispatch-year-dated TED award universe
    con.execute(f"""
        CREATE TEMP TABLE ted AS
        WITH raw AS (
          SELECT notice_id, award_id, dispatch_date, award_date, year AS yr_col, country,
                 cpv_division, n_bidders, value_eur, is_framework, supplier_name, supplier_country
          FROM read_parquet('{yearly_glob}', union_by_name=true)
          WHERE country NOT IN {EXCLUDE}
        ),
        d AS (
          SELECT notice_id, award_id,
            any_value(dispatch_date) dd, any_value(award_date) ad, any_value(yr_col) yc,
            any_value(country) country, any_value(cpv_division) cpv, any_value(n_bidders) nb,
            any_value(value_eur) val, any_value(is_framework) fwk,
            any_value(supplier_name) sname, any_value(supplier_country) scountry
          FROM raw GROUP BY notice_id, award_id
        )
        SELECT
          COALESCE(CAST(notice_id AS VARCHAR),'n') || '-'
            || COALESCE(CAST(award_id AS VARCHAR),'na')                        AS id_award,
          country,
          CAST(COALESCE(YEAR(TRY_CAST(dd AS DATE)), YEAR(TRY_CAST(ad AS DATE)), yc) AS INT) AS year,
          TRY_CAST(cpv AS INT)                                                AS cpv_division,
          TRY_CAST(nb AS INT)                                                 AS n_bidders,
          CASE WHEN TRY_CAST(nb AS INT) IS NULL OR TRY_CAST(nb AS INT) = 0 THEN NULL
               WHEN TRY_CAST(nb AS INT) = 1 THEN TRUE ELSE FALSE END          AS single_bidder,
          TRY_CAST(val AS DOUBLE)                                             AS value_eur,
          COALESCE(TRY_CAST(fwk AS BOOLEAN), FALSE)                           AS is_framework,
          CASE WHEN lower(trim(CAST(sname AS VARCHAR))) IN ('','nan','none','null')
               THEN NULL ELSE CAST(sname AS VARCHAR) END                      AS winner_name,
          CASE WHEN lower(trim(CAST(scountry AS VARCHAR))) IN ('','nan','none','null')
               THEN NULL ELSE CAST(scountry AS VARCHAR) END                   AS winner_country,
          'TED'                                                               AS source
        FROM d
    """)
    # attach validated carbon by cpv_division (default 0.20 for unmapped)
    con.execute("""
        CREATE TEMP TABLE ted2 AS
        SELECT t.id_award, t.country, t.year, t.cpv_division, t.n_bidders, t.single_bidder,
               t.value_eur, t.is_framework,
               COALESCE(c.carbon, 0.20) AS carbon_kg_per_usd,
               t.winner_name, t.winner_country, t.source
        FROM ted t LEFT JOIN carbonmap c ON t.cpv_division = c.cpv
        WHERE t.year BETWEEN 2012 AND 2023
    """)

    # non-TED (SECOP, UK) carried over unchanged; new columns filled NULL/False
    con.execute(f"""
        CREATE TEMP TABLE nonted AS
        SELECT id_award, country, year, TRY_CAST(cpv_division AS INT) AS cpv_division,
               n_bidders,
               CASE WHEN n_bidders IS NULL OR n_bidders = 0 THEN NULL
                    WHEN n_bidders = 1 THEN TRUE ELSE FALSE END AS single_bidder,
               value_eur, FALSE AS is_framework, carbon_kg_per_usd,
               CAST(NULL AS VARCHAR) AS winner_name, CAST(NULL AS VARCHAR) AS winner_country, source
        FROM read_parquet('{old}')
        WHERE source <> 'TED'
    """)

    tmp = str(TMP).replace("\\", "/")
    con.execute(f"""
        COPY (
          SELECT id_award, country, year, cpv_division, n_bidders, single_bidder,
                 value_eur, is_framework, carbon_kg_per_usd, winner_name, winner_country, source
          FROM ted2
          UNION ALL BY NAME
          SELECT * FROM nonted
        ) TO '{tmp}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    # ---- stats from the freshly written file ----
    def scalar(sql):
        return con.execute(sql).fetchone()[0]
    src = con.execute(f"SELECT source, COUNT(*) FROM read_parquet('{tmp}') GROUP BY 1 ORDER BY 1").fetchall()
    total = scalar(f"SELECT COUNT(*) FROM read_parquet('{tmp}')")
    tf = f"read_parquet('{tmp}')"
    tedf = f"{tf} WHERE source='TED'"
    stats = {
        "total_contracts": total,
        "source_counts": {s: n for s, n in src},
        "ted_awards": scalar(f"SELECT COUNT(*) FROM {tedf}"),
        "ted_bidder_count_populated": scalar(f"SELECT COUNT(*) FROM {tedf} AND n_bidders IS NOT NULL"),
        "ted_obs_ge1": scalar(f"SELECT COUNT(*) FROM {tedf} AND n_bidders>=1"),
        "ted_zero_bidders": scalar(f"SELECT COUNT(*) FROM {tedf} AND n_bidders=0"),
        "ted_single_bidder_ct": scalar(f"SELECT COUNT(*) FROM {tedf} AND n_bidders=1"),
        "ted_winner_name_present": scalar(f"SELECT COUNT(*) FROM {tedf} AND winner_name IS NOT NULL"),
        "ted_is_framework": scalar(f"SELECT COUNT(*) FROM {tedf} AND is_framework"),
        "id_award_unique": scalar(f"SELECT COUNT(*)=COUNT(DISTINCT id_award) FROM {tf}"),
        "per_year_ted": {int(y): int(n) for y, n in con.execute(
            f"SELECT year, COUNT(*) FROM {tedf} GROUP BY 1 ORDER BY 1").fetchall()},
    }
    obs = stats["ted_obs_ge1"]
    stats["ted_single_bidder_rate_obs"] = round(stats["ted_single_bidder_ct"] / obs, 4)
    STATS.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    # swap into place
    import os
    os.replace(TMP, OUT)
    print(json.dumps(stats, indent=2))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
