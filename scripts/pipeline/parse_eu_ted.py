#!/usr/bin/env python3
"""
EU TED (Tenders Electronic Daily) Data Processor

Parses EU TED CSV exports (Contract Award Notices and Contract Notices)
and harmonizes them to the GPRD (Global Procurement Research Dataset) schema.

The EU TED data contains procurement from 27 EU member states + EEA countries,
covering years 2006-2023 with ~23.5 GB of CSV files.

Output:
- Data/processed/eu_ted/contracts_harmonized.parquet
- Data/processed/eu_ted/yearly/*.parquet (one file per year)

Author: Abduxoliq Ashuraliyev
License: MIT
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Iterator
import logging
import json
from datetime import datetime
import re

import numpy as np
import pandas as pd
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base paths
# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
BASE_DIR = _d
DATA_DIR = BASE_DIR / "Data"
RAW_TED = DATA_DIR / "raw" / "ocds" / "eu_ted"
OUTPUT_DIR = DATA_DIR / "processed" / "eu_ted"
REF_DIR = DATA_DIR / "reference"

# GPRD Schema columns (subset for TED data)
GPRD_COLUMNS = [
    # Identifiers
    "ocid", "contract_id", "notice_id", "country", "country_name",
    # Temporal
    "tender_date", "award_date", "dispatch_date", "year", "month", "quarter",
    "time_to_award_days",
    # Monetary
    "value_local", "currency_local", "value_eur", "value_usd",
    "estimated_value_eur",
    # Procurement method
    "procurement_method", "procurement_method_details", "procedure_type",
    "contract_type", "is_framework", "is_dps",
    # Buyer
    "buyer_id", "buyer_name", "buyer_address", "buyer_city", "buyer_postal_code",
    "buyer_type", "main_activity",
    # Supplier
    "supplier_id", "supplier_name", "supplier_address", "supplier_city",
    "supplier_postal_code", "supplier_country", "supplier_is_sme",
    # Competition
    "n_bidders", "n_bidders_sme", "n_bidders_other_eu", "n_bidders_non_eu",
    "n_bidders_electronic", "single_bidder", "competitive",
    # Classification
    "cpv_code", "cpv_main", "cpv_additional", "cpv_division", "cpv_group",
    "nuts_code", "gpa_covered",
    # Contract specifics
    "lot_number", "lots_total", "contract_number", "contract_title",
    # Award info
    "award_id", "award_criteria", "price_weight",
    "info_non_award", "awarded_to_group",
    # Quality flags
    "flag_missing_value", "flag_missing_dates", "flag_cancelled",
    "flag_correction", "data_source"
]

# TED column mapping to GPRD
TED_COLUMN_MAP = {
    "ID_NOTICE_CAN": "notice_id",
    "TED_NOTICE_URL": "notice_url",
    "YEAR": "year",
    "ID_TYPE": "notice_type",
    "DT_DISPATCH": "dispatch_date",
    "XSD_VERSION": "xsd_version",
    "CANCELLED": "flag_cancelled",
    "CORRECTIONS": "flag_correction",
    "B_MULTIPLE_CAE": "multiple_buyers",
    "CAE_NAME": "buyer_name",
    "CAE_NATIONALID": "buyer_id",
    "CAE_ADDRESS": "buyer_address",
    "CAE_TOWN": "buyer_city",
    "CAE_POSTAL_CODE": "buyer_postal_code",
    "CAE_GPA_ANNEX": "gpa_annex",
    "ISO_COUNTRY_CODE": "country",
    "ISO_COUNTRY_CODE_GPA": "country_gpa",
    "B_MULTIPLE_COUNTRY": "multiple_country",
    "ISO_COUNTRY_CODE_ALL": "all_countries",
    "CAE_TYPE": "buyer_type_code",
    "EU_INST_CODE": "eu_institution",
    "MAIN_ACTIVITY": "main_activity",
    "B_ON_BEHALF": "on_behalf",
    "B_INVOLVES_JOINT_PROCUREMENT": "joint_procurement",
    "B_AWARDED_BY_CENTRAL_BODY": "central_body",
    "TYPE_OF_CONTRACT": "contract_type_code",
    "TAL_LOCATION_NUTS": "nuts_code",
    "B_FRA_AGREEMENT": "is_framework",
    "FRA_ESTIMATED": "framework_estimated",
    "B_FRA_CONTRACT": "is_framework_contract",
    "B_DYN_PURCH_SYST": "is_dps",
    "CPV": "cpv_code",
    "MAIN_CPV_CODE_GPA": "cpv_main_gpa",
    "ID_LOT": "lot_id",
    "ADDITIONAL_CPVS": "cpv_additional",
    "B_GPA": "gpa_covered",
    "GPA_COVERAGE": "gpa_coverage",
    "LOTS_NUMBER": "lots_total",
    "VALUE_EURO": "value_eur",
    "VALUE_EURO_FIN_1": "value_eur_fin1",
    "VALUE_EURO_FIN_2": "value_eur_fin2",
    "B_EU_FUNDS": "eu_funded",
    "TOP_TYPE": "procedure_type_code",
    "B_ACCELERATED": "accelerated",
    "OUT_OF_DIRECTIVES": "out_of_directives",
    "CRIT_CODE": "award_criteria_code",
    "CRIT_PRICE_WEIGHT": "price_weight",
    "CRIT_CRITERIA": "criteria_list",
    "CRIT_WEIGHTS": "criteria_weights",
    "B_ELECTRONIC_AUCTION": "electronic_auction",
    "NUMBER_AWARDS": "n_awards",
    "ID_AWARD": "award_id",
    "ID_LOT_AWARDED": "lot_awarded",
    "INFO_ON_NON_AWARD": "info_non_award",
    "INFO_UNPUBLISHED": "info_unpublished",
    "B_AWARDED_TO_A_GROUP": "awarded_to_group",
    "WIN_NAME": "supplier_name",
    "WIN_NATIONALID": "supplier_id",
    "WIN_ADDRESS": "supplier_address",
    "WIN_TOWN": "supplier_city",
    "WIN_POSTAL_CODE": "supplier_postal_code",
    "WIN_COUNTRY_CODE": "supplier_country",
    "B_CONTRACTOR_SME": "supplier_is_sme",
    "CONTRACT_NUMBER": "contract_number",
    "TITLE": "contract_title",
    "NUMBER_OFFERS": "n_bidders",
    "NUMBER_TENDERS_SME": "n_bidders_sme",
    "NUMBER_TENDERS_OTHER_EU": "n_bidders_other_eu",
    "NUMBER_TENDERS_NON_EU": "n_bidders_non_eu",
    "NUMBER_OFFERS_ELECTR": "n_bidders_electronic",
    "AWARD_EST_VALUE_EURO": "estimated_value_eur",
    "AWARD_VALUE_EURO": "award_value_eur",
    "AWARD_VALUE_EURO_FIN_1": "award_value_fin1",
    "B_SUBCONTRACTED": "subcontracted",
    "DT_AWARD": "award_date",
}

# Country code to name mapping
COUNTRY_NAMES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus",
    "CZ": "Czechia", "DE": "Germany", "DK": "Denmark", "EE": "Estonia",
    "ES": "Spain", "FI": "Finland", "FR": "France", "GR": "Greece",
    "HR": "Croatia", "HU": "Hungary", "IE": "Ireland", "IT": "Italy",
    "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta",
    "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
    "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia",
    # EEA and others
    "IS": "Iceland", "LI": "Liechtenstein", "NO": "Norway", "CH": "Switzerland",
    "UK": "United Kingdom", "GB": "United Kingdom",
}

# Buyer type mapping
BUYER_TYPE_MAP = {
    "1": "Central government",
    "2": "Regional/local authority",
    "3": "Body governed by public law",
    "4": "EU institution",
    "5": "International organisation",
    "6": "Public undertaking",
    "8": "Utilities",
    "N": "National agency",
    "R": "Regional agency",
    "Z": "Other",
}

# Procedure type mapping
PROCEDURE_TYPE_MAP = {
    "OPE": "Open",
    "RES": "Restricted",
    "NEG": "Negotiated with competition",
    "NOC": "Negotiated without competition",
    "COD": "Competitive dialogue",
    "AWP": "Award without prior publication",
    "DPS": "Dynamic purchasing system",
    "NIC": "Innovation partnership",
    "QUO": "Request for quotation",
}

# Contract type mapping
CONTRACT_TYPE_MAP = {
    "W": "Works",
    "S": "Services",
    "U": "Supplies",
}

# Award criteria mapping
AWARD_CRITERIA_MAP = {
    "L": "Lowest price",
    "M": "Most economically advantageous",
    "C": "Cost",
}


def parse_ted_date(date_str: str) -> Optional[datetime]:
    """Parse TED date format (DD/MM/YY or DD/MM/YYYY)."""
    if pd.isna(date_str) or date_str == "":
        return None
    
    date_str = str(date_str).strip()
    
    for fmt in ["%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def parse_cpv_code(cpv_str: str) -> Tuple[str, str, str]:
    """
    Parse CPV code into division, group, and full code.
    
    CPV format: NNNNNNNN (8 digits) or NNNNNNNN-N (with check digit)
    """
    if pd.isna(cpv_str) or cpv_str == "":
        return "", "", ""
    
    cpv_str = str(cpv_str).strip()
    
    # Remove check digit if present
    cpv_clean = cpv_str.split('-')[0].replace(" ", "")
    
    # Ensure 8 digits
    if len(cpv_clean) < 2:
        return "", "", cpv_str
    
    division = cpv_clean[:2]
    group = cpv_clean[:3] if len(cpv_clean) >= 3 else division
    
    return division, group, cpv_clean


def convert_value_to_usd(value_eur: float, year: int) -> float:
    """Convert EUR to USD using average exchange rate for year."""
    # Average EUR/USD rates by year (from ECB)
    eur_usd_rates = {
        2006: 1.26, 2007: 1.37, 2008: 1.47, 2009: 1.39, 2010: 1.33,
        2011: 1.39, 2012: 1.29, 2013: 1.33, 2014: 1.33, 2015: 1.11,
        2016: 1.11, 2017: 1.13, 2018: 1.18, 2019: 1.12, 2020: 1.14,
        2021: 1.18, 2022: 1.05, 2023: 1.08
    }
    
    rate = eur_usd_rates.get(year, 1.10)
    return value_eur * rate if pd.notna(value_eur) else np.nan


def process_ted_file(file_path: Path, year: int) -> pd.DataFrame:
    """
    Process a single TED CSV file.
    
    Args:
        file_path: Path to CSV file
        year: Year of data
        
    Returns:
        Harmonized DataFrame
    """
    logger.info(f"Processing: {file_path.name}")
    
    # Read CSV with proper encoding
    try:
        df = pd.read_csv(file_path, low_memory=False, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, low_memory=False, encoding='latin-1')
    
    logger.info(f"  Loaded {len(df):,} records")
    
    # Rename columns
    df_renamed = df.rename(columns=TED_COLUMN_MAP)
    
    # Create harmonized records
    records = []
    
    for idx, row in tqdm(df_renamed.iterrows(), total=len(df_renamed), 
                         desc=f"  Processing {year}", leave=False):
        try:
            record = {}
            
            # Identifiers
            record['notice_id'] = row.get('notice_id', '')
            record['ocid'] = f"ocds-ted-eu-{row.get('notice_id', idx)}"
            record['contract_id'] = f"{row.get('notice_id', '')}-{row.get('lot_id', '0')}"
            record['country'] = row.get('country', '')
            record['country_name'] = COUNTRY_NAMES.get(row.get('country', ''), row.get('country', ''))
            
            # Temporal
            record['year'] = int(year)
            dispatch_date = parse_ted_date(row.get('dispatch_date', ''))
            award_date = parse_ted_date(row.get('award_date', ''))
            record['dispatch_date'] = dispatch_date
            record['award_date'] = award_date
            record['tender_date'] = dispatch_date  # Use dispatch as tender date proxy
            
            if dispatch_date:
                record['month'] = dispatch_date.month
                record['quarter'] = (dispatch_date.month - 1) // 3 + 1
            else:
                record['month'] = None
                record['quarter'] = None
            
            # Time to award
            if dispatch_date and award_date:
                delta = award_date - dispatch_date
                record['time_to_award_days'] = delta.days if delta.days > 0 else None
            else:
                record['time_to_award_days'] = None
            
            # Monetary values
            value_eur = pd.to_numeric(row.get('value_eur', np.nan), errors='coerce')
            award_value = pd.to_numeric(row.get('award_value_eur', np.nan), errors='coerce')
            est_value = pd.to_numeric(row.get('estimated_value_eur', np.nan), errors='coerce')
            
            # Use award value if available, otherwise notice value
            record['value_eur'] = award_value if pd.notna(award_value) else value_eur
            record['value_usd'] = convert_value_to_usd(record['value_eur'], year)
            record['estimated_value_eur'] = est_value
            record['value_local'] = record['value_eur']  # TED reports in EUR
            record['currency_local'] = 'EUR'
            
            # Procurement method
            proc_type = row.get('procedure_type_code', '')
            record['procedure_type'] = PROCEDURE_TYPE_MAP.get(proc_type, proc_type)
            record['procurement_method'] = 'open' if proc_type == 'OPE' else 'limited'
            record['procurement_method_details'] = proc_type
            
            contract_type = row.get('contract_type_code', '')
            record['contract_type'] = CONTRACT_TYPE_MAP.get(contract_type, contract_type)
            
            record['is_framework'] = str(row.get('is_framework', '')).upper() in ['Y', '1', 'TRUE']
            record['is_dps'] = str(row.get('is_dps', '')).upper() in ['Y', '1', 'TRUE']
            
            # Buyer
            record['buyer_id'] = row.get('buyer_id', '')
            record['buyer_name'] = row.get('buyer_name', '')
            record['buyer_address'] = row.get('buyer_address', '')
            record['buyer_city'] = row.get('buyer_city', '')
            record['buyer_postal_code'] = row.get('buyer_postal_code', '')
            buyer_type = str(row.get('buyer_type_code', ''))
            record['buyer_type'] = BUYER_TYPE_MAP.get(buyer_type, buyer_type)
            record['main_activity'] = row.get('main_activity', '')
            
            # Supplier
            record['supplier_id'] = row.get('supplier_id', '')
            record['supplier_name'] = row.get('supplier_name', '')
            record['supplier_address'] = row.get('supplier_address', '')
            record['supplier_city'] = row.get('supplier_city', '')
            record['supplier_postal_code'] = row.get('supplier_postal_code', '')
            record['supplier_country'] = row.get('supplier_country', '')
            record['supplier_is_sme'] = str(row.get('supplier_is_sme', '')).upper() in ['Y', '1', 'TRUE']
            
            # Competition
            n_bidders = pd.to_numeric(row.get('n_bidders', np.nan), errors='coerce')
            record['n_bidders'] = int(n_bidders) if pd.notna(n_bidders) else None
            record['n_bidders_sme'] = pd.to_numeric(row.get('n_bidders_sme', np.nan), errors='coerce')
            record['n_bidders_other_eu'] = pd.to_numeric(row.get('n_bidders_other_eu', np.nan), errors='coerce')
            record['n_bidders_non_eu'] = pd.to_numeric(row.get('n_bidders_non_eu', np.nan), errors='coerce')
            record['n_bidders_electronic'] = pd.to_numeric(row.get('n_bidders_electronic', np.nan), errors='coerce')
            record['single_bidder'] = record['n_bidders'] == 1 if record['n_bidders'] else None
            record['competitive'] = record['n_bidders'] > 1 if record['n_bidders'] else None
            
            # Classification
            cpv_str = str(row.get('cpv_code', ''))
            cpv_div, cpv_grp, cpv_full = parse_cpv_code(cpv_str)
            record['cpv_code'] = cpv_full
            record['cpv_main'] = cpv_full[:5] if len(cpv_full) >= 5 else cpv_full
            record['cpv_division'] = cpv_div
            record['cpv_group'] = cpv_grp
            record['cpv_additional'] = row.get('cpv_additional', '')
            record['nuts_code'] = row.get('nuts_code', '')
            record['gpa_covered'] = str(row.get('gpa_covered', '')).upper() in ['Y', '1', 'TRUE']
            
            # Contract specifics
            record['lot_number'] = row.get('lot_id', '')
            record['lots_total'] = pd.to_numeric(row.get('lots_total', 1), errors='coerce')
            record['contract_number'] = row.get('contract_number', '')
            record['contract_title'] = row.get('contract_title', '')
            
            # Award info
            record['award_id'] = row.get('award_id', '')
            criteria_code = row.get('award_criteria_code', '')
            record['award_criteria'] = AWARD_CRITERIA_MAP.get(criteria_code, criteria_code)
            record['price_weight'] = pd.to_numeric(row.get('price_weight', np.nan), errors='coerce')
            record['info_non_award'] = row.get('info_non_award', '')
            record['awarded_to_group'] = str(row.get('awarded_to_group', '')).upper() in ['Y', '1', 'TRUE']
            
            # Quality flags
            record['flag_cancelled'] = str(row.get('flag_cancelled', '0')) in ['1', 'TRUE', 'Y']
            record['flag_correction'] = str(row.get('flag_correction', '0')) in ['1', 'TRUE', 'Y']
            record['flag_missing_value'] = pd.isna(record['value_eur'])
            record['flag_missing_dates'] = pd.isna(dispatch_date) or pd.isna(award_date)
            record['data_source'] = 'EU_TED'
            
            records.append(record)
            
        except Exception as e:
            logger.debug(f"Error processing row {idx}: {e}")
            continue
    
    result_df = pd.DataFrame(records)
    logger.info(f"  Harmonized {len(result_df):,} records")
    
    return result_df


def find_ted_files() -> List[Tuple[Path, int]]:
    """Find all TED CSV files in the raw data directory."""
    files = []
    
    # Pattern: "TED - Contract award notices YYYY" or "TED - Contract notices YYYY"
    for folder in RAW_TED.iterdir():
        if not folder.is_dir():
            continue
        
        # Extract year from folder name
        year_match = re.search(r'(\d{4})', folder.name)
        if not year_match:
            continue
        
        year = int(year_match.group(1))
        
        # Find CSV files in folder
        for csv_file in folder.glob("*.csv"):
            files.append((csv_file, year))
    
    return sorted(files, key=lambda x: (x[1], x[0].name))


def process_all_ted_data(save_yearly: bool = True) -> pd.DataFrame:
    """
    Process all TED CSV files.
    
    Args:
        save_yearly: Whether to save yearly files separately
        
    Returns:
        Combined DataFrame with all TED data
    """
    ted_files = find_ted_files()
    
    if not ted_files:
        logger.error(f"No TED CSV files found in {RAW_TED}")
        return pd.DataFrame()
    
    logger.info(f"Found {len(ted_files)} TED files to process")
    
    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if save_yearly:
        yearly_dir = OUTPUT_DIR / "yearly"
        yearly_dir.mkdir(parents=True, exist_ok=True)
    
    all_dfs = []
    
    for file_path, year in tqdm(ted_files, desc="Processing TED files"):
        try:
            df = process_ted_file(file_path, year)
            
            if save_yearly and not df.empty:
                # Determine if CAN or CN
                notice_type = "CAN" if "award" in file_path.name.lower() else "CN"
                yearly_path = yearly_dir / f"ted_{year}_{notice_type}.parquet"
                df.to_parquet(yearly_path)
                logger.info(f"  Saved: {yearly_path.name}")
            
            all_dfs.append(df)
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            continue
    
    if not all_dfs:
        return pd.DataFrame()
    
    # Combine all data
    combined_df = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"\nCombined total: {len(combined_df):,} records")
    
    return combined_df


def generate_summary_stats(df: pd.DataFrame) -> Dict:
    """Generate summary statistics for TED data."""
    if df.empty:
        return {}
    
    summary = {
        'total_records': len(df),
        'years': sorted(df['year'].unique().tolist()),
        'countries': sorted(df['country'].unique().tolist()),
        'n_countries': df['country'].nunique(),
        'n_buyers': df['buyer_id'].nunique(),
        'n_suppliers': df['supplier_id'].nunique(),
        'total_value_eur': float(df['value_eur'].sum()),
        'total_value_usd': float(df['value_usd'].sum()),
        'mean_value_eur': float(df['value_eur'].mean()),
        'median_value_eur': float(df['value_eur'].median()),
        'mean_n_bidders': float(df['n_bidders'].mean()),
        'single_bidder_rate': float(df['single_bidder'].mean()),
        'missing_value_rate': float(df['flag_missing_value'].mean()),
        'cancelled_rate': float(df['flag_cancelled'].mean()),
        'by_year': df.groupby('year').agg({
            'ocid': 'count',
            'value_eur': 'sum',
            'n_bidders': 'mean',
            'single_bidder': 'mean'
        }).to_dict(),
        'by_country': df.groupby('country').agg({
            'ocid': 'count',
            'value_eur': 'sum'
        }).to_dict(),
    }
    
    return summary


def main():
    """Main processing function."""
    logger.info("=" * 60)
    logger.info("EU TED Data Processing Pipeline")
    logger.info("=" * 60)
    
    # Check for raw data
    if not RAW_TED.exists():
        logger.error(f"EU TED data directory not found: {RAW_TED}")
        logger.info("Please download EU TED data from https://data.europa.eu/data/datasets/ted-csv")
        sys.exit(1)
    
    # Process all TED files
    logger.info("\n1. Processing TED CSV files...")
    df = process_all_ted_data(save_yearly=True)
    
    if df.empty:
        logger.error("No data processed!")
        sys.exit(1)
    
    # Convert all object-type columns to strings to avoid mixed type errors
    logger.info("\n2. Converting object columns to strings...")
    object_cols = df.select_dtypes(include=['object']).columns
    for col in object_cols:
        df[col] = df[col].astype(str)
    logger.info(f"  Converted {len(object_cols)} columns to string")
    
    # Save combined data
    logger.info("\n3. Saving combined dataset...")
    combined_path = OUTPUT_DIR / "eu_ted_harmonized.parquet"
    df.to_parquet(combined_path)
    logger.info(f"Saved: {combined_path}")
    
    # Also save a CSV sample for inspection
    sample_path = OUTPUT_DIR / "eu_ted_sample_10000.csv"
    df.sample(min(10000, len(df))).to_csv(sample_path, index=False)
    logger.info(f"Saved sample: {sample_path}")
    
    # Generate summary statistics
    logger.info("\n3. Generating summary statistics...")
    summary = generate_summary_stats(df)
    
    summary_path = OUTPUT_DIR / "eu_ted_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info(f"Saved summary: {summary_path}")
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("EU TED Processing Summary")
    logger.info("=" * 60)
    logger.info(f"Total records: {summary['total_records']:,}")
    logger.info(f"Years: {min(summary['years'])} - {max(summary['years'])}")
    logger.info(f"Countries: {summary['n_countries']}")
    logger.info(f"Total value: €{summary['total_value_eur']/1e9:.2f}B")
    logger.info(f"Mean bidders: {summary['mean_n_bidders']:.2f}")
    logger.info(f"Single bidder rate: {summary['single_bidder_rate']*100:.1f}%")
    logger.info(f"Missing value rate: {summary['missing_value_rate']*100:.1f}%")
    
    logger.info("\n" + "=" * 60)
    logger.info("EU TED processing complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
