# Data Directory

This directory contains the data files used in the manuscript "Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement" submitted to *Nature Sustainability*.

## Directory Structure

```
Data/
├── README.md                 # This file
├── processed/               # Harmonized analysis datasets
│   └── gprd_with_carbon.parquet  # Main dataset (794 MB, 21.6M contracts)
├── raw/                     # Raw source data
│   ├── eu_ted/             # EU Tenders Electronic Daily
│   ├── ocds/               # Colombia SECOP, UK Contracts Finder
│   └── exiobase/           # Carbon intensity data
├── reference/              # Reference tables
│   ├── cpv_sectors.csv     # CPV to sector mapping
│   └── emission_factors.csv # Carbon intensity by sector
└── audit/                  # Data quality documentation
```

## Data Sources

### Primary Sources

| Source | Coverage | Records | Period | URL |
|--------|----------|---------|--------|-----|
| EU TED | 26 EU/EEA countries | 13.6M | 2012-2023 | ted.europa.eu |
| Colombia SECOP | Colombia | 7.9M | 2015-2023 | datos.gov.co |
| UK Contracts Finder | United Kingdom | 819K | 2016-2023 | gov.uk/contracts-finder |
| **Total** | **27 countries** | **21.6M** | **2012-2023** | |

### Carbon Intensity Data

| Source | Coverage | DOI |
|--------|----------|-----|
| EXIOBASE 3.8.2 | 163 sectors × 49 regions × 28 years | [10.5281/zenodo.5589597](https://doi.org/10.5281/zenodo.5589597) |

## Sample Data Description

The `contracts_sample.csv` files in each country folder contain illustrative samples of the harmonized procurement data. These samples demonstrate the data structure and variable definitions from the full `DATA_CODEBOOK.md`.

### Key Variables

| Variable | Description | Type |
|----------|-------------|------|
| `ocid` | Open Contracting ID | string |
| `contract_id` | Local contract identifier | string |
| `value_usd` | Contract value in USD | float |
| `n_bidders` | Number of bidders | int |
| `single_bidder` | Single bidder indicator | bool |
| `distance_to_threshold` | Normalized distance from threshold | float |
| `text_restrictiveness` | NLP-derived specification restrictiveness | float |

### Threshold Definitions

See `reference/country_thresholds.csv` for complete threshold definitions by country and category.

## Analysis Results

The `reference/` folder contains pre-computed analysis results used to generate figures and tables in the manuscript:

### Main Results
- `rd_estimates.csv`: Primary RDD estimates for all country-threshold pairs
- `robustness_checks.csv`: Bandwidth and polynomial order sensitivity
- `placebo_tests.csv`: Placebo cutoff tests at non-threshold values
- `covariate_balance.csv`: Balance tests for pre-determined covariates

### Heterogeneity Analysis
## Main Analysis Dataset

**File:** `processed/gprd_with_carbon.parquet` (794 MB)

| Metric | Value |
|--------|-------|
| Total contracts | 21,612,129 |
| Countries | 27 |
| Years | 2012-2023 |
| Single-bidder rate | 11.0% |
| Carbon premium | +14.8% |

## Reproducibility

To reproduce the analysis:
```bash
# Install dependencies
pip install -r requirements.txt

# Reproduce all claims
python reproduce_manuscript_claims.py
```

## Citation

If using this data, please cite:

```bibtex
@dataset{ashuraliyev2026replication_archive,
  title={Replication Archive for: Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement},
  author={Ashuraliyev, Abduxoliq},
  year={2026},
  publisher={Zenodo},
  doi={10.5281/zenodo.20098951}
}
```

## Zenodo Archive

The repository-aligned replication archive is published at:
- **DOI:** [10.5281/zenodo.20098951](https://doi.org/10.5281/zenodo.20098951)
- **Primary artifact:** `Data.zip`
- **Extraction target:** repository root, so the archive recreates `Data/`
- **License:** CC-BY 4.0

## Contact

**Abduxoliq Ashuraliyev**  
Independent Researcher  
Email: jack00040008@outlook.com  
ORCID: [0009-0003-5482-5526](https://orcid.org/0009-0003-5482-5526)

---

## Legacy Files: Prozorro Data

The following five files in the root `Data/` directory are retained for archival purposes from a predecessor study:

- `prozorro_ids.json`
- `prozorro_pre_ids_new.json`
- `prozorro_post_details.json`
- `prozorro_pre_details_new.json`
- `prozorro_sample_pre.json`

These files contain contract identifier lists and metadata collected from Ukraine's ProZorro procurement platform (https://prozorro.gov.ua) during an earlier phase of research. Ukraine ProZorro data were **not used** in the current analysis due to data comparability constraints (Ukraine is not an EU member state and was not subject to Directive 2014/24/EU). They are retained for archival completeness but do not contribute to any figures, tables, or claims in the manuscript.

The current paper's cross-continental analysis uses **Colombia SECOP** data (7.9M contracts; https://www.colombiacompra.gov.co), **not** Ukraine ProZorro.
