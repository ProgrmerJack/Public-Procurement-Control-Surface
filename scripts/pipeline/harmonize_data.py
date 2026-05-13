#!/usr/bin/env python3
"""
Data Harmonization Pipeline for Global Procurement Research Dataset (GPRD)

Combines data from multiple sources:
- EU TED (Contract Award Notices)
- Colombia OCDS (SECOP)
- UK OCDS (Contracts Finder)
- EXIOBASE 3.8 (Carbon Intensity Factors)

Creates unified GPRD schema for cross-country analysis.

Output:
- Data/processed/gprd_master.parquet (full dataset)
- Data/processed/gprd_analysis.parquet (filtered for analysis)
- Data/processed/gprd_summary_stats.json

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

import pyarrow as pa
import pyarrow.parquet as pq

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def write_parquet_in_batches(
    df: pd.DataFrame,
    path: Path,
    *,
    batch_rows: int = 1_000_000,
    compression: str = "snappy",
) -> None:
    """Write a large DataFrame to Parquet without a single giant Arrow conversion.

    Pandas/pyarrow conversion of a 46M-row DataFrame can require large contiguous
    allocations (often 256MB+) during Table.from_pandas. Writing in batches keeps
    peak memory bounded and avoids ArrowMemoryError on constrained machines.
    
    Uses a unified schema derived from sampling the full DataFrame to avoid
    schema mismatch errors when some batches have all-null columns.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    total_rows = len(df)
    if total_rows == 0:
        empty_table = pa.Table.from_pandas(df.head(0), preserve_index=False, nthreads=1)
        with pq.ParquetWriter(str(path), empty_table.schema, compression=compression) as writer:
            writer.write_table(empty_table)
        return

    # Build a unified schema by sampling rows from throughout the DataFrame
    # This ensures we capture non-null values for type inference
    sample_indices = []
    n_samples = min(10000, total_rows)
    step = max(1, total_rows // n_samples)
    for i in range(0, total_rows, step):
        sample_indices.append(i)
        if len(sample_indices) >= n_samples:
            break
    
    sample_df = df.iloc[sample_indices]
    schema = pa.Schema.from_pandas(sample_df, preserve_index=False)
    del sample_df
    
    # Write batches with the unified schema
    with pq.ParquetWriter(
        str(path),
        schema,
        compression=compression,
        use_dictionary=True,
        write_statistics=True,
    ) as writer:
        for start in range(0, total_rows, batch_rows):
            end = min(start + batch_rows, total_rows)
            batch = df.iloc[start:end]
            
            # Convert batch to table with the unified schema
            table = pa.Table.from_pandas(batch, schema=schema, preserve_index=False, nthreads=1)
            writer.write_table(table)
            del table

# Paths
# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
BASE_DIR = _d
DATA_DIR = BASE_DIR / "Data"
PROCESSED_DIR = DATA_DIR / "processed"
REF_DIR = DATA_DIR / "reference"

# EU country codes to names
EU_COUNTRIES = {
    'AT': 'Austria', 'BE': 'Belgium', 'BG': 'Bulgaria', 'CY': 'Cyprus',
    'CZ': 'Czechia', 'DE': 'Germany', 'DK': 'Denmark', 'EE': 'Estonia',
    'EL': 'Greece', 'ES': 'Spain', 'FI': 'Finland', 'FR': 'France',
    'HR': 'Croatia', 'HU': 'Hungary', 'IE': 'Ireland', 'IT': 'Italy',
    'LT': 'Lithuania', 'LU': 'Luxembourg', 'LV': 'Latvia', 'MT': 'Malta',
    'NL': 'Netherlands', 'PL': 'Poland', 'PT': 'Portugal', 'RO': 'Romania',
    'SE': 'Sweden', 'SI': 'Slovenia', 'SK': 'Slovakia',
    'GB': 'United Kingdom', 'UK': 'United Kingdom',
    'CO': 'Colombia', 'NO': 'Norway', 'CH': 'Switzerland', 'IS': 'Iceland'
}

# OECD countries for filtering
OECD_COUNTRIES = [
    'AT', 'AU', 'BE', 'CA', 'CH', 'CL', 'CO', 'CZ', 'DE', 'DK',
    'EE', 'ES', 'FI', 'FR', 'GB', 'GR', 'HU', 'IE', 'IL', 'IS',
    'IT', 'JP', 'KR', 'LT', 'LU', 'LV', 'MX', 'NL', 'NO', 'NZ',
    'PL', 'PT', 'SE', 'SI', 'SK', 'TR', 'US'
]

# GPRD Schema (final columns)
GPRD_COLUMNS = [
    # Identifiers
    'record_id', 'ocid', 'contract_id', 'data_source',
    
    # Geography
    'country', 'country_name', 'buyer_region', 'is_oecd',
    
    # Temporal
    'tender_date', 'award_date', 'contract_date',
    'year', 'month', 'quarter', 'year_month',
    'time_to_award_days',
    
    # Values
    'value_local', 'currency_local', 'value_usd', 'value_eur',
    'value_usd_2020', 'log_value_usd',
    'estimated_value_usd',
    
    # Procurement method
    'procurement_method', 'procurement_method_category',
    'is_framework', 'is_emergency', 'is_above_threshold',
    
    # Competition
    'n_bidders', 'single_bidder', 'competitive',
    'hhi_buyer', 'hhi_sector',
    
    # Buyer
    'buyer_id', 'buyer_name', 'buyer_type', 'buyer_type_category',
    
    # Supplier
    'supplier_id', 'supplier_name', 'supplier_country', 'supplier_is_sme',
    'supplier_is_foreign',
    
    # Classification
    'cpv_code', 'cpv_division', 'cpv_group', 'cpv_class',
    'cpv_description', 'sector', 'gprd_sector',
    
    # Carbon (will be linked later)
    'carbon_intensity_kg_usd', 'carbon_footprint_kg',
    
    # Quality flags
    'flag_missing_value', 'flag_missing_dates', 'flag_outlier_value',
    'quality_score',
]

# EU Procurement thresholds (EUR, 2020 values for reference)
EU_THRESHOLDS_2020 = {
    'supplies_services_central': 139000,
    'supplies_services_subcentral': 214000,
    'works': 5350000,
    'social_services': 750000,
}

# Inflation adjustment factors to 2020 USD
INFLATION_FACTORS = {
    2012: 1.18, 2013: 1.15, 2014: 1.13, 2015: 1.13,
    2016: 1.11, 2017: 1.09, 2018: 1.06, 2019: 1.04,
    2020: 1.00, 2021: 0.95, 2022: 0.87, 2023: 0.84
}


def load_eu_ted_data() -> pd.DataFrame:
    """Load harmonized EU TED data."""
    path = PROCESSED_DIR / "eu_ted" / "eu_ted_harmonized.parquet"
    if path.exists():
        logger.info(f"Loading EU TED: {path}")
        df = pd.read_parquet(path)
        df['data_source'] = 'EU_TED'
        return df
    
    logger.warning("EU TED data not found")
    return pd.DataFrame()


def load_ocds_data() -> pd.DataFrame:
    """Load harmonized OCDS data (Colombia, UK)."""
    combined_path = PROCESSED_DIR / "ocds" / "ocds_combined.parquet"
    
    if combined_path.exists():
        logger.info(f"Loading OCDS combined: {combined_path}")
        return pd.read_parquet(combined_path)
    
    # Try loading individual files
    dfs = []
    for country in ['colombia', 'uk']:
        path = PROCESSED_DIR / "ocds" / f"{country}_harmonized.parquet"
        if path.exists():
            logger.info(f"Loading {country}: {path}")
            df = pd.read_parquet(path)
            dfs.append(df)
    
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    
    logger.warning("OCDS data not found")
    return pd.DataFrame()


def load_carbon_factors() -> pd.DataFrame:
    """Load carbon intensity factors from EXIOBASE processing."""
    # Try processed EXIOBASE
    path = PROCESSED_DIR / "exiobase" / "cpv_carbon_factors.parquet"
    if path.exists():
        logger.info(f"Loading carbon factors: {path}")
        return pd.read_parquet(path)
    
    # Try reference file
    ref_path = REF_DIR / "emission_factors.csv"
    if ref_path.exists():
        logger.info(f"Loading reference emission factors: {ref_path}")
        return pd.read_csv(ref_path)
    
    logger.warning("Carbon factors not found")
    return pd.DataFrame()


def load_cpv_sectors() -> pd.DataFrame:
    """Load CPV to sector mapping."""
    path = REF_DIR / "cpv_sectors.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def standardize_columns(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Standardize column names and types across sources."""
    # Work in-place to save memory - no copy needed
    
    # Ensure all GPRD columns exist
    for col in GPRD_COLUMNS:
        if col not in df.columns:
            df[col] = None
    
    # Standardize country codes
    if 'country' in df.columns:
        df['country'] = df['country'].fillna('').astype(str).str.upper().str.strip()
        # Map variations
        df['country'] = df['country'].replace({'UK': 'GB', 'EL': 'GR', '': np.nan})
    
    # Standardize country names
    if 'country' in df.columns:
        df['country_name'] = df['country'].map(EU_COUNTRIES).fillna(df.get('country_name', ''))
        df['is_oecd'] = df['country'].isin(OECD_COUNTRIES)
    
    # Date parsing - optimized for 46M records
    logger.info("  Parsing dates...")
    for date_col in ['tender_date', 'award_date', 'contract_date']:
        if date_col in df.columns:
            # Replace string 'None' with actual None
            df[date_col] = df[date_col].replace('None', None)
            df[date_col] = df[date_col].replace('nan', None)
            
            # Fast parsing with format specification (ISO format is fastest)
            # Try multiple common formats
            try:
                # First try: already datetime
                if pd.api.types.is_datetime64_any_dtype(df[date_col]):
                    continue
                
                # Second try: ISO format YYYY-MM-DD (fastest)
                df[date_col] = pd.to_datetime(df[date_col], format='%Y-%m-%d', errors='coerce')
            except:
                try:
                    # Third try: ISO with time
                    df[date_col] = pd.to_datetime(df[date_col], format='%Y-%m-%d %H:%M:%S', errors='coerce')
                except:
                    # Final fallback: mixed formats (slower but works)
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce', cache=True)
    logger.info("  Dates parsed")
    
    # Temporal derived columns
    if 'tender_date' in df.columns:
        year_from_date = df['tender_date'].dt.year
        month_from_date = df['tender_date'].dt.month
        quarter_from_date = df['tender_date'].dt.quarter
        year_month_from_date = df['tender_date'].dt.to_period('M').astype(str)

        # Preserve existing year/month if already present, only fill gaps
        if 'year' in df.columns:
            df['year'] = pd.to_numeric(df['year'], errors='coerce')
            df['year'] = df['year'].fillna(year_from_date)
        else:
            df['year'] = year_from_date

        if 'month' in df.columns:
            df['month'] = pd.to_numeric(df['month'], errors='coerce')
            df['month'] = df['month'].fillna(month_from_date)
        else:
            df['month'] = month_from_date

        if 'quarter' in df.columns:
            df['quarter'] = pd.to_numeric(df['quarter'], errors='coerce')
            df['quarter'] = df['quarter'].fillna(quarter_from_date)
        else:
            df['quarter'] = quarter_from_date

        if 'year_month' in df.columns:
            df['year_month'] = df['year_month'].fillna(year_month_from_date)
        else:
            df['year_month'] = year_month_from_date
    
    # Value adjustments
    if 'value_usd' in df.columns:
        df['value_usd'] = pd.to_numeric(df['value_usd'], errors='coerce')
        df['log_value_usd'] = np.log10(df['value_usd'].clip(lower=1))
        
        # Inflation adjustment to 2020 USD (vectorized for memory efficiency)
        if 'year' in df.columns:
            # Directly map without creating intermediate column
            year_factors = df['year'].fillna(2020).astype(int).map(INFLATION_FACTORS).fillna(1.0)
            df['value_usd_2020'] = df['value_usd'] * year_factors
            del year_factors  # Free memory
        else:
            df['value_usd_2020'] = df['value_usd']
    
    # Competition standardization
    if 'n_bidders' in df.columns:
        df['n_bidders'] = pd.to_numeric(df['n_bidders'], errors='coerce')
        df['single_bidder'] = df['n_bidders'] == 1
        df['competitive'] = df['n_bidders'] > 1
    
    # CPV processing
    if 'cpv_code' in df.columns:
        df['cpv_code'] = df['cpv_code'].fillna('').astype(str).str.strip().replace('None', '')
        df['cpv_division'] = df['cpv_code'].str[:2]
        df['cpv_group'] = df['cpv_code'].str[:3]
        df['cpv_class'] = df['cpv_code'].str[:4]
    
    # Supplier foreign flag
    if 'supplier_country' in df.columns and 'country_name' in df.columns:
        df['supplier_is_foreign'] = df['supplier_country'] != df['country_name']
    
    # Above threshold flag (simplified - uses 139k EUR threshold)
    if 'value_eur' in df.columns:
        df['is_above_threshold'] = df['value_eur'] > 139000
    
    # Procurement method categorization
    if 'procurement_method' in df.columns:
        method_map = {
            'open': 'OPEN',
            'selective': 'RESTRICTED',
            'limited': 'NEGOTIATED',
            'direct': 'DIRECT',
            'competitive dialogue': 'COMPETITIVE_DIALOGUE',
            'innovation partnership': 'INNOVATION',
        }
        # Use fillna and astype to avoid NaN issues
        proc_lower = df['procurement_method'].fillna('').astype(str).str.lower()
        df['procurement_method_category'] = 'OTHER'
        for key, value in method_map.items():
            mask = proc_lower.str.contains(key, na=False)
            df.loc[mask, 'procurement_method_category'] = value
        del proc_lower  # Free memory
    
    # Buyer type categorization
    if 'buyer_type' in df.columns:
        buyer_type_map = {
            'central': 'CENTRAL_GOVERNMENT',
            'regional': 'REGIONAL_AUTHORITY',
            'local': 'LOCAL_AUTHORITY',
            'body': 'PUBLIC_BODY',
            'utility': 'UTILITY',
        }
        # Use fillna and astype to avoid NaN issues
        buyer_lower = df['buyer_type'].fillna('').astype(str).str.lower()
        df['buyer_type_category'] = 'OTHER'
        for key, value in buyer_type_map.items():
            mask = buyer_lower.str.contains(key, na=False)
            df.loc[mask, 'buyer_type_category'] = value
        del buyer_lower  # Free memory
    
    # Generate record ID
    df['record_id'] = df['data_source'].astype(str) + '_' + df.index.astype(str)
    
    return df


def calculate_market_concentration(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate HHI indices for buyer and sector concentration."""
    logger.info("Calculating market concentration indices...")
    
    # HHI by buyer (supplier concentration per buyer)
    if 'buyer_id' in df.columns and 'supplier_id' in df.columns and 'value_usd' in df.columns:
        buyer_supplier = df.groupby(['buyer_id', 'supplier_id'])['value_usd'].sum().reset_index()
        buyer_total = df.groupby('buyer_id')['value_usd'].sum()
        
        # Vectorized share calculation
        buyer_supplier['buyer_total'] = buyer_supplier['buyer_id'].map(buyer_total)
        buyer_supplier['share'] = buyer_supplier['value_usd'] / buyer_supplier['buyer_total']
        buyer_supplier['share_sq'] = buyer_supplier['share'] ** 2
        
        hhi_buyer = buyer_supplier.groupby('buyer_id')['share_sq'].sum()
        
        # Use map instead of merge to avoid memory allocation
        df['hhi_buyer'] = df['buyer_id'].map(hhi_buyer)
    
    # HHI by sector (supplier concentration per sector)
    if 'sector' in df.columns and 'supplier_id' in df.columns and 'value_usd' in df.columns:
        sector_supplier = df.groupby(['sector', 'supplier_id'])['value_usd'].sum().reset_index()
        sector_total = df.groupby('sector')['value_usd'].sum()
        
        # Vectorized share calculation
        sector_supplier['sector_total'] = sector_supplier['sector'].map(sector_total)
        sector_supplier['share'] = sector_supplier['value_usd'] / sector_supplier['sector_total']
        sector_supplier['share_sq'] = sector_supplier['share'] ** 2
        
        hhi_sector = sector_supplier.groupby('sector')['share_sq'].sum()
        
        # Use map instead of merge to avoid memory allocation
        df['hhi_sector'] = df['sector'].map(hhi_sector)
    
    return df


def link_carbon_intensity(df: pd.DataFrame, carbon_df: pd.DataFrame, cpv_sectors: pd.DataFrame) -> pd.DataFrame:
    """Link carbon intensity factors to contracts."""
    logger.info("Linking carbon intensity factors...")
    
    if carbon_df.empty:
        logger.warning("No carbon factors available")
        df['carbon_intensity_kg_usd'] = np.nan
        df['carbon_footprint_kg'] = np.nan
        return df
    
    # First try CPV-based linking
    if not cpv_sectors.empty and 'cpv_division' in df.columns:
        if 'emission_intensity_kg_usd' in cpv_sectors.columns:
            cpv_carbon = cpv_sectors[['cpv_division', 'emission_intensity_kg_usd']].drop_duplicates()
            cpv_carbon['cpv_division'] = cpv_carbon['cpv_division'].astype(str).str.zfill(2)
            
            # Create dictionary for mapping
            cpv_dict = dict(zip(cpv_carbon['cpv_division'], cpv_carbon['emission_intensity_kg_usd']))
            
            # Use map instead of merge to avoid memory allocation
            df['carbon_intensity_kg_usd'] = df['cpv_division'].map(cpv_dict)
    
    # Fall back to sector-based linking
    if 'carbon_intensity_kg_usd' not in df.columns or df['carbon_intensity_kg_usd'].isna().all():
        if 'sector' in carbon_df.columns and 'carbon_intensity' in carbon_df.columns:
            sector_carbon = carbon_df[['sector', 'carbon_intensity']].drop_duplicates()
            
            # Create dictionary for mapping
            sector_dict = dict(zip(sector_carbon['sector'], sector_carbon['carbon_intensity']))
            
            if 'sector' in df.columns:
                # Use map instead of merge to avoid memory allocation
                df['carbon_intensity_kg_usd'] = df['sector'].map(sector_dict)
    
    # Calculate carbon footprint
    if 'carbon_intensity_kg_usd' in df.columns and 'value_usd' in df.columns:
        df['carbon_footprint_kg'] = df['carbon_intensity_kg_usd'] * df['value_usd']
    
    return df


def calculate_quality_score(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate data quality score for each record."""
    # Work in-place to save memory
    
    # Quality criteria
    criteria = []
    
    if 'value_usd' in df.columns:
        criteria.append(df['value_usd'].notna() & (df['value_usd'] > 0))
    
    if 'tender_date' in df.columns:
        criteria.append(df['tender_date'].notna())
    
    if 'award_date' in df.columns:
        criteria.append(df['award_date'].notna())
    
    if 'buyer_id' in df.columns:
        criteria.append(df['buyer_id'].notna() & (df['buyer_id'] != ''))
    
    if 'supplier_id' in df.columns:
        criteria.append(df['supplier_id'].notna() & (df['supplier_id'] != ''))
    
    if 'cpv_code' in df.columns:
        criteria.append(df['cpv_code'].notna() & (df['cpv_code'].str.len() >= 2))
    
    if 'n_bidders' in df.columns:
        criteria.append(df['n_bidders'].notna() & (df['n_bidders'] > 0))
    
    # Calculate score (0-1)
    if criteria:
        df['quality_score'] = sum(c.astype(float) for c in criteria) / len(criteria)
    else:
        df['quality_score'] = 0.5
    
    return df


def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Flag outlier values."""
    # Work in-place to save memory
    
    if 'value_usd' in df.columns:
        # Flag very small or very large values
        df['flag_outlier_value'] = (df['value_usd'] < 100) | (df['value_usd'] > 1e12)
    
    return df


def generate_summary_statistics(df: pd.DataFrame) -> Dict:
    """Generate comprehensive summary statistics."""
    summary = {
        'dataset_info': {
            'total_records': len(df),
            'date_generated': datetime.now().isoformat(),
            'years_covered': sorted(df['year'].dropna().unique().tolist()),
        },
        'by_source': df['data_source'].value_counts().to_dict(),
        'by_country': df['country'].value_counts().to_dict(),
        'by_year': df['year'].value_counts().sort_index().to_dict(),
        'by_sector': df['sector'].value_counts().to_dict(),
        'value_statistics': {
            'total_usd': float(df['value_usd'].sum()),
            'mean_usd': float(df['value_usd'].mean()),
            'median_usd': float(df['value_usd'].median()),
            'std_usd': float(df['value_usd'].std()),
        },
        'competition_statistics': {
            'mean_bidders': float(df['n_bidders'].mean()) if df['n_bidders'].notna().any() else None,
            'single_bidder_rate': float(df['single_bidder'].mean()) if df['single_bidder'].notna().any() else None,
            'competitive_rate': float(df['competitive'].mean()) if df['competitive'].notna().any() else None,
        },
        'quality_statistics': {
            'mean_quality_score': float(df['quality_score'].mean()) if 'quality_score' in df.columns else None,
            'missing_value_rate': float(df['flag_missing_value'].mean()) if 'flag_missing_value' in df.columns else None,
            'outlier_rate': float(df['flag_outlier_value'].mean()) if 'flag_outlier_value' in df.columns else None,
        },
        'carbon_statistics': {
            'mean_carbon_intensity': float(df['carbon_intensity_kg_usd'].mean()) if df['carbon_intensity_kg_usd'].notna().any() else None,
            'total_carbon_footprint_mt': float(df['carbon_footprint_kg'].sum() / 1e9) if df['carbon_footprint_kg'].notna().any() else None,
        },
        'n_unique': {
            'buyers': int(df['buyer_id'].nunique()),
            'suppliers': int(df['supplier_id'].nunique()),
            'countries': int(df['country'].nunique()),
            'cpv_divisions': int(df['cpv_division'].nunique()) if 'cpv_division' in df.columns else 0,
        }
    }
    
    return summary


def main():
    """Main harmonization pipeline."""
    logger.info("=" * 70)
    logger.info("Global Procurement Research Dataset (GPRD) Harmonization Pipeline")
    logger.info("=" * 70)
    
    # Create output directories
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load data from all sources
    logger.info("\n[1/6] Loading data sources...")
    
    dfs = []
    
    # EU TED
    eu_df = load_eu_ted_data()
    if not eu_df.empty:
        logger.info(f"  EU TED: {len(eu_df):,} records")
        dfs.append(eu_df)
    
    # OCDS (Colombia, UK)
    ocds_df = load_ocds_data()
    if not ocds_df.empty:
        logger.info(f"  OCDS: {len(ocds_df):,} records")
        dfs.append(ocds_df)
    
    if not dfs:
        logger.error("No data loaded! Please run parse_eu_ted.py and parse_ocds_jsonl.py first.")
        return
    
    # Combine all sources
    logger.info("\n[2/6] Combining data sources...")
    combined_df = pd.concat(dfs, ignore_index=True)
    logger.info(f"  Combined: {len(combined_df):,} records")
    
    # Standardize columns
    logger.info("\n[3/6] Standardizing columns...")
    df = standardize_columns(combined_df, 'combined')
    logger.info(f"  Standardized columns: {len(df.columns)}")
    
    # Load auxiliary data
    logger.info("\n[4/6] Loading auxiliary data and linking...")
    carbon_df = load_carbon_factors()
    cpv_sectors = load_cpv_sectors()
    
    # Link carbon intensity
    df = link_carbon_intensity(df, carbon_df, cpv_sectors)
    
    # Calculate market concentration
    df = calculate_market_concentration(df)
    
    # Calculate quality scores
    logger.info("\n[5/6] Calculating quality metrics...")
    df = calculate_quality_score(df)
    df = flag_outliers(df)
    
    # Fix data types BEFORE filtering to avoid SettingWithCopyWarning
    # Force consistent numeric types (even if column is all-null, it gets a proper dtype)
    numeric_cols = [
        'time_to_award_days', 'n_bidders', 'value_local', 'value_usd', 'value_eur',
        'value_usd_2020', 'log_value_usd', 'estimated_value_usd',
        'hhi_buyer', 'hhi_sector', 'carbon_intensity_kg_usd', 'carbon_footprint_kg',
        'quality_score', 'year', 'month', 'quarter'
    ]
    for col in numeric_cols:
        if col in df.columns:
            # Force to float64 regardless of current dtype (handles object and null columns)
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')
    
    # Convert boolean columns - handle various input types safely
    bool_cols = [
        'is_framework', 'is_emergency', 'is_above_threshold',
        'single_bidder', 'competitive', 'supplier_is_sme', 'supplier_is_foreign',
        'is_oecd', 'is_outlier_value', 'is_outlier_time'
    ]
    for col in bool_cols:
        if col in df.columns:
            # First convert to bool-compatible values (handle strings, numbers, etc)
            if df[col].dtype == 'object':
                # Map common string representations to boolean
                bool_series = df[col].map({
                    'true': True, 'True': True, 'TRUE': True, 't': True, 'T': True, '1': True, 1: True, 1.0: True,
                    'false': False, 'False': False, 'FALSE': False, 'f': False, 'F': False, '0': False, 0: False, 0.0: False,
                    True: True, False: False
                })
                df[col] = bool_series
            # Now safely convert to boolean dtype (nullable)
            try:
                df[col] = df[col].astype('boolean')
            except TypeError:
                # If conversion fails, keep as-is (will be object/bool)
                pass
    
    # Force string columns to proper string dtype (avoid null type inference issues)
    string_cols = [
        'record_id', 'ocid', 'contract_id', 'data_source', 'country', 'country_name',
        'buyer_region', 'year_month', 'currency_local', 'procurement_method',
        'procurement_method_category', 'buyer_id', 'buyer_name', 'buyer_type',
        'buyer_type_category', 'supplier_id', 'supplier_name', 'supplier_country',
        'cpv_code', 'cpv_division', 'cpv_group', 'cpv_class', 'cpv_description',
        'sector', 'gprd_sector'
    ]
    for col in string_cols:
        if col in df.columns:
            # Convert to string, replacing None/NaN with empty string then back to proper nulls
            df[col] = df[col].astype('object').where(df[col].notna(), None)
    
    # Filter to GPRD columns (after dtype conversion to avoid copy issues)
    available_cols = [c for c in GPRD_COLUMNS if c in df.columns]
    df = df[available_cols]
    
    # Save outputs
    logger.info("\n[6/6] Saving outputs...")
    
    # Full dataset
    master_path = PROCESSED_DIR / "gprd_master.parquet"
    write_parquet_in_batches(df, master_path)
    logger.info(f"  Saved master dataset: {master_path}")
    logger.info(f"  Size: {master_path.stat().st_size / 1e9:.2f} GB")
    
    # Analysis dataset (filtered)
    # Filter: valid years, OECD countries, reasonable values
    analysis_df = df[
        (df['year'] >= 2012) & (df['year'] <= 2023) &
        (df['is_oecd'] == True) &
        (df['value_usd'] > 1000) & (df['value_usd'] < 1e10) &
        (df['quality_score'] >= 0.3)
    ]
    
    analysis_path = PROCESSED_DIR / "gprd_analysis.parquet"
    write_parquet_in_batches(analysis_df, analysis_path, batch_rows=1_000_000)
    logger.info(f"  Saved analysis dataset: {analysis_path} ({len(analysis_df):,} records)")
    
    # Sample for inspection
    sample_path = PROCESSED_DIR / "gprd_sample_10000.csv"
    df.sample(min(10000, len(df))).to_csv(sample_path, index=False)
    
    # Summary statistics
    summary = generate_summary_statistics(df)
    summary_path = PROCESSED_DIR / "gprd_summary_stats.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info(f"  Saved summary: {summary_path}")
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("Dataset Summary")
    logger.info("=" * 70)
    logger.info(f"Total records: {summary['dataset_info']['total_records']:,}")
    logger.info(f"Years: {min(summary['dataset_info']['years_covered'])} - {max(summary['dataset_info']['years_covered'])}")
    logger.info(f"Countries: {summary['n_unique']['countries']}")
    logger.info(f"Buyers: {summary['n_unique']['buyers']:,}")
    logger.info(f"Suppliers: {summary['n_unique']['suppliers']:,}")
    logger.info(f"Total value: ${summary['value_statistics']['total_usd']/1e12:.2f}T USD")
    if summary['competition_statistics']['single_bidder_rate']:
        logger.info(f"Single-bidder rate: {summary['competition_statistics']['single_bidder_rate']*100:.1f}%")
    
    logger.info("\n" + "=" * 70)
    logger.info("Harmonization complete!")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
