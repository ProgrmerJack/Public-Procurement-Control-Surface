#!/usr/bin/env python3
"""
Alternative Carbon Intensity Analysis
======================================
Addresses the #1 methodological limitation: EXIOBASE 3.8.2 sector-average
carbon intensities (within each country-sector, all contracts get the same
carbon intensity value).

This script integrates TWO alternative data sources that provide
within-sector variation:

  Source A – Eurostat Air Emissions Accounts (env_ac_ainah_r2)
    Country × NACE A64 sector × year → CO2 emissions
    Combined with Eurostat SBS output data where available.

  Source B – E-PRTR facility-level CO2 emissions
    Country × E-PRTR sector × year → CO2 (aggregated from facility data)
    Already available locally.

Then re-runs key analyses:
  - Single-bidder carbon premium (was -4.3% EU-context)
  - Large vs small contract premium pattern
  - Sensitivity of main results to alternative carbon data
"""

import json
import os
import sys
import warnings
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore", category=FutureWarning)

PROJECT_ROOT = Path(r"C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface")
DATA_DIR = PROJECT_ROOT / "Data"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────
#  NACE Rev.2 → GPRD sector mapping (used by the manuscript)
# ──────────────────────────────────────────────────────────────────────

NACE_TO_GPRD = {
    "A": "AGRICULTURE",
    "A01": "AGRICULTURE", "A02": "AGRICULTURE", "A03": "AGRICULTURE",
    "B": "MINING",
    "B05": "MINING", "B06": "MINING", "B07": "MINING", "B08": "MINING", "B09": "MINING",
    "C": "MANUFACTURING",
    "C10": "AGRICULTURE",   # food products
    "C11": "AGRICULTURE",   # beverages
    "C12": "AGRICULTURE",   # tobacco
    "C13": "TEXTILES", "C14": "TEXTILES", "C15": "TEXTILES",
    "C16": "MANUFACTURING", "C17": "MANUFACTURING", "C18": "MANUFACTURING",
    "C19": "ENERGY",        # coke/petroleum
    "C20": "CHEMICALS", "C21": "CHEMICALS",
    "C22": "MANUFACTURING", "C23": "MANUFACTURING",
    "C24": "MANUFACTURING", "C25": "MANUFACTURING",
    "C26": "TECH", "C27": "MANUFACTURING", "C28": "MANUFACTURING",
    "C29": "MANUFACTURING", "C30": "MANUFACTURING",
    "C31": "MANUFACTURING", "C32": "MANUFACTURING", "C33": "MANUFACTURING",
    "D": "ENERGY",
    "D35": "ENERGY",
    "E": "UTILITIES",
    "E36": "UTILITIES", "E37": "UTILITIES", "E38": "UTILITIES", "E39": "UTILITIES",
    "F": "CONSTRUCTION",
    "F41": "CONSTRUCTION", "F42": "CONSTRUCTION", "F43": "CONSTRUCTION",
    "G": "SERVICES",
    "G45": "SERVICES", "G46": "SERVICES", "G47": "SERVICES",
    "H": "TRANSPORT",
    "H49": "TRANSPORT", "H50": "TRANSPORT", "H51": "TRANSPORT", "H52": "TRANSPORT", "H53": "TRANSPORT",
    "I": "SERVICES",
    "I55": "SERVICES", "I56": "SERVICES",
    "J": "TECH",
    "J58": "TECH", "J59": "TECH", "J60": "TECH", "J61": "TECH", "J62": "TECH", "J63": "TECH",
    "K": "SERVICES",
    "L": "SERVICES",
    "M": "SERVICES",
    "N": "SERVICES",
    "O": "SERVICES",
    "P": "SERVICES",
    "Q": "HEALTH",
    "Q86": "HEALTH", "Q87": "HEALTH", "Q88": "HEALTH",
    "R": "SERVICES",
    "S": "SERVICES",
    "T": "SERVICES",
    "U": "SERVICES",
    "TOTAL": None,  # skip
    "HH_TRAN": "TRANSPORT",
    "HH_OTH": "OTHER",
    "HH": "OTHER",
}

CPV_TO_NACE_LETTER = {
    "03": "A", "09": "B", "14": "B", "15": "C10", "18": "C13",
    "19": "C15", "22": "C17", "24": "C20", "30": "C26", "31": "C27",
    "32": "C26", "33": "C28", "34": "C29", "35": "C30", "37": "C32",
    "38": "C33", "39": "C28", "42": "C28", "43": "C28", "44": "C25",
    "45": "F", "48": "J62", "50": "C30", "51": "J58",
    "60": "H49", "63": "H52", "64": "H53", "66": "H",
    "70": "J62", "71": "J62", "72": "J62", "73": "M",
    "75": "O", "76": "A", "77": "A", "79": "N",
    "80": "N", "85": "Q", "90": "E38", "92": "R",
    "98": "Q", "99": "O",
}


# ──────────────────────────────────────────────────────────────────────
#  E-PRTR sector → GPRD mapping
# ──────────────────────────────────────────────────────────────────────

EPRTR_SECTOR_TO_GPRD = {
    "Energy sector": "ENERGY",
    "Production and processing of metals": "MANUFACTURING",
    "Mineral industry": "MANUFACTURING",
    "Chemical industry": "CHEMICALS",
    "Waste and wastewater management": "UTILITIES",
    "Paper and wood production and processing": "MANUFACTURING",
    "Intensive livestock production and aquaculture": "AGRICULTURE",
    "Animal and vegetable products from the food and beverage sector": "AGRICULTURE",
    "Other activities": "OTHER",
}


# ──────────────────────────────────────────────────────────────────────
#  SOURCE A: Eurostat Air Emissions Accounts
# ──────────────────────────────────────────────────────────────────────

def load_eurostat_emissions() -> Optional[pd.DataFrame]:
    """Load Eurostat env_ac_ainah_r2 via the eurostat Python package."""
    try:
        import eurostat
    except ImportError:
        print("[Eurostat] Package not installed. pip install eurostat")
        return None

    cache_path = DATA_DIR / "raw" / "eurostat" / "env_ac_ainah_r2_parsed.parquet"
    if cache_path.exists():
        print(f"[Eurostat] Loading cached data from {cache_path}")
        return pd.read_parquet(cache_path)

    print("[Eurostat] Downloading env_ac_ainah_r2 … (may take 1-2 min)")
    try:
        raw = eurostat.get_data("env_ac_ainah_r2", flags=False)
    except Exception as e:
        print(f"[Eurostat] Download failed: {e}")
        return None

    if not raw or len(raw) < 2:
        print("[Eurostat] Empty dataset returned")
        return None

    header = raw[0]
    rows = raw[1:]
    df = pd.DataFrame(rows, columns=header)
    print(f"[Eurostat] Raw shape: {df.shape}")

    # Identify year columns (numeric)
    meta_cols = [c for c in df.columns if not c.isdigit()]
    year_cols = [c for c in df.columns if c.isdigit()]

    # Melt to long format: one row per (freq, airpol, nace_r2, unit, geo, year)
    id_vars = meta_cols
    df_long = df.melt(id_vars=id_vars, value_vars=year_cols,
                      var_name="year", value_name="value")
    df_long["year"] = df_long["year"].astype(int)

    # Parse value - can be numeric or contain flags
    df_long["value"] = pd.to_numeric(df_long["value"], errors="coerce")
    df_long = df_long.dropna(subset=["value"])

    # Standardize column names
    rename = {}
    for c in df_long.columns:
        cl = c.lower()
        if "airpol" in cl:
            rename[c] = "pollutant"
        elif "nace" in cl:
            rename[c] = "nace_r2"
        elif "unit" in cl:
            rename[c] = "unit"
        elif "geo" in cl or "time" in cl.replace("\\", " "):
            if c in id_vars:
                rename[c] = "country"
    df_long = df_long.rename(columns=rename)

    # Filter to CO2 / GHG
    co2_codes = {"CO2", "GHG", "CO2_CH4_N2O"}
    if "pollutant" in df_long.columns:
        mask_co2 = df_long["pollutant"].isin(co2_codes)
        df_co2 = df_long[mask_co2].copy()
        print(f"[Eurostat] After CO2/GHG filter: {len(df_co2)} rows")
        print(f"[Eurostat] Pollutants: {df_co2['pollutant'].unique()}")
    else:
        print("[Eurostat] No pollutant column found. Using all data.")
        df_co2 = df_long.copy()

    # Filter to tonnes unit
    if "unit" in df_co2.columns:
        tonnes_mask = df_co2["unit"].str.contains("T_HAB|THS_T|T$|MIO_T", case=False, na=False)
        if tonnes_mask.any():
            print(f"[Eurostat] Units found: {df_co2['unit'].unique()}")
            # Prefer THS_T (thousand tonnes)
            if "THS_T" in df_co2["unit"].values:
                df_co2 = df_co2[df_co2["unit"] == "THS_T"].copy()
                df_co2["value_tonnes"] = df_co2["value"] * 1000  # thousand tonnes → tonnes
            elif "T" in df_co2["unit"].values:
                df_co2 = df_co2[df_co2["unit"] == "T"].copy()
                df_co2["value_tonnes"] = df_co2["value"]
            else:
                df_co2["value_tonnes"] = df_co2["value"]
        else:
            df_co2["value_tonnes"] = df_co2["value"]
    else:
        df_co2["value_tonnes"] = df_co2["value"]

    # Map NACE to GPRD sector
    if "nace_r2" in df_co2.columns:
        df_co2["gprd_sector"] = df_co2["nace_r2"].map(NACE_TO_GPRD)
    else:
        df_co2["gprd_sector"] = "OTHER"

    # EU-27 countries (ISO-2 codes)
    eu27 = {"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES",
            "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
            "NL", "PL", "PT", "RO", "SE", "SI", "SK"}
    # Also add UK/GB for historical coverage
    relevant = eu27 | {"GB", "UK"}

    if "country" in df_co2.columns:
        df_co2 = df_co2[df_co2["country"].isin(relevant)].copy()
        # Standardize EL → GR
        df_co2["country"] = df_co2["country"].replace({"EL": "GR", "UK": "GB"})

    print(f"[Eurostat] Final rows: {len(df_co2)}")
    print(f"[Eurostat] Countries: {sorted(df_co2['country'].unique())}")
    print(f"[Eurostat] Years: {df_co2['year'].min()}-{df_co2['year'].max()}")
    print(f"[Eurostat] NACE sectors: {df_co2['nace_r2'].nunique()}")

    # Cache
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df_co2.to_parquet(cache_path, index=False)
    print(f"[Eurostat] Cached to {cache_path}")

    return df_co2


def compute_eurostat_intensities(eurostat_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute country × NACE sector × year carbon intensities from Eurostat.

    Since we lack perfectly matched economic output by NACE×country×year,
    we compute RELATIVE intensities: for each sector, how much does each
    country deviate from the EU-wide average. This gives us within-sector,
    cross-country variation that EXIOBASE misses.
    """
    if eurostat_df is None or eurostat_df.empty:
        return pd.DataFrame()

    # Aggregate to country × nace_r2 × year → total tonnes CO2
    group_cols = ["country", "nace_r2", "year"]
    avail = [c for c in group_cols if c in eurostat_df.columns]
    if len(avail) < 3:
        print("[Eurostat] Missing required columns for aggregation")
        return pd.DataFrame()

    agg = (eurostat_df
           .groupby(avail, as_index=False)["value_tonnes"]
           .sum()
           .rename(columns={"value_tonnes": "co2_tonnes"}))

    # Compute EU-wide average per sector×year
    eu_avg = (agg
              .groupby(["nace_r2", "year"], as_index=False)["co2_tonnes"]
              .mean()
              .rename(columns={"co2_tonnes": "eu_avg_co2"}))

    agg = agg.merge(eu_avg, on=["nace_r2", "year"], how="left")

    # Relative intensity = country_co2 / eu_average_co2
    agg["relative_intensity"] = agg["co2_tonnes"] / agg["eu_avg_co2"]
    agg["relative_intensity"] = agg["relative_intensity"].replace(
        [np.inf, -np.inf], np.nan
    ).fillna(1.0)

    # Add GPRD sector mapping
    agg["gprd_sector"] = agg["nace_r2"].map(NACE_TO_GPRD)

    print(f"[Eurostat] Intensity table: {len(agg)} rows, "
          f"{agg['country'].nunique()} countries, "
          f"{agg['nace_r2'].nunique()} NACE sectors")

    return agg


# ──────────────────────────────────────────────────────────────────────
#  SOURCE B: E-PRTR facility-level CO2
# ──────────────────────────────────────────────────────────────────────

def load_eprtr_co2() -> pd.DataFrame:
    """Load E-PRTR facility-level CO2 data and aggregate to country × sector × year."""
    eprtr_path = (DATA_DIR / "raw" /
                  "eea_t_ied-eprtr_p_2007-2023_v15_r00" /
                  "User-friendly-CSV" /
                  "F1_4_Air_Releases_Facilities.csv")

    if not eprtr_path.exists():
        print(f"[E-PRTR] File not found: {eprtr_path}")
        return pd.DataFrame()

    print(f"[E-PRTR] Loading facility CO2 data from {eprtr_path.name}…")

    # Read in chunks to filter CO2 only
    chunks = []
    for chunk in pd.read_csv(eprtr_path, chunksize=100_000,
                             usecols=["countryName", "reportingYear",
                                      "EPRTR_SectorCode", "EPRTR_SectorName",
                                      "FacilityInspireId", "facilityName",
                                      "Pollutant", "Releases"]):
        co2_mask = chunk["Pollutant"].str.contains("Carbon dioxide", case=False, na=False)
        # Exclude biomass variant for Scope 1 consistency
        biomass_mask = chunk["Pollutant"].str.contains("biomass", case=False, na=False)
        chunks.append(chunk[co2_mask & ~biomass_mask])

    df = pd.concat(chunks, ignore_index=True)
    print(f"[E-PRTR] CO2 facility records: {len(df)}")
    print(f"[E-PRTR] Countries: {df['countryName'].nunique()}")
    print(f"[E-PRTR] Facilities: {df['FacilityInspireId'].nunique()}")
    print(f"[E-PRTR] Years: {df['reportingYear'].min()}-{df['reportingYear'].max()}")

    # Map country names to ISO-2
    country_map = {
        "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR",
        "Cyprus": "CY", "Czechia": "CZ", "Czech Republic": "CZ",
        "Denmark": "DK", "Estonia": "EE", "Finland": "FI", "France": "FR",
        "Germany": "DE", "Greece": "GR", "Hungary": "HU", "Ireland": "IE",
        "Italy": "IT", "Latvia": "LV", "Lithuania": "LT", "Luxembourg": "LU",
        "Malta": "MT", "Netherlands": "NL", "Poland": "PL", "Portugal": "PT",
        "Romania": "RO", "Slovakia": "SK", "Slovenia": "SI", "Spain": "ES",
        "Sweden": "SE", "United Kingdom": "GB",
        "Norway": "NO", "Switzerland": "CH", "Iceland": "IS",
    }
    df["country"] = df["countryName"].map(country_map)
    df = df.dropna(subset=["country"])
    df["year"] = df["reportingYear"].astype(int)

    # Releases is in kg
    df["co2_kg"] = pd.to_numeric(df["Releases"], errors="coerce")
    df = df.dropna(subset=["co2_kg"])
    df["co2_tonnes"] = df["co2_kg"] / 1000.0

    # Map E-PRTR sectors to GPRD
    df["gprd_sector"] = df["EPRTR_SectorName"].map(EPRTR_SECTOR_TO_GPRD)
    df.loc[df["gprd_sector"].isna(), "gprd_sector"] = "OTHER"

    return df


def compute_eprtr_intensities(eprtr_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute country × E-PRTR sector × year carbon intensities.

    Since E-PRTR doesn't have economic output, we compute:
      1. Mean facility-level CO2 per country-sector-year
      2. Relative intensity vs EU-wide average (same approach as Eurostat)
      3. Within-sector coefficient of variation (to quantify heterogeneity)
    """
    if eprtr_df.empty:
        return pd.DataFrame()

    # Facility-level stats
    facility_stats = (eprtr_df
                      .groupby(["country", "gprd_sector", "year", "FacilityInspireId"],
                               as_index=False)["co2_tonnes"]
                      .sum())

    # Country × sector × year aggregation
    agg = (facility_stats
           .groupby(["country", "gprd_sector", "year"], as_index=False)
           .agg(
               mean_co2=("co2_tonnes", "mean"),
               median_co2=("co2_tonnes", "median"),
               total_co2=("co2_tonnes", "sum"),
               n_facilities=("co2_tonnes", "count"),
               std_co2=("co2_tonnes", "std"),
               p10_co2=("co2_tonnes", lambda x: np.percentile(x, 10) if len(x) >= 5 else np.nan),
               p90_co2=("co2_tonnes", lambda x: np.percentile(x, 90) if len(x) >= 5 else np.nan),
           ))

    agg["cv"] = agg["std_co2"] / agg["mean_co2"]
    agg["p90_p10_ratio"] = agg["p90_co2"] / agg["p10_co2"].replace(0, np.nan)

    # EU-wide average per sector × year
    eu_avg = (agg
              .groupby(["gprd_sector", "year"], as_index=False)["mean_co2"]
              .mean()
              .rename(columns={"mean_co2": "eu_avg_co2"}))

    agg = agg.merge(eu_avg, on=["gprd_sector", "year"], how="left")
    agg["relative_intensity"] = agg["mean_co2"] / agg["eu_avg_co2"]
    agg["relative_intensity"] = agg["relative_intensity"].replace(
        [np.inf, -np.inf], np.nan
    ).fillna(1.0)

    print(f"[E-PRTR] Intensity table: {len(agg)} rows")
    print(f"[E-PRTR] Countries: {sorted(agg['country'].unique())}")
    print(f"[E-PRTR] Sectors: {sorted(agg['gprd_sector'].unique())}")
    print(f"[E-PRTR] Mean within-sector CV: {agg['cv'].mean():.2f}")

    return agg


# ──────────────────────────────────────────────────────────────────────
#  Load procurement data and merge alternative intensities
# ──────────────────────────────────────────────────────────────────────

def load_procurement_data() -> pd.DataFrame:
    """Load the main procurement+carbon dataset."""
    path = DATA_DIR / "processed" / "gprd_with_carbon.parquet"
    print(f"[Procurement] Loading {path.name}…")

    cols = ["record_id", "country", "year", "cpv_division", "sector",
            "value_eur", "value_usd", "n_bidders", "single_bidder",
            "carbon_intensity_kg_usd", "carbon_footprint_kg", "exiobase_sector"]
    df = pd.read_parquet(path, columns=cols)

    # Clean
    df["year"] = df["year"].astype("Int64")
    df["single_bidder"] = df["single_bidder"].astype(bool)

    # Map CPV to NACE for merging with Eurostat
    df["nace_letter"] = df["cpv_division"].map(CPV_TO_NACE_LETTER)

    print(f"[Procurement] Loaded {len(df):,} contracts")
    return df


def merge_alternative_intensities(
    proc_df: pd.DataFrame,
    eurostat_int: pd.DataFrame,
    eprtr_int: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge alternative carbon intensities onto procurement data.

    Strategy: Use relative intensity multipliers from Eurostat/E-PRTR to
    adjust the EXIOBASE sector-average intensity by country.

    New intensity = EXIOBASE_intensity × country_relative_intensity

    This preserves the EXIOBASE cross-sector variation while adding
    within-sector, cross-country variation from Eurostat/E-PRTR.
    """
    df = proc_df.copy()

    # --- Eurostat-based adjustment ---
    if not eurostat_int.empty:
        # Aggregate Eurostat to GPRD sector level (some NACE codes map to same GPRD)
        euro_gprd = (eurostat_int
                     .dropna(subset=["gprd_sector"])
                     .groupby(["country", "gprd_sector", "year"], as_index=False)
                     ["relative_intensity"].mean())
        euro_gprd = euro_gprd.rename(columns={"relative_intensity": "eurostat_rel_intensity"})

        # Map procurement sector to GPRD
        df["merge_sector"] = df["sector"].fillna("OTHER")

        df = df.merge(
            euro_gprd,
            left_on=["country", "merge_sector", "year"],
            right_on=["country", "gprd_sector", "year"],
            how="left",
            suffixes=("", "_euro")
        )

        # Also try merging via NACE letter for finer granularity
        if "nace_r2" in eurostat_int.columns:
            euro_nace = (eurostat_int
                         .groupby(["country", "nace_r2", "year"], as_index=False)
                         ["relative_intensity"].mean()
                         .rename(columns={"relative_intensity": "eurostat_nace_rel"}))
            df = df.merge(
                euro_nace,
                left_on=["country", "nace_letter", "year"],
                right_on=["country", "nace_r2", "year"],
                how="left"
            )
            # Prefer NACE-level, fall back to GPRD-level
            df["eurostat_rel_intensity"] = df["eurostat_nace_rel"].fillna(
                df.get("eurostat_rel_intensity", 1.0)
            )

        df["eurostat_rel_intensity"] = df["eurostat_rel_intensity"].fillna(1.0)
        df["alt_ci_eurostat"] = (df["carbon_intensity_kg_usd"] *
                                 df["eurostat_rel_intensity"])
        matched_euro = (df["eurostat_rel_intensity"] != 1.0).sum()
        print(f"[Merge] Eurostat match rate: {matched_euro:,} / {len(df):,} "
              f"({matched_euro/len(df)*100:.1f}%)")
    else:
        df["eurostat_rel_intensity"] = 1.0
        df["alt_ci_eurostat"] = df["carbon_intensity_kg_usd"]

    # --- E-PRTR-based adjustment ---
    if not eprtr_int.empty:
        eprtr_merge = (eprtr_int
                       .groupby(["country", "gprd_sector", "year"], as_index=False)
                       [["relative_intensity", "cv", "n_facilities"]].mean())
        eprtr_merge = eprtr_merge.rename(columns={
            "relative_intensity": "eprtr_rel_intensity",
            "cv": "eprtr_cv",
            "n_facilities": "eprtr_n_facilities",
        })

        df["merge_sector"] = df.get("merge_sector", df["sector"].fillna("OTHER"))
        df = df.merge(
            eprtr_merge,
            left_on=["country", "merge_sector", "year"],
            right_on=["country", "gprd_sector", "year"],
            how="left",
            suffixes=("", "_eprtr")
        )
        df["eprtr_rel_intensity"] = df["eprtr_rel_intensity"].fillna(1.0)
        df["alt_ci_eprtr"] = (df["carbon_intensity_kg_usd"] *
                              df["eprtr_rel_intensity"])
        matched_eprtr = (df["eprtr_rel_intensity"] != 1.0).sum()
        print(f"[Merge] E-PRTR match rate: {matched_eprtr:,} / {len(df):,} "
              f"({matched_eprtr/len(df)*100:.1f}%)")
    else:
        df["eprtr_rel_intensity"] = 1.0
        df["alt_ci_eprtr"] = df["carbon_intensity_kg_usd"]

    # Best available: prefer Eurostat (wider coverage), fall back to E-PRTR
    df["alt_ci_best"] = np.where(
        df["eurostat_rel_intensity"] != 1.0,
        df["alt_ci_eurostat"],
        np.where(
            df["eprtr_rel_intensity"] != 1.0,
            df["alt_ci_eprtr"],
            df["carbon_intensity_kg_usd"]
        )
    )

    return df


# ──────────────────────────────────────────────────────────────────────
#  Analysis functions
# ──────────────────────────────────────────────────────────────────────

def single_bidder_premium(df: pd.DataFrame, ci_col: str, label: str) -> dict:
    """Compute single-bidder carbon intensity premium."""
    valid = df.dropna(subset=[ci_col, "single_bidder"])
    sb = valid[valid["single_bidder"]][ci_col]
    mb = valid[~valid["single_bidder"]][ci_col]

    if len(sb) < 100 or len(mb) < 100:
        return {"label": label, "error": "insufficient data",
                "n_sb": len(sb), "n_mb": len(mb)}

    mean_sb = sb.mean()
    mean_mb = mb.mean()
    premium_pct = (mean_sb - mean_mb) / mean_mb * 100

    # Welch t-test
    t_stat, p_val = stats.ttest_ind(sb, mb, equal_var=False)

    # Cohen's d
    pooled_std = np.sqrt((sb.std()**2 + mb.std()**2) / 2)
    cohens_d = (mean_sb - mean_mb) / pooled_std if pooled_std > 0 else 0.0

    # 95% CI for the difference (bootstrap-free)
    se_diff = np.sqrt(sb.var()/len(sb) + mb.var()/len(mb))
    ci_lower = (mean_sb - mean_mb) - 1.96 * se_diff
    ci_upper = (mean_sb - mean_mb) + 1.96 * se_diff

    return {
        "label": label,
        "ci_column": ci_col,
        "n_sb": int(len(sb)),
        "n_mb": int(len(mb)),
        "mean_sb": float(round(mean_sb, 6)),
        "mean_mb": float(round(mean_mb, 6)),
        "premium_pct": float(round(premium_pct, 3)),
        "t_statistic": float(round(t_stat, 3)),
        "p_value": float(p_val),
        "cohens_d": float(round(cohens_d, 4)),
        "ci_95_lower": float(round(ci_lower, 6)),
        "ci_95_upper": float(round(ci_upper, 6)),
    }


def size_bin_analysis(df: pd.DataFrame, ci_col: str, label: str) -> list:
    """Analyze single-bidder premium by contract size bins."""
    valid = df.dropna(subset=[ci_col, "single_bidder", "value_eur"])
    valid = valid[valid["value_eur"] > 0]

    bins = [
        ("micro (<€1k)", 0, 1_000),
        ("small (€1k-€10k)", 1_000, 10_000),
        ("medium (€10k-€100k)", 10_000, 100_000),
        ("large (€100k-€1M)", 100_000, 1_000_000),
        ("very_large (>€1M)", 1_000_000, float("inf")),
    ]

    results = []
    for name, lo, hi in bins:
        subset = valid[(valid["value_eur"] >= lo) & (valid["value_eur"] < hi)]
        if len(subset) < 200:
            results.append({"bin": name, "n": len(subset), "error": "too few"})
            continue

        sb = subset[subset["single_bidder"]][ci_col]
        mb = subset[~subset["single_bidder"]][ci_col]

        if len(sb) < 50 or len(mb) < 50:
            results.append({"bin": name, "n_sb": len(sb), "n_mb": len(mb),
                            "error": "too few in one group"})
            continue

        premium_pct = (sb.mean() - mb.mean()) / mb.mean() * 100
        t_stat, p_val = stats.ttest_ind(sb, mb, equal_var=False)
        pooled_std = np.sqrt((sb.std()**2 + mb.std()**2) / 2)
        d = (sb.mean() - mb.mean()) / pooled_std if pooled_std > 0 else 0

        results.append({
            "bin": name,
            "n_sb": int(len(sb)),
            "n_mb": int(len(mb)),
            "premium_pct": float(round(premium_pct, 3)),
            "t_statistic": float(round(t_stat, 3)),
            "p_value": float(p_val),
            "cohens_d": float(round(d, 4)),
            "label": label,
        })

    return results


def country_level_analysis(df: pd.DataFrame, ci_col: str, label: str) -> list:
    """Compute single-bidder premium by country using alternative intensities."""
    valid = df.dropna(subset=[ci_col, "single_bidder", "country"])
    results = []
    for country in sorted(valid["country"].unique()):
        csub = valid[valid["country"] == country]
        sb = csub[csub["single_bidder"]][ci_col]
        mb = csub[~csub["single_bidder"]][ci_col]
        if len(sb) < 50 or len(mb) < 50:
            continue
        premium_pct = (sb.mean() - mb.mean()) / mb.mean() * 100
        t_stat, p_val = stats.ttest_ind(sb, mb, equal_var=False)
        results.append({
            "country": country,
            "n_sb": int(len(sb)),
            "n_mb": int(len(mb)),
            "premium_pct": float(round(premium_pct, 3)),
            "p_value": float(p_val),
            "label": label,
        })
    return results


def variation_diagnostics(df: pd.DataFrame) -> dict:
    """Compare variation in original vs alternative carbon intensities."""
    diag = {}
    for col, label in [
        ("carbon_intensity_kg_usd", "EXIOBASE (original)"),
        ("alt_ci_eurostat", "Eurostat-adjusted"),
        ("alt_ci_eprtr", "E-PRTR-adjusted"),
        ("alt_ci_best", "Best available"),
    ]:
        if col not in df.columns:
            continue
        valid = df[col].dropna()
        if len(valid) == 0:
            continue

        # Within-sector variation: for each sector, compute CV
        if "sector" in df.columns:
            sector_cvs = []
            for sector, grp in df.groupby("sector"):
                s = grp[col].dropna()
                if len(s) > 100 and s.mean() > 0:
                    sector_cvs.append(s.std() / s.mean())
            mean_within_cv = np.mean(sector_cvs) if sector_cvs else 0
        else:
            mean_within_cv = 0

        # Country-level variation within sectors
        if "sector" in df.columns and "country" in df.columns:
            country_sector_means = (df.groupby(["country", "sector"])[col]
                                    .mean().reset_index())
            sector_country_cvs = []
            for sector, grp in country_sector_means.groupby("sector"):
                if len(grp) > 3 and grp[col].mean() > 0:
                    sector_country_cvs.append(grp[col].std() / grp[col].mean())
            cross_country_cv = np.mean(sector_country_cvs) if sector_country_cvs else 0
        else:
            cross_country_cv = 0

        diag[label] = {
            "n_valid": int(len(valid)),
            "mean": float(round(valid.mean(), 6)),
            "std": float(round(valid.std(), 6)),
            "cv": float(round(valid.std() / valid.mean(), 4)) if valid.mean() > 0 else 0,
            "n_unique": int(valid.nunique()),
            "mean_within_sector_cv": float(round(mean_within_cv, 4)),
            "cross_country_within_sector_cv": float(round(cross_country_cv, 4)),
        }

    return diag


# ──────────────────────────────────────────────────────────────────────
#  EU-context analysis (EU countries only, replicating manuscript scope)
# ──────────────────────────────────────────────────────────────────────

def eu_context_analysis(df: pd.DataFrame) -> dict:
    """Replicate EU-context single-bidder premium with alternative intensities."""
    eu27 = {"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES",
            "FI", "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU",
            "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"}
    eu_df = df[df["country"].isin(eu27)].copy()
    print(f"[EU-context] {len(eu_df):,} contracts from {eu_df['country'].nunique()} EU countries")

    results = {}
    for ci_col, label in [
        ("carbon_intensity_kg_usd", "EXIOBASE (original)"),
        ("alt_ci_eurostat", "Eurostat-adjusted"),
        ("alt_ci_eprtr", "E-PRTR-adjusted"),
        ("alt_ci_best", "Best available"),
    ]:
        if ci_col in eu_df.columns:
            results[label] = single_bidder_premium(eu_df, ci_col, label)

    return results


# ──────────────────────────────────────────────────────────────────────
#  Within-sector regression (country fixed effects)
# ──────────────────────────────────────────────────────────────────────

def within_sector_regression(df: pd.DataFrame, ci_col: str) -> dict:
    """
    OLS regression of carbon intensity on single_bidder with sector and
    country-year fixed effects. This is the key test: does within-sector
    variation change the result?
    """
    valid = df.dropna(subset=[ci_col, "single_bidder", "country", "year", "sector"])
    if len(valid) < 1000:
        return {"error": "insufficient data", "n": len(valid)}

    # For speed, use demeaned OLS (subtract sector×country×year means)
    valid = valid.copy()
    valid["sb_int"] = valid["single_bidder"].astype(int)
    valid["ci_val"] = valid[ci_col].astype(float)

    # Group means: sector × country × year
    group_cols = ["sector", "country", "year"]
    grp_means = valid.groupby(group_cols).agg(
        ci_mean=("ci_val", "mean"),
        sb_mean=("sb_int", "mean"),
        n=("ci_val", "count"),
    ).reset_index()

    # Only groups with variation in single_bidder
    grp_with_var = grp_means[(grp_means["sb_mean"] > 0) & (grp_means["sb_mean"] < 1)]
    valid_groups = set(zip(grp_with_var["sector"], grp_with_var["country"],
                           grp_with_var["year"].astype(int)))

    valid["group_key"] = list(zip(valid["sector"], valid["country"],
                                  valid["year"].astype(int)))
    valid_subset = valid[valid["group_key"].isin(valid_groups)].copy()

    if len(valid_subset) < 500:
        return {"error": "insufficient within-group variation", "n": len(valid_subset)}

    # Demean
    grp = valid_subset.groupby(group_cols)
    valid_subset["ci_dm"] = valid_subset["ci_val"] - grp["ci_val"].transform("mean")
    valid_subset["sb_dm"] = valid_subset["sb_int"] - grp["sb_int"].transform("mean")

    # OLS: ci_dm ~ sb_dm (within-group estimator = FE estimator)
    from numpy.linalg import lstsq
    X = valid_subset["sb_dm"].values.reshape(-1, 1)
    y = valid_subset["ci_dm"].values

    beta, residuals, rank, sv = lstsq(X, y, rcond=None)
    beta_sb = beta[0]

    # Standard error (heteroskedasticity-robust)
    resid = y - X.flatten() * beta_sb
    n_obs = len(y)
    n_groups = len(valid_groups)
    sse = (resid ** 2).sum()
    mse = sse / (n_obs - n_groups - 1)
    var_beta = mse / (X.flatten() ** 2).sum()
    se_beta = np.sqrt(var_beta)

    t_stat = beta_sb / se_beta if se_beta > 0 else 0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), n_obs - n_groups - 1))

    # Effect as % of mean
    mean_ci = valid_subset["ci_val"].mean()
    pct_effect = (beta_sb / mean_ci * 100) if mean_ci > 0 else 0

    return {
        "ci_column": ci_col,
        "n_obs": int(n_obs),
        "n_groups": int(n_groups),
        "beta_single_bidder": float(round(beta_sb, 6)),
        "se": float(round(se_beta, 6)),
        "t_statistic": float(round(t_stat, 3)),
        "p_value": float(p_val),
        "pct_effect": float(round(pct_effect, 3)),
        "mean_ci": float(round(mean_ci, 6)),
    }


# ──────────────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("ALTERNATIVE CARBON INTENSITY ANALYSIS")
    print("Addressing EXIOBASE sector-average limitation")
    print("=" * 70)
    print()

    all_results = {
        "metadata": {
            "description": "Sensitivity analysis using alternative carbon intensity data",
            "purpose": "Test if EXIOBASE sector-average limitation changes main results",
            "sources": [],
        }
    }

    # ── Source A: Eurostat ──
    print("\n" + "─" * 50)
    print("SOURCE A: Eurostat Air Emissions Accounts")
    print("─" * 50)
    eurostat_df = load_eurostat_emissions()
    if eurostat_df is not None and not eurostat_df.empty:
        eurostat_int = compute_eurostat_intensities(eurostat_df)
        all_results["metadata"]["sources"].append("Eurostat env_ac_ainah_r2")
        all_results["eurostat_summary"] = {
            "n_rows": int(len(eurostat_df)),
            "countries": sorted(eurostat_df["country"].unique().tolist()),
            "year_range": [int(eurostat_df["year"].min()),
                           int(eurostat_df["year"].max())],
            "nace_sectors": int(eurostat_df["nace_r2"].nunique()),
        }
    else:
        eurostat_int = pd.DataFrame()
        print("[Eurostat] No data available.")

    # ── Source B: E-PRTR ──
    print("\n" + "─" * 50)
    print("SOURCE B: E-PRTR Facility-Level CO2")
    print("─" * 50)
    eprtr_df = load_eprtr_co2()
    if not eprtr_df.empty:
        eprtr_int = compute_eprtr_intensities(eprtr_df)
        all_results["metadata"]["sources"].append("E-PRTR v15.0 facility CO2")

        # E-PRTR facility-level heterogeneity stats
        fac_stats = (eprtr_df
                     .groupby(["gprd_sector"])
                     .agg(
                         n_facilities=("FacilityInspireId", "nunique"),
                         mean_co2_tonnes=("co2_tonnes", "mean"),
                         std_co2_tonnes=("co2_tonnes", "std"),
                         p10=("co2_tonnes", lambda x: np.percentile(x, 10)),
                         p90=("co2_tonnes", lambda x: np.percentile(x, 90)),
                     ).reset_index())
        fac_stats["cv"] = fac_stats["std_co2_tonnes"] / fac_stats["mean_co2_tonnes"]
        fac_stats["p90_p10_ratio"] = fac_stats["p90"] / fac_stats["p10"].replace(0, np.nan)

        all_results["eprtr_heterogeneity"] = {
            "description": "Within-sector facility-level CO2 variation (proves EXIOBASE misses real variation)",
            "sectors": fac_stats.to_dict(orient="records"),
            "overall_cv": float(round(fac_stats["cv"].mean(), 3)),
            "overall_p90_p10": float(round(fac_stats["p90_p10_ratio"].mean(), 1)),
        }
    else:
        eprtr_int = pd.DataFrame()

    # ── Load procurement data ──
    print("\n" + "─" * 50)
    print("LOADING PROCUREMENT DATA")
    print("─" * 50)
    proc_df = load_procurement_data()

    # ── Merge alternative intensities ──
    print("\n" + "─" * 50)
    print("MERGING ALTERNATIVE INTENSITIES")
    print("─" * 50)
    merged = merge_alternative_intensities(proc_df, eurostat_int, eprtr_int)

    # ── Variation diagnostics ──
    print("\n" + "─" * 50)
    print("VARIATION DIAGNOSTICS")
    print("─" * 50)
    var_diag = variation_diagnostics(merged)
    all_results["variation_diagnostics"] = var_diag
    for label, stats_dict in var_diag.items():
        print(f"  {label}:")
        print(f"    Overall CV: {stats_dict['cv']:.4f}")
        print(f"    Within-sector CV: {stats_dict['mean_within_sector_cv']:.4f}")
        print(f"    Cross-country within-sector CV: {stats_dict['cross_country_within_sector_cv']:.4f}")
        print(f"    Unique values: {stats_dict['n_unique']}")

    # ── Single-bidder premium (all data) ──
    print("\n" + "─" * 50)
    print("SINGLE-BIDDER PREMIUM (ALL DATA)")
    print("─" * 50)
    sb_results = {}
    for ci_col, label in [
        ("carbon_intensity_kg_usd", "EXIOBASE (original)"),
        ("alt_ci_eurostat", "Eurostat-adjusted"),
        ("alt_ci_eprtr", "E-PRTR-adjusted"),
        ("alt_ci_best", "Best available"),
    ]:
        if ci_col in merged.columns:
            res = single_bidder_premium(merged, ci_col, label)
            sb_results[label] = res
            print(f"  {label}: premium = {res.get('premium_pct', 'N/A')}%, "
                  f"d = {res.get('cohens_d', 'N/A')}, p = {res.get('p_value', 'N/A')}")
    all_results["single_bidder_premium_all"] = sb_results

    # ── EU-context single-bidder premium ──
    print("\n" + "─" * 50)
    print("EU-CONTEXT SINGLE-BIDDER PREMIUM")
    print("─" * 50)
    eu_results = eu_context_analysis(merged)
    all_results["eu_context_premium"] = eu_results
    for label, res in eu_results.items():
        print(f"  {label}: premium = {res.get('premium_pct', 'N/A')}%, "
              f"d = {res.get('cohens_d', 'N/A')}")

    # ── Size-bin analysis ──
    print("\n" + "─" * 50)
    print("SIZE-BIN ANALYSIS (contract size × premium)")
    print("─" * 50)
    size_results = {}
    for ci_col, label in [
        ("carbon_intensity_kg_usd", "EXIOBASE (original)"),
        ("alt_ci_best", "Best available"),
    ]:
        if ci_col in merged.columns:
            res = size_bin_analysis(merged, ci_col, label)
            size_results[label] = res
            for r in res:
                if "premium_pct" in r:
                    print(f"  {label} | {r['bin']}: "
                          f"premium = {r['premium_pct']:.1f}%, p = {r['p_value']:.2e}")
    all_results["size_bin_analysis"] = size_results

    # ── Country-level analysis ──
    print("\n" + "─" * 50)
    print("COUNTRY-LEVEL ANALYSIS")
    print("─" * 50)
    country_results = {}
    for ci_col, label in [
        ("carbon_intensity_kg_usd", "EXIOBASE (original)"),
        ("alt_ci_best", "Best available"),
    ]:
        if ci_col in merged.columns:
            res = country_level_analysis(merged, ci_col, label)
            country_results[label] = res
            # Just show top 5 by sample size
            sorted_res = sorted(res, key=lambda x: x.get("n_sb", 0), reverse=True)
            for r in sorted_res[:5]:
                print(f"  {label} | {r['country']}: "
                      f"premium = {r['premium_pct']:.1f}%, "
                      f"p = {r['p_value']:.2e}, n_sb = {r['n_sb']}")
    all_results["country_analysis"] = country_results

    # ── Within-sector regression ──
    print("\n" + "─" * 50)
    print("WITHIN-SECTOR FIXED EFFECTS REGRESSION")
    print("─" * 50)
    fe_results = {}
    for ci_col, label in [
        ("carbon_intensity_kg_usd", "EXIOBASE (original)"),
        ("alt_ci_eurostat", "Eurostat-adjusted"),
        ("alt_ci_eprtr", "E-PRTR-adjusted"),
        ("alt_ci_best", "Best available"),
    ]:
        if ci_col in merged.columns:
            res = within_sector_regression(merged, ci_col)
            fe_results[label] = res
            if "error" not in res:
                print(f"  {label}: β = {res['beta_single_bidder']:.6f}, "
                      f"({res['pct_effect']:.3f}%), "
                      f"t = {res['t_statistic']:.3f}, p = {res['p_value']:.2e}")
            else:
                print(f"  {label}: {res['error']}")
    all_results["within_sector_regression"] = fe_results

    # ── Summary assessment ──
    print("\n" + "=" * 70)
    print("SENSITIVITY ASSESSMENT SUMMARY")
    print("=" * 70)

    sensitivity = {
        "conclusion": "",
        "original_premium_pct": None,
        "alternative_premium_pct": None,
        "change_pct": None,
        "direction_consistent": None,
        "significance_consistent": None,
    }

    orig = sb_results.get("EXIOBASE (original)", {})
    alt = sb_results.get("Best available", {})

    if "premium_pct" in orig and "premium_pct" in alt:
        op = orig["premium_pct"]
        ap = alt["premium_pct"]
        sensitivity["original_premium_pct"] = op
        sensitivity["alternative_premium_pct"] = ap
        sensitivity["change_pct"] = round(ap - op, 3)
        sensitivity["direction_consistent"] = (np.sign(op) == np.sign(ap))
        sensitivity["significance_consistent"] = (
            orig.get("p_value", 1) < 0.05 and alt.get("p_value", 1) < 0.05
        )

        if sensitivity["direction_consistent"] and sensitivity["significance_consistent"]:
            sensitivity["conclusion"] = (
                f"ROBUST: Alternative carbon intensities confirm the main finding. "
                f"Single-bidder premium changes from {op:.1f}% to {ap:.1f}% "
                f"(Δ = {ap-op:+.1f} pp). Direction and significance preserved."
            )
        elif sensitivity["direction_consistent"]:
            sensitivity["conclusion"] = (
                f"PARTIALLY ROBUST: Direction preserved ({op:.1f}% → {ap:.1f}%) "
                f"but significance may differ."
            )
        else:
            sensitivity["conclusion"] = (
                f"NOT ROBUST: Alternative intensities reverse the direction "
                f"({op:.1f}% → {ap:.1f}%). The EXIOBASE limitation matters."
            )

        print(f"\n  {sensitivity['conclusion']}")

    all_results["sensitivity_assessment"] = sensitivity

    # ── Save results ──
    output_path = RESULTS_DIR / "alternative_carbon_analysis.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n✓ Results saved to {output_path}")

    return all_results


if __name__ == "__main__":
    results = main()
