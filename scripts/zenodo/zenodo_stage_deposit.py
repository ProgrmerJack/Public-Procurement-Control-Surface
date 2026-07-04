"""
Stage a NEW VERSION of the Zenodo concept record 19456216 so the named Data
Descriptor files are individually downloadable (replacing the 12.7 GB Data.zip
bundle of the current version). Reads the token from .env (ZENODO_API_TOKEN).

Steps (all reversible up to publish):
  1. create a new version draft from the latest published version;
  2. remove the inherited bundled files from the draft;
  3. upload the 9 named manifest files from Scientific_Data_Descriptor/deposit/;
  4. set clean dataset metadata.

Publishing (irreversible, mints the version DOI, makes it public) is performed
ONLY if you pass --publish AND set ZENODO_PUBLISH=yes. Default: stop before publish.

Usage:
  python zenodo_stage_deposit.py            # create draft + upload, no publish
  python zenodo_stage_deposit.py --publish  # also publish (requires ZENODO_PUBLISH=yes)
"""
import os, sys, json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[2]
DEPOSIT = ROOT / "deposit"
BASE = "https://zenodo.org/api"
PARENT_RECID = "20823936"   # current published latest version (concept 19456216)
PUBLISH = ("--publish" in sys.argv) and (os.environ.get("ZENODO_PUBLISH") == "yes")

TITLE = ("Recovered TED bidder counts and full-bid-set eForms tenderers for European public "
         "procurement")
DESCRIPTION = (
    "<p>Two-part open resource accompanying the <i>Scientific Data</i> Data Descriptor. "
    "<b>Part A</b>: a contract-level EU public-procurement competition-carbon dataset "
    "(16.97M de-duplicated, carbon-mapped contracts; 33 territories) rebuilt directly from the raw "
    "TED contract-award-notice files. Rebuilding from source eliminates a 2018 ingestion artifact "
    "(~25x inflation) present in processed extracts and recovers the offers-received count across "
    "a 2018 schema field-rename. Includes a deterministically rebuilt country x CPV x month "
    "single-bidder/competition panel (2017-2020), a source-verified winner name, a CPV-EXIOBASE "
    "carbon weight validated against Eurostat (Spearman rho=0.82), Directive 2014/24 transposition "
    "dates, and an EU-ETS emitter crosswalk. <b>Part B</b>: among the first publicly released "
    "EU-wide full-bid-set corpora parsed from eForms (302,555 single-award notices, 2024-2025) "
    "giving the complete ranked tenderer set per award, plus a pre-registered worked example "
    "(protocol + verdict). Each file is an individually downloadable object. See DEPOSIT_README.md "
    "for the full manifest and dictionary.</p>")

FILES = [
    "procurement_awards_2012_2023.parquet",
    "competition_panel_country_cpv_month.parquet",
    "cpv_exiobase_crosswalk.csv",
    "transposition_dates.csv",
    "eutl_matched_firms.csv",
    "eforms_bids_2024_2025.jsonl",
    "PREREGISTRATION.md",
    "BATTERY_VERDICT.json",
    "DEPOSIT_README.md",
]

METADATA = {
    "metadata": {
        "title": TITLE,
        "upload_type": "dataset",
        "description": DESCRIPTION,
        "creators": [{"name": "Ashuraliyev, Abduxoliq", "orcid": "0009-0003-5482-5526",
                      "affiliation": "Independent Researcher, Tashkent, Uzbekistan"}],
        "license": "cc-by-4.0",
        "access_right": "open",
        "keywords": ["public procurement", "Tenders Electronic Daily", "eForms", "single bidding",
                     "competition", "EXIOBASE", "carbon intensity", "green public procurement",
                     "full bid set", "open contracting"],
    }
}


def token():
    for line in open(ROOT / ".env"):
        if line.startswith("ZENODO_API_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("ZENODO_API_TOKEN not found in .env")


def main():
    H = {"Authorization": f"Bearer {token()}"}
    for f in FILES:
        if not (DEPOSIT / f).exists():
            raise SystemExit(f"missing deposit file: {f}")

    # 1. new version draft (idempotent: reuse an existing unpublished draft if present)
    parent = requests.get(f"{BASE}/deposit/depositions/{PARENT_RECID}", headers=H, timeout=60).json()
    r = requests.post(parent["links"]["newversion"], headers=H, timeout=120)
    r.raise_for_status()
    draft_url = r.json()["links"]["latest_draft"]
    draft = requests.get(draft_url, headers=H, timeout=60).json()
    did = draft["id"]
    print(f"new version draft id={did}  doi(reserved)={draft.get('doi') or draft['metadata'].get('prereserve_doi',{}).get('doi')}")

    # 2. remove inherited files
    for f in draft.get("files", []):
        fid = f.get("id")
        dr = requests.delete(f"{BASE}/deposit/depositions/{did}/files/{fid}", headers=H, timeout=120)
        print(f"  removed inherited {f.get('filename')}: {dr.status_code}")

    # 3. upload named files to the bucket
    bucket = draft["links"]["bucket"]
    for f in FILES:
        p = DEPOSIT / f
        with open(p, "rb") as fh:
            up = requests.put(f"{bucket}/{f}", headers=H, data=fh, timeout=3600)
        print(f"  uploaded {f} ({p.stat().st_size:,} B): {up.status_code}")
        up.raise_for_status()

    # 4. metadata
    mr = requests.put(f"{BASE}/deposit/depositions/{did}", headers={**H, "Content-Type": "application/json"},
                      data=json.dumps(METADATA), timeout=60)
    print("  metadata update:", mr.status_code)
    mr.raise_for_status()

    draft = requests.get(draft_url, headers=H, timeout=60).json()
    print("\n=== DRAFT READY (NOT published) ===")
    print("draft id:", did)
    print("draft page:", draft["links"].get("html"))
    print("reserved version DOI:", draft["metadata"].get("prereserve_doi", {}).get("doi"))
    print("files in draft:", [f["filename"] for f in draft.get("files", [])])

    if PUBLISH:
        pr = requests.post(draft["links"]["publish"], headers=H, timeout=120)
        pr.raise_for_status()
        print("\nPUBLISHED. version DOI:", pr.json().get("doi"))
    else:
        print("\nNOT publishing (no --publish / ZENODO_PUBLISH!=yes). "
              "Review the draft, then publish from the Zenodo UI or rerun with --publish.")


if __name__ == "__main__":
    main()
