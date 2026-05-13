#!/usr/bin/env python3
"""
Data Acquisition Module for Global Procurement Research Dataset (GPRD)

Downloads and caches OCDS-format procurement data from:
- Ukraine: ProZorro (https://prozorro.gov.ua)
- Colombia: SECOP (https://www.colombiacompra.gov.co)
- UK: Contracts Finder (https://www.contractsfinder.service.gov.uk)

Author: Abduxoliq Ashuraliyev
License: MIT
"""

import json
import gzip
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Iterator, Dict, Any, List
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"

# API Endpoints
APIS = {
    "ukraine": {
        "name": "ProZorro",
        "base_url": "https://public.api.openprocurement.org/api/2.5",
        "tenders_endpoint": "/tenders",
        "ocds_releases": "https://prozorro.gov.ua/api/ocds/releases",
        "rate_limit": 0.5,  # seconds between requests
        "docs": "https://prozorro.gov.ua/en/developer"
    },
    "colombia": {
        "name": "SECOP",
        "base_url": "https://apiocds.colombiacompra.gov.co",
        "releases_endpoint": "/releases",
        "packages_endpoint": "/packages",
        "rate_limit": 1.0,
        "docs": "https://www.colombiacompra.gov.co/datos-abiertos"
    },
    "uk": {
        "name": "Contracts Finder",
        "base_url": "https://www.contractsfinder.service.gov.uk/Published",
        "notices_endpoint": "/Notices/OCDS/Search",
        "rate_limit": 0.5,
        "docs": "https://www.contractsfinder.service.gov.uk/apidocumentation/home"
    }
}


def get_session(retries: int = 3, backoff_factor: float = 0.3) -> requests.Session:
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(500, 502, 503, 504),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


class OCDSDownloader:
    """Base class for OCDS data downloaders."""
    
    def __init__(self, country: str, output_dir: Optional[Path] = None):
        self.country = country.lower()
        self.config = APIS.get(self.country)
        if not self.config:
            raise ValueError(f"Unknown country: {country}. Available: {list(APIS.keys())}")
        
        self.output_dir = output_dir or DATA_DIR / self.country.capitalize()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = get_session()
        self.rate_limit = self.config.get("rate_limit", 1.0)
        
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make an API request with rate limiting."""
        import time
        time.sleep(self.rate_limit)
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def _save_releases(self, releases: List[Dict], filename: str):
        """Save OCDS releases to compressed JSON."""
        filepath = self.output_dir / f"{filename}.json.gz"
        with gzip.open(filepath, 'wt', encoding='utf-8') as f:
            json.dump(releases, f, ensure_ascii=False)
        logger.info(f"Saved {len(releases)} releases to {filepath}")
        return filepath
    
    def download(self, start_date: str, end_date: str) -> List[Path]:
        """Download OCDS data for date range. Override in subclasses."""
        raise NotImplementedError


class UkraineDownloader(OCDSDownloader):
    """Download OCDS data from Ukraine ProZorro."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        super().__init__("ukraine", output_dir)
        
    def get_tender_ids(self, offset: str = "") -> Iterator[Dict]:
        """Stream tender IDs from ProZorro API."""
        url = f"{self.config['base_url']}/tenders"
        params = {"offset": offset, "limit": 100, "opt_fields": "dateModified"}
        
        while True:
            data = self._make_request(url, params)
            tenders = data.get("data", [])
            if not tenders:
                break
                
            for tender in tenders:
                yield tender
                
            # Get next page offset
            params["offset"] = data.get("next_page", {}).get("offset", "")
            if not params["offset"]:
                break
    
    def get_tender_detail(self, tender_id: str) -> Dict:
        """Get full tender details."""
        url = f"{self.config['base_url']}/tenders/{tender_id}"
        return self._make_request(url)
    
    def download(self, start_date: str, end_date: str, max_tenders: int = 10000) -> List[Path]:
        """Download tenders for date range."""
        logger.info(f"Downloading Ukraine ProZorro data from {start_date} to {end_date}")
        
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        releases = []
        saved_files = []
        
        for tender in tqdm(self.get_tender_ids(), desc="Fetching tenders"):
            if len(releases) >= max_tenders:
                break
                
            date_modified = tender.get("dateModified", "")
            if date_modified:
                tender_date = datetime.fromisoformat(date_modified.replace("Z", "+00:00"))
                if tender_date.date() < start.date():
                    continue
                if tender_date.date() > end.date():
                    continue
            
            # Get full tender details
            try:
                detail = self.get_tender_detail(tender["id"])
                releases.append(detail.get("data", {}))
            except Exception as e:
                logger.warning(f"Failed to fetch tender {tender['id']}: {e}")
                continue
            
            # Save in batches
            if len(releases) >= 1000:
                filename = f"prozorro_{start_date}_{len(saved_files):04d}"
                saved_files.append(self._save_releases(releases, filename))
                releases = []
        
        # Save remaining
        if releases:
            filename = f"prozorro_{start_date}_{len(saved_files):04d}"
            saved_files.append(self._save_releases(releases, filename))
        
        return saved_files


class ColombiaDownloader(OCDSDownloader):
    """Download OCDS data from Colombia SECOP."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        super().__init__("colombia", output_dir)
        
    def download_bulk_packages(self, year: int) -> List[Path]:
        """Download bulk OCDS packages from data.open-contracting.org."""
        # Colombia provides yearly bulk downloads
        bulk_url = f"https://data.open-contracting.org/publication/colombia/{year}/releases.json.gz"
        
        logger.info(f"Downloading Colombia SECOP bulk package for {year}")
        
        filepath = self.output_dir / f"secop_{year}_releases.json.gz"
        
        response = self.session.get(bulk_url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        with open(filepath, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc=f"SECOP {year}") as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    pbar.update(len(chunk))
        
        return [filepath]
    
    def download(self, start_date: str, end_date: str) -> List[Path]:
        """Download OCDS data for date range."""
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])
        
        saved_files = []
        for year in range(start_year, end_year + 1):
            try:
                files = self.download_bulk_packages(year)
                saved_files.extend(files)
            except Exception as e:
                logger.warning(f"Failed to download Colombia {year}: {e}")
        
        return saved_files


class UKDownloader(OCDSDownloader):
    """Download OCDS data from UK Contracts Finder."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        super().__init__("uk", output_dir)
        
    def search_notices(
        self, 
        published_from: str, 
        published_to: str,
        page: int = 1,
        size: int = 100
    ) -> Dict:
        """Search notices via Contracts Finder API."""
        url = f"{self.config['base_url']}/Notices/OCDS/Search"
        params = {
            "publishedFrom": published_from,
            "publishedTo": published_to,
            "page": page,
            "size": size,
            "orderBy": "publishedDate",
            "order": "asc"
        }
        return self._make_request(url, params)
    
    def download(self, start_date: str, end_date: str) -> List[Path]:
        """Download OCDS notices for date range."""
        logger.info(f"Downloading UK Contracts Finder data from {start_date} to {end_date}")
        
        releases = []
        saved_files = []
        page = 1
        
        while True:
            try:
                result = self.search_notices(start_date, end_date, page=page)
                notices = result.get("releases", [])
                
                if not notices:
                    break
                    
                releases.extend(notices)
                logger.info(f"Fetched page {page}, total releases: {len(releases)}")
                
                # Check if more pages
                total_pages = result.get("totalPages", 1)
                if page >= total_pages:
                    break
                    
                page += 1
                
            except Exception as e:
                logger.warning(f"Failed to fetch page {page}: {e}")
                break
            
            # Save in batches
            if len(releases) >= 5000:
                filename = f"contracts_finder_{start_date}_{len(saved_files):04d}"
                saved_files.append(self._save_releases(releases, filename))
                releases = []
        
        # Save remaining
        if releases:
            filename = f"contracts_finder_{start_date}_{len(saved_files):04d}"
            saved_files.append(self._save_releases(releases, filename))
        
        return saved_files


def download_reference_data(output_dir: Optional[Path] = None):
    """Download reference data (CPV codes, exchange rates, etc.)."""
    ref_dir = output_dir or DATA_DIR / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    
    session = get_session()
    
    # CPV codes (EU Common Procurement Vocabulary)
    cpv_url = "https://simap.ted.europa.eu/cpv"
    logger.info("Note: CPV codes should be downloaded manually from TED")
    
    # Exchange rates from FRED / World Bank
    # This is a placeholder - actual implementation would use APIs
    logger.info("Exchange rates: Use World Bank WDI or FRED APIs")
    
    # Threshold data
    thresholds = {
        "ukraine": {
            "goods_services": {"UAH": 200000, "effective_date": "2020-04-19"},
            "works": {"UAH": 1500000, "effective_date": "2020-04-19"},
            "eu_threshold": {"EUR": 133000, "effective_date": "2022-01-01"}
        },
        "colombia": {
            "direct_purchase_smmlv": 28,
            "minor_contract_smmlv": 280,
            "open_tender_smmlv": 1000,
            "smmlv_2024": 1160000  # COP
        },
        "uk": {
            "below_threshold_gbp": 12000,
            "pcr2015_works_gbp": 5336937,
            "pcr2015_other_gbp": 213477,
            "effective_date": "2024-01-01"
        }
    }
    
    with open(ref_dir / "thresholds.json", "w") as f:
        json.dump(thresholds, f, indent=2)
    
    logger.info(f"Saved threshold data to {ref_dir / 'thresholds.json'}")


def main():
    """Main entry point for data acquisition."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Download OCDS procurement data")
    parser.add_argument(
        "--country", 
        choices=["ukraine", "colombia", "uk", "all"],
        default="all",
        help="Country to download data from"
    )
    parser.add_argument(
        "--years",
        default="2020-2024",
        help="Year range (e.g., 2020-2024)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DATA_DIR,
        help="Output directory"
    )
    parser.add_argument(
        "--reference-only",
        action="store_true",
        help="Only download reference data"
    )
    
    args = parser.parse_args()
    
    # Download reference data
    download_reference_data(args.output / "reference")
    
    if args.reference_only:
        return
    
    # Parse year range
    years = args.years.split("-")
    start_date = f"{years[0]}-01-01"
    end_date = f"{years[-1]}-12-31"
    
    # Download by country
    countries = ["ukraine", "colombia", "uk"] if args.country == "all" else [args.country]
    
    downloaders = {
        "ukraine": UkraineDownloader,
        "colombia": ColombiaDownloader,
        "uk": UKDownloader
    }
    
    for country in countries:
        logger.info(f"\n{'='*60}")
        logger.info(f"Downloading {country.upper()} procurement data")
        logger.info(f"{'='*60}")
        
        try:
            downloader = downloaders[country](args.output / country.capitalize())
            files = downloader.download(start_date, end_date)
            logger.info(f"Downloaded {len(files)} files for {country}")
        except Exception as e:
            logger.error(f"Failed to download {country}: {e}")


if __name__ == "__main__":
    main()
