# Global Procurement Research Dataset (GPRD) Schema

## Overview

The GPRD harmonizes procurement data from multiple national e-procurement systems into a unified analytical schema compatible with the Open Contracting Data Standard (OCDS). This schema supports carbon intensity analysis using EXIOBASE sector mappings.

## Data Sources

| Source | Coverage | Records | Period | Threshold (EUR) |
|--------|----------|---------|--------|-----------------|
| EU TED | 26 EU/EEA countries | 13.6M | 2012-2023 | 139,000 (supplies/services), 5,350,000 (works) |
| Colombia SECOP | Colombia | 7.9M | 2015-2023 | 22,000 (goods), 220,000 (works) |
| UK Contracts Finder | United Kingdom | 819K | 2016-2023 | 139,000 (goods), 5,350,000 (works) |

**Total:** 21,612,129 contracts across 27 countries

## Schema Definition

### Core Tables

#### `contracts`
Primary analytical table with one row per procurement contract.

| Column | Type | Description |
|--------|------|-------------|
| `contract_id` | string | Unique identifier (OCID format) |
| `country` | string | ISO 3166-1 alpha-2 code |
| `buyer_id` | string | Contracting authority identifier |
| `buyer_name` | string | Contracting authority name |
| `buyer_region` | string | Subnational region (NUTS2 or equivalent) |
| `cpv_code` | string | Common Procurement Vocabulary code |
| `cpv_division` | string | 2-digit CPV division |
| `category` | string | goods \| works \| services |
| `procedure_type` | string | open \| restricted \| negotiated \| direct |
| `value_local` | float | Contract value in local currency |
| `currency` | string | ISO 4217 currency code |
| `value_eur` | float | Contract value in EUR (using annual avg exchange rate) |
| `value_ppp` | float | Contract value in PPP-adjusted EUR |
| `estimated_value` | float | Pre-tender estimate in EUR |
| `tender_date` | date | Publication date |
| `award_date` | date | Award decision date |
| `signature_date` | date | Contract signature date |
| `year` | int | Fiscal year |
| `quarter` | int | Fiscal quarter |
| `n_bidders` | int | Number of valid bids received |
| `n_lots` | int | Number of lots |
| `winner_id` | string | Winning supplier identifier |
| `winner_name` | string | Winning supplier name |
| `is_sme` | bool | Winner is SME (where available) |
| `is_local` | bool | Winner from same region as buyer |
| `threshold_type` | string | EU \| national \| none |
| `above_threshold` | bool | Above relevant procurement threshold |
| `distance_to_threshold` | float | Normalized distance to nearest threshold |

#### `mechanism_features`
Text-derived features for mechanism analysis.

| Column | Type | Description |
|--------|------|-------------|
| `contract_id` | string | Foreign key to contracts |
| `description_raw` | text | Original tender description |
| `description_clean` | text | Preprocessed text |
| `word_count` | int | Number of words |
| `restrictiveness` | float | Restrictiveness score (0-1) |
| `complexity` | float | Text complexity score (0-1) |
| `innovation_score` | float | Innovation orientation (0-1) |
| `mechanism_index` | float | Composite mechanism index |
| `flesch_kincaid` | float | Readability grade level |
| `keyword_restrictive` | int | Count of restrictive keywords |
| `keyword_innovation` | int | Count of innovation keywords |

#### `bidders`
Bidding activity for competition analysis.

| Column | Type | Description |
|--------|------|-------------|
| `bid_id` | string | Unique bid identifier |
| `contract_id` | string | Foreign key to contracts |
| `bidder_id` | string | Bidder identifier |
| `bidder_name` | string | Bidder name |
| `bid_amount` | float | Bid value in EUR |
| `bid_date` | date | Submission date |
| `is_winner` | bool | Winning bid |
| `status` | string | valid \| disqualified \| withdrawn |

#### `buyers`
Contracting authority characteristics.

| Column | Type | Description |
|--------|------|-------------|
| `buyer_id` | string | Primary key |
| `country` | string | Country code |
| `name` | string | Official name |
| `region` | string | NUTS2 region |
| `sector` | string | Central \| regional \| local \| utility |
| `n_contracts` | int | Total contracts (all years) |
| `total_value` | float | Total procurement value |
| `first_contract` | date | First observed contract |
| `last_contract` | date | Most recent contract |

### Derived Variables

#### Distance to Threshold

```python
def compute_distance_to_threshold(value, threshold, normalize=True):
    """
    Compute normalized distance to procurement threshold.
    
    Parameters
    ----------
    value : float
        Contract value in EUR
    threshold : float
        Relevant threshold in EUR
    normalize : bool
        If True, normalize by threshold value
        
    Returns
    -------
    float
        Distance (positive = above threshold)
    """
    distance = value - threshold
    
    if normalize:
        distance = distance / threshold
    
    return distance
```

#### Price Ratio

```python
def compute_price_ratio(award_value, estimated_value):
    """
    Compute ratio of final price to pre-tender estimate.
    
    Returns
    -------
    float
        Ratio (1.0 = exactly at estimate)
    """
    if estimated_value is None or estimated_value <= 0:
        return None
    
    return award_value / estimated_value
```

## Data Quality

### Coverage

| Region | Contracts | Countries | Years |
|--------|-----------|-----------|-------|
| EU/EEA | 13.6M | 26 | 2012-2023 |
| Colombia | 7.9M | 1 | 2015-2023 |
| UK | 819K | 1 | 2016-2023 |
| **Total** | **21.6M** | **27** | **2012-2023** |

### Validation Checks

1. **Completeness**: All required fields present
2. **Consistency**: Cross-field validation (e.g., award_date ≥ tender_date)
3. **Referential**: Foreign keys resolve correctly
4. **Range**: Values within plausible bounds
5. **Format**: Dates, currencies, codes follow standards

### Known Limitations

- **EU TED**: Historical data quality varies by member state
- **Colombia**: SME status often missing; currency conversion challenges
- **UK**: Framework agreements may have multiple awards
- **Carbon intensity**: Sector mapping introduces measurement error (attenuated by extreme value analysis)

## File Formats

### Parquet (Primary)
- Columnar format for efficient analysis
- Compression: snappy
- Partitioning: by country and year

### JSONL (Interchange)
- One JSON object per line
- UTF-8 encoding
- OCDS-compliant structure

### CSV (Export)
- For spreadsheet analysis
- Includes data dictionary header row
- UTF-8 with BOM for Excel compatibility

## Checksums

All released data files include SHA-256 checksums in `MANIFEST.sha256`:

```
sha256sum data/processed/*.parquet > MANIFEST.sha256
```

Verify with:

```bash
sha256sum -c MANIFEST.sha256
```
