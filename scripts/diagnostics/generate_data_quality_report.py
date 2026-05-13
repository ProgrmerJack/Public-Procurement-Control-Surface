#!/usr/bin/env python3
"""
Generate Data Quality Report for Processed GPRD Data

Creates a comprehensive quality report that documents:
- Sample composition and coverage
- Variable completeness
- Distributional statistics
- Outlier detection
- Consistency checks
- Validation against manuscript claims

This report is essential for reproducibility without raw data.

Author: Abduxoliq Ashuraliyev
License: MIT
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

import pandas as pd
import numpy as np

# Paths
# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
BASE_DIR = _d
DATA_DIR = BASE_DIR / "Data"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_FILE = PROCESSED_DIR / "DATA_QUALITY_REPORT.json"


def load_processed_data() -> pd.DataFrame:
    """Load the main processed dataset."""
    possible_files = [
        PROCESSED_DIR / "gprd_master.parquet",
        PROCESSED_DIR / "gprd_analysis.parquet",
        PROCESSED_DIR / "gprd_with_carbon.parquet",
    ]
    
    for path in possible_files:
        if path.exists():
            print(f"Loading: {path}")
            return pd.read_parquet(path)
    
    raise FileNotFoundError(f"No processed data found in {PROCESSED_DIR}")


def analyze_sample_composition(df: pd.DataFrame) -> Dict[str, Any]:
    """Analyze sample composition by country and year."""
    print("Analyzing sample composition...")
    
    composition = {
        "total_records": int(len(df)),
        "countries": {},
        "temporal_coverage": {}
    }
    
    # Country-level statistics
    for country in df["country"].unique():
        country_df = df[df["country"] == country]
        composition["countries"][country] = {
            "n_contracts": int(len(country_df)),
            "pct_total": float(len(country_df) / len(df) * 100),
            "date_range": {
                "start": str(country_df["tender_date"].min() if "tender_date" in country_df else "N/A"),
                "end": str(country_df["tender_date"].max() if "tender_date" in country_df else "N/A")
            },
            "mean_value_usd": float(country_df["value_usd"].mean()) if "value_usd" in country_df else None,
            "median_bidders": float(country_df["n_bidders"].median()) if "n_bidders" in country_df else None
        }
    
    # Temporal coverage
    if "year" in df.columns:
        by_year = df.groupby("year").size()
        composition["temporal_coverage"] = {
            "by_year": by_year.to_dict(),
            "start_year": int(by_year.index.min()),
            "end_year": int(by_year.index.max())
        }
    
    return composition


def analyze_variable_completeness(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Analyze completeness for each variable."""
    print("Analyzing variable completeness...")
    
    completeness = {}
    
    for col in df.columns:
        n_total = len(df)
        n_non_null = df[col].notna().sum()
        n_null = df[col].isna().sum()
        
        completeness[col] = {
            "non_null": int(n_non_null),
            "null": int(n_null),
            "coverage_pct": float(n_non_null / n_total * 100),
            "dtype": str(df[col].dtype)
        }
    
    return completeness


def analyze_distributions(df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Analyze distributions of key numeric variables."""
    print("Analyzing distributions...")
    
    numeric_vars = [
        "value_usd", "value_eur", "value_local",
        "n_bidders", "distance_to_threshold",
        "carbon_intensity_kg_usd", "text_restrictiveness",
        "text_complexity", "text_innovation"
    ]
    
    distributions = {}
    
    for var in numeric_vars:
        if var not in df.columns:
            continue
        
        series = df[var].dropna()
        if len(series) == 0:
            continue
        
        distributions[var] = {
            "count": int(len(series)),
            "mean": float(series.mean()),
            "median": float(series.median()),
            "std": float(series.std()),
            "min": float(series.min()),
            "max": float(series.max()),
            "q25": float(series.quantile(0.25)),
            "q50": float(series.quantile(0.50)),
            "q75": float(series.quantile(0.75)),
            "q90": float(series.quantile(0.90)),
            "q95": float(series.quantile(0.95)),
            "q99": float(series.quantile(0.99))
        }
    
    return distributions


def detect_outliers(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Detect outliers using IQR method."""
    print("Detecting outliers...")
    
    numeric_vars = ["value_usd", "n_bidders", "distance_to_threshold"]
    outliers = {}
    
    for var in numeric_vars:
        if var not in df.columns:
            continue
        
        series = df[var].dropna()
        if len(series) == 0:
            continue
        
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        
        # Outliers: outside 3*IQR
        lower_bound = q1 - 3 * iqr
        upper_bound = q3 + 3 * iqr
        
        outlier_mask = (series < lower_bound) | (series > upper_bound)
        n_outliers = outlier_mask.sum()
        
        outliers[var] = {
            "count": int(n_outliers),
            "percentage": float(n_outliers / len(series) * 100),
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound),
            "min_outlier": float(series[outlier_mask].min()) if n_outliers > 0 else None,
            "max_outlier": float(series[outlier_mask].max()) if n_outliers > 0 else None
        }
    
    return outliers


def run_consistency_checks(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Run consistency checks across variables."""
    print("Running consistency checks...")
    
    checks = {}
    
    # Check 1: Award date >= Tender date
    if "tender_date" in df.columns and "award_date" in df.columns:
        valid_dates = (df["award_date"] >= df["tender_date"]).sum()
        checks["award_after_tender"] = {
            "valid": int(valid_dates),
            "invalid": int(len(df) - valid_dates),
            "pass_rate": float(valid_dates / len(df) * 100)
        }
    
    # Check 2: Value > 0
    if "value_usd" in df.columns:
        positive_values = (df["value_usd"] > 0).sum()
        checks["positive_value"] = {
            "valid": int(positive_values),
            "invalid": int(len(df) - positive_values),
            "pass_rate": float(positive_values / len(df) * 100)
        }
    
    # Check 3: Bidders >= 1
    if "n_bidders" in df.columns:
        valid_bidders = (df["n_bidders"] >= 1).sum()
        checks["at_least_one_bidder"] = {
            "valid": int(valid_bidders),
            "invalid": int(len(df) - valid_bidders),
            "pass_rate": float(valid_bidders / len(df) * 100)
        }
    
    # Check 4: Single bidder consistency
    if "n_bidders" in df.columns and "single_bidder" in df.columns:
        consistent = ((df["n_bidders"] == 1) == df["single_bidder"]).sum()
        checks["single_bidder_consistency"] = {
            "consistent": int(consistent),
            "inconsistent": int(len(df) - consistent),
            "pass_rate": float(consistent / len(df) * 100)
        }
    
    # Check 5: Year range validity
    if "year" in df.columns:
        valid_years = ((df["year"] >= 2010) & (df["year"] <= 2025)).sum()
        checks["valid_year_range"] = {
            "valid": int(valid_years),
            "invalid": int(len(df) - valid_years),
            "pass_rate": float(valid_years / len(df) * 100)
        }
    
    return checks


def validate_against_manuscript_claims(df: pd.DataFrame) -> Dict[str, Any]:
    """Validate processed data against manuscript claims."""
    print("Validating against manuscript claims...")
    
    validations = []
    
    # Claim 1: Sample size ~2.3M contracts
    validations.append({
        "claim": "Sample size approximately 2.3M contracts",
        "manuscript_value": 2_300_000,
        "actual_value": int(len(df)),
        "difference_pct": abs(len(df) - 2_300_000) / 2_300_000 * 100,
        "within_tolerance": abs(len(df) - 2_300_000) / 2_300_000 < 0.50  # 50% tolerance
    })
    
    # Claim 2: 3 countries
    validations.append({
        "claim": "Three countries (Ukraine, Colombia, UK)",
        "manuscript_value": 3,
        "actual_value": int(df["country"].nunique()) if "country" in df else None,
        "match": df["country"].nunique() == 3 if "country" in df else False
    })
    
    # Claim 3: Date range 2012-2023
    if "year" in df.columns:
        year_min = int(df["year"].min())
        year_max = int(df["year"].max())
        validations.append({
            "claim": "Date range 2012-2023",
            "manuscript_value": "2012-2023",
            "actual_value": f"{year_min}-{year_max}",
            "covers_period": year_min <= 2012 and year_max >= 2023
        })
    
    # Claim 4: Average ~3.2 bidders
    if "n_bidders" in df.columns:
        mean_bidders = float(df["n_bidders"].mean())
        validations.append({
            "claim": "Average 3.2 bidders per contract",
            "manuscript_value": 3.2,
            "actual_value": mean_bidders,
            "difference": abs(mean_bidders - 3.2),
            "within_tolerance": abs(mean_bidders - 3.2) < 1.0  # ±1 bidder tolerance
        })
    
    # Claim 5: ~38% single-bidder rate
    if "single_bidder" in df.columns:
        single_bid_rate = float(df["single_bidder"].mean() * 100)
        validations.append({
            "claim": "Single-bidder rate approximately 38%",
            "manuscript_value": 38.0,
            "actual_value": single_bid_rate,
            "difference_pp": abs(single_bid_rate - 38.0),
            "within_tolerance": abs(single_bid_rate - 38.0) < 10.0  # ±10pp tolerance
        })
    
    return {
        "validations": validations,
        "all_passed": all(v.get("within_tolerance") or v.get("match") or v.get("covers_period") 
                         for v in validations if any(k in v for k in ["within_tolerance", "match", "covers_period"]))
    }


def generate_rdd_sample_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate statistics for RDD sample near thresholds."""
    print("Analyzing RDD sample composition...")
    
    rdd_stats = {}
    
    if "distance_to_threshold" not in df.columns:
        return {"error": "distance_to_threshold variable not found"}
    
    # Define bandwidth
    bandwidth = 0.5  # ±50% of threshold
    rdd_sample = df[abs(df["distance_to_threshold"]) <= bandwidth]
    
    rdd_stats["total_near_threshold"] = int(len(rdd_sample))
    rdd_stats["pct_of_full_sample"] = float(len(rdd_sample) / len(df) * 100)
    
    # By country
    rdd_stats["by_country"] = {}
    for country in rdd_sample["country"].unique():
        country_rdd = rdd_sample[rdd_sample["country"] == country]
        below = country_rdd[country_rdd["distance_to_threshold"] < 0]
        above = country_rdd[country_rdd["distance_to_threshold"] >= 0]
        
        rdd_stats["by_country"][country] = {
            "below_threshold": int(len(below)),
            "above_threshold": int(len(above)),
            "total": int(len(country_rdd))
        }
    
    return rdd_stats


def main():
    """Generate comprehensive data quality report."""
    print("=" * 60)
    print("Generating Data Quality Report for Processed GPRD Data")
    print("=" * 60)
    
    # Load data
    df = load_processed_data()
    print(f"\nLoaded {len(df):,} records")
    print(f"Variables: {len(df.columns)}")
    
    # Generate report sections
    report = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_records": int(len(df)),
            "n_variables": int(len(df.columns))
        },
        "sample_composition": analyze_sample_composition(df),
        "variable_completeness": analyze_variable_completeness(df),
        "distributions": analyze_distributions(df),
        "outliers": detect_outliers(df),
        "consistency_checks": run_consistency_checks(df),
        "manuscript_validation": validate_against_manuscript_claims(df),
        "rdd_sample": generate_rdd_sample_stats(df)
    }
    
    # Save report
    print(f"\nSaving report to: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print("\n" + "=" * 60)
    print("Data Quality Report Generated Successfully!")
    print("=" * 60)
    
    # Print summary
    print("\n📊 SUMMARY")
    print(f"  Total Records: {report['metadata']['total_records']:,}")
    print(f"  Countries: {len(report['sample_composition']['countries'])}")
    print(f"  Variables: {report['metadata']['n_variables']}")
    
    print("\n✅ MANUSCRIPT VALIDATION")
    for v in report['manuscript_validation']['validations']:
        status = "✅" if v.get("within_tolerance") or v.get("match") or v.get("covers_period") else "⚠️"
        print(f"  {status} {v['claim']}")
    
    print("\n📁 Report saved to:")
    print(f"  {OUTPUT_FILE}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
