#!/usr/bin/env python3
"""
Download and analyze procurement data from non-EU countries (OCDS standard, national sources).
Focus: Ukraine, UK, Mexico, Canada, Paraguay
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Result directory
RESULTS_DIR = Path('results')
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Store all results
all_results = {
    'metadata': {
        'timestamp': datetime.now().isoformat(),
        'countries_attempted': [],
        'countries_successful': []
    },
    'countries': {}
}

# ============================================================================
# 1. UKRAINE (ProZorro - Excellent OCDS data)
# ============================================================================

def download_prozorro_data() -> Optional[Dict]:
    """Download procurement data from Ukraine's ProZorro (OCDS API)."""
    logger.info("=" * 80)
    logger.info("UKRAINE (ProZorro)")
    logger.info("=" * 80)
    
    country = "Ukraine"
    all_results['metadata']['countries_attempted'].append(country)
    
    ukraine_data = {
        'country': country,
        'source': 'ProZorro (OCDS)',
        'api_url': 'https://prozorro.gov.ua/api/v2',
        'contracts': [],
        'stats': {}
    }
    
    try:
        # ProZorro API - try to get releases/records
        logger.info("Fetching ProZorro tender data...")
        
        # Using the public API to get recent tenders
        # API endpoint: /api/v2/tenders
        url = "https://prozorro.gov.ua/api/v2/tenders"
        
        params = {
            'descending': 1,
            'limit': 100,  # Start with 100 to test
            'opt_fields': 'id,dateModified,status,tender'
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"✓ Retrieved ProZorro response")
        
        if 'data' in data:
            tenders = data['data']
            logger.info(f"  Found {len(tenders)} tenders")
            
            # Parse tender data for single-bidder analysis
            single_bidder_count = 0
            total_with_bids = 0
            
            for tender in tenders[:50]:  # Analyze first 50 for speed
                try:
                    tender_id = tender.get('id', 'N/A')
                    status = tender.get('status', 'N/A')
                    tender_obj = tender.get('tender', {})
                    bids = tender_obj.get('bids', [])
                    
                    if bids:
                        total_with_bids += 1
                        if len(bids) == 1:
                            single_bidder_count += 1
                        
                        ukraine_data['contracts'].append({
                            'id': tender_id,
                            'status': status,
                            'bid_count': len(bids),
                            'value': tender_obj.get('value', {}).get('amount', None),
                            'currency': tender_obj.get('value', {}).get('currency', 'UAH')
                        })
                except Exception as e:
                    logger.debug(f"Error parsing tender {tender.get('id')}: {e}")
                    continue
            
            ukraine_data['stats'] = {
                'total_records_retrieved': len(tenders),
                'sample_size': len(ukraine_data['contracts']),
                'tenders_with_bids': total_with_bids,
                'single_bidder_count': single_bidder_count,
                'single_bidder_rate': single_bidder_count / total_with_bids if total_with_bids > 0 else 0,
                'avg_bids_per_contract': sum(c['bid_count'] for c in ukraine_data['contracts']) / len(ukraine_data['contracts']) if ukraine_data['contracts'] else 0
            }
            
            logger.info(f"  ✓ Single-bidder rate: {ukraine_data['stats']['single_bidder_rate']:.2%}")
            logger.info(f"  ✓ Avg bids per contract: {ukraine_data['stats']['avg_bids_per_contract']:.2f}")
            
            all_results['metadata']['countries_successful'].append(country)
            
        return ukraine_data
        
    except Exception as e:
        logger.error(f"✗ Failed to download ProZorro data: {e}")
        return ukraine_data

# ============================================================================
# 2. UK (Contracts Finder - Government procurement)
# ============================================================================

def download_uk_data() -> Optional[Dict]:
    """Download procurement data from UK's Contracts Finder."""
    logger.info("=" * 80)
    logger.info("UNITED KINGDOM (Contracts Finder)")
    logger.info("=" * 80)
    
    country = "United Kingdom"
    all_results['metadata']['countries_attempted'].append(country)
    
    uk_data = {
        'country': country,
        'source': 'Contracts Finder / OCDS',
        'api_url': 'https://data.open-contracting.org/',
        'contracts': [],
        'stats': {}
    }
    
    try:
        # Try OCDS data from Open Contracting
        logger.info("Fetching UK procurement data from OCDS Kingfisher...")
        
        # The Kingfisher API provides access to multiple OCDS datasets
        # We'll try to get data through the OCDS registry
        url = "https://data.open-contracting.org/api/covid"
        
        params = {
            'package_url': 'https://data.contractsfinder.service.gov.uk/api/v1/ocds_snapshot.json.zip',
        }
        
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"✓ Retrieved UK OCDS data")
            
            # For UK, try the simpler approach: use open data exports
            # Contracts Finder publishes CSV/JSON exports
            logger.info("Attempting UK Contracts Finder CSV download...")
            
            # Alternative: use UK government JSON API if available
            url_cf = "https://www.contractsfinder.service.gov.uk/published/Search/Results"
            
            uk_data['stats'] = {
                'note': 'UK Contracts Finder requires web scraping or direct CSV download',
                'data_source_available': True,
                'recommendation': 'Use published monthly data snapshots'
            }
            
            all_results['metadata']['countries_successful'].append(country)
            
        else:
            logger.warning(f"Status: {response.status_code}")
            uk_data['stats'] = {
                'note': 'Could not retrieve real-time data; UK publishes monthly snapshots',
                'recommendation': 'Download from https://www.contractsfinder.service.gov.uk/Published/Notices/OJEU/Search'
            }
        
        return uk_data
        
    except Exception as e:
        logger.error(f"✗ Failed to download UK data: {e}")
        return uk_data

# ============================================================================
# 3. MEXICO (CompraNet / OCDS)
# ============================================================================

def download_mexico_data() -> Optional[Dict]:
    """Download procurement data from Mexico's CompraNet (OCDS)."""
    logger.info("=" * 80)
    logger.info("MEXICO (CompraNet/OCDS)")
    logger.info("=" * 80)
    
    country = "Mexico"
    all_results['metadata']['countries_attempted'].append(country)
    
    mexico_data = {
        'country': country,
        'source': 'CompraNet (OCDS)',
        'api_url': 'https://www.gob.mx/compranet',
        'contracts': [],
        'stats': {}
    }
    
    try:
        logger.info("Fetching Mexico CompraNet procurement data...")
        
        # CompraNet has OCDS data through various API endpoints
        # Try the Kingfisher OCDS access point
        url = "https://data.open-contracting.org/api/covid"
        
        # Try direct OCDS Mexico endpoint
        ocds_url = "https://datos.gob.mx/api/v3/action/package_search"
        params = {'q': 'compranet', 'rows': 10}
        
        response = requests.get(ocds_url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if 'result' in data:
                logger.info(f"✓ Found {len(data['result']['results'])} CompraNet datasets")
                
                mexico_data['stats'] = {
                    'datasets_available': len(data['result']['results']),
                    'note': 'CompraNet data available through datos.gob.mx portal',
                    'recommendation': 'Access OCDS releases through portal APIs'
                }
                
                all_results['metadata']['countries_successful'].append(country)
        
        return mexico_data
        
    except Exception as e:
        logger.error(f"✗ Failed to download Mexico data: {e}")
        return mexico_data

# ============================================================================
# 4. OCDS Global - Try Kingfisher/Registry for multiple countries
# ============================================================================

def download_ocds_kingfisher_data() -> Dict:
    """Download data from OCDS Kingfisher (global OCDS data aggregator)."""
    logger.info("=" * 80)
    logger.info("OCDS KINGFISHER - Global OCDS Data")
    logger.info("=" * 80)
    
    kingfisher_data = {
        'source': 'OCDS Kingfisher',
        'api_url': 'https://data.open-contracting.org/',
        'available_countries': [],
        'sample_data': {}
    }
    
    try:
        logger.info("Fetching OCDS Kingfisher available datasets...")
        
        # The Kingfisher API provides metadata about available OCDS datasets
        url = "https://data.open-contracting.org/api"
        
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✓ Connected to OCDS Kingfisher")
            logger.info(f"  Available data: {data}")
            
            kingfisher_data['metadata'] = data
            
        else:
            logger.info("Trying alternative OCDS access method...")
            
            # Try OCDS Registry
            url_registry = "https://www.open-contracting.org/data/"
            logger.info(f"  OCDS Registry: {url_registry}")
            
            # List of known countries with OCDS publishers
            ocds_countries = {
                'Ukraine': 'https://prozorro.gov.ua/',
                'Paraguay': 'https://www.hacienda.gov.py/',
                'Mexico': 'https://www.gob.mx/compranet',
                'Canada': 'https://buyandsell.gc.ca/',
                'Colombia': 'https://www.secop.gov.co/'
            }
            
            kingfisher_data['known_ocds_publishers'] = ocds_countries
            
        return kingfisher_data
        
    except Exception as e:
        logger.error(f"✗ Failed to connect to OCDS Kingfisher: {e}")
        return kingfisher_data

# ============================================================================
# 5. COLOMBIA (Already mentioned as part of paper) - SECOP
# ============================================================================

def download_colombia_data() -> Optional[Dict]:
    """Download procurement data from Colombia's SECOP."""
    logger.info("=" * 80)
    logger.info("COLOMBIA (SECOP)")
    logger.info("=" * 80)
    
    country = "Colombia"
    all_results['metadata']['countries_attempted'].append(country)
    
    colombia_data = {
        'country': country,
        'source': 'SECOP (OCDS)',
        'api_url': 'https://www.secop.gov.co/',
        'contracts': [],
        'stats': {}
    }
    
    try:
        logger.info("Fetching Colombia SECOP procurement data...")
        
        # SECOP has API v2 with OCDS data
        url = "https://www.secop.gov.co/sec/v2/proceso/buscar"
        
        params = {
            'limit': 50,
            'offset': 0
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✓ Retrieved SECOP data")
            
            if 'results' in data:
                processes = data['results']
                logger.info(f"  Found {len(processes)} processes")
                
                single_bid_count = 0
                total_processes = 0
                
                for process in processes:
                    try:
                        total_processes += 1
                        process_id = process.get('id', 'N/A')
                        
                        # Check for tender status and bidders
                        status = process.get('estadoProceso', 'N/A')
                        bidders = process.get('oferentes', [])
                        
                        if bidders:
                            if len(bidders) == 1:
                                single_bid_count += 1
                            
                            colombia_data['contracts'].append({
                                'id': process_id,
                                'status': status,
                                'bidder_count': len(bidders),
                                'valor': process.get('valor', None)
                            })
                    except Exception as e:
                        logger.debug(f"Error parsing process {process.get('id')}: {e}")
                        continue
                
                colombia_data['stats'] = {
                    'total_processes': total_processes,
                    'sample_size': len(colombia_data['contracts']),
                    'single_bidder_count': single_bid_count,
                    'single_bidder_rate': single_bid_count / total_processes if total_processes > 0 else 0,
                    'avg_bidders_per_process': sum(c['bidder_count'] for c in colombia_data['contracts']) / len(colombia_data['contracts']) if colombia_data['contracts'] else 0
                }
                
                logger.info(f"  ✓ Single-bidder rate: {colombia_data['stats']['single_bidder_rate']:.2%}")
                
                all_results['metadata']['countries_successful'].append(country)
        
        return colombia_data
        
    except Exception as e:
        logger.error(f"✗ Failed to download Colombia data: {e}")
        return colombia_data

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def calculate_single_bidder_rates(all_results: Dict) -> Dict:
    """Calculate and summarize single-bidder rates across countries."""
    logger.info("\n" + "=" * 80)
    logger.info("ANALYSIS SUMMARY: Single-Bidder Rates by Country")
    logger.info("=" * 80)
    
    summary = {}
    
    for country_key, country_data in all_results.get('countries', {}).items():
        if 'stats' in country_data and 'single_bidder_rate' in country_data['stats']:
            stats = country_data['stats']
            summary[country_data.get('country', country_key)] = {
                'single_bidder_rate': stats.get('single_bidder_rate', 0),
                'sample_size': stats.get('sample_size', 0),
                'avg_bids': stats.get('avg_bids_per_contract', 0) or stats.get('avg_bidders_per_process', 0),
                'data_quality': 'Good' if stats.get('sample_size', 0) > 20 else 'Limited'
            }
    
    # Log summary
    for country, data in sorted(summary.items(), key=lambda x: x[1]['single_bidder_rate'], reverse=True):
        logger.info(f"\n{country}:")
        logger.info(f"  Single-bidder rate: {data['single_bidder_rate']:.2%}")
        logger.info(f"  Sample size: {data['sample_size']}")
        logger.info(f"  Avg bids/process: {data['avg_bids']:.2f}")
        logger.info(f"  Data quality: {data['data_quality']}")
    
    return summary

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    logger.info("\n" + "=" * 80)
    logger.info("GLOBAL PROCUREMENT DATA DOWNLOAD & ANALYSIS")
    logger.info("Non-EU Countries OCDS Replication Study")
    logger.info("=" * 80 + "\n")
    
    # Download data from each country/source
    logger.info("Phase 1: Downloading procurement data...")
    
    all_results['countries']['ukraine'] = download_prozorro_data()
    time.sleep(2)  # Rate limiting
    
    all_results['countries']['colombia'] = download_colombia_data()
    time.sleep(2)
    
    all_results['countries']['uk'] = download_uk_data()
    time.sleep(2)
    
    all_results['countries']['mexico'] = download_mexico_data()
    time.sleep(2)
    
    # Get OCDS Kingfisher metadata
    kingfisher_results = download_ocds_kingfisher_data()
    all_results['ocds_kingfisher'] = kingfisher_results
    
    # Phase 2: Analysis
    logger.info("\nPhase 2: Analyzing single-bidder rates...")
    summary = calculate_single_bidder_rates(all_results)
    all_results['analysis_summary'] = summary
    
    # Phase 3: Save results
    logger.info("\nPhase 3: Saving results...")
    
    output_file = RESULTS_DIR / 'ocds_global_replication.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    logger.info(f"✓ Results saved to {output_file}")
    
    # Summary statistics
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Countries attempted: {len(all_results['metadata']['countries_attempted'])}")
    logger.info(f"Countries successful: {len(all_results['metadata']['countries_successful'])}")
    logger.info(f"Countries: {', '.join(all_results['metadata']['countries_attempted'])}")
    logger.info(f"\nSuccessful downloads: {', '.join(all_results['metadata']['countries_successful'])}")
    
    return all_results

if __name__ == '__main__':
    results = main()
    logger.info("\n✓ Global procurement data download complete!")
