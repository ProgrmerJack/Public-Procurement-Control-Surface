# A harmonised EU public-procurement competition resource

[![DOI](https://img.shields.io/badge/Zenodo-10.5281%2Fzenodo.20823936-blue.svg)](https://doi.org/10.5281/zenodo.20823936)
[![License: MIT](https://img.shields.io/badge/Code-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![License: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

Data and code for the *Scientific Data* Data Descriptor:

> **A harmonised EU public-procurement competition resource: a raw-TED competition–carbon panel
> (2012–2023) with recovered bidder counts, and a full-bid-set tender corpus from eForms (2024–2025).**
> Ashuraliyev, A. (2026).

The resource addresses a single measurement problem — observing who competes for public contracts —
across two generations of EU procurement reporting:

- **Part A** — a contract-level competition + carbon panel rebuilt from the harmonised TED
  contract-award-notice layer (21.6M carbon-mapped contracts, 27 territories), with a deterministically
  rebuilt country×CPV×month single-bidding panel (2017–2020), a CPV→EXIOBASE carbon weight validated
  against Eurostat (ρ=0.82), and Directive 2014/24 transposition dates.
- **Part B** — an eForms full-bid-set corpus (302,555 single-award notices, 2024–2025) giving the
  complete ranked tenderer set per award, with a pre-registered worked example.

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
| [`archive/`](archive/) | Superseded work, including the earlier Nature Sustainability manuscript (`old_manuscript_NC/`) |

## Data and code availability

- **Deposit (data + code):** Zenodo version DOI **[10.5281/zenodo.20823936](https://doi.org/10.5281/zenodo.20823936)**
  (concept DOI 10.5281/zenodo.19456216). Data CC-BY 4.0; code MIT.
- **Repository:** https://github.com/ProgrmerJack/Public-Procurement-Control-Surface

## Quick start

```bash
pip install -r requirements.txt

# Build the descriptor's figures and verify every claim against the deposited data
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
  title  = {A harmonised EU public-procurement competition resource},
  year   = {2026},
  doi    = {10.5281/zenodo.20823936},
  note   = {Data CC-BY 4.0; code MIT}
}
```

## License

Code: MIT. Data: CC-BY 4.0.
