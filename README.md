# Recovered TED bidder counts and full-bid-set eForms tenderers for European public procurement

[![DOI](https://img.shields.io/badge/Zenodo-10.5281%2Fzenodo.21176249-blue.svg)](https://doi.org/10.5281/zenodo.21176249)
[![License: MIT](https://img.shields.io/badge/Code-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![License: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

Data and code for the *Scientific Data* Data Descriptor:

> **Recovered TED bidder counts and full-bid-set eForms tenderers for European public procurement.**
> Ashuraliyev, A. (2026).

The resource addresses a single measurement problem — observing who competes for public contracts —
across two generations of EU procurement reporting:

- **Part A** — a contract-level competition + carbon dataset rebuilt directly from the raw TED
  contract-award-notice files (16.97M de-duplicated, carbon-mapped contracts across 33 territories;
  8.18M TED awards plus flagged non-TED sources). Rebuilding from source eliminates a 2018 ingestion
  artifact and recovers the bidder count across a schema field-rename; includes a deterministic
  country×CPV×month single-bidding panel (2017–2020), a CPV→EXIOBASE carbon weight validated against
  Eurostat (ρ=0.82), a source-verified winner name, and Directive 2014/24 transposition dates.
- **Part B** — a full-bid-set eForms corpus (302,555 single-award notices, 2024–2025) giving the
  complete ranked tenderer set per award.

## Repository layout

| Path | Contents |
|---|---|
| [`Scientific_Data_Descriptor/`](Scientific_Data_Descriptor/) | The manuscript (`descriptor.tex`), Supplementary Information, cover letter, figures, claims index, deposit files, and descriptor-specific scripts |
| [`scripts/`](scripts/) | Data-pipeline and analysis code (acquisition, parsing, carbon linkage, eForms extraction, validation) |
| [`results/`](results/) | Computed result files (JSON/CSV) consumed by the descriptor |
| [`Data/`](Data/) | Source and processed data (large files gitignored; available from Zenodo) |
| [`docs/`](docs/) | Documentation — data catalogue, data-source audit, schema, API, contributing |
| [`workflow/`](workflow/) | Snakemake pipeline (`Snakefile`, `rules/`) |
| [`config/`](config/) | Pipeline configuration |
| [`tests/`](tests/) | Test suite |
| [`archive/`](archive/) | Superseded earlier analyses, retained for provenance only |

## Data and code availability

- **Deposit (data + code):** Zenodo version DOI **[10.5281/zenodo.21176249](https://doi.org/10.5281/zenodo.21176249)**
  (concept DOI 10.5281/zenodo.19456216, resolves to the latest version). Data CC-BY 4.0; code MIT.
- **Repository:** https://github.com/ProgrmerJack/Public-Procurement-Control-Surface
- **Reproduction:** see [`REPRODUCE_SCIENTIFIC_DATA.md`](REPRODUCE_SCIENTIFIC_DATA.md).

### Deposited files (Zenodo 10.5281/zenodo.21176249)

| File | Part | Rows | Description |
|---|---|---|---|
| `procurement_awards_2012_2023.parquet` | A | 16.97M | Contract-level competition + carbon records (TED 8.18M + SECOP 7.97M + Contracts Finder 0.82M), 33 territories |
| `competition_panel_country_cpv_month.parquet` | A | 44,998 | Rebuilt single-bidder / ≥3-offer shares by country×CPV×month, 2017–2020 |
| `cpv_exiobase_crosswalk.csv` | A | 40 | CPV→EXIOBASE carbon-weight map |
| `transposition_dates.csv` | A | 25 | Directive 2014/24 national entry-into-force months |
| `eutl_matched_firms.csv` | A | 1,105 | Procurement-winner ↔ EU-ETS emitter matched cells |
| `eforms_bids_2024_2025.jsonl` | B | 302,555 | Full ranked bid set per single-award eForms notice |
| `PREREGISTRATION.md`, `BATTERY_VERDICT.json` | B | — | Worked-example protocol + verdict |
| `DEPOSIT_README.md` | — | — | Manifest, full data dictionary, provenance, validation |

## Quick start

```bash
pip install -r requirements.txt

# Rebuild the deposit, build figures, and verify every claim against the deposited data
python scripts/descriptor/build_contract_file.py # rebuild flagship contract file from raw CAN
python scripts/descriptor/build_partA_panel.py   # Part A panel + validation stats
python scripts/descriptor/si_make_tables.py      # SI tables from deposited data
python scripts/descriptor/make_figures.py        # figures
python scripts/descriptor/verify_claims.py       # claim-by-claim verification (PASS/FAIL)
```

Every quantitative claim is traced to its source in
[`Scientific_Data_Descriptor/CLAIMS_INDEX.md`](Scientific_Data_Descriptor/CLAIMS_INDEX.md).
See [`docs/reproduction.md`](docs/reproduction.md) for the full reproduction guide.

## Citation

```bibtex
@misc{ashuraliyev2026procurement,
  author = {Ashuraliyev, Abduxoliq},
  title  = {Recovered TED bidder counts and full-bid-set eForms tenderers for European public procurement},
  year   = {2026},
  doi    = {10.5281/zenodo.21176249},
  note   = {Data CC-BY 4.0; code MIT}
}
```

## License

Code: MIT. Data: CC-BY 4.0.
