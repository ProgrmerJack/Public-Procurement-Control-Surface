# OCDS Data Coverage Audit

This directory contains systematic audit documentation for OCDS data quality and coverage across all three source countries. This audit is essential for reviewer confidence in the data foundation.

## Audit Components

### 1. Coverage Tables (`coverage/`)
- `coverage_by_stage.csv` - Field availability by contracting stage
- `coverage_by_country.csv` - Cross-country comparison
- `coverage_timeline.csv` - Data availability over time

### 2. Missingness Analysis (`missingness/`)
- `missingness_map.csv` - Missing value rates per field per country
- `missingness_patterns.csv` - MCAR/MAR/MNAR analysis
- `imputation_strategy.md` - How missing data is handled

### 3. Entity Resolution (`entity_resolution/`)
- `entity_resolution_policy.md` - Supplier name matching methodology
- `duplicate_analysis.csv` - Detected duplicates and resolution
- `alias_mapping.csv` - Known company name aliases

### 4. Data Provenance (`provenance/`)
- `source_documentation.md` - API endpoints, access dates, versions
- `schema_mapping.md` - Country-specific OCDS extensions
- `data_licenses.md` - Legal terms for each source

## Quick Reference

| Country | API Endpoint | OCDS Version | Coverage Period | Records (est.) |
|---------|--------------|--------------|-----------------|----------------|
| Ukraine | api.prozorro.gov.ua | 1.1 + extensions | 2016-present | ~10M+ |
| Colombia | api.colombiacompra.gov.co | 1.1 | 2012-present | ~5M+ |
| UK | contractsfinder.service.gov.uk | 1.1 subset | 2015-present | ~1M+ |

## Audit Methodology

Following OCDS audit standards from Open Contracting Partnership:
- https://standard.open-contracting.org/latest/en/guidance/
- https://data.open-contracting.org/

Each country's data undergoes:
1. Schema validation against OCDS 1.1
2. Field coverage quantification
3. Value distribution analysis
4. Temporal consistency checks
5. Cross-reference validation
