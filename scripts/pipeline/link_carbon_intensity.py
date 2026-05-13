#!/usr/bin/env python3
"""
Carbon Intensity Linking Script

Links EXIOBASE 3.8 carbon intensity factors to procurement contracts
based on CPV codes and sector classification.

Features:
- Year-specific carbon factors (EXIOBASE covers 1995-2022)
- CPV code to EXIOBASE sector mapping
- Contract-level carbon footprint calculation
- Temporal tracking of carbon intensity trends

Input:
- Data/processed/gprd_master.parquet
- Data/processed/exiobase/carbon_factors_by_year.parquet
- Data/reference/cpv_sectors.csv

Output:
- Data/processed/gprd_with_carbon.parquet
- Data/processed/carbon_analysis_summary.json

Author: Abduxoliq Ashuraliyev
License: MIT
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / "pyproject.toml").exists() and _d != _d.parent:
    _d = _d.parent
BASE_DIR = _d
DATA_DIR = BASE_DIR / "Data"
PROCESSED_DIR = DATA_DIR / "processed"
REF_DIR = DATA_DIR / "reference"
EXIOBASE_DIR = PROCESSED_DIR / "exiobase"

# GPRD Sector to EXIOBASE sector mapping
GPRD_TO_EXIOBASE = {
    "AGRICULTURE": "Agriculture",
    "MINING": "Mining",
    "FOOD": "Food products",
    "TEXTILES": "Textiles",
    "CHEMICALS": "Chemicals",
    "MANUFACTURING": "Machinery",
    "ENERGY": "Electricity",
    "UTILITIES": "Water supply",
    "CONSTRUCTION": "Construction",
    "TRANSPORT": "Transport",
    "TECH": "Computer services",
    "SERVICES": "Other business services",
    "HEALTH": "Health services",
    "DEFENSE": "Public administration",
    "OFFICE": "Other business services",
    "OTHER": "Other services",
}

# CPV Division to EXIOBASE sector (more granular mapping)
CPV_TO_EXIOBASE = {
    "03": "Agriculture",  # Agricultural products
    "09": "Mining",  # Petroleum, fuel
    "14": "Mining",  # Mining products
    "15": "Food products",  # Food and beverages
    "18": "Textiles",  # Clothing
    "19": "Leather",  # Leather products
    "22": "Paper",  # Printing
    "24": "Chemicals",  # Chemical products
    "30": "Computer equipment",  # Office machinery
    "31": "Electrical equipment",  # Electrical machinery
    "32": "Telecommunications",  # Radio, TV equipment
    "33": "Medical instruments",  # Medical equipment
    "34": "Motor vehicles",  # Transport equipment
    "35": "Weapons",  # Security equipment
    "38": "Precision instruments",  # Lab equipment
    "39": "Furniture",  # Furniture
    "42": "Machinery",  # Industrial machinery
    "43": "Mining machinery",  # Mining equipment
    "44": "Metal products",  # Metal structures
    "45": "Construction",  # Construction work
    "48": "Computer services",  # Software
    "50": "Repair services",  # Repair and maintenance
    "55": "Hotels",  # Hotel services
    "60": "Land transport",  # Transport services
    "63": "Transport support",  # Supporting transport services
    "64": "Post",  # Postal services
    "65": "Utilities",  # Public utilities
    "66": "Financial services",  # Financial services
    "70": "Real estate",  # Real estate services
    "71": "Architectural services",  # Engineering services
    "72": "Computer services",  # IT services
    "73": "R&D",  # Research services
    "75": "Public administration",  # Government services
    "77": "Agriculture",  # Agricultural services
    "79": "Other business services",  # Business services
    "80": "Education",  # Education services
    "85": "Health services",  # Health services
    "90": "Water supply",  # Sewage and waste
    "92": "Recreation",  # Recreation services
    "98": "Other services",  # Other services
}

# Default carbon intensity factors (kg CO2 per USD)
# Based on EXIOBASE 3.8.2 sector averages (reference year 2019).
# Used ONLY as fallback when the pre-computed carbon_factors_by_year.parquet
# is absent. In the published analysis, all contracts use parquet-derived values.
DEFAULT_CARBON_FACTORS = {
    "Agriculture": 0.85,
    "Mining": 1.20,
    "Food products": 0.65,
    "Textiles": 0.45,
    "Leather": 0.40,
    "Wood": 0.35,
    "Paper": 0.55,
    "Chemicals": 0.90,
    "Rubber and plastics": 0.70,
    "Non-metallic minerals": 0.95,
    "Basic metals": 1.10,
    "Metal products": 0.75,
    "Machinery": 0.35,
    "Electrical equipment": 0.40,
    "Computer equipment": 0.30,
    "Motor vehicles": 0.45,
    "Other transport": 0.50,
    "Furniture": 0.30,
    "Electricity": 1.50,
    "Gas": 0.80,
    "Water supply": 0.25,
    "Construction": 0.50,
    "Wholesale trade": 0.15,
    "Retail trade": 0.15,
    "Land transport": 0.85,
    "Water transport": 0.95,
    "Air transport": 1.80,
    "Transport support": 0.45,
    "Post": 0.20,
    "Hotels": 0.35,
    "Telecommunications": 0.15,
    "Financial services": 0.08,
    "Real estate": 0.12,
    "Computer services": 0.10,
    "R&D": 0.12,
    "Other business services": 0.15,
    "Public administration": 0.20,
    "Education": 0.15,
    "Health services": 0.25,
    "Recreation": 0.20,
    "Other services": 0.20,
    "Medical instruments": 0.30,
    "Precision instruments": 0.28,
    "Weapons": 0.60,
    "Repair services": 0.20,
    "Architectural services": 0.12,
    "Utilities": 0.60,
}


def load_gprd_data() -> pd.DataFrame:
    """Load the master GPRD dataset."""
    analysis_path = PROCESSED_DIR / "gprd_analysis.parquet"
    master_path = PROCESSED_DIR / "gprd_master.parquet"
    required_columns = [
        "record_id",
        "ocid",
        "country",
        "year",
        "month",
        "cpv_division",
        "cpv_code",
        "tender_date",
        "sector",
        "value_usd",
        "value_eur",
        "procurement_method",
        "n_bidders",
        "single_bidder",
        "competitive",
        "buyer_id",
        "supplier_id",
    ]

    def _load_parquet(path: Path) -> pd.DataFrame:
        try:
            import pyarrow.parquet as pq

            available_cols = set(pq.read_schema(path).names)
            cols = [c for c in required_columns if c in available_cols]
        except Exception:
            cols = required_columns
        return pd.read_parquet(path, columns=cols)

    # Prefer analysis subset for cleaner sample; fall back to master
    if analysis_path.exists():
        logger.info(f"Loading GPRD analysis: {analysis_path}")
        return _load_parquet(analysis_path)

    if master_path.exists():
        logger.info(f"Loading GPRD master: {master_path}")
        return _load_parquet(master_path)

    logger.error("No GPRD data found. Run harmonize_data.py first.")
    return pd.DataFrame()


def load_exiobase_carbon_factors() -> pd.DataFrame:
    """Load year-specific carbon factors from EXIOBASE processing."""
    path = EXIOBASE_DIR / "carbon_factors_by_year.parquet"
    if path.exists():
        logger.info(f"Loading EXIOBASE carbon factors: {path}")
        return normalize_exiobase_factors(pd.read_parquet(path))

    # Try CSV fallback
    csv_path = EXIOBASE_DIR / "carbon_factors_by_year.csv"
    if csv_path.exists():
        return normalize_exiobase_factors(pd.read_csv(csv_path))

    logger.warning("EXIOBASE carbon factors not found")
    return pd.DataFrame()


def normalize_exiobase_factors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize EXIOBASE carbon factors to expected columns.

    The EXIOBASE parser emits `gprd_sector`/`carbon_intensity_kg_per_usd`,
    while the linker expects `sector`/`carbon_intensity_kg_usd`.
    Harmonize column names and units so lookups do not fail.
    """
    if df.empty:
        return df

    normalized = df.copy()

    # Harmonize sector naming
    if "sector" not in normalized.columns:
        for cand in ["gprd_sector", "exiobase_sector"]:
            if cand in normalized.columns:
                normalized["sector"] = normalized[cand]
                break
    if "sector" not in normalized.columns:
        normalized["sector"] = ""
    normalized["sector"] = normalized["sector"].astype(str)

    # Harmonize carbon intensity column
    if "carbon_intensity_kg_usd" not in normalized.columns:
        if "carbon_intensity_kg_per_usd" in normalized.columns:
            normalized["carbon_intensity_kg_usd"] = normalized[
                "carbon_intensity_kg_per_usd"
            ]
        elif "emission_intensity_kg_co2_per_usd" in normalized.columns:
            normalized["carbon_intensity_kg_usd"] = normalized[
                "emission_intensity_kg_co2_per_usd"
            ]
        elif "carbon_intensity_kg_per_meur" in normalized.columns:
            normalized["carbon_intensity_kg_usd"] = (
                normalized["carbon_intensity_kg_per_meur"] / 1e6 * 1.1
            )
        elif "co2_kg" in normalized.columns and "output_meur" in normalized.columns:
            output = normalized["output_meur"].replace(0, np.nan)
            normalized["carbon_intensity_kg_usd"] = (
                (normalized["co2_kg"] / output) / 1e6 * 1.1
            )
    if "carbon_intensity_kg_usd" not in normalized.columns:
        normalized["carbon_intensity_kg_usd"] = np.nan

    # Ensure year is numeric for comparisons
    if "year" in normalized.columns:
        normalized["year"] = pd.to_numeric(normalized["year"], errors="coerce").astype(
            "Int64"
        )

    return normalized


def load_cpv_sectors() -> pd.DataFrame:
    """Load CPV to sector mapping."""
    path = REF_DIR / "cpv_sectors.csv"
    if path.exists():
        logger.info(f"Loading CPV sectors: {path}")
        return pd.read_csv(path)
    return pd.DataFrame()


def get_carbon_factor(cpv_division: str, year: int, exiobase_df: pd.DataFrame) -> float:
    """
    Get carbon intensity factor for a CPV division and year.

    Args:
        cpv_division: 2-digit CPV division code
        year: Year of the contract
        exiobase_df: EXIOBASE carbon factors DataFrame

    Returns:
        Carbon intensity in kg CO2 per USD
    """
    # Map CPV to EXIOBASE sector
    exio_sector = CPV_TO_EXIOBASE.get(cpv_division, "Other services")

    # Try year-specific factor from EXIOBASE
    if not exiobase_df.empty and "carbon_intensity_kg_usd" in exiobase_df.columns:
        # Clamp year to EXIOBASE range
        year_adj = min(max(year, 1995), 2022)

        # Ensure comparable dtypes
        sectors = exiobase_df.get("sector", "").fillna("").astype(str)
        if "year" in exiobase_df.columns:
            years = pd.to_numeric(exiobase_df["year"], errors="coerce")
        else:
            years = pd.Series([np.nan] * len(exiobase_df))

        # Look for matching sector and year
        mask = sectors.str.contains(exio_sector, case=False, na=False)
        if not years.isna().all():
            mask = mask & (years == year_adj)

        if mask.any():
            return float(exiobase_df.loc[mask, "carbon_intensity_kg_usd"].iloc[0])

        # Try without year specificity
        mask_sector = sectors.str.contains(exio_sector, case=False, na=False)
        if mask_sector.any():
            return float(exiobase_df.loc[mask_sector, "carbon_intensity_kg_usd"].mean())

    # Fall back to default factors
    return DEFAULT_CARBON_FACTORS.get(exio_sector, 0.30)


def link_carbon_to_contracts(
    df: pd.DataFrame, exiobase_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Link carbon intensity factors to each contract.

    Args:
        df: GPRD DataFrame
        exiobase_df: EXIOBASE carbon factors

    Returns:
        DataFrame with carbon columns added
    """
    logger.info("Linking carbon intensity to contracts...")

    # Work in-place to save memory - no copy needed

    # Ensure CPV division exists
    if "cpv_division" not in df.columns:
        if "cpv_code" in df.columns:
            df["cpv_division"] = df["cpv_code"].astype(str).str[:2]
        else:
            df["cpv_division"] = ""

    # Get unique CPV-year combinations for efficiency
    if "year" not in df.columns:
        df["year"] = pd.to_datetime(df["tender_date"]).dt.year

    cpv_years = df[["cpv_division", "year"]].drop_duplicates()
    logger.info(f"  Computing factors for {len(cpv_years)} CPV-year combinations")

    # Build lookup dictionary
    carbon_lookup = {}
    for _, row in tqdm(
        cpv_years.iterrows(), total=len(cpv_years), desc="  Building carbon lookup"
    ):
        cpv = row["cpv_division"]
        year = row["year"]
        try:
            year_int = int(year)
        except Exception:
            year_int = None

        if pd.notna(cpv) and year_int is not None:
            carbon_lookup[(cpv, year_int)] = get_carbon_factor(
                cpv, year_int, exiobase_df
            )

    # Apply to dataframe - vectorized approach
    logger.info("  Applying carbon factors to contracts...")

    # Create a lookup key
    def _build_key(row):
        cpv = row.get("cpv_division")
        year_val = row.get("year")
        if pd.isna(cpv) or pd.isna(year_val):
            return None
        try:
            return (cpv, int(year_val))
        except Exception:
            return None

    df["_lookup_key"] = df.apply(_build_key, axis=1)

    # Map the lookup
    default_factor = DEFAULT_CARBON_FACTORS.get("Other services", 0.30)
    df["carbon_intensity_kg_usd"] = (
        df["_lookup_key"].map(carbon_lookup).fillna(default_factor)
    )
    df.drop("_lookup_key", axis=1, inplace=True)

    # Calculate carbon footprint
    if "value_usd" in df.columns:
        df["carbon_footprint_kg"] = df["carbon_intensity_kg_usd"] * df["value_usd"]
        df["carbon_footprint_tonnes"] = df["carbon_footprint_kg"] / 1000

    # Add EXIOBASE sector
    df["exiobase_sector"] = (
        df["cpv_division"].map(CPV_TO_EXIOBASE).fillna("Other services")
    )

    return df


def calculate_carbon_statistics(df: pd.DataFrame) -> Dict:
    """Calculate carbon-related statistics."""
    stats = {
        "total_contracts": len(df),
        "contracts_with_carbon": int((df["carbon_intensity_kg_usd"] > 0).sum()),
        "carbon_coverage_rate": float((df["carbon_intensity_kg_usd"] > 0).mean()),
    }

    # Value statistics
    if df["carbon_intensity_kg_usd"].notna().any():
        stats["carbon_intensity"] = {
            "mean_kg_usd": float(df["carbon_intensity_kg_usd"].mean()),
            "median_kg_usd": float(df["carbon_intensity_kg_usd"].median()),
            "std_kg_usd": float(df["carbon_intensity_kg_usd"].std()),
            "min_kg_usd": float(df["carbon_intensity_kg_usd"].min()),
            "max_kg_usd": float(df["carbon_intensity_kg_usd"].max()),
        }

    # Total footprint
    if df["carbon_footprint_tonnes"].notna().any():
        stats["carbon_footprint"] = {
            "total_tonnes": float(df["carbon_footprint_tonnes"].sum()),
            "total_megatonnes": float(df["carbon_footprint_tonnes"].sum() / 1e6),
            "mean_per_contract_tonnes": float(df["carbon_footprint_tonnes"].mean()),
            "median_per_contract_tonnes": float(df["carbon_footprint_tonnes"].median()),
        }

    # By sector
    if "exiobase_sector" in df.columns:
        sector_stats = (
            df.groupby("exiobase_sector")
            .agg(
                {
                    "carbon_footprint_tonnes": ["sum", "mean", "count"],
                    "carbon_intensity_kg_usd": "mean",
                }
            )
            .round(2)
        )
        sector_stats.columns = [
            "total_tonnes",
            "mean_tonnes",
            "n_contracts",
            "mean_intensity",
        ]
        stats["by_sector"] = (
            sector_stats.sort_values("total_tonnes", ascending=False)
            .head(15)
            .to_dict("index")
        )

    # By year
    if "year" in df.columns:
        year_stats = (
            df.groupby("year")
            .agg(
                {
                    "carbon_footprint_tonnes": "sum",
                    "carbon_intensity_kg_usd": "mean",
                    "value_usd": "sum",
                }
            )
            .round(2)
        )
        year_stats["weighted_intensity"] = (
            year_stats["carbon_footprint_tonnes"] * 1000
        ) / year_stats["value_usd"]
        stats["by_year"] = year_stats.to_dict("index")

    # By country
    if "country" in df.columns:
        country_stats = (
            df.groupby("country")
            .agg(
                {
                    "carbon_footprint_tonnes": ["sum", "mean"],
                    "carbon_intensity_kg_usd": "mean",
                }
            )
            .round(2)
        )
        country_stats.columns = ["total_tonnes", "mean_tonnes", "mean_intensity"]
        stats["by_country"] = country_stats.sort_values(
            "total_tonnes", ascending=False
        ).to_dict("index")

    return stats


def analyze_carbon_trends(df: pd.DataFrame) -> Dict:
    """Analyze carbon intensity trends over time."""
    trends = {}

    if "year" not in df.columns or df["carbon_intensity_kg_usd"].isna().all():
        return trends

    # Filter to valid years
    yearly = df[(df["year"] >= 2012) & (df["year"] <= 2023)]

    # Average intensity by year
    intensity_trend = yearly.groupby("year")["carbon_intensity_kg_usd"].mean()

    if len(intensity_trend) >= 2:
        # Calculate trend (simple linear regression)
        years = np.array(intensity_trend.index)
        values = np.array(intensity_trend.values)

        slope, intercept = np.polyfit(years, values, 1)

        trends["intensity_trend"] = {
            "slope_per_year": float(slope),
            "intercept": float(intercept),
            "annual_change_percent": float(slope / values.mean() * 100),
            "start_value": float(values[0]),
            "end_value": float(values[-1]),
            "total_change_percent": float((values[-1] - values[0]) / values[0] * 100),
        }

        # Year-by-year values
        trends["yearly_intensity"] = intensity_trend.to_dict()

    # Weighted average (by value)
    if "value_usd" in yearly.columns:
        weighted = yearly.groupby("year", group_keys=False).apply(
            lambda x: (
                np.average(x["carbon_intensity_kg_usd"], weights=x["value_usd"])
                if x["value_usd"].sum() > 0
                else x["carbon_intensity_kg_usd"].mean()
            )
        )
        trends["yearly_weighted_intensity"] = weighted.to_dict()

    return trends


def main():
    """Main carbon linking process."""
    logger.info("=" * 70)
    logger.info("Carbon Intensity Linking Pipeline")
    logger.info("=" * 70)

    # Load data
    logger.info("\n[1/5] Loading data...")
    df = load_gprd_data()

    if df.empty:
        logger.error("No GPRD data to process!")
        return

    exiobase_df = load_exiobase_carbon_factors()

    # Link carbon factors
    logger.info("\n[2/5] Linking carbon factors...")
    df = link_carbon_to_contracts(df, exiobase_df)

    # Calculate statistics
    logger.info("\n[3/5] Calculating carbon statistics...")
    stats = calculate_carbon_statistics(df)

    # Analyze trends
    logger.info("\n[4/5] Analyzing carbon trends...")
    trends = analyze_carbon_trends(df)
    stats["trends"] = trends

    # Save outputs
    logger.info("\n[5/5] Saving outputs...")

    # Save enriched dataset
    output_path = PROCESSED_DIR / "gprd_with_carbon.parquet"
    df.to_parquet(output_path)
    logger.info(f"  Saved: {output_path}")

    # Save carbon-focused analysis dataset
    carbon_cols = [
        "record_id",
        "ocid",
        "country",
        "year",
        "month",
        "cpv_division",
        "sector",
        "exiobase_sector",
        "value_usd",
        "value_eur",
        "carbon_intensity_kg_usd",
        "carbon_footprint_kg",
        "carbon_footprint_tonnes",
        "procurement_method",
        "n_bidders",
        "single_bidder",
        "competitive",
        "buyer_id",
        "supplier_id",
    ]
    carbon_cols = [c for c in carbon_cols if c in df.columns]

    carbon_df = df[carbon_cols]
    carbon_path = PROCESSED_DIR / "gprd_carbon_analysis.parquet"
    carbon_df.to_parquet(carbon_path)
    logger.info(f"  Saved: {carbon_path}")

    # Save statistics
    stats_path = PROCESSED_DIR / "carbon_analysis_summary.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2, default=str)
    logger.info(f"  Saved: {stats_path}")

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("Carbon Linking Summary")
    logger.info("=" * 70)
    logger.info(f"Total contracts: {stats['total_contracts']:,}")
    logger.info(
        f"With carbon data: {stats['contracts_with_carbon']:,} ({stats['carbon_coverage_rate'] * 100:.1f}%)"
    )

    if "carbon_intensity" in stats:
        logger.info(f"\nCarbon Intensity (kg CO2/USD):")
        logger.info(f"  Mean: {stats['carbon_intensity']['mean_kg_usd']:.3f}")
        logger.info(f"  Median: {stats['carbon_intensity']['median_kg_usd']:.3f}")

    if "carbon_footprint" in stats:
        logger.info(f"\nTotal Carbon Footprint:")
        logger.info(f"  {stats['carbon_footprint']['total_megatonnes']:.2f} Mt CO2")

    if "trends" in stats and "intensity_trend" in stats["trends"]:
        trend = stats["trends"]["intensity_trend"]
        logger.info(f"\nCarbon Intensity Trend (2012-2023):")
        logger.info(f"  Change: {trend['total_change_percent']:.1f}%")
        logger.info(f"  Annual change: {trend['annual_change_percent']:.2f}%")

    logger.info("\n" + "=" * 70)
    logger.info("Carbon linking complete!")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
