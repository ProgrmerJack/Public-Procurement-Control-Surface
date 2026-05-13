# Data Documentation for Reproduction

## Overview

This folder contains all processed data necessary to reproduce the findings in:

**"Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement"**

Total processed data: ~12 GB
Total contracts: 21,612,129
Countries: 27
Years: 2012-2023

---

## Quick Start: Reproduce All Claims

Run the reproduction script to confirm all manuscript claims:

```bash
python verify_all_claims.py
```

This verifies all 36 quantitative claims against the current repository results.

---

## Primary Analysis File

### `gprd_with_carbon.parquet` (794 MB)
**The main dataset used for all manuscript analyses.**

Contains 21,612,129 contracts with:
- Contract metadata (ID, country, year, value_eur)
- Competition variables (n_bidders, single_bidder)
- Carbon intensity (carbon_intensity_kg_usd)
- CPV product codes

**Key Statistics (verified 2026-01-27):**
| Metric | Value |
|--------|-------|
| Single-bidder mean | 0.3371 kg CO2/USD |
| Multi-bidder mean | 0.2936 kg CO2/USD |
| Carbon premium | +14.8% |
| t-statistic | 333.7 |
| p-value | < 10^-300 |
| Cohen's d | 0.228 |

**U-CURVE BREAKTHROUGH (verified 2026-01-27):**
| Contract Size | N | Premium | Cohen's d |
|--------------|---|---------|-----------|
| <€10k | 7.8M | +50.2% | 0.75 (LARGE) |
| €10k-200k | 5.6M | +12.5% | 0.20 |
| >€200k | 8.2M | -7.1% | -0.12 |

---

## Source Data

### EU TED (Tenders Electronic Daily)
- Source: https://ted.europa.eu/TED/browse/browseByMap.do
- Files: `eu_ted/eu_ted_harmonized.parquet` + `eu_ted/yearly/*.parquet`
- Total: 2.4 GB
- Coverage: 27 EU/EEA countries, 2006-2023

### OCDS (Open Contracting Data Standard)
- Colombia SECOP: `ocds/colombia_harmonized.parquet` (1.9 GB)
  - Source: https://www.datos.gov.co
  - 7.9 million contracts
- UK Contracts Finder: `ocds/uk_harmonized.parquet` (254 MB)
  - Source: https://www.gov.uk/contracts-finder
  - 819,000 contracts

### EXIOBASE 3.8.2 Carbon Data
- Source: https://doi.org/10.5281/zenodo.5589597
- Files: `exiobase/carbon_factors_by_year.parquet`, `exiobase/cpv_carbon_factors.parquet`
- Provides carbon intensity (kg CO2e/USD) by industry sector
- Used to map CPV codes to carbon intensity

---

## Data Provenance

All data processing is documented in:
- `DATA_PROVENANCE.json` - Full lineage of data transformations
- `DATA_QUALITY_REPORT.json` - Quality checks and coverage statistics

---

## Reproduction Commands

```bash
# Load main dataset
import pandas as pd
df = pd.read_parquet("Data/processed/gprd_with_carbon.parquet")

# Verify key statistics
from scipy import stats
single = df[df['single_bidder'] == True]['carbon_intensity_kg_usd']
multi = df[df['single_bidder'] == False]['carbon_intensity_kg_usd']
print(f"Carbon premium: {(single.mean() - multi.mean()) / multi.mean() * 100:.1f}%")
```

---

## File Checksums (SHA-256)

Run `python scripts/verify_checksums.py` to validate data integrity.

---

## Citation

If using this data, please cite:

```bibtex
@dataset{ashuraliyev2026replication_archive,
  author = {Ashuraliyev, Abduxoliq},
  title = {Replication Archive for: Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement},
  year = {2026},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.20098951}
}
```

---

## Data License

- Procurement data: Open Government License / Public Domain
- EXIOBASE data: CC-BY 4.0
- Processed dataset: CC-BY 4.0
