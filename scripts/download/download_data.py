#!/usr/bin/env python3
"""
download_data.py - Data acquisition utilities.

Downloads external data sources required for the analysis:
- Exchange rates from World Bank
- CPV code taxonomy
- GDP/population data for controls

Usage:
    python -m scripts.download_data exchange-rates --output data/raw/exchange_rates.csv
    python -m scripts.download_data cpv-codes --output data/raw/cpv_taxonomy.json
    python -m scripts.download_data gdp --countries UA,CO,GB --output data/raw/gdp.csv
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

import requests
import pandas as pd


class WorldBankAPI:
    """Client for World Bank Open Data API."""
    
    BASE_URL = "https://api.worldbank.org/v2"
    
    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        self.session = requests.Session()
    
    def get_indicator(
        self,
        indicator: str,
        countries: List[str],
        start_year: int,
        end_year: int
    ) -> pd.DataFrame:
        """
        Fetch indicator data for countries.
        
        Parameters
        ----------
        indicator : str
            World Bank indicator code (e.g., 'PA.NUS.FCRF' for exchange rates)
        countries : list
            ISO country codes
        start_year, end_year : int
            Year range
            
        Returns
        -------
        pd.DataFrame
        """
        countries_str = ";".join(countries)
        url = f"{self.BASE_URL}/country/{countries_str}/indicator/{indicator}"
        
        params = {
            "format": "json",
            "per_page": 1000,
            "date": f"{start_year}:{end_year}"
        }
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if len(data) < 2:
            return pd.DataFrame()
        
        records = []
        for item in data[1]:
            records.append({
                "country": item["country"]["id"],
                "country_name": item["country"]["value"],
                "year": int(item["date"]),
                "value": item["value"],
                "indicator": indicator
            })
        
        time.sleep(self.rate_limit)
        return pd.DataFrame(records)
    
    def get_exchange_rates(
        self,
        countries: List[str],
        start_year: int,
        end_year: int,
        rate_type: str = "ppp"
    ) -> pd.DataFrame:
        """
        Get exchange rates.
        
        Parameters
        ----------
        countries : list
            Country codes
        start_year, end_year : int
            Year range
        rate_type : str
            'ppp' for PPP rates, 'official' for market rates
            
        Returns
        -------
        pd.DataFrame
        """
        indicator = "PA.NUS.PPPC.RF" if rate_type == "ppp" else "PA.NUS.FCRF"
        return self.get_indicator(indicator, countries, start_year, end_year)
    
    def get_gdp(
        self,
        countries: List[str],
        start_year: int,
        end_year: int,
        per_capita: bool = True
    ) -> pd.DataFrame:
        """Get GDP data."""
        indicator = "NY.GDP.PCAP.CD" if per_capita else "NY.GDP.MKTP.CD"
        return self.get_indicator(indicator, countries, start_year, end_year)


def download_cpv_codes(output_path: Path) -> None:
    """
    Download CPV (Common Procurement Vocabulary) taxonomy.
    
    Parameters
    ----------
    output_path : Path
        Output file path for JSON
    """
    # CPV codes are available from EU publications office
    # Using a simplified structure here
    
    cpv_divisions = {
        "03": {"name": "Agricultural products", "category": "goods"},
        "09": {"name": "Petroleum products, fuel, electricity", "category": "goods"},
        "14": {"name": "Mining, basic metals", "category": "goods"},
        "15": {"name": "Food, beverages, tobacco", "category": "goods"},
        "18": {"name": "Clothing, footwear, luggage", "category": "goods"},
        "22": {"name": "Printed matter", "category": "goods"},
        "24": {"name": "Chemical products", "category": "goods"},
        "30": {"name": "Office machinery, computers", "category": "goods"},
        "31": {"name": "Electrical machinery", "category": "goods"},
        "32": {"name": "Radio, TV, communication", "category": "goods"},
        "33": {"name": "Medical equipment", "category": "goods"},
        "34": {"name": "Transport equipment", "category": "goods"},
        "35": {"name": "Security, fire-fighting", "category": "goods"},
        "37": {"name": "Musical instruments, sports", "category": "goods"},
        "38": {"name": "Laboratory, optical", "category": "goods"},
        "39": {"name": "Furniture, furnishings", "category": "goods"},
        "42": {"name": "Industrial machinery", "category": "goods"},
        "43": {"name": "Mining machinery", "category": "goods"},
        "44": {"name": "Construction structures", "category": "goods"},
        "45": {"name": "Construction work", "category": "works"},
        "48": {"name": "Software packages", "category": "goods"},
        "50": {"name": "Repair, maintenance", "category": "services"},
        "51": {"name": "Installation services", "category": "services"},
        "55": {"name": "Hotel, restaurant services", "category": "services"},
        "60": {"name": "Transport services", "category": "services"},
        "63": {"name": "Supporting transport services", "category": "services"},
        "64": {"name": "Postal, telecommunications", "category": "services"},
        "65": {"name": "Public utilities", "category": "services"},
        "66": {"name": "Financial, insurance services", "category": "services"},
        "70": {"name": "Real estate services", "category": "services"},
        "71": {"name": "Architectural, engineering", "category": "services"},
        "72": {"name": "IT services", "category": "services"},
        "73": {"name": "Research, development", "category": "services"},
        "75": {"name": "Administration, defence", "category": "services"},
        "76": {"name": "Oil, gas industry services", "category": "services"},
        "77": {"name": "Agriculture, forestry services", "category": "services"},
        "79": {"name": "Business services", "category": "services"},
        "80": {"name": "Education, training", "category": "services"},
        "85": {"name": "Health, social services", "category": "services"},
        "90": {"name": "Sewage, refuse", "category": "services"},
        "92": {"name": "Recreational, cultural", "category": "services"},
        "98": {"name": "Other community services", "category": "services"}
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(cpv_divisions, f, indent=2)
    
    print(f"Saved CPV taxonomy to {output_path}")


def validate_ocds(input_path: Path, output_path: Path) -> None:
    """
    Validate OCDS data against schema.
    
    Parameters
    ----------
    input_path : Path
        Input JSONL file
    output_path : Path
        Output validation report JSON
    """
    import jsonschema
    
    # OCDS 1.1 release schema (simplified for validation)
    required_fields = ["ocid", "id", "date", "tag", "initiationType"]
    valid_tags = ["planning", "tender", "award", "contract", "implementation"]
    
    validation_results = {
        "total": 0,
        "valid": 0,
        "invalid": 0,
        "errors": []
    }
    
    with open(input_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            validation_results["total"] += 1
            
            try:
                release = json.loads(line)
                
                # Check required fields
                missing = [f for f in required_fields if f not in release]
                if missing:
                    validation_results["invalid"] += 1
                    validation_results["errors"].append({
                        "line": line_num,
                        "error": f"Missing required fields: {missing}"
                    })
                    continue
                
                # Check tag values
                if not all(t in valid_tags for t in release.get("tag", [])):
                    validation_results["invalid"] += 1
                    validation_results["errors"].append({
                        "line": line_num,
                        "error": f"Invalid tag values: {release.get('tag')}"
                    })
                    continue
                
                validation_results["valid"] += 1
                
            except json.JSONDecodeError as e:
                validation_results["invalid"] += 1
                validation_results["errors"].append({
                    "line": line_num,
                    "error": f"JSON parse error: {str(e)}"
                })
    
    # Only keep first 100 errors
    validation_results["errors"] = validation_results["errors"][:100]
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(validation_results, f, indent=2)
    
    print(f"Validation complete: {validation_results['valid']}/{validation_results['total']} valid")
    print(f"Report saved to {output_path}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Download external data for GPRD analysis'
    )
    subparsers = parser.add_subparsers(dest='command', help='Data type')
    
    # Exchange rates
    exch_parser = subparsers.add_parser('exchange-rates', help='Download exchange rates')
    exch_parser.add_argument('--output', required=True, type=Path)
    exch_parser.add_argument('--start-year', type=int, default=2015)
    exch_parser.add_argument('--end-year', type=int, default=2024)
    exch_parser.add_argument('--source', choices=['world_bank'], default='world_bank')
    
    # CPV codes
    cpv_parser = subparsers.add_parser('cpv-codes', help='Download CPV taxonomy')
    cpv_parser.add_argument('--output', required=True, type=Path)
    
    # GDP data
    gdp_parser = subparsers.add_parser('gdp', help='Download GDP data')
    gdp_parser.add_argument('--output', required=True, type=Path)
    gdp_parser.add_argument('--countries', required=True, help='Comma-separated country codes')
    gdp_parser.add_argument('--start-year', type=int, default=2010)
    gdp_parser.add_argument('--end-year', type=int, default=2024)
    
    # Validate OCDS
    val_parser = subparsers.add_parser('validate-ocds', help='Validate OCDS data')
    val_parser.add_argument('--input', required=True, type=Path)
    val_parser.add_argument('--output', required=True, type=Path)
    val_parser.add_argument('--schema-version', default='1.1')
    
    args = parser.parse_args()
    
    if args.command == 'exchange-rates':
        api = WorldBankAPI()
        countries = ['UA', 'CO', 'GB']  # Ukraine, Colombia, UK
        
        df = api.get_exchange_rates(
            countries=countries,
            start_year=args.start_year,
            end_year=args.end_year
        )
        
        args.output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.output, index=False)
        print(f"Saved exchange rates to {args.output}")
        
    elif args.command == 'cpv-codes':
        download_cpv_codes(args.output)
        
    elif args.command == 'gdp':
        api = WorldBankAPI()
        countries = args.countries.split(',')
        
        df = api.get_gdp(
            countries=countries,
            start_year=args.start_year,
            end_year=args.end_year
        )
        
        args.output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.output, index=False)
        print(f"Saved GDP data to {args.output}")
        
    elif args.command == 'validate-ocds':
        validate_ocds(args.input, args.output)
        
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
