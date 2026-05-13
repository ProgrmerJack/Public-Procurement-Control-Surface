"""
Download US federal procurement microdata from USASpending.gov.

Approach 1: Bulk Download API - request contract data with specific columns
Approach 2: Award Data Archive - pre-built full-year contract files
Approach 3: Spending by Award API - paginated search for smaller samples

Target fields: contract value, number of offers/bidders, product/service code,
award date, contracting agency.
"""

import json
import os
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

OUTPUT_DIR = Path(r"C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\raw\us_fpds")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_API = "https://api.usaspending.gov/api/v2"
SESSION = requests.Session()
SESSION.headers.update({"Content-Type": "application/json"})


# ── Approach 1: Bulk Download API ───────────────────────────────────────────

def try_bulk_download_api(fiscal_year: int = 2024) -> Path | None:
    """Request a bulk download of contract awards for a fiscal year."""
    url = f"{BASE_API}/bulk_download/awards/"

    # Use prime_award_types for contract subtypes
    payload = {
        "filters": {
            "prime_award_types": ["A", "B", "C", "D"],
            "date_type": "action_date",
            "date_range": {
                "start_date": f"{fiscal_year - 1}-10-01",
                "end_date": f"{fiscal_year}-09-30",
            },
        },
        "columns": [],
        "file_format": "csv",
    }

    print(f"[Approach 1] Requesting bulk download for FY{fiscal_year} contracts...")
    try:
        resp = SESSION.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        print(f"  Response: {json.dumps(data, indent=2)[:500]}")

        # The response should contain a status_url or file_url
        file_url = data.get("file_url")
        status_url = data.get("status_url")

        if status_url:
            file_url = poll_status(status_url)

        if file_url:
            return download_file(file_url, OUTPUT_DIR / f"FY{fiscal_year}_contracts_bulk.zip")

    except Exception as e:
        print(f"  Bulk download API failed: {e}")

    return None


def poll_status(status_url: str, max_wait: int = 600) -> str | None:
    """Poll a status URL until the file is ready."""
    print(f"  Polling status: {status_url}")
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = SESSION.get(status_url, timeout=30)
            data = resp.json()
            status = data.get("status", "unknown")
            print(f"  Status: {status} (elapsed: {int(time.time() - start)}s)")

            if status == "finished":
                return data.get("file_url")
            elif status == "failed":
                print(f"  Download job failed: {data}")
                return None

            time.sleep(10)
        except Exception as e:
            print(f"  Poll error: {e}")
            time.sleep(10)

    print("  Timed out waiting for download.")
    return None


# ── Approach 2: Award Data Archive (pre-built files) ───────────────────────

def try_award_data_archive(fiscal_year: int = 2024) -> Path | None:
    """Download pre-built award data archive for a fiscal year."""
    # Try different URL patterns
    urls = [
        f"https://files.usaspending.gov/award_data_archive/FY{fiscal_year}_All_Contracts_Full_{fiscal_year}0930.zip",
        f"https://files.usaspending.gov/award_data_archive/FY{fiscal_year}_All_Contracts_Full.zip",
        f"https://files.usaspending.gov/award_data_archive/FY{fiscal_year}_Contracts_Full_{fiscal_year}0930.zip",
    ]

    for url in urls:
        print(f"[Approach 2] Trying archive URL: {url}")
        try:
            resp = SESSION.head(url, timeout=30, allow_redirects=True)
            if resp.status_code == 200:
                content_length = resp.headers.get("Content-Length", "unknown")
                print(f"  File found! Size: {content_length} bytes")

                # Only download if under 2GB
                if content_length != "unknown" and int(content_length) > 2_000_000_000:
                    print(f"  File too large ({int(content_length) / 1e9:.1f} GB), skipping.")
                    continue

                return download_file(url, OUTPUT_DIR / f"FY{fiscal_year}_All_Contracts_Full.zip")
            else:
                print(f"  HTTP {resp.status_code}")
        except Exception as e:
            print(f"  Failed: {e}")

    return None


# ── Approach 2b: Try to find the actual archive URL from the page ──────────

def discover_archive_urls() -> list[str]:
    """Scrape the award data archive page for actual download URLs."""
    print("[Approach 2b] Discovering archive URLs from USASpending.gov...")
    try:
        # Try the API that backs the download center
        url = f"{BASE_API}/bulk_download/list_monthly_files/"
        payload = {
            "fiscal_year": 2024,
            "type": "Contracts",
            "agency": "all",
        }
        resp = SESSION.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Found monthly files response: {json.dumps(data, indent=2)[:800]}")
            urls = []
            for item in data.get("monthly_files", []):
                if "url" in item:
                    urls.append(item["url"])
            return urls
    except Exception as e:
        print(f"  Discovery failed: {e}")
    return []


# ── Approach 3: Spending by Award API (paginated, for smaller samples) ─────

def try_spending_by_award_api(fiscal_year: int = 2024, max_pages: int = 50) -> Path | None:
    """
    Use the award search API to get contract data with bidder counts.
    This is paginated and slower but gives us direct access to fields.
    """
    url = f"{BASE_API}/search/spending_by_award/"
    all_records = []

    print(f"[Approach 3] Fetching contracts via spending_by_award API for FY{fiscal_year}...")

    # Fetch page by page
    for page in range(1, max_pages + 1):
        payload = {
            "filters": {
                "award_type_codes": ["A", "B", "C", "D"],
                "time_period": [
                    {
                        "start_date": f"{fiscal_year - 1}-10-01",
                        "end_date": f"{fiscal_year}-09-30",
                    }
                ],
            },
            "fields": [
                "Award ID",
                "Recipient Name",
                "Start Date",
                "End Date",
                "Award Amount",
                "Total Outlays",
                "Awarding Agency",
                "Awarding Sub Agency",
                "Award Type",
                "Contract Award Type",
                "internal_id",
                "generated_internal_id",
            ],
            "page": page,
            "limit": 100,
            "sort": "Award Amount",
            "order": "desc",
            "subawards": False,
        }

        try:
            resp = SESSION.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            if not results:
                print(f"  No more results at page {page}.")
                break

            all_records.extend(results)

            if page == 1:
                print(f"  Total hits: {data.get('page_metadata', {}).get('total', '?')}")
                print(f"  Sample record: {json.dumps(results[0], indent=2)[:400]}")

            if page % 10 == 0:
                print(f"  Page {page}: {len(all_records)} records so far...")

            # Check if we have all pages
            has_next = data.get("page_metadata", {}).get("hasNext", False)
            if not has_next:
                break

            time.sleep(0.5)  # rate limit courtesy
        except Exception as e:
            print(f"  Error on page {page}: {e}")
            break

    if all_records:
        df = pd.DataFrame(all_records)
        out_path = OUTPUT_DIR / f"FY{fiscal_year}_contracts_api_sample.csv"
        df.to_csv(out_path, index=False)
        print(f"  Saved {len(df)} records to {out_path}")
        return out_path

    return None


# ── Approach 4: Award detail API for bidder count info ──────────────────────

def enrich_with_bidder_counts(csv_path: Path, max_records: int = 200) -> Path | None:
    """
    For each award, fetch the detail page to get number_of_offers_received.
    Uses /api/v2/awards/{generated_internal_id}/ endpoint.
    """
    print("[Approach 4] Enriching records with bidder count data...")
    df = pd.read_csv(csv_path)

    if "generated_internal_id" not in df.columns:
        print("  No generated_internal_id column to look up details.")
        return None

    bidder_counts = []
    psc_codes = []
    naics_codes = []

    for idx, row in df.head(max_records).iterrows():
        award_id = row["generated_internal_id"]
        try:
            url = f"{BASE_API}/awards/{award_id}/"
            resp = SESSION.get(url, timeout=30)
            if resp.status_code == 200:
                detail = resp.json()
                exec_data = detail.get("latest_transaction_contract_data", {}) or {}
                bidder_counts.append(exec_data.get("number_of_offers_received"))
                psc_code = detail.get("psc_hierarchy", {})
                psc_codes.append(
                    psc_code.get("base_code", {}).get("code") if psc_code else None
                )
                naics = detail.get("naics_hierarchy", {})
                naics_codes.append(
                    naics.get("toptier_code", {}).get("code") if naics else None
                )

                if idx == 0:
                    # Print a sample to show available fields
                    print(f"  Sample contract detail fields: {list(detail.keys())}")
                    print(
                        f"  number_of_offers_received: "
                        f"{exec_data.get('number_of_offers_received')}"
                    )
            else:
                bidder_counts.append(None)
                psc_codes.append(None)
                naics_codes.append(None)

            if (idx + 1) % 20 == 0:
                print(f"  Enriched {idx + 1}/{min(len(df), max_records)} records...")

            time.sleep(0.3)
        except Exception as e:
            bidder_counts.append(None)
            psc_codes.append(None)
            naics_codes.append(None)

    # Add columns (only for the rows we enriched)
    enriched = df.head(max_records).copy()
    enriched["number_of_offers_received"] = bidder_counts
    enriched["psc_code"] = psc_codes
    enriched["naics_code"] = naics_codes

    out_path = OUTPUT_DIR / csv_path.stem.replace("_sample", "_enriched") + ".csv"
    enriched.to_csv(out_path, index=False)
    print(f"  Saved enriched data to {out_path}")
    return out_path


# ── Approach 5: FPDS ATOM Feed for direct download with all fields ─────────

def try_fpds_atom_feed(fiscal_year: int = 2024, max_records: int = 5000) -> Path | None:
    """
    Try FPDS ATOM feed for direct access to contract data with all fields.
    """
    print(f"[Approach 5] Trying FPDS ATOM feed for FY{fiscal_year}...")
    base_url = "https://www.fpds.gov/ezsearch/LATEST/runSearch"
    params = {
        "indexName": "awardfull",
        "templateName": "1.5.3",
        "s": f"SIGNED_DATE:[{fiscal_year - 1}/10/01,{fiscal_year}/09/30]",
        "q": "",
        "feed": "",
    }
    try:
        resp = SESSION.get(base_url, params=params, timeout=30)
        print(f"  FPDS response status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  Content type: {resp.headers.get('Content-Type', 'unknown')}")
            print(f"  First 500 chars: {resp.text[:500]}")
    except Exception as e:
        print(f"  FPDS ATOM feed failed: {e}")
    return None


def download_file(url: str, dest: Path) -> Path:
    """Download a file with progress reporting."""
    print(f"  Downloading {url}...")
    print(f"  Saving to {dest}")

    resp = SESSION.get(url, stream=True, timeout=300)
    resp.raise_for_status()

    total = int(resp.headers.get("Content-Length", 0))
    downloaded = 0

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0 and downloaded % (50 * 1024 * 1024) == 0:
                print(f"  Progress: {downloaded / 1e6:.0f} / {total / 1e6:.0f} MB")

    print(f"  Downloaded: {dest} ({downloaded / 1e6:.1f} MB)")

    # Extract if ZIP
    if dest.suffix == ".zip":
        extract_dir = dest.parent / dest.stem
        extract_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Extracting to {extract_dir}...")
        with zipfile.ZipFile(dest, "r") as zf:
            zf.extractall(extract_dir)
            print(f"  Extracted files: {zf.namelist()[:10]}")
        return extract_dir

    return dest


def inspect_data(path: Path):
    """Inspect downloaded data for key fields."""
    print(f"\n{'='*60}")
    print(f"INSPECTING DATA: {path}")
    print(f"{'='*60}")

    csv_files = list(path.rglob("*.csv")) if path.is_dir() else [path]
    if not csv_files:
        print("  No CSV files found.")
        return

    for csv_file in csv_files[:3]:
        print(f"\n  File: {csv_file.name}")
        try:
            df = pd.read_csv(csv_file, nrows=100, low_memory=False)
            print(f"  Shape (first 100 rows): {df.shape}")
            print(f"  Columns ({len(df.columns)}): {list(df.columns)}")

            # Look for bidder/offer columns
            bidder_cols = [
                c
                for c in df.columns
                if any(
                    kw in c.lower()
                    for kw in ["offer", "bidder", "bid", "compete", "solicitation"]
                )
            ]
            if bidder_cols:
                print(f"\n  *** BIDDER/OFFER COLUMNS FOUND: {bidder_cols} ***")
                for col in bidder_cols:
                    print(f"    {col}: {df[col].value_counts().head(10).to_dict()}")
            else:
                print("  No bidder/offer columns found in this file.")

            # Look for value columns
            value_cols = [
                c
                for c in df.columns
                if any(
                    kw in c.lower()
                    for kw in ["amount", "value", "price", "obligat", "dollar"]
                )
            ]
            if value_cols:
                print(f"  Value columns: {value_cols[:5]}")

            # Look for PSC/NAICS columns
            code_cols = [
                c
                for c in df.columns
                if any(kw in c.lower() for kw in ["psc", "naics", "product", "service_code"])
            ]
            if code_cols:
                print(f"  Product/Service code columns: {code_cols[:5]}")

            # Look for agency columns
            agency_cols = [
                c for c in df.columns if any(kw in c.lower() for kw in ["agency", "department"])
            ]
            if agency_cols:
                print(f"  Agency columns: {agency_cols[:5]}")

            # Show sample
            print(f"\n  First 3 rows (key columns):")
            key_cols = bidder_cols + value_cols[:2] + code_cols[:2] + agency_cols[:2]
            if key_cols:
                print(df[key_cols].head(3).to_string())

        except Exception as e:
            print(f"  Error reading {csv_file}: {e}")


def main():
    print("=" * 70)
    print("US FEDERAL PROCUREMENT DATA DOWNLOAD")
    print("Source: USASpending.gov / FPDS")
    print("=" * 70)

    result = None

    # Approach 1: Bulk Download API
    result = try_bulk_download_api(fiscal_year=2024)
    if result:
        inspect_data(result)
        return

    # Approach 2: Award Data Archive (pre-built files)
    result = try_award_data_archive(fiscal_year=2024)
    if result:
        inspect_data(result)
        return

    # Approach 2b: Discover archive URLs
    archive_urls = discover_archive_urls()
    if archive_urls:
        print(f"  Found {len(archive_urls)} archive URLs")
        for url in archive_urls[:3]:
            try:
                dest = OUTPUT_DIR / url.split("/")[-1]
                result = download_file(url, dest)
                if result:
                    inspect_data(result)
                    return
            except Exception as e:
                print(f"  Failed: {e}")

    # Try FY2023 if 2024 not available
    result = try_award_data_archive(fiscal_year=2023)
    if result:
        inspect_data(result)
        return

    # Approach 3: API sample
    result = try_spending_by_award_api(fiscal_year=2024, max_pages=50)
    if result:
        inspect_data(result)
        # Try to enrich with bidder counts
        enriched = enrich_with_bidder_counts(result, max_records=200)
        if enriched:
            inspect_data(enriched)
        return

    # Approach 5: FPDS ATOM feed
    try_fpds_atom_feed(fiscal_year=2024)

    print("\nAll approaches attempted. Check output above for results.")


if __name__ == "__main__":
    main()
