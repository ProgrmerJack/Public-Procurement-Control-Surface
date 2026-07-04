# Reproducing the Data Descriptor

Reproduction guide for the *Scientific Data* Data Descriptor **"Recovered TED bidder counts and
full-bid-set eForms tenderers for European public procurement."**

- **Deposit (data + code):** Zenodo concept DOI [10.5281/zenodo.19456216](https://doi.org/10.5281/zenodo.19456216)
  → latest version [10.5281/zenodo.21176249](https://doi.org/10.5281/zenodo.21176249). Data CC-BY 4.0; code MIT.
- **Claim provenance:** every quantitative claim is traced in
  [`Scientific_Data_Descriptor/CLAIMS_INDEX.md`](Scientific_Data_Descriptor/CLAIMS_INDEX.md).

## 1. Environment

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows (use bin/activate on Linux/Mac)
pip install -r requirements.txt                    # needs pandas, pyarrow, duckdb, numpy, scipy, matplotlib
```

## 2. Get the deposited data

Download the nine files from Zenodo (10.5281/zenodo.21176249) into `deposit/`, **or** rebuild the
flagship contract file from the raw TED contract-award-notice (CAN) parquet layer:

```bash
python scripts/descriptor/build_contract_file.py   # -> deposit/procurement_awards_2012_2023.parquet
```

`build_contract_file.py` unions the yearly CAN files, de-duplicates on `notice_id × award_id`, dates
each award by dispatch date, attaches the CPV→EXIOBASE carbon weight, and merges the flagged non-TED
sources — eliminating the 2018 ingestion vintage by construction and adding `winner_name`,
`winner_country`, `is_framework`, and a null-safe `single_bidder`.

## 3. Rebuild panel, tables, figures

```bash
python scripts/descriptor/build_partA_panel.py     # panel + validation stats -> results/descriptor/
python scripts/descriptor/si_make_tables.py        # SI tables -> Scientific_Data_Descriptor/si_tables/
python scripts/descriptor/make_figures.py          # figures -> Scientific_Data_Descriptor/figures/
```

## 4. Verify every claim

```bash
python scripts/descriptor/verify_claims.py         # recomputes 41 claims from the deposit -> 41/41 PASS
```

## 5. Build the PDFs

```bash
cd Scientific_Data_Descriptor
pdflatex descriptor.tex && pdflatex descriptor.tex
pdflatex supplementary_information.tex && pdflatex supplementary_information.tex
```

## Key scripts

| Purpose | Script |
|---|---|
| Streaming raw-TED extraction + schema map | `scripts/pipeline/ted_bulk_stream_extract.py` |
| Rebuild flagship contract file from raw CAN | `scripts/descriptor/build_contract_file.py` |
| Part A panel + validation | `scripts/descriptor/build_partA_panel.py` |
| eForms full-bid-set extraction | `scripts/eforms_competition/extract_eforms_bids.py` |
| Carbon validation vs Eurostat | `scripts/within_sector/exiobase_eurostat_validation_v2.py` |
| Claim verification (41/41) | `scripts/descriptor/verify_claims.py` |
| Zenodo deposit | `scripts/zenodo/zenodo_stage_deposit.py` |

> Folders under `scripts/causal_id/`, `scripts/dead_zones/`, and similar implement earlier,
> superseded causal analyses; they are not part of the deposited resource.
