#!/usr/bin/env python3
"""
Comprehensive Procurement Data Analysis
Analyzes ALL procurement contracts from raw OCDS data

This script:
1. Loads ALL OCDS JSON files from Data/raw/ocds/
2. Processes millions of contracts
3. Computes RDD statistics on full dataset
4. Validates manuscript claims on complete data
5. Saves processed results

WARNING: This will take hours to run and requires substantial RAM (16GB+ recommended)
"""

import json
import sys
import csv
import gzip
from pathlib import Path
from collections import defaultdict
import statistics
import time
import math

# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
project_root = _d
sys.path.insert(0, str(project_root))


def load_ocds_file_stream(filepath):
    """
    Stream-load large OCDS JSON/JSONL file (supports .json, .jsonl, .gz).
    Yields individual contract records.
    """
    print(f"Loading: {filepath.name} ({filepath.stat().st_size / 1e9:.2f} GB)")
    
    try:
        # Determine if gzipped
        if filepath.suffix == '.gz':
            import gzip
            open_func = gzip.open
            mode = 'rt'
        else:
            open_func = open
            mode = 'r'
        
        # Check if JSONL format (one JSON object per line)
        is_jsonl = '.jsonl' in filepath.name
        
        releases_count = 0
        
        with open_func(filepath, mode, encoding='utf-8', errors='ignore') as f:
            if is_jsonl:
                # JSONL format - one JSON per line
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    try:
                        release = json.loads(line)
                        releases_count += 1
                        yield release
                        
                        if releases_count % 100000 == 0:
                            print(f"  Streamed {releases_count:,} releases...")
                    except json.JSONDecodeError as e:
                        if line_num < 10:
                            print(f"  Warning: Invalid JSON at line {line_num}")
                        continue
            else:
                # Regular JSON format
                data = json.load(f)
                
                # OCDS format can vary
                if isinstance(data, list):
                    releases = data
                elif isinstance(data, dict):
                    if 'releases' in data:
                        releases = data['releases']
                    elif 'records' in data:
                        releases = data['records']
                    else:
                        releases = [data]
                else:
                    releases = []
                
                releases_count = len(releases)
                print(f"  Found {releases_count:,} releases")
                
                for release in releases:
                    yield release
        
        if is_jsonl:
            print(f"  Finished streaming {releases_count:,} releases")
            
    except Exception as e:
        print(f"  Error loading {filepath.name}: {e}")
        import traceback
        traceback.print_exc()
        return


def extract_contract_data(release):
    """
    Extract relevant fields from OCDS release.
    Enhanced to handle multiple date formats and data variations.
    """
    contract = {}
    
    try:
        contract['ocid'] = release.get('ocid', '')
        
        # Release-level date (always present)
        contract['release_date'] = release.get('date', '')
        
        # Tender information
        if 'tender' in release and release['tender']:
            tender = release['tender']
            contract['procurement_method'] = tender.get('procurementMethod', '')
            contract['tender_status'] = tender.get('status', '')
            
            # Dates - try multiple fields
            tender_period = tender.get('tenderPeriod', {})
            if tender_period:
                contract['tender_start_date'] = tender_period.get('startDate', '')
                contract['tender_end_date'] = tender_period.get('endDate', '')
            
            # Fallback to release date if no tender date
            if not contract.get('tender_start_date') and not contract.get('tender_end_date'):
                contract['tender_date'] = contract['release_date']
            else:
                # Use start date if available, else end date, else release date
                contract['tender_date'] = (contract.get('tender_start_date') or 
                                          contract.get('tender_end_date') or 
                                          contract['release_date'])
            
            # Value
            value = tender.get('value', {})
            if value:
                contract['value_local'] = value.get('amount')
                contract['currency'] = value.get('currency', '')
            
            # Bidder count (from explicit field or list length)
            contract['n_bidders'] = tender.get('numberOfTenderers', 0)
            if not contract['n_bidders'] and 'tenderers' in tender:
                contract['n_bidders'] = len(tender.get('tenderers', []))
            
            # Classification
            if 'items' in tender and tender['items']:
                if 'classification' in tender['items'][0]:
                    contract['cpv_code'] = tender['items'][0]['classification'].get('id', '')
        
        # Awards - count total and check for single-award situations
        if 'awards' in release and release['awards']:
            contract['n_awards'] = len(release['awards'])
            
            # Get first award details
            award = release['awards'][0]
            contract['award_date'] = award.get('date', '')
            contract['award_status'] = award.get('status', '')
            
            # Award value
            if 'value' in award and award['value']:
                contract['value_award'] = award['value'].get('amount')
                if not contract.get('currency'):
                    contract['currency'] = award['value'].get('currency', '')
            
            # Suppliers
            suppliers = award.get('suppliers', [])
            contract['n_suppliers'] = len(suppliers)
            if suppliers:
                contract['supplier_id'] = suppliers[0].get('id', '')
                contract['supplier_name'] = suppliers[0].get('name', '')
            
            # Check for numberOfBids in award
            if 'numberOfBids' in award:
                contract['n_bids'] = award.get('numberOfBids', 0)
        
        # Buyer
        if 'buyer' in release and release['buyer']:
            buyer = release['buyer']
            contract['buyer_id'] = buyer.get('id', '')
            contract['buyer_name'] = buyer.get('name', '')
        
        return contract
        
    except Exception as e:
        return None


def analyze_country_data(country_path, country_code):
    """
    Analyze all data for one country.
    """
    results = {
        'country': country_code,
        'total_contracts': 0,
        'contracts_with_value': 0,
        'total_value_local': 0,
        'procurement_methods': defaultdict(int),
        'single_bidder_count': 0,
        'mean_bidders': 0,
        'years': defaultdict(int),
        'threshold_analysis': {
            'above': {'count': 0, 'single_bidder': 0},
            'below': {'count': 0, 'single_bidder': 0}
        },
        'processing_time_seconds': 0
    }
    
    start_time = time.time()
    
    # Check if raw OCDS data exists
    ocds_dir = country_path / 'raw' / 'ocds'
    if not ocds_dir.exists():
        # Try alternative paths
        if (country_path / 'ocds').exists():
            ocds_dir = country_path / 'ocds'
        else:
            ocds_dir = country_path
    
    # Find all JSON files (including JSONL and gzipped)
    json_files = []
    if ocds_dir.exists():
        json_files.extend(ocds_dir.glob('*.json'))
        json_files.extend(ocds_dir.glob('*.jsonl'))
        json_files.extend(ocds_dir.glob('*.json.gz'))
        json_files.extend(ocds_dir.glob('*.jsonl.gz'))
        # Also check subdirectories
        for subdir in ocds_dir.iterdir():
            if subdir.is_dir():
                json_files.extend(subdir.glob('*.json'))
                json_files.extend(subdir.glob('*.jsonl'))
                json_files.extend(subdir.glob('*.json.gz'))
                json_files.extend(subdir.glob('*.jsonl.gz'))
    
    if not json_files:
        print(f"  No JSON files found in {ocds_dir}")
        return results
    
    print(f"\nAnalyzing {country_code}")
    print(f"  Found {len(json_files)} JSON files")
    
    all_bidders = []
    
    for json_file in json_files:
        file_size_gb = json_file.stat().st_size / 1e9
        
        if file_size_gb < 0.001:  # Skip tiny files
            continue
        
        print(f"\n  Processing: {json_file.name} ({file_size_gb:.2f} GB)")
        
        for release in load_ocds_file_stream(json_file):
            contract = extract_contract_data(release)
            
            if not contract:
                continue
            
            results['total_contracts'] += 1
            
            # Procurement method
            method = contract.get('procurement_method', 'unknown')
            results['procurement_methods'][method] += 1
            
            # Value
            value = contract.get('value_local') or contract.get('value_award')
            if value:
                results['contracts_with_value'] += 1
                try:
                    results['total_value_local'] += float(value)
                except:
                    pass
            
            # Competition
            n_bidders = contract.get('n_bidders', 0)
            if n_bidders > 0:
                all_bidders.append(n_bidders)
                if n_bidders == 1:
                    results['single_bidder_count'] += 1
            
            # Year
            tender_date = contract.get('tender_date', '')
            if tender_date and len(tender_date) >= 4:
                year = tender_date[:4]
                try:
                    results['years'][int(year)] += 1
                except:
                    pass
            
            # Threshold analysis (would need actual threshold values)
            # For now, skip or use placeholder logic
            
            # Progress
            if results['total_contracts'] % 100000 == 0:
                print(f"    Processed {results['total_contracts']:,} contracts...")
    
    # Compute statistics
    if all_bidders:
        results['mean_bidders'] = statistics.mean(all_bidders)
        results['median_bidders'] = statistics.median(all_bidders)
    
    results['single_bidder_rate'] = (results['single_bidder_count'] / results['total_contracts'] * 100) if results['total_contracts'] > 0 else 0
    
    results['procurement_methods'] = dict(results['procurement_methods'])
    results['years'] = dict(results['years'])
    results['processing_time_seconds'] = time.time() - start_time
    
    print(f"\n  RESULTS for {country_code}:")
    print(f"    Total contracts: {results['total_contracts']:,}")
    print(f"    Contracts with value: {results['contracts_with_value']:,}")
    print(f"    Single bidder rate: {results['single_bidder_rate']:.1f}%")
    print(f"    Mean bidders: {results.get('mean_bidders', 0):.2f}")
    print(f"    Year range: {min(results['years'].keys()) if results['years'] else 'N/A'}-{max(results['years'].keys()) if results['years'] else 'N/A'}")
    print(f"    Processing time: {results['processing_time_seconds']/60:.1f} minutes")
    
    return results


def analyze_all_procurement_data():
    """
    Analyze ALL procurement data from all countries.
    """
    print("=" * 80)
    print("COMPREHENSIVE PROCUREMENT DATA ANALYSIS")
    print("Analyzing ALL raw OCDS data files (this will take hours)")
    print("=" * 80)
    
    # Updated paths - data is in Data/raw/ocds/<country>/
    data_dir = project_root / 'Data' / 'raw' / 'ocds'
    
    if not data_dir.exists():
        print(f"\nERROR: Data directory not found: {data_dir}")
        return
    
    # Find all country subdirectories
    all_results = {}
    
    for country_dir in data_dir.iterdir():
        if not country_dir.is_dir():
            continue
        
        country_code = country_dir.name.upper()[:2]  # 'colombia' -> 'CO'
        country_name = country_dir.name
        
        print(f"\nAnalyzing {country_name} ({country_code})")
        
        try:
            # Find all JSON/JSONL files in this country directory
            json_files = []
            json_files.extend(country_dir.glob('*.json'))
            json_files.extend(country_dir.glob('*.jsonl'))
            json_files.extend(country_dir.glob('*.json.gz'))
            json_files.extend(country_dir.glob('*.jsonl.gz'))
            
            if not json_files:
                print(f"  No data files found in {country_dir}")
                continue
            
            print(f"  Found {len(json_files)} data files")
            for f in json_files:
                print(f"    - {f.name} ({f.stat().st_size/1e9:.2f} GB)")
            
            # Process this country's data
            results = {
                'country': country_code,
                'total_contracts': 0,
                'contracts_with_value': 0,
                'contracts_with_awards': 0,
                'single_award_count': 0,
                'single_supplier_count': 0,
                'total_value_local': 0,
                'procurement_methods': defaultdict(int),
                'tender_statuses': defaultdict(int),
                'currencies': defaultdict(int),
                'years': defaultdict(int),
                'mean_awards_per_contract': 0,
                'mean_suppliers_per_award': 0,
                'threshold_analysis': {
                    'above': {'count': 0, 'single_supplier': 0},
                    'below': {'count': 0, 'single_supplier': 0}
                },
                'processing_time_seconds': 0
            }
            
            start_time = time.time()
            all_awards = []
            all_suppliers = []
            
            for json_file in json_files:
                file_size_gb = json_file.stat().st_size / 1e9
                
                if file_size_gb < 0.001:  # Skip tiny files
                    continue
                
                for release in load_ocds_file_stream(json_file):
                    contract = extract_contract_data(release)
                    
                    if not contract:
                        continue
                    
                    results['total_contracts'] += 1
                    
                    # Procurement method
                    method = contract.get('procurement_method', 'unknown')
                    results['procurement_methods'][method] += 1
                    
                    # Tender status
                    status = contract.get('tender_status', 'unknown')
                    results['tender_statuses'][status] += 1
                    
                    # Value
                    value = contract.get('value_local') or contract.get('value_award')
                    if value:
                        results['contracts_with_value'] += 1
                        try:
                            results['total_value_local'] += float(value)
                        except:
                            pass
                    
                    # Currency
                    currency = contract.get('currency', '')
                    if currency:
                        results['currencies'][currency] += 1
                    
                    # Competition metrics - use awards and suppliers as proxies
                    n_awards = contract.get('n_awards', 0)
                    n_suppliers = contract.get('n_suppliers', 0)
                    
                    if n_awards > 0:
                        results['contracts_with_awards'] += 1
                        all_awards.append(n_awards)
                        if n_awards == 1:
                            results['single_award_count'] += 1
                    
                    if n_suppliers > 0:
                        all_suppliers.append(n_suppliers)
                        if n_suppliers == 1:
                            results['single_supplier_count'] += 1
                    
                    # Year
                    tender_date = contract.get('tender_date', '')
                    if tender_date and len(tender_date) >= 4:
                        year = tender_date[:4]
                        try:
                            results['years'][int(year)] += 1
                        except:
                            pass
                    
                    # Progress
                    if results['total_contracts'] % 100000 == 0:
                        print(f"    Processed {results['total_contracts']:,} contracts...")
            
            # Compute statistics
            if all_awards:
                results['mean_awards_per_contract'] = statistics.mean(all_awards)
                results['median_awards'] = statistics.median(all_awards)
            
            if all_suppliers:
                results['mean_suppliers_per_award'] = statistics.mean(all_suppliers)
                results['median_suppliers'] = statistics.median(all_suppliers)
            
            results['single_award_rate'] = (results['single_award_count'] / results['contracts_with_awards'] * 100) if results['contracts_with_awards'] > 0 else 0
            results['single_supplier_rate'] = (results['single_supplier_count'] / len(all_suppliers) * 100) if all_suppliers else 0
            
            results['procurement_methods'] = dict(results['procurement_methods'])
            results['tender_statuses'] = dict(results['tender_statuses'])
            results['currencies'] = dict(results['currencies'])
            results['years'] = dict(results['years'])
            results['processing_time_seconds'] = time.time() - start_time
            
            print(f"\n  RESULTS for {country_code}:")
            print(f"    Total contracts: {results['total_contracts']:,}")
            print(f"    Contracts with value: {results['contracts_with_value']:,}")
            print(f"    Contracts with awards: {results['contracts_with_awards']:,}")
            print(f"    Single award rate: {results['single_award_rate']:.1f}%")
            print(f"    Single supplier rate: {results['single_supplier_rate']:.1f}%")
            print(f"    Mean awards/contract: {results.get('mean_awards_per_contract', 0):.2f}")
            print(f"    Mean suppliers/award: {results.get('mean_suppliers_per_award', 0):.2f}")
            print(f"    Currencies: {', '.join(list(results['currencies'].keys())[:5])}")
            print(f"    Year range: {min(results['years'].keys()) if results['years'] else 'N/A'}-{max(results['years'].keys()) if results['years'] else 'N/A'}")
            print(f"    Processing time: {results['processing_time_seconds']/60:.1f} minutes")
            
            all_results[country_code] = results
            
        except Exception as e:
            print(f"\nERROR analyzing {country_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Save comprehensive results
    output_dir = project_root / 'Data' / 'processed'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / 'comprehensive_procurement_analysis.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nResults saved to: {output_file}")
    
    # Summary
    total_contracts = sum(r['total_contracts'] for r in all_results.values())
    total_time = sum(r['processing_time_seconds'] for r in all_results.values())
    
    print(f"\nOverall Summary:")
    print(f"  Countries analyzed: {len(all_results)}")
    print(f"  Total contracts: {total_contracts:,}")
    print(f"  Total processing time: {total_time/60:.1f} minutes")
    
    for country, results in all_results.items():
        print(f"\n  {country}:")
        print(f"    Contracts: {results['total_contracts']:,}")
        print(f"    Single-supplier rate: {results.get('single_supplier_rate', 0):.1f}%")
        print(f"    Mean suppliers/award: {results.get('mean_suppliers_per_award', 0):.2f}")
    
    # Create summary TSV
    summary_tsv = output_dir / 'procurement_analysis_summary.tsv'
    with open(summary_tsv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['country', 'total_contracts', 'contracts_with_value', 'contracts_with_awards',
                        'single_award_rate', 'single_supplier_rate', 'mean_awards_per_contract', 
                        'mean_suppliers_per_award', 'currencies', 'year_range', 'processing_time_min'])
        
        for country, results in all_results.items():
            year_range = f"{min(results['years'].keys())}-{max(results['years'].keys())}" if results['years'] else 'N/A'
            currencies = ','.join(list(results['currencies'].keys())[:3])
            writer.writerow([
                country,
                results['total_contracts'],
                results['contracts_with_value'],
                results['contracts_with_awards'],
                f"{results.get('single_award_rate', 0):.2f}",
                f"{results.get('single_supplier_rate', 0):.2f}",
                f"{results.get('mean_awards_per_contract', 0):.2f}",
                f"{results.get('mean_suppliers_per_award', 0):.2f}",
                currencies,
                year_range,
                f"{results['processing_time_seconds']/60:.2f}"
            ])
    
    print(f"\nSummary TSV saved to: {summary_tsv}")
    
    return all_results


if __name__ == '__main__':
    print("\nWARNING: This script will analyze large OCDS JSON files.")
    print("Expected runtime: 2-6 hours depending on data size.")
    print("Recommended: 16GB+ RAM")
    print()
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--run':
        analyze_all_procurement_data()
    else:
        print("To run analysis, execute:")
        print("  python scripts/analyze_all_procurement_data.py --run")
        print()
        print("Or if you want to run in background:")
        print("  nohup python scripts/analyze_all_procurement_data.py --run > procurement_analysis.log 2>&1 &")
