"""
Data-integrity audit responding to desk review M5(a)/M5(b).

Investigates:
  1. Annual contract counts (EU-context vs Colombia vs GB) and the 2018 surge.
  2. Whether 2018 is a genuine award volume or an ingestion artifact
     (record_id / ocid duplication, tender_date snapshot multiplication).
  3. Supplier concentration: share of contracts to 500+ -contract suppliers,
     share of buyer-supplier pairs with 11+ repeat transactions, and the role
     of null / placeholder supplier identifiers.
  4. Country-level single-bidder rates (sanity vs review's 5.4% GB .. 33.7% PL).

Output: results/audit/data_integrity_audit.json + console report.
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT_DIR = ROOT / "results" / "audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

report = {}


def jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    return o


print("Reading columns for audit ...")
cols = [
    "record_id", "ocid", "country", "year", "tender_date",
    "single_bidder", "n_bidders", "buyer_id", "supplier_id",
]
df = pq.read_table(PARQUET, columns=cols).to_pandas()
df["year"] = df["year"].astype("Int64")
N = len(df)
report["total_rows"] = N
print(f"Loaded {N:,} rows")

# ---------------------------------------------------------------------------
# 1. Annual counts: EU-context (country != CO) vs Colombia vs GB
# ---------------------------------------------------------------------------
df["bucket"] = np.where(df["country"] == "CO", "Colombia",
                np.where(df["country"] == "GB", "GB", "EU-context (ex GB, ex CO)"))
annual = (df.groupby(["year", "bucket"]).size()
            .unstack(fill_value=0).sort_index())
annual["EU-context total (ex CO)"] = annual.drop(columns=["Colombia"], errors="ignore").sum(axis=1)
report["annual_counts_by_bucket"] = jsonable(annual.to_dict(orient="index"))

eu_ctx = df[df["country"] != "CO"]
eu_annual = eu_ctx.groupby("year").size()
report["eu_context_annual"] = jsonable(eu_annual.to_dict())

# 2018 surge magnitude vs adjacent years
def ratio_2018(s):
    adj = [s.get(2016, np.nan), s.get(2017, np.nan), s.get(2019, np.nan), s.get(2020, np.nan)]
    adj = [x for x in adj if pd.notna(x) and x > 0]
    base = np.mean(adj) if adj else np.nan
    return float(s.get(2018, np.nan)) / base if base else np.nan

report["2018_surge"] = {
    "eu_context_2018": int(eu_annual.get(2018, 0)),
    "eu_context_adjacent_mean_2016_17_19_20": float(np.mean(
        [eu_annual.get(y, np.nan) for y in (2016, 2017, 2019, 2020)])),
    "ratio_2018_to_adjacent": ratio_2018(eu_annual),
    "2018_share_of_full_dataset": float(int(eu_annual.get(2018, 0)) / N),
}

# Which countries drive 2018?
d2018 = df[df["year"] == 2018]
by_country_2018 = d2018.groupby("country").size().sort_values(ascending=False)
report["2018_by_country_top15"] = jsonable(by_country_2018.head(15).to_dict())

# ---------------------------------------------------------------------------
# 2. Duplication diagnostics for 2018 vs other years
# ---------------------------------------------------------------------------
dup = {}
for label, sub in [("2018", d2018), ("2017", df[df["year"] == 2017]),
                   ("2019", df[df["year"] == 2019]), ("all", df)]:
    n = len(sub)
    rid_unique = sub["record_id"].nunique(dropna=True)
    rid_null = int(sub["record_id"].isna().sum())
    ocid_unique = sub["ocid"].nunique(dropna=True)
    ocid_null = int(sub["ocid"].isna().sum())
    dup[label] = {
        "rows": n,
        "record_id_unique": int(rid_unique),
        "record_id_dup_rows": int(n - rid_unique - rid_null),
        "record_id_null": rid_null,
        "ocid_unique": int(ocid_unique),
        "ocid_dup_rows": int(n - ocid_unique - ocid_null),
        "ocid_null": ocid_null,
        "frac_rows_with_dup_ocid": float((n - ocid_unique - ocid_null) / n) if n else None,
    }
report["duplication_by_year"] = jsonable(dup)

# tender_date concentration in 2018 (snapshot multiplication would spike single days)
if d2018["tender_date"].notna().any():
    td = pd.to_datetime(d2018["tender_date"], unit="ms", errors="coerce")
    by_day = td.dt.date.value_counts()
    report["2018_tender_date"] = {
        "non_null": int(td.notna().sum()),
        "distinct_days": int(by_day.shape[0]),
        "max_single_day_count": int(by_day.max()) if by_day.shape[0] else 0,
        "top5_days": jsonable({str(k): int(v) for k, v in by_day.head(5).items()}),
    }

# ---------------------------------------------------------------------------
# 3. Supplier concentration
# ---------------------------------------------------------------------------
sup = df["supplier_id"]
sup_null = int(sup.isna().sum()) + int((sup == "").sum())
report["supplier_id_null_or_empty"] = sup_null
report["supplier_id_null_frac"] = float(sup_null / N)

valid = df[sup.notna() & (sup != "")]
counts = valid["supplier_id"].value_counts()
# Share of contracts attributable to 500+ -contract suppliers
big = counts[counts >= 500]
report["supplier_concentration"] = {
    "n_distinct_suppliers": int(counts.shape[0]),
    "n_suppliers_500plus": int(big.shape[0]),
    "contracts_to_500plus": int(big.sum()),
    "frac_dataset_to_500plus": float(big.sum() / N),
    "top10_suppliers": jsonable({str(k): int(v) for k, v in counts.head(10).items()}),
}

# Buyer-supplier repeat pairs with 11+ transactions
pair = valid.groupby(["buyer_id", "supplier_id"]).size()
big_pairs = pair[pair >= 11]
report["repeat_pairs"] = {
    "n_pairs": int(pair.shape[0]),
    "n_pairs_11plus": int(big_pairs.shape[0]),
    "contracts_in_11plus_pairs": int(big_pairs.sum()),
    "frac_dataset_in_11plus_pairs": float(big_pairs.sum() / N),
}

# ---------------------------------------------------------------------------
# 4. Country single-bidder rates
# ---------------------------------------------------------------------------
sb = (df.groupby("country")["single_bidder"]
        .agg(["mean", "size"]).sort_values("mean"))
report["country_sb_rates"] = jsonable(
    {c: {"sb_rate": float(r["mean"]), "n": int(r["size"])}
     for c, r in sb.iterrows()})

# ---------------------------------------------------------------------------
out = OUT_DIR / "data_integrity_audit.json"
with open(out, "w", encoding="utf-8") as fh:
    json.dump(jsonable(report), fh, indent=2)

# Console summary
print("\n" + "=" * 70)
print("DATA-INTEGRITY AUDIT SUMMARY")
print("=" * 70)
print("\n[1] EU-context annual counts:")
for y, c in sorted(report["eu_context_annual"].items()):
    flag = "   <== SURGE" if int(y) == 2018 else ""
    print(f"    {y}: {int(c):>10,}{flag}")
s = report["2018_surge"]
print(f"\n    2018 / adjacent-mean ratio: {s['ratio_2018_to_adjacent']:.1f}x")
print(f"    2018 share of full dataset: {s['2018_share_of_full_dataset']*100:.1f}%")
print("\n[2] 2018 by country (top 8):")
for c, n in list(report["2018_by_country_top15"].items())[:8]:
    print(f"    {c}: {int(n):,}")
print("\n[3] Duplication (2018 vs 2017/2019):")
for lab in ("2017", "2018", "2019"):
    d = report["duplication_by_year"][lab]
    print(f"    {lab}: rows={d['rows']:,}  ocid_dup_rows={d['ocid_dup_rows']:,} "
          f"({(d['frac_rows_with_dup_ocid'] or 0)*100:.1f}%)  ocid_null={d['ocid_null']:,}")
print("\n[4] Supplier concentration:")
sc = report["supplier_concentration"]
print(f"    supplier_id null/empty: {report['supplier_id_null_frac']*100:.1f}%")
print(f"    contracts to 500+ suppliers: {sc['frac_dataset_to_500plus']*100:.1f}% "
      f"({sc['contracts_to_500plus']:,})")
rp = report["repeat_pairs"]
print(f"    contracts in 11+ repeat pairs: {rp['frac_dataset_in_11plus_pairs']*100:.1f}% "
      f"({rp['contracts_in_11plus_pairs']:,})")
print("\n[5] Country SB rates (extremes):")
items = list(report["country_sb_rates"].items())
for c, r in items[:3] + items[-3:]:
    print(f"    {c}: {r['sb_rate']*100:.1f}%  (n={r['n']:,})")
print(f"\nSaved -> {out}")
