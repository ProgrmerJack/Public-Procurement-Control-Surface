"""
Analyze Eurostat greenhouse gas emissions by NACE sector for
Nature Sustainability procurement-competition / carbon-intensity paper.
"""

import json
import os
import sys
import pandas as pd
from pathlib import Path
from collections import OrderedDict

# ── paths ────────────────────────────────────────────────────────────────────
DATA_PATH = Path(r"C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\raw\eurostat_ghg_by_nace_sector.csv")
OUT_DIR   = Path(r"C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\results")
OUT_PATH  = OUT_DIR / "eurostat_ghg_results.json"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 1. Load with encoding fallback ──────────────────────────────────────────
print("=" * 80)
print("STEP 1 — Loading data")
print("=" * 80)

df = None
for enc in ("utf-8", "latin-1", "cp1252"):
    for sep in (",", "\t"):
        try:
            df = pd.read_csv(DATA_PATH, encoding=enc, sep=sep, low_memory=False)
            if len(df.columns) > 3:
                print(f"  Loaded OK  encoding={enc}  sep={'TAB' if sep == chr(9) else 'COMMA'}  "
                      f"shape={df.shape}")
                break
            df = None
        except Exception:
            df = None
    if df is not None:
        break

if df is None:
    sys.exit("ERROR: could not load CSV with any encoding / separator combination")

# ── 2. Column names ─────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("STEP 2 — Column names")
print("=" * 80)
for i, c in enumerate(df.columns):
    print(f"  [{i}] {c}")

# ── 3. First 10 rows ────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("STEP 3 — First 10 rows")
print("=" * 80)
print(df.head(10).to_string(index=False))

# ── 4. Unique values for sector / country columns ───────────────────────────
print("\n" + "=" * 80)
print("STEP 4 — Unique values in key columns")
print("=" * 80)

# Identify relevant columns (NACE, geo, airpol, unit)
key_cols = [c for c in df.columns if c.lower() in
            ("nace_r2", "geo", "airpol", "unit", "nace", "sector", "country")]
for c in key_cols:
    vals = sorted(df[c].dropna().unique())
    print(f"\n  Column '{c}' — {len(vals)} unique values:")
    # Print all if <=60, otherwise first 60
    show = vals[:60]
    for v in show:
        print(f"    {v}")
    if len(vals) > 60:
        print(f"    ... ({len(vals) - 60} more)")

# ── NACE sector labels ──────────────────────────────────────────────────────
NACE_LABELS = {
    "A":        "Agriculture, forestry and fishing",
    "A01":      "Crop and animal production",
    "A02":      "Forestry and logging",
    "A03":      "Fishing and aquaculture",
    "B":        "Mining and quarrying",
    "B05-B09":  "Mining and quarrying (detailed)",
    "C":        "Manufacturing",
    "C10-C12":  "Food products, beverages and tobacco",
    "C13-C15":  "Textiles, wearing apparel, leather",
    "C16":      "Wood products (excl. furniture)",
    "C17":      "Paper and paper products",
    "C18":      "Printing and recorded media",
    "C19":      "Coke and refined petroleum",
    "C20":      "Chemicals and chemical products",
    "C21":      "Pharmaceuticals",
    "C22":      "Rubber and plastic products",
    "C23":      "Other non-metallic mineral products",
    "C24":      "Basic metals",
    "C25":      "Fabricated metal products",
    "C26":      "Computer, electronic and optical products",
    "C27":      "Electrical equipment",
    "C28":      "Machinery and equipment n.e.c.",
    "C29":      "Motor vehicles, trailers",
    "C30":      "Other transport equipment",
    "C31_C32":  "Furniture; other manufacturing",
    "C33":      "Repair/installation of machinery",
    "D":        "Electricity, gas, steam and AC supply",
    "D35":      "Electricity, gas, steam and AC supply",
    "E":        "Water supply; sewerage, waste",
    "E36":      "Water collection, treatment, supply",
    "E37-E39":  "Sewerage; waste management",
    "F":        "Construction",
    "G":        "Wholesale and retail trade",
    "G45":      "Wholesale/retail of motor vehicles",
    "G46":      "Wholesale trade (excl. motor vehicles)",
    "G47":      "Retail trade (excl. motor vehicles)",
    "H":        "Transportation and storage",
    "H49":      "Land transport and pipelines",
    "H50":      "Water transport",
    "H51":      "Air transport",
    "H52":      "Warehousing and support for transport",
    "H53":      "Postal and courier activities",
    "I":        "Accommodation and food service",
    "J":        "Information and communication",
    "K":        "Financial and insurance activities",
    "L":        "Real estate activities",
    "L68A":     "Real estate activities (imputed rents excl.)",
    "M":        "Professional, scientific, technical",
    "N":        "Administrative and support services",
    "O":        "Public administration and defence",
    "P":        "Education",
    "Q":        "Human health and social work",
    "R":        "Arts, entertainment and recreation",
    "S":        "Other service activities",
    "T":        "Households as employers",
    "U":        "Extraterritorial organisations",
    "TOTAL":    "Total – all NACE activities",
    "TOTAL_HH": "Total – households",
    "HH":       "Households",
    "HH_TRA":   "Households – transport",
    "HH_OTH":   "Households – heating/other",
}

# EXIOBASE mapping (NACE → EXIOBASE equivalent)
EXIOBASE_MAP = {
    "A":        "Agriculture",
    "A01":      "Agriculture – crops & livestock",
    "A02":      "Forestry",
    "A03":      "Fishing",
    "B":        "Mining and quarrying",
    "B05-B09":  "Mining and quarrying",
    "C":        "Manufacturing (aggregate)",
    "C10-C12":  "Food products",
    "C13-C15":  "Textiles",
    "C16":      "Wood products",
    "C17":      "Paper products",
    "C19":      "Coke & petroleum refining",
    "C20":      "Chemicals",
    "C21":      "Pharmaceuticals",
    "C22":      "Rubber & plastics",
    "C23":      "Other non-metallic minerals (cement, glass)",
    "C24":      "Basic metals (iron, steel, aluminium)",
    "C25":      "Fabricated metals",
    "C29":      "Motor vehicles",
    "D":        "Electricity, gas & steam",
    "D35":      "Electricity, gas & steam",
    "E":        "Water & waste management",
    "E37-E39":  "Sewerage & waste",
    "F":        "Construction",
    "G":        "Wholesale & retail trade",
    "H":        "Transport services",
    "H49":      "Land transport",
    "H50":      "Water transport",
    "H51":      "Air transport",
    "I":        "Hotels & restaurants",
    "J":        "Post & telecommunications / IT",
    "K":        "Financial services",
    "L":        "Real estate",
    "M":        "Business services (R&D, consulting)",
    "N":        "Other business services",
    "O":        "Public administration",
    "P":        "Education",
    "Q":        "Health & social work",
    "TOTAL_HH": "Households (direct emissions)",
    "HH":       "Households (direct emissions)",
    "HH_TRA":   "Household transport",
    "HH_OTH":   "Household heating",
}

# Procurement-relevant sectors
PROCUREMENT_SECTORS = {
    "F":        "Construction — largest single public-procurement sector",
    "D":        "Energy supply — public utilities procurement",
    "D35":      "Electricity & gas — public utilities procurement",
    "H":        "Transport — public transport procurement",
    "H49":      "Land transport — public transport / rail",
    "H50":      "Water transport — public maritime / ports",
    "H51":      "Air transport — government air-travel contracts",
    "C":        "Manufacturing — public equipment procurement",
    "C10-C12":  "Food — public catering / school meals",
    "C19":      "Petroleum — government fuel procurement",
    "C20":      "Chemicals — government supplies (cleaning, etc.)",
    "C24":      "Basic metals — infrastructure materials",
    "C23":      "Non-metallic minerals — cement/glass for infrastructure",
    "E":        "Water & waste — municipal services",
    "E37-E39":  "Waste management — municipal contracts",
    "O":        "Public admin — in-house government operations",
    "Q":        "Health — public health procurement",
    "P":        "Education — public education procurement",
    "J":        "ICT — government IT procurement",
    "B":        "Mining — raw material extraction for public works",
}

# ── 5. EU27 country codes ───────────────────────────────────────────────────
EU27 = {"AT","BE","BG","CY","CZ","DE","DK","EE","EL","ES","FI","FR","HR",
        "HU","IE","IT","LT","LU","LV","MT","NL","PL","PT","RO","SE","SI","SK"}

# Filter to GHG, thousand tonnes, EU countries
nace_col = "nace_r2"
geo_col  = "geo"
year_col = "TIME_PERIOD"
val_col  = "OBS_VALUE"

df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
df[year_col] = pd.to_numeric(df[year_col], errors="coerce")

eu = df[df[geo_col].isin(EU27)].copy()

print("\n" + "=" * 80)
print("STEP 5 — Most recent year with ≥15 EU countries reporting")
print("=" * 80)

# Exclude aggregate rows (TOTAL, TOTAL_HH, HH*) when checking coverage
eu_sectors = eu[~eu[nace_col].isin(["TOTAL", "TOTAL_HH", "HH", "HH_TRA", "HH_OTH"])]

year_cov = (eu_sectors.dropna(subset=[val_col])
            .groupby(year_col)[geo_col].nunique()
            .sort_index(ascending=False))

print("\n  Year  |  Countries with data")
print("  ------+---------------------")
for yr, cnt in year_cov.items():
    marker = "  ◄" if cnt >= 15 else ""
    print(f"  {int(yr):>5} |  {cnt}{marker}")

best_year = None
for yr in sorted(year_cov.index, reverse=True):
    if year_cov[yr] >= 15:
        best_year = int(yr)
        break

if best_year is None:
    best_year = int(year_cov.idxmax())
    print(f"\n  ⚠  No year with ≥15 countries; using year with max coverage: {best_year}")
else:
    print(f"\n  ✓  Best year: {best_year}  ({year_cov[best_year]} countries)")

country_coverage = int(year_cov.get(best_year, 0))

# ── 6. Country × sector emission intensities ────────────────────────────────
print("\n" + "=" * 80)
print(f"STEP 6 — Country × Sector emissions for {best_year}")
print("=" * 80)

yr_data = eu_sectors[eu_sectors[year_col] == best_year].copy()
pivot = yr_data.pivot_table(index=nace_col, columns=geo_col,
                            values=val_col, aggfunc="sum")
print(f"\n  Pivot shape (sectors × countries): {pivot.shape}")
print(f"  Sectors:   {list(pivot.index[:10])} ...")
print(f"  Countries: {sorted(pivot.columns.tolist())}")

# ── 7 & 8. Top 10 sectors by total emissions ────────────────────────────────
print("\n" + "=" * 80)
print("STEP 7–8 — Top 10 NACE sectors by total EU emissions")
print("=" * 80)

sector_totals = pivot.sum(axis=1).sort_values(ascending=False)

# Determine unit from data
unit_vals = eu_sectors["unit"].dropna().unique()
unit_str = unit_vals[0] if len(unit_vals) else "unknown"
unit_readable = "thousand tonnes CO2-eq" if "THS_T" in str(unit_str) else str(unit_str)

top10 = sector_totals.head(10)
print(f"\n  {'Rank':>4}  {'NACE':>10}  {'Label':<50}  {'Total (THS_T)':>14}")
print("  " + "-" * 82)
for rank, (code, val) in enumerate(top10.items(), 1):
    label = NACE_LABELS.get(code, code)
    print(f"  {rank:>4}  {code:>10}  {label:<50}  {val:>14,.2f}")

# ── 9. EXIOBASE mapping ─────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("STEP 9 — NACE → EXIOBASE sector mapping (top 10)")
print("=" * 80)

top_sectors_list = []
for code, val in top10.items():
    entry = OrderedDict([
        ("nace_code", code),
        ("nace_label", NACE_LABELS.get(code, code)),
        ("total_emissions", round(float(val), 2)),
        ("unit", unit_readable),
        ("exiobase_equivalent", EXIOBASE_MAP.get(code, "No direct EXIOBASE match")),
    ])
    top_sectors_list.append(entry)
    print(f"  {code:>10}  →  {entry['exiobase_equivalent']}")

# ── 10. High-emission procurement sectors ────────────────────────────────────
print("\n" + "=" * 80)
print("STEP 10 — High-emission sectors that are ALSO major procurement sectors")
print("=" * 80)

high_emission_procurement = []
for code, val in sector_totals.items():
    if code in PROCUREMENT_SECTORS:
        label = NACE_LABELS.get(code, code)
        reason = PROCUREMENT_SECTORS[code]
        print(f"  {code:>10}  {val:>12,.2f} THS_T  |  {reason}")
        high_emission_procurement.append(OrderedDict([
            ("nace_code", code),
            ("nace_label", label),
            ("total_emissions", round(float(val), 2)),
            ("procurement_relevance", reason),
        ]))

# Sort by emissions descending
high_emission_procurement.sort(key=lambda x: x["total_emissions"], reverse=True)

# ── 11. Save JSON ────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("STEP 11 — Saving results JSON")
print("=" * 80)

notes = (
    f"Eurostat ENV_AC_AINAH_R2 — air emissions accounts by NACE Rev.2 industry. "
    f"GHG = greenhouse gases (CO2-equivalent). Unit: thousand tonnes. "
    f"Year {best_year} selected as most recent with ≥15 EU27 countries reporting. "
    f"Sectors ranked by sum across all reporting EU27 countries. "
    f"EXIOBASE equivalences are approximate conceptual mappings. "
    f"Procurement-relevant sectors identified based on EU public-procurement spending patterns "
    f"(construction, energy, transport, health, ICT, waste/water are dominant categories)."
)

result = OrderedDict([
    ("most_recent_year", best_year),
    ("country_coverage", country_coverage),
    ("countries_included", sorted(yr_data[geo_col].unique().tolist())),
    ("top_sectors", top_sectors_list),
    ("high_emission_procurement_sectors", high_emission_procurement),
    ("notes", notes),
])

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"  ✓  Saved to {OUT_PATH}")
print(f"  ✓  {len(top_sectors_list)} top sectors, {len(high_emission_procurement)} procurement-relevant sectors")
print("\nDone.")
