#!/usr/bin/env python3
"""
OCDS JSONL Parser for Colombia and UK Procurement Data

Parses OCDS (Open Contracting Data Standard) data in JSONL.gz format
from Colombia and UK data sources and harmonizes to GPRD schema.

Data sources:
- Colombia: SECOP (Sistema Electrónico de Contratación Pública)
- UK: Contracts Finder

Output:
- Data/processed/ocds/colombia_harmonized.parquet
- Data/processed/ocds/uk_harmonized.parquet
- Data/processed/ocds/ocds_combined.parquet

Author: Abduxoliq Ashuraliyev
License: MIT
"""

import os
import sys
import gzip
import json
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Any
import logging
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
RAW_OCDS = DATA_DIR / "raw" / "ocds"
OUTPUT_DIR = DATA_DIR / "processed" / "ocds"
REF_DIR = DATA_DIR / "reference"

# Country configurations
COUNTRY_CONFIG = {
    "colombia": {
        "file": "full.jsonl.gz",
        "country_code": "CO",
        "country_name": "Colombia",
        "currency": "COP",
        "usd_rate": 0.00025,  # Approximate average
    },
    "uk": {
        "file": "full.jsonl.gz",
        "country_code": "GB",
        "country_name": "United Kingdom",
        "currency": "GBP",
        "usd_rate": 1.27,  # Approximate average
    }
}

# GPRD Schema columns
GPRD_COLUMNS = [
    "ocid", "contract_id", "country", "country_name",
    "tender_date", "award_date", "contract_date", "year", "month", "quarter",
    "time_to_award_days",
    "value_local", "currency_local", "value_usd", "value_eur",
    "estimated_value_local", "estimated_value_usd",
    "procurement_method", "procurement_method_details", "procurement_category",
    "is_framework", "is_emergency",
    "buyer_id", "buyer_name", "buyer_region", "buyer_type",
    "supplier_id", "supplier_name", "supplier_country", "supplier_is_sme",
    "n_bidders", "single_bidder", "competitive",
    "cpv_code", "cpv_division", "cpv_description", "sector",
    "tender_title", "tender_description",
    "flag_missing_value", "flag_missing_dates", "data_source",
]

# CPV to GPRD sector mapping
CPV_SECTOR_MAP = {
    "03": "AGRICULTURE", "09": "ENERGY", "14": "MINING", "15": "AGRICULTURE",
    "18": "TEXTILES", "22": "OFFICE", "24": "CHEMICALS", "30": "TECH",
    "31": "ENERGY", "32": "TECH", "33": "HEALTH", "34": "TRANSPORT",
    "35": "DEFENSE", "38": "TECH", "39": "CONSTRUCTION", "41": "UTILITIES",
    "42": "MANUFACTURING", "43": "MINING", "44": "CONSTRUCTION",
    "45": "CONSTRUCTION", "48": "TECH", "50": "SERVICES", "55": "SERVICES",
    "60": "TRANSPORT", "63": "TRANSPORT", "64": "SERVICES", "65": "UTILITIES",
    "66": "SERVICES", "70": "CONSTRUCTION", "71": "SERVICES", "72": "TECH",
    "73": "TECH", "75": "SERVICES", "76": "ENERGY", "77": "AGRICULTURE",
    "79": "SERVICES", "80": "SERVICES", "85": "HEALTH", "90": "UTILITIES",
    "92": "SERVICES", "98": "OTHER",
}

# Exchange rates by year (COP/USD and GBP/USD)
EXCHANGE_RATES = {
    "COP": {
        2010: 1900, 2011: 1850, 2012: 1800, 2013: 1870, 2014: 2000,
        2015: 2740, 2016: 3050, 2017: 2950, 2018: 2950, 2019: 3280,
        2020: 3690, 2021: 3740, 2022: 4250, 2023: 4050, 2024: 4000
    },
    "GBP": {
        2010: 1.55, 2011: 1.60, 2012: 1.59, 2013: 1.56, 2014: 1.65,
        2015: 1.53, 2016: 1.35, 2017: 1.29, 2018: 1.33, 2019: 1.28,
        2020: 1.28, 2021: 1.38, 2022: 1.24, 2023: 1.24, 2024: 1.27
    }
}


def parse_iso_date(date_str: Any) -> Optional[datetime]:
    """Parse ISO format date string."""
    if not date_str or pd.isna(date_str):
        return None
    
    date_str = str(date_str).strip()
    
    # Handle various formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str[:26], fmt)
        except (ValueError, IndexError):
            continue
    
    # Try parsing with timezone offset
    try:
        date_str_clean = re.sub(r'\+\d{2}:\d{2}$', '', date_str)
        return datetime.fromisoformat(date_str_clean)
    except:
        return None


def extract_cpv_from_classifications(classifications: List[Dict]) -> str:
    """Extract CPV code from OCDS classifications array."""
    if not classifications:
        return ""
    
    for cls in classifications:
        scheme = cls.get('scheme', '').upper()
        if scheme in ['CPV', 'CPVCODE', 'CPV2008']:
            return cls.get('id', '')
    
    # If no CPV, try first classification
    if classifications:
        return classifications[0].get('id', '')
    
    return ""


def convert_to_usd(value: float, currency: str, year: int) -> float:
    """Convert value to USD using exchange rates."""
    if pd.isna(value) or value <= 0:
        return np.nan
    
    if currency == "USD":
        return value
    
    if currency in EXCHANGE_RATES:
        rate = EXCHANGE_RATES[currency].get(year, EXCHANGE_RATES[currency].get(2020))
        if currency == "GBP":
            return value * rate  # GBP to USD
        else:
            return value / rate  # COP to USD
    
    # Default: assume EUR
    eur_usd = 1.10
    return value * eur_usd


def process_ocds_release(release: Dict, country_config: Dict) -> Optional[Dict]:
    """
    Process a single OCDS release into GPRD format.
    
    Args:
        release: OCDS release dictionary
        country_config: Country configuration
        
    Returns:
        Harmonized record dictionary or None
    """
    try:
        record = {}
        
        # Basic identifiers
        record['ocid'] = release.get('ocid', '')
        record['country'] = country_config['country_code']
        record['country_name'] = country_config['country_name']
        record['data_source'] = f"OCDS_{country_config['country_code']}"
        
        # Get tender data
        tender = release.get('tender', {})
        record['contract_id'] = tender.get('id', release.get('id', ''))
        record['tender_title'] = tender.get('title', '')
        record['tender_description'] = tender.get('description', '')
        
        # Procurement method
        record['procurement_method'] = tender.get('procurementMethod', '')
        record['procurement_method_details'] = tender.get('procurementMethodDetails', '')
        record['procurement_category'] = tender.get('mainProcurementCategory', '')
        
        # Tender dates
        tender_period = tender.get('tenderPeriod', {})
        record['tender_date'] = parse_iso_date(tender_period.get('startDate'))
        
        # Release date as fallback
        release_date = parse_iso_date(release.get('date'))
        if not record['tender_date'] and release_date:
            record['tender_date'] = release_date
        
        # Temporal
        if record['tender_date']:
            record['year'] = record['tender_date'].year
            record['month'] = record['tender_date'].month
            record['quarter'] = (record['tender_date'].month - 1) // 3 + 1
        else:
            record['year'] = release.get('anio', release.get('year'))
            record['month'] = None
            record['quarter'] = None
        
        # Get year for exchange rates
        year = record.get('year', 2020)
        if not year or year < 2000 or year > 2030:
            year = 2020
        
        # Tender value (estimated)
        tender_value = tender.get('value', {})
        estimated_local = tender_value.get('amount')
        if estimated_local:
            record['estimated_value_local'] = float(estimated_local)
            record['estimated_value_usd'] = convert_to_usd(
                record['estimated_value_local'],
                country_config['currency'],
                year
            )
        else:
            record['estimated_value_local'] = np.nan
            record['estimated_value_usd'] = np.nan
        
        # Awards
        awards = release.get('awards', [])
        if awards:
            award = awards[0]  # Take first award
            record['award_date'] = parse_iso_date(award.get('date'))
            
            # Award value
            award_value = award.get('value', {})
            if award_value.get('amount'):
                record['value_local'] = float(award_value['amount'])
                record['currency_local'] = award_value.get('currency', country_config['currency'])
            else:
                record['value_local'] = np.nan
                record['currency_local'] = country_config['currency']
            
            # Suppliers
            suppliers = award.get('suppliers', [])
            if suppliers:
                supplier = suppliers[0]
                record['supplier_id'] = supplier.get('id', supplier.get('identifier', {}).get('id', ''))
                record['supplier_name'] = supplier.get('name', '')
                
                # Get address
                address = supplier.get('address', {})
                record['supplier_country'] = address.get('countryName', country_config['country_name'])
                
                # SME status (if available)
                details = supplier.get('details', {})
                record['supplier_is_sme'] = details.get('scale', '').lower() in ['sme', 'small', 'medium', 'micro']
        else:
            record['award_date'] = None
            record['value_local'] = np.nan
            record['currency_local'] = country_config['currency']
            record['supplier_id'] = ''
            record['supplier_name'] = ''
            record['supplier_country'] = ''
            record['supplier_is_sme'] = False
        
        # Convert to USD
        record['value_usd'] = convert_to_usd(
            record['value_local'],
            record['currency_local'],
            year
        )
        
        # EUR conversion (approximate)
        if pd.notna(record['value_usd']):
            record['value_eur'] = record['value_usd'] / 1.10
        else:
            record['value_eur'] = np.nan
        
        # Time to award
        if record['tender_date'] and record['award_date']:
            delta = record['award_date'] - record['tender_date']
            record['time_to_award_days'] = delta.days if delta.days >= 0 else None
        else:
            record['time_to_award_days'] = None
        
        # Buyer
        buyer = release.get('buyer', {})
        if not buyer:
            # Try parties
            parties = release.get('parties', [])
            for party in parties:
                if 'buyer' in party.get('roles', []):
                    buyer = party
                    break
        
        record['buyer_id'] = buyer.get('id', buyer.get('identifier', {}).get('id', ''))
        record['buyer_name'] = buyer.get('name', '')
        buyer_address = buyer.get('address', {})
        record['buyer_region'] = buyer_address.get('region', buyer_address.get('locality', ''))
        record['buyer_type'] = buyer.get('details', {}).get('classification', '')
        
        # Bidders / Competition
        tender_details = tender.get('numberOfTenderers', tender.get('tenderers', []))
        if isinstance(tender_details, int):
            record['n_bidders'] = tender_details
        elif isinstance(tender_details, list):
            record['n_bidders'] = len(tender_details)
        else:
            # Try submissions
            submissions = release.get('bids', {}).get('details', [])
            record['n_bidders'] = len(submissions) if submissions else None
        
        record['single_bidder'] = record['n_bidders'] == 1 if record['n_bidders'] else None
        record['competitive'] = record['n_bidders'] > 1 if record['n_bidders'] else None
        
        # Classifications (CPV)
        classifications = tender.get('classification', [])
        if isinstance(classifications, dict):
            classifications = [classifications]
        
        items = tender.get('items', [])
        for item in items:
            item_cls = item.get('classification')
            if item_cls:
                if isinstance(item_cls, list):
                    classifications.extend(item_cls)
                else:
                    classifications.append(item_cls)
        
        cpv_code = extract_cpv_from_classifications(classifications)
        record['cpv_code'] = cpv_code
        record['cpv_division'] = cpv_code[:2] if len(cpv_code) >= 2 else ''
        record['cpv_description'] = ''  # Would need CPV taxonomy lookup
        record['sector'] = CPV_SECTOR_MAP.get(record['cpv_division'], 'OTHER')
        
        # Framework and emergency flags
        record['is_framework'] = tender.get('hasFrameworkAgreement', False)
        record['is_emergency'] = 'emergency' in record['procurement_method_details'].lower() if record['procurement_method_details'] else False
        
        # Quality flags
        record['flag_missing_value'] = pd.isna(record['value_local'])
        record['flag_missing_dates'] = record['tender_date'] is None or record['award_date'] is None
        
        return record
        
    except Exception as e:
        logger.debug(f"Error processing release: {e}")
        return None


def read_jsonl_gz(file_path: Path, max_records: int = None) -> Iterator[Dict]:
    """
    Read JSONL.gz file and yield records.
    
    Args:
        file_path: Path to JSONL.gz file
        max_records: Maximum number of records to read (None for all)
        
    Yields:
        JSON record dictionaries
    """
    count = 0
    
    with gzip.open(file_path, 'rt', encoding='utf-8') as f:
        for line in f:
            if max_records and count >= max_records:
                break
            
            line = line.strip()
            if not line:
                continue
            
            try:
                record = json.loads(line)
                yield record
                count += 1
            except json.JSONDecodeError as e:
                logger.debug(f"JSON decode error: {e}")
                continue


def count_lines_gz(file_path: Path) -> int:
    """Count lines in gzipped file."""
    count = 0
    with gzip.open(file_path, 'rt', encoding='utf-8') as f:
        for _ in f:
            count += 1
    return count


def process_country_data(country: str, max_records: int = None) -> pd.DataFrame:
    """
    Process OCDS data for a specific country.
    
    Args:
        country: Country key ('colombia' or 'uk')
        max_records: Maximum records to process (None for all)
        
    Returns:
        Harmonized DataFrame
    """
    config = COUNTRY_CONFIG.get(country)
    if not config:
        logger.error(f"Unknown country: {country}")
        return pd.DataFrame()
    
    file_path = RAW_OCDS / country / config['file']
    
    if not file_path.exists():
        logger.error(f"Data file not found: {file_path}")
        return pd.DataFrame()
    
    logger.info(f"Processing {country.upper()} data from {file_path}")
    
    # Count total records for progress bar
    logger.info("  Counting records...")
    if max_records:
        total = max_records
    else:
        total = count_lines_gz(file_path)
    logger.info(f"  Total records: {total:,}")
    
    # Process records
    records = []
    errors = 0
    
    for release in tqdm(read_jsonl_gz(file_path, max_records), 
                        total=total, desc=f"  Processing {country}"):
        result = process_ocds_release(release, config)
        if result:
            records.append(result)
        else:
            errors += 1
    
    logger.info(f"  Processed: {len(records):,} records, {errors:,} errors")
    
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame(records)
    
    return df


def generate_summary(df: pd.DataFrame, country: str) -> Dict:
    """Generate summary statistics for processed data."""
    if df.empty:
        return {}
    
    summary = {
        'country': country,
        'total_records': len(df),
        'years': sorted(df['year'].dropna().unique().tolist()),
        'date_range': {
            'min': str(df['tender_date'].min()) if df['tender_date'].notna().any() else None,
            'max': str(df['tender_date'].max()) if df['tender_date'].notna().any() else None,
        },
        'n_buyers': int(df['buyer_id'].nunique()),
        'n_suppliers': int(df['supplier_id'].nunique()),
        'total_value_local': float(df['value_local'].sum()),
        'total_value_usd': float(df['value_usd'].sum()),
        'mean_value_usd': float(df['value_usd'].mean()),
        'median_value_usd': float(df['value_usd'].median()),
        'mean_n_bidders': float(df['n_bidders'].mean()) if df['n_bidders'].notna().any() else None,
        'single_bidder_rate': float(df['single_bidder'].mean()) if df['single_bidder'].notna().any() else None,
        'missing_value_rate': float(df['flag_missing_value'].mean()),
        'missing_dates_rate': float(df['flag_missing_dates'].mean()),
        'procurement_methods': df['procurement_method'].value_counts().to_dict(),
        'sectors': df['sector'].value_counts().to_dict(),
    }
    
    return summary


def main():
    """Main processing function."""
    logger.info("=" * 60)
    logger.info("OCDS JSONL Processing Pipeline")
    logger.info("=" * 60)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    all_dfs = []
    all_summaries = {}
    
    # Process each country
    for country in ['colombia', 'uk']:
        country_path = RAW_OCDS / country
        if not country_path.exists():
            logger.warning(f"Country directory not found: {country_path}")
            continue
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {country.upper()}")
        logger.info(f"{'='*60}")
        
        # Process data (no limit for full analysis)
        df = process_country_data(country, max_records=None)
        
        if df.empty:
            logger.warning(f"No data processed for {country}")
            continue
        
        # Convert all object-type columns to strings to avoid mixed type errors
        object_cols = df.select_dtypes(include=['object']).columns
        for col in object_cols:
            df[col] = df[col].astype(str)
        
        # Save country-specific data
        output_path = OUTPUT_DIR / f"{country}_harmonized.parquet"
        df.to_parquet(output_path)
        logger.info(f"Saved: {output_path}")
        
        # Sample for inspection
        sample_path = OUTPUT_DIR / f"{country}_sample_10000.csv"
        df.sample(min(10000, len(df))).to_csv(sample_path, index=False)
        
        # Generate summary
        summary = generate_summary(df, country)
        all_summaries[country] = summary
        
        # Save summary
        summary_path = OUTPUT_DIR / f"{country}_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        all_dfs.append(df)
        
        # Print summary
        logger.info(f"\n{country.upper()} Summary:")
        logger.info(f"  Records: {summary['total_records']:,}")
        logger.info(f"  Years: {summary['years'][0]} - {summary['years'][-1]}" if summary['years'] else "  Years: N/A")
        logger.info(f"  Buyers: {summary['n_buyers']:,}")
        logger.info(f"  Suppliers: {summary['n_suppliers']:,}")
        logger.info(f"  Total value: ${summary['total_value_usd']/1e9:.2f}B USD")
        if summary['single_bidder_rate']:
            logger.info(f"  Single bidder rate: {summary['single_bidder_rate']*100:.1f}%")
    
    # Combine all data
    if all_dfs:
        logger.info(f"\n{'='*60}")
        logger.info("Combining all OCDS data")
        logger.info(f"{'='*60}")
        
        combined_df = pd.concat(all_dfs, ignore_index=True)
        
        combined_path = OUTPUT_DIR / "ocds_combined.parquet"
        combined_df.to_parquet(combined_path)
        logger.info(f"Saved combined: {combined_path}")
        
        # Combined summary
        combined_summary = {
            'countries': list(all_summaries.keys()),
            'total_records': len(combined_df),
            'by_country': all_summaries,
        }
        
        combined_summary_path = OUTPUT_DIR / "ocds_combined_summary.json"
        with open(combined_summary_path, 'w') as f:
            json.dump(combined_summary, f, indent=2, default=str)
        
        logger.info(f"\nCombined total: {len(combined_df):,} records")
    
    logger.info("\n" + "=" * 60)
    logger.info("OCDS processing complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
