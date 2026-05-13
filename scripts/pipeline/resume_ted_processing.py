#!/usr/bin/env python3
"""
Resume EU TED processing - processes only the missing CAN (Contract Award Notices) files
and the VEAT file that weren't saved before the crash.
"""

import logging
import pandas as pd
from pathlib import Path
import sys
from tqdm import tqdm

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
RAW_TED = DATA_DIR / "raw" / "ocds" / "eu_ted"
OUTPUT_DIR = DATA_DIR / "processed" / "eu_ted"
YEARLY_DIR = OUTPUT_DIR / "yearly"

def get_missing_files():
    """Find files that haven't been processed yet."""
    # Get all existing yearly parquet files
    existing = set()
    if YEARLY_DIR.exists():
        for f in YEARLY_DIR.glob("*.parquet"):
            existing.add(f.name)
    
    # Find all TED directories that should be processed
    missing_files = []
    
    for folder in sorted(RAW_TED.iterdir()):
        if not folder.is_dir():
            continue
        
        # Extract year from folder name
        year = None
        for part in folder.name.split():
            if part.isdigit() and 2000 <= int(part) <= 2030:
                year = int(part)
                break
        
        if not year:
            # Handle ranges like "2018 - 2023"
            parts = folder.name.split('-')
            for part in parts:
                cleaned = part.strip()
                if cleaned.isdigit() and 2000 <= int(cleaned) <= 2030:
                    year = int(cleaned)
                    break
        
        if not year:
            logger.warning(f"Could not extract year from: {folder.name}")
            continue
        
        # Determine notice type
        notice_type = "CAN" if "award" in folder.name.lower() else "CN"
        if "veat" in folder.name.lower():
            notice_type = "VEAT"
        
        expected_name = f"ted_{year}_{notice_type}.parquet"
        
        # Check if this file exists
        if expected_name not in existing:
            # Find CSV in this folder
            csv_files = list(folder.glob("*.csv"))
            if csv_files:
                missing_files.append((csv_files[0], year, notice_type, folder.name))
    
    return missing_files

def main():
    """Process missing TED files."""
    logger.info("=" * 60)
    logger.info("Resuming EU TED Processing - Missing Files Only")
    logger.info("=" * 60)
    
    # Get missing files
    missing = get_missing_files()
    
    if not missing:
        logger.info("No missing files found! All data already processed.")
        return
    
    logger.info(f"\nFound {len(missing)} missing files to process:")
    for csv_path, year, notice_type, folder in missing:
        logger.info(f"  - {year} {notice_type}: {csv_path.name}")
    
    logger.info(f"\nStarting processing...")
    
    # Import the processing function from the main script
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    from parse_eu_ted import process_ted_file
    
    # Process each missing file
    YEARLY_DIR.mkdir(parents=True, exist_ok=True)
    
    for csv_path, year, notice_type, folder in tqdm(missing, desc="Processing missing files"):
        try:
            logger.info(f"\nProcessing: {folder}")
            df = process_ted_file(csv_path, year)
            
            if not df.empty:
                yearly_path = YEARLY_DIR / f"ted_{year}_{notice_type}.parquet"
                
                # Convert all object columns to strings
                object_cols = df.select_dtypes(include=['object']).columns
                for col in object_cols:
                    df[col] = df[col].astype(str)
                
                df.to_parquet(yearly_path)
                logger.info(f"  Saved: {yearly_path.name} ({len(df):,} records)")
            else:
                logger.warning(f"  No data extracted from {csv_path.name}")
                
        except Exception as e:
            logger.error(f"  Error processing {csv_path.name}: {e}")
            continue
    
    logger.info("\n" + "=" * 60)
    logger.info("Missing files processed!")
    logger.info("=" * 60)
    logger.info("\nRun combine_eu_ted_only.py again to create the full combined dataset.")

if __name__ == "__main__":
    main()
