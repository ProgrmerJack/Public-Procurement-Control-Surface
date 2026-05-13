#!/usr/bin/env python3
"""
Quick script to combine already-processed yearly EU TED parquet files.
Use this when processing completed but combining/saving failed.
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

# Paths
# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
BASE_DIR = _d
DATA_DIR = BASE_DIR / "Data"
OUTPUT_DIR = DATA_DIR / "processed" / "eu_ted"
YEARLY_DIR = OUTPUT_DIR / "yearly"

def main():
    """Combine yearly parquet files into single dataset."""
    logger.info("=" * 60)
    logger.info("Combining EU TED Yearly Files")
    logger.info("=" * 60)
    
    # Check if yearly directory exists
    if not YEARLY_DIR.exists():
        logger.error(f"Yearly directory not found: {YEARLY_DIR}")
        logger.info("Run parse_eu_ted.py first to process the raw files.")
        sys.exit(1)
    
    # Get all yearly parquet files
    yearly_files = sorted(YEARLY_DIR.glob("ted_*.parquet"))
    
    if not yearly_files:
        logger.error(f"No yearly parquet files found in {YEARLY_DIR}")
        sys.exit(1)
    
    logger.info(f"Found {len(yearly_files)} yearly files to combine")
    
    # Load and combine all files
    logger.info("\n1. Loading yearly files...")
    all_dfs = []
    
    for file_path in yearly_files:
        logger.info(f"  Loading {file_path.name}...")
        df = pd.read_parquet(file_path)
        logger.info(f"    Records: {len(df):,}")
        all_dfs.append(df)
    
    logger.info("\n2. Combining all data...")
    combined_df = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"Combined total: {len(combined_df):,} records")
    
    # Convert all object-type columns to strings to avoid mixed type errors
    logger.info("\n3. Converting object columns to strings...")
    object_cols = combined_df.select_dtypes(include=['object']).columns
    for col in object_cols:
        combined_df[col] = combined_df[col].astype(str)
    logger.info(f"  Converted {len(object_cols)} columns to string")
    
    # Save combined data
    logger.info("\n4. Saving combined dataset...")
    combined_path = OUTPUT_DIR / "eu_ted_harmonized.parquet"
    combined_df.to_parquet(combined_path)
    logger.info(f"Saved: {combined_path}")
    
    # Also save a CSV sample for inspection
    logger.info("\n5. Saving sample CSV...")
    sample_path = OUTPUT_DIR / "eu_ted_sample_10000.csv"
    combined_df.sample(min(10000, len(combined_df))).to_csv(sample_path, index=False)
    logger.info(f"Saved sample: {sample_path}")
    
    # Generate summary statistics
    logger.info("\n6. Generating summary statistics...")
    summary = {
        'total_records': len(combined_df),
        'years': sorted(combined_df['year'].unique().tolist()) if 'year' in combined_df.columns else [],
        'countries': sorted(combined_df['country'].unique().tolist()) if 'country' in combined_df.columns else [],
        'n_countries': combined_df['country'].nunique() if 'country' in combined_df.columns else 0,
        'n_buyers': combined_df['buyer_id'].nunique() if 'buyer_id' in combined_df.columns else 0,
        'total_value_eur': float(combined_df['value_eur'].sum()) if 'value_eur' in combined_df.columns else 0,
        'mean_value_eur': float(combined_df['value_eur'].mean()) if 'value_eur' in combined_df.columns else 0,
    }
    
    import json
    summary_path = OUTPUT_DIR / "eu_ted_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    logger.info(f"Saved summary: {summary_path}")
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("Summary:")
    logger.info(f"  Total records: {summary['total_records']:,}")
    logger.info(f"  Countries: {summary['n_countries']}")
    logger.info(f"  Unique buyers: {summary['n_buyers']:,}")
    logger.info(f"  Total value: €{summary['total_value_eur']:,.2f}")
    logger.info("=" * 60)
    logger.info("\nCombining complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
