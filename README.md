# Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20098951.svg)](https://doi.org/10.5281/zenodo.20098951)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

**Reproducible Research Repository for Nature Sustainability Article**

> Ashuraliyev, A. (2026). Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement.

---

## Abstract

Green Public Procurement (GPP) can only function where competitive supplier markets exist, yet the structural prerequisites for competition in high-carbon sectors remain unquantified. Analysing 21.6 million government contracts from 27 countries (2012–2023), we identify Decarbonization Dead Zones—high-carbon sectors with entrenched single-bidder awards—that lock an estimated €190–250 billion in annual EU spending beyond GPP reach. In countries with transparent procurement frameworks, governance reform has opened these sectors to competitive bidding: single-bidder contracts concentrate in lower-carbon categories (**−4.3%**; Cohen’s *d* = −0.08). A staggered Callaway & Sant’Anna difference-in-differences evaluation finds that the EU’s 2014 transparency directive reduced single-bidder rates by **7.2 percentage points** (root-mean-square prediction error permutation *p* = 0.042, rank 1 of 24 placebos), corroborated by regression discontinuity at the EU €139,000 disclosure threshold (+15.2% more bidders; *p* = 7.5×10⁻²⁰). Observational post-pandemic increases (+2.5 pp since 2019) warrant monitoring. Dead Zone carbon represents 3–6% of national Paris Agreement targets; competition savings could offset 39–100% of Green Premium transition costs.

---

## Key Findings

| Finding | Result | Significance |
|---------|--------|--------------|
| **EU-context carbon premium** | Single-bidder contracts −4.3% carbon intensity | *t* = −110, *d* = −0.08 |
| **Decarbonization Dead Zones** | 22 sectors (global threshold); 51.5% of procurement value | €190–250B locked beyond GPP reach |
| **DiD causal effect (ATT)** | −7.2 pp reduction in single-bidder rates | RMSPE permutation *p* = 0.042 (rank 1/24) |
| **RDD threshold effect** | +15.2% more bidders above €139k | *p* = 7.5×10⁻²⁰ |
| **Post-pandemic trend** | +2.5 pp single-bidder rates since 2019 | Warrants monitoring |
| **Dead Zone NDC share** | 3–6% of national Paris Agreement targets | Dead Zone-specific |
| **Green Premium offset** | 39–100% of Green Premium from competition savings | Scale-invariant |
| **Within-sector potential** | Up to 43% reduction (*d* = −0.37, EU ETS data) | Conservative lower bound |

---

## Quick Reproduction

### 1. Setup

```bash
git clone https://github.com/ProgrmerJack/Public-Procurement-Control-Surface.git
cd Public-Procurement-Control-Surface
python -m venv .venv
.venv/Scripts/activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Download Data.zip from Zenodo and extract it at repository root
# https://doi.org/10.5281/zenodo.20098951
# The archive recreates the Data/ directory expected by the scripts
```

### 2. Unified Verification (Recommended)

```bash
# Verify ALL 36 claims in one command
python verify_all_claims.py
```

**Expected Output:**
```
VERIFICATION SUMMARY
================================================================================
Total claims verified: 36/36
Pass rate: 100.0%

✓ ALL CLAIMS VERIFIED - Results are reproducible
```

### 3. Detailed Claim Tracing

See [`CLAIMS_INDEX.md`](CLAIMS_INDEX.md) for comprehensive mapping of **every** claim (193 manuscript + 500+ SI) to source code, result files, and JSON keys.

### 4. Legacy Reproduction Scripts

```bash
python reproduce_manuscript_claims.py
```

Legacy six-claim reproduction scripts are retained for backward compatibility, but the authoritative verification entry point is `python verify_all_claims.py`.

---

## Project Structure

```
Public-Procurement-Control-Surface/
├── NC_Submission/                    # Nature Sustainability submission
│   ├── manuscript.tex                # Main article (LaTeX)
│   ├── cover_letter.tex              # Cover letter to editors
│   ├── Main_Figures/                 # Publication-ready figures (300 DPI)
│   ├── Extended_Data_Figures/        # Extended Data figures
│   ├── Source_Data/                  # Figure source data files
│   └── Supplementary_Information/    # Extended methods and tables
│
├── Data/
│   ├── processed/
│   │   └── gprd_with_carbon.parquet  # Main analysis dataset (794 MB)
│   └── raw/
│       ├── exiobase/                 # EXIOBASE 3.8.2 IO tables
│       └── ocds/                     # Raw procurement data
│
├── scripts/                          # ~130 scripts organized in 20 subfolders
│   ├── causal_id/                    # DiD, synthetic control, dose-response (10)
│   ├── rdd/                          # Regression discontinuity (2)
│   ├── within_sector/                # Within-sector evidence (7)
│   ├── dead_zones/                   # Dead zone classification (4)
│   ├── eu_ets/                       # EU ETS analysis (2)
│   ├── cross_continental/            # US, AU, CA, non-EU (5)
│   ├── validation/                   # External triangulation (16)
│   ├── projections/                  # Forward scenarios, Monte Carlo (4)
│   ├── robustness/                   # Sensitivity & robustness (8)
│   ├── mechanism/                    # Mediation, mechanisms (3)
│   ├── core_stats/                   # Basic statistics (7)
│   ├── pipeline/                     # Data processing (9)
│   ├── download/                     # Data acquisition (5)
│   ├── figures/                      # Figure generation (6)
│   ├── diagnostics/                  # Data quality checks (10)
│   ├── zenodo/                       # Archive upload (1)
│   ├── exploratory/                  # Development (8)
│   ├── verification/                 # Legacy verification (6)
│   ├── reanalysis/                   # 12 numbered robustness checks + results/
│   └── lib/                          # Reusable library modules (4)
│
├── results/                          # 86 result files organized by category
│   ├── causal_id/                    # DiD, synthetic control results
│   ├── rdd/                          # RDD results
│   ├── within_sector/                # Within-sector results
│   ├── dead_zones/                   # Dead zone results
│   ├── cross_continental/            # Cross-continental results
│   ├── validation/                   # Validation results
│   ├── projections/                  # Projection results
│   ├── robustness/                   # Robustness results
│   ├── mechanism/                    # Mechanism results
│   ├── core_stats/                   # Core statistics
│   ├── eu_ets/                       # EU ETS results
│   ├── csv/                          # Tabular outputs
│   ├── other/                        # Exploratory results
│   └── figures/                      # Publication-ready figures
│
├── docs/                             # Documentation
├── tests/                            # Unit tests (import from scripts.lib.*)
│
├── verify_all_claims.py              # ← RUN THIS: unified verification (36 claims)
├── CLAIMS_INDEX.md                   # Comprehensive claim-to-code index
├── VERIFICATION_RESULTS.json         # Verification output
├── REPRODUCE.md                      # Detailed reproduction guide
├── START_HERE.md                     # Quick guide for reviewers
└── requirements.txt                  # Python dependencies
```

---

## Data Sources

### Procurement Data

| Source | Coverage | Records | DOI/URL |
|--------|----------|---------|---------|
| **EU TED** | 26 EU/EEA countries (2012–2023) | 13.6M contracts | [ted.europa.eu](https://ted.europa.eu/TED/browse/browseByMap.do) |
| **Colombia SECOP** | Colombia (2012–2023) | 7.9M contracts | [datos.gov.co](https://www.datos.gov.co/d/jbjy-vk9h) |
| **UK Contracts Finder** | United Kingdom (2015–2023) | 819K contracts | [gov.uk/contracts-finder](https://www.gov.uk/contracts-finder) |

### Carbon Intensity Data

| Source | Coverage | DOI |
|--------|----------|-----|
| **EXIOBASE 3.8.2** | 163 sectors × 49 regions (1995–2022) | [10.5281/zenodo.5589597](https://doi.org/10.5281/zenodo.5589597) |

### Replication Archive

The repository-aligned replication archive is deposited at Zenodo under CC-BY 4.0 license:

- **DOI**: [10.5281/zenodo.20098951](https://doi.org/10.5281/zenodo.20098951)
- **Primary artifact**: `Data.zip` (12.73 GB)
- **Extraction target**: repository root, so the archive recreates `Data/`
- **Key included file**: `Data/processed/gprd_with_carbon.parquet`

---

## Manuscript

The Nature Sustainability submission is located in `NC_Submission/`:

| Document | Description |
|----------|-------------|
| `manuscript.tex` | Main article (~3,200 words) |
| `cover_letter.tex` | Editor cover letter |
| `Supplementary_Information/supplementary_information.tex` | Extended methods (~5,000 words) |

### Compile Manuscript

```bash
cd NC_Submission
pdflatex manuscript.tex
pdflatex cover_letter.tex
cd Supplementary_Information && pdflatex supplementary_information.tex
```

---

## Citation

```bibtex
@dataset{ashuraliyev2026replication_archive,
  title     = {Replication Archive for: Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement},
  author    = {Ashuraliyev, Abduxoliq},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.20098951}
}
```

---

## System Requirements

- **Python**: 3.10+
- **RAM**: 16 GB minimum (32 GB recommended)
- **Storage**: 15 GB for processed data

### Dependencies

```
pandas>=2.0
numpy>=1.24
scipy>=1.10
pyarrow>=14.0
matplotlib>=3.8
```

---

## License

- **Code**: [MIT License](LICENSE)
- **Data**: [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- **Manuscript**: All rights reserved

---

## Contact

**Abduxoliq Ashuraliyev**  
Independent Researcher  
Email: jack00040008@outlook.com  
ORCID: [0009-0003-5482-5526](https://orcid.org/0009-0003-5482-5526)  
GitHub: [@ProgrmerJack](https://github.com/ProgrmerJack)
