"""
Stage-2 data-integrity audit (desk review M5a/M5b).

Nails two diagnoses surfaced in stage 1:
  A. The 2018 surge: tender_date null-rate by year, and within 2018 the
     cross-tab of date-null x duplicate-ocid. A genuine award year carries
     publication dates; a bulk ingestion artifact does not.
  B. Supplier concentration: stage 1's pandas isna() missed the literal
     string placeholders ('nan', '1', '0', 'PL', ...). Recompute the share
     of contracts with NO usable supplier identifier, and re-derive
     concentration after removing placeholders.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "audit" / "data_integrity_audit_stage2.json"

df = pq.read_table(
    PARQUET,
    columns=["year", "country", "ocid", "tender_date", "supplier_id", "buyer_id"],
).to_pandas()
df["year"] = df["year"].astype("Int64")
N = len(df)
rep = {"total_rows": N}

# ---- A. tender_date null-rate by year (all countries + EU-context) ----
df["date_null"] = df["tender_date"].isna()
by_year = df.groupby("year").agg(
    rows=("ocid", "size"),
    date_null=("date_null", "sum"),
).assign(date_null_frac=lambda d: d["date_null"] / d["rows"])
rep["date_null_by_year"] = {
    int(y): {"rows": int(r["rows"]), "date_null": int(r["date_null"]),
             "date_null_frac": float(r["date_null_frac"])}
    for y, r in by_year.iterrows()
}

# Within 2018: date-null x duplicate-ocid cross-tab
d18 = df[df["year"] == 2018].copy()
d18["dup_ocid"] = d18["ocid"].duplicated(keep=False)
ct = pd.crosstab(d18["date_null"], d18["dup_ocid"])
rep["2018_datenull_x_dupocid"] = {
    f"date_null={i}": {f"dup_ocid={j}": int(ct.loc[i, j])
                       for j in ct.columns}
    for i in ct.index
}
# Plausible genuine 2018 volume = rows that carry a date
rep["2018_dated_rows"] = int((~d18["date_null"]).sum())
rep["2018_dated_rows_eu_context"] = int(
    ((~d18["date_null"]) & (d18["country"] != "CO")).sum())

# Distinct-ocid count per year (dedup ceiling)
rep["distinct_ocid_by_year"] = {
    int(y): int(g["ocid"].nunique())
    for y, g in df.groupby("year")
}

# ---- B. usable supplier identifier ----
sid = df["supplier_id"].astype("string")
sid_str = sid.str.strip().str.lower()
PLACEHOLDERS = {"", "nan", "none", "null", "na", "n/a", "0", "1", "-", "unknown"}
invalid = sid.isna() | sid_str.isin(PLACEHOLDERS) | (sid_str.str.len() <= 2)
rep["supplier_id_unusable"] = {
    "n_unusable": int(invalid.sum()),
    "frac_unusable": float(invalid.mean()),
    "n_pandas_na_only": int(sid.isna().sum()),
    "n_string_nan": int((sid_str == "nan").sum()),
}

valid = df[~invalid]
counts = valid["supplier_id"].value_counts()
big = counts[counts >= 500]
rep["concentration_valid_only"] = {
    "n_valid_contracts": int(len(valid)),
    "n_distinct_suppliers": int(counts.shape[0]),
    "n_suppliers_500plus": int(big.shape[0]),
    "contracts_to_500plus": int(big.sum()),
    "frac_of_VALID_to_500plus": float(big.sum() / len(valid)) if len(valid) else None,
    "frac_of_FULL_to_500plus": float(big.sum() / N),
    "top10_valid_suppliers": {str(k): int(v) for k, v in counts.head(10).items()},
}
pair = valid.groupby(["buyer_id", "supplier_id"]).size()
big_pairs = pair[pair >= 11]
rep["repeat_pairs_valid_only"] = {
    "n_pairs": int(pair.shape[0]),
    "n_pairs_11plus": int(big_pairs.shape[0]),
    "contracts_in_11plus_pairs": int(big_pairs.sum()),
    "frac_of_VALID_in_11plus_pairs": float(big_pairs.sum() / len(valid)) if len(valid) else None,
    "frac_of_FULL_in_11plus_pairs": float(big_pairs.sum() / N),
}

OUT.write_text(json.dumps(rep, indent=2), encoding="utf-8")

print("=" * 70)
print("STAGE-2 AUDIT")
print("=" * 70)
print("\n[A] tender_date null-rate by year (all countries):")
for y, r in rep["date_null_by_year"].items():
    flag = "  <== 2018" if y == 2018 else ""
    print(f"    {y}: rows={r['rows']:>9,}  null={r['date_null_frac']*100:5.1f}%{flag}")
print(f"\n    2018 dated rows (genuine-volume proxy): {rep['2018_dated_rows']:,} "
      f"(EU-context {rep['2018_dated_rows_eu_context']:,})")
print("\n    2018 date-null x dup-ocid crosstab:")
for k, v in rep["2018_datenull_x_dupocid"].items():
    print(f"      {k}: {v}")
print("\n[B] Supplier identifier usability:")
u = rep["supplier_id_unusable"]
print(f"    unusable supplier_id: {u['frac_unusable']*100:.1f}% "
      f"({u['n_unusable']:,}); string 'nan' alone = {u['n_string_nan']:,}")
c = rep["concentration_valid_only"]
print(f"    After removing placeholders: contracts to 500+ suppliers = "
      f"{c['frac_of_FULL_to_500plus']*100:.1f}% of full "
      f"({c['frac_of_VALID_to_500plus']*100:.1f}% of valid)")
rp = rep["repeat_pairs_valid_only"]
print(f"    11+ repeat pairs: {rp['frac_of_FULL_in_11plus_pairs']*100:.1f}% of full "
      f"({rp['frac_of_VALID_in_11plus_pairs']*100:.1f}% of valid)")
print(f"\nSaved -> {OUT}")
