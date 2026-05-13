"""
OECD Procurement Data Analysis for Nature Sustainability Paper
Produces country-level dead-zone exposure estimates from OECD Government at a Glance data.
"""

import json
import os
import pandas as pd

# ── Paths ────────────────────────────────────────────────────────────────────
SPENDING_CSV = r"C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\raw\oecd_procurement_spending.csv"
GDP_CSV = r"C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\raw\oecd_procurement_gdp.csv"
OUTPUT_JSON = r"C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\results\oecd_results.json"

# ── Helper: load CSV with encoding fallback ──────────────────────────────────
def load_csv(path):
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(path, encoding=enc)
            # Reject if it looks like HTML (corrupted download)
            first_col = str(df.columns[0])
            if first_col.startswith("<!") or first_col.startswith("<html"):
                print(f"  ⚠  {os.path.basename(path)} contains HTML, not CSV data (encoding={enc})")
                return None
            print(f"  ✓  Loaded {os.path.basename(path)}  ({enc}, {df.shape[0]} rows × {df.shape[1]} cols)")
            return df
        except Exception as e:
            continue
    print(f"  ✗  Could not load {os.path.basename(path)}")
    return None

# ══════════════════════════════════════════════════════════════════════════════
print("=" * 80)
print("SECTION 1 — LOAD DATA FILES")
print("=" * 80)

df_spending = load_csv(SPENDING_CSV)
df_gdp = load_csv(GDP_CSV)

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 2 — DATA STRUCTURE: oecd_procurement_spending.csv")
print("=" * 80)

if df_spending is not None:
    print("\nColumn names:")
    for c in df_spending.columns:
        print(f"  • {c}")
    print("\nFirst 5 rows:")
    print(df_spending.head().to_string(index=False))
    print(f"\nUNIT_MEASURE values : {sorted(df_spending['UNIT_MEASURE'].unique())}")
    print(f"REF_AREA  values    : {sorted(df_spending['REF_AREA'].unique())}")
    print(f"TIME_PERIOD range   : {df_spending['TIME_PERIOD'].min()} – {df_spending['TIME_PERIOD'].max()}")

print("\n" + "-" * 80)
print("SECTION 2b — DATA STRUCTURE: oecd_procurement_gdp.csv")
print("-" * 80)

if df_gdp is not None:
    print("\nColumn names:")
    for c in df_gdp.columns:
        print(f"  • {c}")
    print("\nFirst 5 rows:")
    print(df_gdp.head().to_string(index=False))
else:
    print("  (file unavailable — GDP % data will come from spending file's PT_B1GQ unit)")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 3 — EXTRACT PROCUREMENT AS % OF GDP FOR TARGET COUNTRIES")
print("=" * 80)

# Target countries: ISO-3 code → (display name, GDP in EUR bn, SB rate %)
TARGETS = {
    "USA": ("United States",  22_000, 15.0),
    "JPN": ("Japan",           4_200,  7.5),
    "KOR": ("Korea",           1_500,  9.0),
    "AUS": ("Australia",       1_400, 50.0),
    "BRA": ("Brazil",          1_600, 15.0),
    "IND": ("India",           3_000, 20.0),
    "ZAF": ("South Africa",      350, 30.0),
    "CAN": ("Canada",          1_700, 10.0),
    "GBR": ("United Kingdom",  2_700, 20.0),
}

# Filter spending data to PT_B1GQ (procurement as % of GDP)
pct_gdp = df_spending[df_spending["UNIT_MEASURE"] == "PT_B1GQ"].copy()
print(f"\nRows with UNIT_MEASURE == PT_B1GQ: {len(pct_gdp)}")

# Also try alternative codes in case the dataset uses them
alt_codes = {
    "US": "USA", "USA": "USA",
    "JP": "JPN", "JPN": "JPN",
    "KR": "KOR", "KOR": "KOR",
    "AU": "AUS", "AUS": "AUS",
    "BR": "BRA", "BRA": "BRA",
    "IN": "IND", "IND": "IND",
    "ZA": "ZAF", "ZAF": "ZAF",
    "CA": "CAN", "CAN": "CAN",
    "GB": "GBR", "GBR": "GBR", "UK": "GBR",
}

# Find most-recent-year observation for each target
results = []
for iso3, (name, gdp_eur_bn, sb_rate) in TARGETS.items():
    # Try the iso3 code directly
    mask = pct_gdp["REF_AREA"] == iso3
    if mask.sum() == 0:
        # Try alternative codes
        for alt, canonical in alt_codes.items():
            if canonical == iso3:
                mask = pct_gdp["REF_AREA"] == alt
                if mask.sum() > 0:
                    break

    subset = pct_gdp[mask].sort_values("TIME_PERIOD", ascending=False)
    if len(subset) == 0:
        print(f"  ⚠  {name} ({iso3}): NOT found in dataset")
        results.append({
            "name": name, "iso3": iso3, "year": None,
            "procurement_gdp_pct": None, "estimated_procurement_eur_bn": None,
            "sb_rate_literature": sb_rate, "dead_zone_estimate_eur_bn": None,
            "note": "not in OECD dataset"
        })
        continue

    row = subset.iloc[0]
    year = int(row["TIME_PERIOD"])
    pct = float(row["OBS_VALUE"])
    est_procurement = gdp_eur_bn * pct / 100.0
    dead_zone = est_procurement * sb_rate / 100.0

    print(f"  ✓  {name:20s} ({iso3})  year={year}  procurement/GDP={pct:.1f}%"
          f"  est. procurement=€{est_procurement:,.0f}bn  dead-zone=€{dead_zone:,.0f}bn")

    results.append({
        "name": name,
        "iso3": iso3,
        "year": year,
        "procurement_gdp_pct": round(pct, 2),
        "estimated_procurement_eur_bn": round(est_procurement, 1),
        "sb_rate_literature": sb_rate,
        "dead_zone_estimate_eur_bn": round(dead_zone, 1),
    })

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 4 — FORMATTED RESULTS TABLE")
print("=" * 80)

header = (f"{'Country':<20} {'Year':>4}  {'Proc/GDP%':>9}  {'Est.Proc €bn':>13}"
          f"  {'SB Rate%':>8}  {'Dead Zone €bn':>14}")
print(f"\n{header}")
print("-" * len(header))
for r in results:
    yr = str(r["year"]) if r["year"] else "n/a"
    pct = f"{r['procurement_gdp_pct']:.1f}" if r["procurement_gdp_pct"] is not None else "n/a"
    proc = f"{r['estimated_procurement_eur_bn']:,.1f}" if r["estimated_procurement_eur_bn"] is not None else "n/a"
    sb = f"{r['sb_rate_literature']:.0f}"
    dz = f"{r['dead_zone_estimate_eur_bn']:,.1f}" if r["dead_zone_estimate_eur_bn"] is not None else "n/a"
    print(f"{r['name']:<20} {yr:>4}  {pct:>9}  {proc:>13}  {sb:>8}  {dz:>14}")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 5 — GLOBAL TOTALS")
print("=" * 80)

total_procurement = sum(r["estimated_procurement_eur_bn"] for r in results
                        if r["estimated_procurement_eur_bn"] is not None)
total_dead_zone = sum(r["dead_zone_estimate_eur_bn"] for r in results
                      if r["dead_zone_estimate_eur_bn"] is not None)

print(f"\n  Total estimated procurement (these {len([r for r in results if r['year']])} countries): €{total_procurement:,.1f} bn")
print(f"  Total dead-zone exposure:  €{total_dead_zone:,.1f} bn")
print(f"  Weighted-average SB rate:  {total_dead_zone / total_procurement * 100:.1f}%"
      if total_procurement else "")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 6 — SAVE JSON")
print("=" * 80)

os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

output = {
    "countries": results,
    "total_dead_zone_eur_bn": round(total_dead_zone, 1),
    "total_procurement_eur_bn": round(total_procurement, 1),
    "data_source": "OECD Government at a Glance",
}

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"  ✓  Saved to {OUTPUT_JSON}")
print(f"\n{'=' * 80}")
print("DONE")
print("=" * 80)
