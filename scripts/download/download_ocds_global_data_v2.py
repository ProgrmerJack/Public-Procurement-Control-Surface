#!/usr/bin/env python3
"""
Enhanced procurement data download with multiple fallback sources.
Tries OCDS APIs, CSV exports, and alternative data formats.
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
from pathlib import Path
import time
from io import StringIO
import zipfile
import tempfile

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RESULTS_DIR = Path('results')
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

all_results = {
    'metadata': {
        'timestamp': datetime.now().isoformat(),
        'countries_attempted': [],
        'countries_successful': [],
        'data_sources_tried': {}
    },
    'countries': {}
}

# ============================================================================
# 1. UKRAINE - ProZorro (Multiple API endpoints)
# ============================================================================

def download_ukraine_data() -> Dict:
    """Try multiple Ukraine ProZorro endpoints."""
    logger.info("\n" + "="*80)
    logger.info("UKRAINE (ProZorro)")
    logger.info("="*80)
    
    country = "Ukraine"
    all_results['metadata']['countries_attempted'].append(country)
    
    ukraine_data = {
        'country': country,
        'source': 'ProZorro (OCDS)',
        'contracts': [],
        'stats': {}
    }
    
    # Try multiple ProZorro endpoints
    endpoints = [
        {
            'name': 'ProZorro v2 API',
            'url': 'https://api.prozorro.gov.ua/api/v2/tenders',
            'params': {'descending': '1', 'limit': '50'}
        },
        {
            'name': 'ProZorro Releases',
            'url': 'https://api.prozorro.gov.ua/api/v2.1/releases',
            'params': {'limit': '50'}
        },
        {
            'name': 'ProZorro Contracts',
            'url': 'https://api.prozorro.gov.ua/api/v2.1/contracts',
            'params': {'limit': '50'}
        },
    ]
    
    for endpoint in endpoints:
        try:
            logger.info(f"Trying: {endpoint['name']} ({endpoint['url']})")
            response = requests.get(endpoint['url'], params=endpoint['params'], timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'data' in data:
                    items = data['data']
                    logger.info(f"  ✓ Success! Retrieved {len(items)} items")
                    
                    # Process bidding data
                    single_bid = 0
                    total_bids = 0
                    bid_counts = []
                    
                    for item in items:
                        try:
                            if 'bids' in item:
                                bid_count = len(item['bids'])
                                bid_counts.append(bid_count)
                                total_bids += 1
                                if bid_count == 1:
                                    single_bid += 1
                        except:
                            pass
                    
                    if bid_counts:
                        ukraine_data['stats'] = {
                            'api_endpoint': endpoint['name'],
                            'total_records': len(items),
                            'records_with_bids': total_bids,
                            'single_bidder_count': single_bid,
                            'single_bidder_rate': single_bid / total_bids if total_bids > 0 else 0,
                            'avg_bids': sum(bid_counts) / len(bid_counts) if bid_counts else 0,
                            'min_bids': min(bid_counts),
                            'max_bids': max(bid_counts)
                        }
                        logger.info(f"  ✓ Single-bidder rate: {ukraine_data['stats']['single_bidder_rate']:.2%}")
                        all_results['metadata']['countries_successful'].append(country)
                        return ukraine_data
            else:
                logger.info(f"  ✗ Status {response.status_code}")
                
        except Exception as e:
            logger.info(f"  ✗ Error: {e}")
    
    logger.warning(f"  Could not access ProZorro APIs directly")
    return ukraine_data

# ============================================================================
# 2. COLOMBIA - SECOP (Multiple versions)
# ============================================================================

def download_colombia_data() -> Dict:
    """Try multiple Colombia SECOP endpoints."""
    logger.info("\n" + "="*80)
    logger.info("COLOMBIA (SECOP)")
    logger.info("="*80)
    
    country = "Colombia"
    all_results['metadata']['countries_attempted'].append(country)
    
    colombia_data = {
        'country': country,
        'source': 'SECOP (Colombian procurement)',
        'contracts': [],
        'stats': {}
    }
    
    endpoints = [
        {
            'name': 'SECOP API v2',
            'url': 'https://www.secop.gov.co/sec/v2/proceso/buscar',
            'params': {'limit': '50', 'offset': '0'}
        },
        {
            'name': 'SECOP API estadoProceso',
            'url': 'https://www.secop.gov.co/sec/v2/estadoProceso',
            'params': {'limit': '50'}
        },
    ]
    
    for endpoint in endpoints:
        try:
            logger.info(f"Trying: {endpoint['name']} ({endpoint['url']})")
            response = requests.get(endpoint['url'], params=endpoint['params'], timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"  ✓ Response received")
                
                # Try different response formats
                items = None
                if 'results' in data:
                    items = data['results']
                elif 'data' in data:
                    items = data['data']
                elif isinstance(data, list):
                    items = data
                
                if items and len(items) > 0:
                    logger.info(f"  ✓ Retrieved {len(items)} processes")
                    
                    bidder_counts = []
                    single_bid = 0
                    total_processes = 0
                    
                    for proc in items:
                        try:
                            # Different field names for bidders
                            bidders = proc.get('oferentes') or proc.get('bidders') or proc.get('bids')
                            if isinstance(bidders, list):
                                bidder_counts.append(len(bidders))
                                total_processes += 1
                                if len(bidders) == 1:
                                    single_bid += 1
                        except:
                            pass
                    
                    if bidder_counts:
                        colombia_data['stats'] = {
                            'api_endpoint': endpoint['name'],
                            'total_records': len(items),
                            'processes_with_bidders': total_processes,
                            'single_bidder_count': single_bid,
                            'single_bidder_rate': single_bid / total_processes if total_processes > 0 else 0,
                            'avg_bidders': sum(bidder_counts) / len(bidder_counts),
                            'min_bidders': min(bidder_counts),
                            'max_bidders': max(bidder_counts)
                        }
                        logger.info(f"  ✓ Single-bidder rate: {colombia_data['stats']['single_bidder_rate']:.2%}")
                        all_results['metadata']['countries_successful'].append(country)
                        return colombia_data
                        
        except Exception as e:
            logger.info(f"  ✗ Error: {e}")
    
    logger.warning(f"  Could not access SECOP APIs")
    return colombia_data

# ============================================================================
# 3. UK - Try Open Contracting + Alternative sources
# ============================================================================

def download_uk_data() -> Dict:
    """Try UK procurement data sources."""
    logger.info("\n" + "="*80)
    logger.info("UNITED KINGDOM (Contracts Finder / CompOps)")
    logger.info("="*80)
    
    country = "United Kingdom"
    all_results['metadata']['countries_attempted'].append(country)
    
    uk_data = {
        'country': country,
        'source': 'UK Government Procurement',
        'contracts': [],
        'stats': {}
    }
    
    endpoints = [
        {
            'name': 'Contracts Finder API',
            'url': 'https://www.contractsfinder.service.gov.uk/api/notices',
            'params': {'limit': '50', 'page': '1'}
        },
        {
            'name': 'OpenOpps JSON',
            'url': 'https://data.open-contracting.org/api/v1/publishers',
            'params': {}
        },
    ]
    
    for endpoint in endpoints:
        try:
            logger.info(f"Trying: {endpoint['name']}")
            response = requests.get(endpoint['url'], params=endpoint['params'], timeout=15)
            
            if response.status_code == 200:
                logger.info(f"  ✓ Response: {response.status_code}")
                uk_data['stats'] = {
                    'api_endpoint': endpoint['name'],
                    'status': 'accessible',
                    'note': 'UK procurement data available but requires specific access keys',
                    'recommendation': 'Use Contracts Finder monthly snapshots or CompOps API'
                }
                all_results['metadata']['countries_successful'].append(country)
                return uk_data
                
        except Exception as e:
            logger.info(f"  ✗ Error: {e}")
    
    uk_data['stats'] = {
        'note': 'UK procurement data exists but requires authentication or specific formats',
        'sources': ['Contracts Finder', 'CompOps', 'Find a Tender Service']
    }
    
    return uk_data

# ============================================================================
# 4. MEXICO - CompraNet
# ============================================================================

def download_mexico_data() -> Dict:
    """Try Mexico procurement data."""
    logger.info("\n" + "="*80)
    logger.info("MEXICO (CompraNet / OCDS)")
    logger.info("="*80)
    
    country = "Mexico"
    all_results['metadata']['countries_attempted'].append(country)
    
    mexico_data = {
        'country': country,
        'source': 'CompraNet (Mexican procurement)',
        'contracts': [],
        'stats': {}
    }
    
    endpoints = [
        {
            'name': 'datos.gob.mx CompraNet',
            'url': 'https://datos.gob.mx/api/3/action/package_search',
            'params': {'q': 'compranet OCDS', 'rows': '50'}
        },
        {
            'name': 'CompraNet direct',
            'url': 'https://api.compranet.gob.mx/compranet',
            'params': {}
        },
    ]
    
    for endpoint in endpoints:
        try:
            logger.info(f"Trying: {endpoint['name']}")
            response = requests.get(endpoint['url'], params=endpoint['params'], timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"  ✓ Response received")
                
                if 'result' in data and 'results' in data['result']:
                    results = data['result']['results']
                    logger.info(f"  ✓ Found {len(results)} CompraNet datasets")
                    
                    mexico_data['stats'] = {
                        'api_endpoint': endpoint['name'],
                        'datasets_available': len(results),
                        'status': 'accessible',
                        'recommendation': 'Access OCDS releases through datos.gob.mx'
                    }
                    all_results['metadata']['countries_successful'].append(country)
                    return mexico_data
                    
        except Exception as e:
            logger.info(f"  ✗ Error: {e}")
    
    return mexico_data

# ============================================================================
# 5. PARAGUAY - OCDS Pioneer
# ============================================================================

def download_paraguay_data() -> Dict:
    """Try Paraguay procurement data."""
    logger.info("\n" + "="*80)
    logger.info("PARAGUAY (OCDS Pioneer)")
    logger.info("="*80)
    
    country = "Paraguay"
    all_results['metadata']['countries_attempted'].append(country)
    
    paraguay_data = {
        'country': country,
        'source': 'Paraguay Government Procurement',
        'contracts': [],
        'stats': {}
    }
    
    endpoints = [
        {
            'name': 'Paraguay OCDS',
            'url': 'https://www.hacienda.gov.py/api/v1',
            'params': {}
        },
        {
            'name': 'Paraguay SICP',
            'url': 'https://sicp.hacienda.gov.py/api/v1/proceso',
            'params': {'limit': '50'}
        },
    ]
    
    for endpoint in endpoints:
        try:
            logger.info(f"Trying: {endpoint['name']}")
            response = requests.get(endpoint['url'], params=endpoint['params'], timeout=15)
            
            if response.status_code == 200:
                logger.info(f"  ✓ Status: {response.status_code}")
                
        except Exception as e:
            logger.info(f"  ✗ Error: {e}")
    
    return paraguay_data

# ============================================================================
# 6. CANADA - BuyAndSell
# ============================================================================

def download_canada_data() -> Dict:
    """Try Canada procurement data."""
    logger.info("\n" + "="*80)
    logger.info("CANADA (BuyAndSell / Open Data)")
    logger.info("="*80)
    
    country = "Canada"
    all_results['metadata']['countries_attempted'].append(country)
    
    canada_data = {
        'country': country,
        'source': 'Canada Government Procurement',
        'contracts': [],
        'stats': {}
    }
    
    endpoints = [
        {
            'name': 'BuyAndSell API',
            'url': 'https://buyandsell.gc.ca/cgi-bin/publication/advanced_search.cgi',
            'params': {}
        },
        {
            'name': 'Open Government API',
            'url': 'https://open.canada.ca/api/3/action/package_search',
            'params': {'q': 'procurement', 'rows': '50'}
        },
    ]
    
    for endpoint in endpoints:
        try:
            logger.info(f"Trying: {endpoint['name']}")
            response = requests.get(endpoint['url'], params=endpoint['params'], timeout=15)
            
            if response.status_code in [200, 301, 302]:
                logger.info(f"  ✓ Status: {response.status_code}")
                
                if response.status_code == 200:
                    canada_data['stats'] = {
                        'api_endpoint': endpoint['name'],
                        'status': 'accessible'
                    }
                    all_results['metadata']['countries_successful'].append(country)
                    return canada_data
                    
        except Exception as e:
            logger.info(f"  ✗ Error: {e}")
    
    return canada_data

# ============================================================================
# 7. GLOBAL OCDS REGISTRY
# ============================================================================

def get_ocds_registry() -> Dict:
    """Get metadata about OCDS publishers globally."""
    logger.info("\n" + "="*80)
    logger.info("GLOBAL OCDS REGISTRY & PUBLISHERS")
    logger.info("="*80)
    
    registry_data = {
        'source': 'Open Contracting Data Standard',
        'publishers': {},
        'stats': {}
    }
    
    # Known OCDS publishers (from open-contracting.org)
    known_publishers = {
        'Ukraine': {
            'api': 'https://api.prozorro.gov.ua',
            'portal': 'https://prozorro.gov.ua',
            'coverage': 'Central and local government'
        },
        'Colombia': {
            'api': 'https://www.secop.gov.co/sec/v2',
            'portal': 'https://www.secop.gov.co',
            'coverage': 'Central government'
        },
        'Paraguay': {
            'api': 'https://sicp.hacienda.gov.py/api',
            'portal': 'https://www.hacienda.gov.py',
            'coverage': 'Government procurement'
        },
        'Mexico': {
            'api': 'https://api.compranet.gob.mx',
            'portal': 'https://www.gob.mx/compranet',
            'coverage': 'Federal government'
        },
        'United Kingdom': {
            'api': 'https://www.contractsfinder.service.gov.uk/api',
            'portal': 'https://www.contractsfinder.service.gov.uk',
            'coverage': 'Government contracting'
        },
        'Canada': {
            'api': 'https://buyandsell.gc.ca',
            'portal': 'https://buyandsell.gc.ca',
            'coverage': 'Federal procurement'
        }
    }
    
    registry_data['publishers'] = known_publishers
    registry_data['stats'] = {
        'total_known_publishers': len(known_publishers),
        'countries': list(known_publishers.keys()),
        'ocds_compliance': 'Varying - from full OCDS to partial'
    }
    
    logger.info(f"✓ Known OCDS publishers: {len(known_publishers)}")
    for country, info in known_publishers.items():
        logger.info(f"  {country}: {info['coverage']}")
    
    return registry_data

# ============================================================================
# ANALYSIS & EXPORT
# ============================================================================

def analyze_and_export() -> None:
    """Analyze data and export results."""
    logger.info("\n" + "="*80)
    logger.info("ANALYSIS & EXPORT")
    logger.info("="*80)
    
    # Collect statistics
    stats_summary = []
    
    for key, country_data in all_results.get('countries', {}).items():
        if country_data.get('stats'):
            stats_summary.append({
                'country': country_data.get('country'),
                'source': country_data.get('source'),
                **country_data['stats']
            })
    
    if stats_summary:
        df = pd.DataFrame(stats_summary)
        logger.info("\nSummary Statistics:")
        logger.info(df.to_string())
        
        all_results['summary_table'] = df.to_dict(orient='records')
    
    # Save results
    output_file = RESULTS_DIR / 'ocds_global_replication.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    logger.info(f"\n✓ Results saved to {output_file}")
    
    # Also save human-readable summary
    summary_file = RESULTS_DIR / 'ocds_global_summary.txt'
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("GLOBAL PROCUREMENT DATA - OCDS ANALYSIS\n")
        f.write("="*80 + "\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"Countries Attempted: {len(all_results['metadata']['countries_attempted'])}\n")
        f.write(f"Countries Successful: {len(all_results['metadata']['countries_successful'])}\n\n")
        
        if stats_summary:
            f.write("Single-Bidder Rates by Country:\n")
            f.write("-"*80 + "\n")
            for stat in sorted(stats_summary, key=lambda x: x.get('single_bidder_rate', 0), reverse=True):
                if 'single_bidder_rate' in stat:
                    f.write(f"{stat['country']:20} | SB Rate: {stat['single_bidder_rate']:.2%} | ")
                    f.write(f"Records: {stat.get('total_records', stat.get('records_with_bidders', 'N/A'))}\n")
    
    logger.info(f"✓ Summary saved to {summary_file}")

# ============================================================================
# MAIN
# ============================================================================

def main():
    logger.info("\n" + "="*80)
    logger.info("GLOBAL OCDS PROCUREMENT DATA DOWNLOAD")
    logger.info("Multi-source, multi-country analysis")
    logger.info("="*80)
    
    # Download data
    all_results['countries']['ukraine'] = download_ukraine_data()
    time.sleep(1)
    
    all_results['countries']['colombia'] = download_colombia_data()
    time.sleep(1)
    
    all_results['countries']['uk'] = download_uk_data()
    time.sleep(1)
    
    all_results['countries']['mexico'] = download_mexico_data()
    time.sleep(1)
    
    all_results['countries']['paraguay'] = download_paraguay_data()
    time.sleep(1)
    
    all_results['countries']['canada'] = download_canada_data()
    time.sleep(1)
    
    # Global registry
    all_results['ocds_registry'] = get_ocds_registry()
    
    # Analysis & export
    analyze_and_export()
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("DOWNLOAD SUMMARY")
    logger.info("="*80)
    logger.info(f"Countries attempted: {len(all_results['metadata']['countries_attempted'])}")
    logger.info(f"Successful: {len(all_results['metadata']['countries_successful'])}")
    logger.info(f"Success rate: {len(all_results['metadata']['countries_successful'])/len(all_results['metadata']['countries_attempted']):.0%}")
    
    return all_results

if __name__ == '__main__':
    results = main()
