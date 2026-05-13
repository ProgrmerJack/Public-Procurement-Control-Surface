#!/usr/bin/env python3
"""
Process UK OCDS data only (since Colombia is already done).
"""

import logging
import pandas as pd
from pathlib import Path
import sys

# Set up logging
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
OUTPUT_DIR = DATA_DIR / "processed" / "ocds"

def main():
    """Process UK OCDS data."""
    logger.info("=" * 60)
    logger.info("Processing UK OCDS Data")
    logger.info("=" * 60)
    
    # Check if UK file already exists
    uk_output = OUTPUT_DIR / "uk_harmonized.parquet"
    if uk_output.exists():
        logger.info(f"\nUK data already processed: {uk_output}")
        logger.info(f"File size: {uk_output.stat().st_size / 1024 / 1024:.2f} MB")
        logger.info("\nSkipping processing. Delete the file to reprocess.")
        return
    
    # Import the processing function from the main script
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    from parse_ocds_jsonl import process_country_data
    
    logger.info("\nProcessing UK JSONL data...")
    df = process_country_data('uk', max_records=None)
    
    if df.empty:
        logger.error("No data processed for UK!")
        sys.exit(1)
    
    logger.info(f"\nProcessed {len(df):,} UK records")
    
    # Convert all object columns to strings to avoid Arrow errors
    logger.info("Converting object columns to strings...")
    object_cols = df.select_dtypes(include=['object']).columns
    for col in object_cols:
        df[col] = df[col].astype(str)
    
    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving to {uk_output}...")
    df.to_parquet(uk_output)
    logger.info(f"Saved: {uk_output}")
    
    # Save sample
    sample_path = OUTPUT_DIR / "uk_sample_10000.csv"
    df.sample(min(10000, len(df))).to_csv(sample_path, index=False)
    logger.info(f"Saved sample: {sample_path}")
    
    logger.info("\n" + "=" * 60)
    logger.info("UK processing complete!")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
