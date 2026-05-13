# Data Documentation for Reproducibility

## Overview

This folder contains the processed data required to reproduce all analyses in the manuscript "Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement."

## Data Files

### Primary Analysis File

**`processed/gprd_with_carbon.parquet`** (793.8 MB)
- Main analysis dataset with 21,612,129 contracts
- Contains the variables needed to reproduce the manuscript and Supplementary Information after `Data.zip` is extracted at repository root

| Column | Description | Type |
|--------|-------------|------|
| `record_id` | Unique contract identifier | string |
| `ocid` | Open Contracting ID | string |
| `country` | Country code (ISO 2-letter) | string |
| `year` | Award year | float |
| `month` | Award month | float |
| `cpv_division` | CPV division (2-digit) | string |
| `cpv_code` | Full CPV code | string |
| `tender_date` | Tender publication date | datetime |
| `sector` | Economic sector | string |
| `value_usd` | Contract value in USD | float |
| `value_eur` | Contract value in EUR | float |
| `procurement_method` | Procurement procedure type | string |
| `n_bidders` | Number of bidders | float |
| `single_bidder` | True if only one bidder | bool |
| `competitive` | True if >1 bidder | bool |
| `buyer_id` | Contracting authority ID | string |
| `supplier_id` | Supplier ID | string |
| `carbon_intensity_kg_usd` | kg CO₂e per USD | float |
| `carbon_footprint_kg` | Total carbon footprint (kg) | float |
| `carbon_footprint_tonnes` | Total carbon footprint (t) | float |
| `exiobase_sector` | EXIOBASE sector mapping | string |

### Supporting Files

- **`processed/gprd_master.parquet`** (2.5 GB): Full procurement data without carbon
- **`processed/gprd_analysis.parquet`** (1.5 GB): Analysis-ready subset
- **`processed/gprd_carbon_analysis.parquet`** (727 MB): Carbon-focused analysis

## Data Sources

### Procurement Data

1. **EU Tenders Electronic Daily (TED)**
   - URL: https://ted.europa.eu/
   - Coverage: 27 EU/EEA countries, 2006-2023
   - License: EU Open Data

2. **Colombia SECOP**
   - URL: https://www.datos.gov.co
   - Coverage: 7.9 million contracts
   - License: CC-BY 4.0

3. **UK Contracts Finder**
   - URL: https://www.gov.uk/contracts-finder
   - Coverage: 819,000 contracts
   - License: Open Government Licence

### Carbon Intensity Data

**EXIOBASE 3.8.2**
- DOI: 10.5281/zenodo.5589597
- URL: https://zenodo.org/records/5589597
- Variables used: Carbon satellite accounts (kg CO₂e per EUR output)
- Citation: Stadler, K. et al. (2018). EXIOBASE 3. J. Ind. Ecol. 22, 502-515.

## Reproduction Instructions

### Requirements

```bash
pip install pandas pyarrow scipy numpy matplotlib
```

### Verify Statistics

```python
import pandas as pd
from scipy import stats

# Load data
df = pd.read_parquet('processed/gprd_with_carbon.parquet')

# Reproduce Table 1 statistics
single = df[df['single_bidder'] == True]['carbon_intensity_kg_usd']
multi = df[df['single_bidder'] == False]['carbon_intensity_kg_usd']

print(f"Single-bidder mean: {single.mean():.4f}")  # 0.3371
print(f"Multi-bidder mean: {multi.mean():.4f}")    # 0.2936
print(f"Premium: {(single.mean()-multi.mean())/multi.mean()*100:.1f}%")  # 14.8%

t, p = stats.ttest_ind(single, multi, equal_var=False)
print(f"t-statistic: {t:.1f}")  # 333.7
```

### Reproduce Figures

```bash
python generate_verified_figures.py
```

## Data Quality

- **Completeness**: 100% of contracts have carbon intensity estimates
- **Competition data**: 71.9% have bidder count information
- **Validation**: All statistics verified against VERIFICATION_RESULTS.json

## Zenodo Deposit

The repository-aligned replication archive is published at:
- DOI: 10.5281/zenodo.20098951
- Primary artifact: `Data.zip`
- Extraction target: repository root, recreating `Data/`
- License: CC-BY 4.0

## Contact

For data questions, contact the corresponding author.
