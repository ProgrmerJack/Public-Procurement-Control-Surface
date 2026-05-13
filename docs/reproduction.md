# Reproduction Guide

## Overview

This guide provides step-by-step instructions to reproduce all results in the paper:

> **Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement**
>
> Ashuraliyev, A. (2026). *Nature Sustainability*.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/ProgrmerJack/Public-Procurement-Control-Surface.git
cd Public-Procurement-Control-Surface

# 2. Setup environment
python -m venv .venv
.venv/Scripts/activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# 3. Download Data.zip from Zenodo and extract it at repository root
# https://doi.org/10.5281/zenodo.20098951

# 4. Verify all quantitative claims (~2 minutes)
python verify_all_claims.py
```

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Windows 10, Linux, macOS | Any |
| **RAM** | 16 GB | 32 GB |
| **Storage** | 15 GB free | 50 GB (for raw data) |
| **Python** | 3.10+ | 3.12 |
| **CPU** | 4 cores | 8+ cores |

### Python Dependencies

```
pandas>=2.0
numpy>=1.24
scipy>=1.10
pyarrow>=14.0
matplotlib>=3.8
seaborn>=0.12
```

Install all with: `pip install -r requirements.txt`

---

## Data Access

### Processed Data (Recommended)

The published replication archive is available on Zenodo:

- **DOI:** [10.5281/zenodo.20098951](https://doi.org/10.5281/zenodo.20098951)
- **Primary artifact:** `Data.zip` (12.73 GB)
- **Contents:** Recreates the `Data/` directory, including `Data/processed/gprd_with_carbon.parquet`

After downloading `Data.zip`, extract it at repository root so the archive restores the `Data/` tree expected by the scripts.

### Raw Data Sources

If you wish to rebuild from raw data:

| Source | URL | Coverage |
|--------|-----|----------|
| EU TED | [ted.europa.eu](https://ted.europa.eu/en/) | 26 EU/EEA countries |
| Colombia SECOP | [datos.gov.co](https://www.datos.gov.co) | Colombia |
| UK Contracts Finder | [gov.uk](https://www.gov.uk/contracts-finder) | United Kingdom |
| EXIOBASE 3.8.2 | [DOI: 10.5281/zenodo.5589597](https://doi.org/10.5281/zenodo.5589597) | Carbon intensities |

---

## Step-by-Step Reproduction

### Step 1: Verify Data Integrity

```bash
python reproduce_data_comprehensive.py
```

This validates:
- File exists and loads correctly
- All required columns present
- No missing critical values
- Value ranges are plausible

### Step 2: Verify Quantitative Claims

```bash
python verify_all_claims.py
```

**Expected output:**
```
VERIFICATION SUMMARY
================================================================================
Total claims verified: 36/36
Pass rate: 100.0%

✓ ALL CLAIMS VERIFIED - Results are reproducible
```

### Step 3: Generate Figures (Optional)

```bash
cd NC_Submission
python -c "import generate_figures; generate_figures.main()"
```

---

## Verification Checklist

- Run `python verify_all_claims.py` for the repository-wide 36-claim verification pass.
- Inspect `VERIFICATION_RESULTS.json` for the machine-readable PASS/FAIL output.
- Use `CLAIMS_INDEX.md` to trace any manuscript or SI claim back to the producing script and result file.

---

## Troubleshooting

### Memory Issues
If you encounter memory errors:
```python
# Use chunked loading
df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet',
                     columns=['is_single_bidder', 'carbon_intensity', 'value_eur', 'year'])
```

### Missing Data File
Download `Data.zip` from Zenodo and extract it at repository root:
```bash
# https://doi.org/10.5281/zenodo.20098951
```

### Import Errors
Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

---

## Contact

For reproduction issues:
- **GitHub Issues:** https://github.com/ProgrmerJack/Public-Procurement-Control-Surface/issues
- **Email:** jack00040008@outlook.com
- **ORCID:** [0009-0003-5482-5526](https://orcid.org/0009-0003-5482-5526)
