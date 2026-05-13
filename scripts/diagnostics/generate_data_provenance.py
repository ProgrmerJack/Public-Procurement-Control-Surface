#!/usr/bin/env python3
"""
Generate Data Provenance Documentation

Creates comprehensive provenance metadata for processed GPRD data:
- Source API details and access dates
- Raw record counts and processing statistics  
- Transformation steps and filters applied
- SHA-256 checksums for data integrity
- Processing script versions

This documentation is CRITICAL for reproducibility without raw data.

Author: Abduxoliq Ashuraliyev
License: MIT
"""

import json
import hashlib
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import pandas as pd

# Paths
# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
BASE_DIR = _d
DATA_DIR = BASE_DIR / "Data"
PROCESSED_DIR = DATA_DIR / "processed"
SCRIPTS_DIR = BASE_DIR / "scripts"
OUTPUT_FILE = PROCESSED_DIR / "DATA_PROVENANCE.json"


def compute_file_checksum(filepath: Path) -> str:
    """Compute SHA-256 checksum for a file."""
    sha256_hash = hashlib.sha256()
    
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    return sha256_hash.hexdigest()


def get_file_info(filepath: Path) -> Dict[str, Any]:
    """Get file size and modification time."""
    if not filepath.exists():
        return None
    
    stat = filepath.stat()
    return {
        "size_bytes": int(stat.st_size),
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "checksum_sha256": compute_file_checksum(filepath)
    }


def analyze_processed_files() -> Dict[str, Any]:
    """Analyze all processed data files."""
    print("Analyzing processed data files...")
    
    files_info = {}
    
    processed_files = [
        "gprd_master.parquet",
        "gprd_analysis.parquet",
        "gprd_with_carbon.parquet",
        "gprd_sample_10000.csv",
        "gprd_summary_stats.json",
        "carbon_analysis_summary.json"
    ]
    
    for filename in processed_files:
        filepath = PROCESSED_DIR / filename
        if filepath.exists():
            print(f"  Processing: {filename}")
            files_info[filename] = get_file_info(filepath)
            
            # Get record count for parquet/csv files
            if filename.endswith(".parquet"):
                try:
                    df = pd.read_parquet(filepath)
                    files_info[filename]["records"] = len(df)
                    files_info[filename]["columns"] = len(df.columns)
                except:
                    pass
            elif filename.endswith(".csv"):
                try:
                    df = pd.read_csv(filepath)
                    files_info[filename]["records"] = len(df)
                    files_info[filename]["columns"] = len(df.columns)
                except:
                    pass
    
    return files_info


def get_source_metadata() -> Dict[str, Any]:
    """Get metadata about data sources."""
    print("Documenting data sources...")
    
    sources = {
        "ukraine": {
            "name": "ProZorro",
            "api_endpoint": "https://api.prozorro.gov.ua",
            "ocds_version": "1.1",
            "coverage_period": "2016-01-01 to 2024-12-31",
            "data_license": "Ukrainian Open Data License",
            "download_method": "API streaming (releases endpoint)",
            "estimated_raw_records": "2,500,000+",
            "description": "Ukrainian government e-procurement system"
        },
        "colombia": {
            "name": "SECOP II",
            "api_endpoint": "https://api.colombiacompra.gov.co",
            "ocds_version": "1.1",
            "coverage_period": "2012-01-01 to 2024-12-31",
            "data_license": "Open Government License Colombia",
            "download_method": "API batch download",
            "estimated_raw_records": "1,800,000+",
            "description": "Colombian government procurement system"
        },
        "uk": {
            "name": "Contracts Finder",
            "api_endpoint": "https://www.contractsfinder.service.gov.uk",
            "ocds_version": "1.1 (subset)",
            "coverage_period": "2015-01-01 to 2024-12-31",
            "data_license": "Open Government Licence v3.0",
            "download_method": "API bulk download",
            "estimated_raw_records": "850,000+",
            "description": "UK government contracts portal"
        }
    }
    
    return sources


def document_processing_pipeline() -> Dict[str, Any]:
    """Document the data processing pipeline."""
    print("Documenting processing pipeline...")
    
    pipeline = {
        "harmonization": {
            "script": "scripts/harmonize_data.py",
            "description": "Harmonize OCDS data from multiple sources to GPRD schema",
            "steps": [
                "Parse OCDS JSONL files",
                "Extract core contract fields",
                "Normalize country-specific formats",
                "Convert currencies to USD/EUR",
                "Map CPV codes to sectors",
                "Calculate distance to threshold",
                "Apply quality filters"
            ]
        },
        "filters_applied": {
            "missing_value": {
                "description": "Remove contracts with missing contract value",
                "rationale": "Cannot analyze value-based effects without value data"
            },
            "missing_dates": {
                "description": "Remove contracts with missing tender/award dates",
                "rationale": "Need dates for temporal analysis and RDD identification"
            },
            "duplicates": {
                "description": "Remove duplicate records based on OCID",
                "rationale": "Prevent double-counting in analysis"
            },
            "invalid_cpv": {
                "description": "Flag contracts with unmappable CPV codes",
                "rationale": "Some analyses require sector classification"
            },
            "outlier_values": {
                "description": "Flag but retain extreme values (>99.9th percentile)",
                "rationale": "Preserve data but allow filtering in sensitivity tests"
            }
        },
        "derived_variables": {
            "distance_to_threshold": "Normalized distance from contract value to relevant threshold",
            "above_threshold": "Boolean indicator for threshold crossing",
            "single_bidder": "Derived from n_bidders field",
            "competitive": "Boolean for n_bidders > 1",
            "value_usd": "Converted from local currency using World Bank rates",
            "carbon_intensity": "Linked via CPV-EXIOBASE sector mapping"
        }
    }
    
    return pipeline


def get_script_versions() -> Dict[str, Any]:
    """Get version info for processing scripts."""
    print("Recording script versions...")
    
    scripts = {}
    
    key_scripts = [
        "harmonize_data.py",
        "parse_ocds_jsonl.py",
        "analyze_all_procurement_data.py",
        "link_carbon_intensity.py"
    ]
    
    for script_name in key_scripts:
        script_path = SCRIPTS_DIR / script_name
        if script_path.exists():
            info = get_file_info(script_path)
            if info:
                scripts[script_name] = {
                    "modified": info["modified"],
                    "size_bytes": info["size_bytes"],
                    "checksum": info["checksum_sha256"]
                }
    
    return scripts


def main():
    """Generate comprehensive data provenance documentation."""
    print("=" * 60)
    print("Generating Data Provenance Documentation")
    print("=" * 60)
    
    provenance = {
        "metadata": {
            "version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "description": "Data provenance for GPRD processed dataset"
        },
        "sources": get_source_metadata(),
        "processed_files": analyze_processed_files(),
        "processing_pipeline": document_processing_pipeline(),
        "processing_scripts": get_script_versions(),
        "data_quality": {
            "quality_report": "See DATA_QUALITY_REPORT.json",
            "audit_documentation": "See Data/audit/ directory",
            "codebook": "See DATA_CODEBOOK.md"
        },
        "reproducibility": {
            "from_processed_data": [
                "All RDD estimates",
                "All robustness checks",
                "All figures and tables",
                "Summary statistics",
                "Descriptive analysis"
            ],
            "requires_raw_data": [
                "Alternative preprocessing choices",
                "Different filter thresholds",
                "Source data verification",
                "Download date validation"
            ]
        },
        "citation": {
            "dataset": "Global Procurement Research Dataset (GPRD) v1.0",
            "author": "Abduxoliq Ashuraliyev",
            "year": 2025,
            "doi": "10.5281/zenodo.XXXXXXX",  # To be assigned
            "license": "CC-BY-4.0 (data) + MIT (code)"
        }
    }
    
    # Save provenance file
    print(f"\nSaving provenance to: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(provenance, f, indent=2, default=str)
    
    print("\n" + "=" * 60)
    print("Data Provenance Documentation Generated!")
    print("=" * 60)
    
    # Print summary
    print("\n📁 PROCESSED FILES:")
    for filename, info in provenance["processed_files"].items():
        if info:
            size = info['size_mb']
            records = info.get('records', 'N/A')
            print(f"  • {filename}: {size} MB, {records} records")
    
    print("\n🔗 DATA SOURCES:")
    for country, source in provenance["sources"].items():
        print(f"  • {country.upper()}: {source['name']} ({source['estimated_raw_records']} records)")
    
    print("\n✅ CHECKSUMS GENERATED:")
    print(f"  Use these to verify data integrity")
    
    print("\n📄 Documentation saved to:")
    print(f"  {OUTPUT_FILE}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
