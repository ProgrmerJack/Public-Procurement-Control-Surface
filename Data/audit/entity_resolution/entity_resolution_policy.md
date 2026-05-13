# Entity Resolution Policy

## Overview

Supplier entity resolution is the **#1 silent failure mode** in cross-country procurement analysis. This document specifies our methodology for:

1. Detecting duplicate supplier entities
2. Resolving name variants to canonical identifiers
3. Handling cross-country subsidiaries
4. Quality assurance and validation

## The Problem

| Issue | Example | Impact |
|-------|---------|--------|
| Spelling variants | "Siemens AG" vs "SIEMENS A.G." | Over-counts unique suppliers |
| Legal suffix variations | "ABC Ltd" vs "ABC Limited" | Same |
| Transliteration | "Сіменс" vs "Siemens" (Ukraine) | Cross-country linkage fails |
| Mergers/acquisitions | Historical names | Time-series inconsistency |
| Subsidiaries | "Siemens Healthcare" vs "Siemens" | Depends on research question |

## Resolution Pipeline

### Stage 1: Pre-processing

```python
def normalize_name(name: str, country: str) -> str:
    """
    Normalize supplier name for matching.
    
    Steps:
    1. Convert to lowercase
    2. Remove legal suffixes (Ltd, LLC, Inc, GmbH, etc.)
    3. Remove punctuation
    4. Normalize whitespace
    5. Transliterate non-Latin scripts (Ukraine)
    6. Apply country-specific rules
    """
```

**Legal Suffix Removal**:
```
EN: ltd, limited, llc, inc, incorporated, corp, corporation, plc, co, company
DE: gmbh, ag, kg, ohg, mbh
ES: sa, sas, srl, ltda, cia
UA: тов, пп, пат, ат, зат (Ukrainian legal forms)
```

### Stage 2: Blocking

To avoid O(n²) comparisons, we use blocking strategies:

1. **First-N characters** (n=3): Group by first 3 chars of normalized name
2. **Country + CPV sector**: Within-country, within-sector blocking
3. **Soundex/Metaphone**: Phonetic blocking for similar-sounding names

### Stage 3: Similarity Scoring

We compute multiple similarity metrics:

| Metric | Weight | Use Case |
|--------|--------|----------|
| Levenshtein ratio | 0.3 | Short name changes |
| Jaro-Winkler | 0.3 | Prefix similarity |
| Token sort ratio | 0.2 | Word order independence |
| Token set ratio | 0.2 | Subset matching |

**Combined score**: Weighted average ≥ 85 → candidate match

### Stage 4: Disambiguation

For candidate matches, we apply disambiguation rules:

1. **Exact identifier match**: If official ID (EDRPOU, NIT, Companies House) matches → same entity
2. **Address similarity**: If address matches → higher confidence
3. **Contract overlap**: If same buyer contracts → possible same entity
4. **Time overlap**: Active in same periods → not a successor relationship

### Stage 5: Manual Review Queue

Matches with 75 ≤ score < 85 go to manual review queue:
- Presented with full context
- Binary decision: same/different
- Used to refine matching rules

## Country-Specific Handling

### Ukraine (ProZorro)

**Identifier**: EDRPOU (8-digit Unified State Register code)
- EDRPOU is mandatory and reliable
- Primary linkage key when available
- Name matching as fallback

**Transliteration**: Ukrainian/Russian → Latin
- Using standard ISO 9 transliteration
- Common variations handled (і→i, ї→yi, є→ye)

**Example**:
```
Original: ТОВ "СІМЕНС УКРАЇНА"
Normalized: siemens ukraina
EDRPOU: 25284097
```

### Colombia (SECOP)

**Identifier**: NIT (Número de Identificación Tributaria)
- 9-10 digit tax ID
- Present in ~70% of records
- Name matching required for remainder

**Challenges**:
- Accented characters (ñ, á, é, etc.)
- Spanish abbreviations (S.A., Ltda., etc.)

**Example**:
```
Original: CONSTRUCCIONES CIVILES S.A.S.
Normalized: construcciones civiles
NIT: 900123456-7
```

### UK (Contracts Finder)

**Identifier**: Companies House number
- 8-character alphanumeric
- Present in ~40% of records only
- Heavy reliance on name matching

**Challenges**:
- Many unincorporated suppliers (no CH number)
- Trading name vs. legal name discrepancies

**Example**:
```
Original: Capita Business Services Limited
Normalized: capita business services
Companies House: 02299747
```

## Cross-Country Linkage

For multinational companies operating across countries:

1. **Parent company identification**: Link local subsidiaries to global parent
2. **Headquarters assignment**: Assign HQ country for patent linkage
3. **Separate analysis option**: Keep subsidiaries separate for within-country analysis

**Known Multinationals Alias List** (`aliases/multinationals.csv`):
```csv
canonical_name,alias,country,local_id
Siemens AG,Siemens Ukraine,UA,25284097
Siemens AG,Siemens Colombia,CO,860000000
Siemens AG,Siemens plc,GB,00727817
```

## Validation

### Precision/Recall Estimation

Manual review of stratified sample (n=500):
- True positive rate (precision): Target ≥ 95%
- True negative rate: Target ≥ 99%
- False merge rate: Target ≤ 2%

### Known Ground Truth

Use procurement framework agreements as ground truth:
- Multiple contracts to same supplier should resolve
- Framework lots reveal true supplier counts

## Output Schema

### Canonical Supplier Table

```python
@dataclass
class CanonicalSupplier:
    canonical_id: str      # Generated UUID
    canonical_name: str    # Best/most common name
    country_hq: str        # Headquarters country
    identifiers: Dict[str, str]  # {country: local_id}
    aliases: List[str]     # All known name variants
    first_seen: date
    last_seen: date
    total_contracts: int
    resolution_method: str  # 'exact_id', 'high_confidence', 'manual'
    confidence: float       # 0-1
```

### Linkage Table

```csv
original_supplier_id,original_name,country,canonical_id,match_score,match_method
UA-123456,ТОВ СІМЕНС УКРАЇНА,UA,supplier-uuid-001,100,exact_id
CO-789012,Siemens Colombia S.A.S.,CO,supplier-uuid-001,92,fuzzy_match
GB-345678,Siemens Healthcare Ltd,GB,supplier-uuid-002,88,fuzzy_match
```

## Implementation

See `src/entity_resolution.py` for full implementation.

Key functions:
- `normalize_supplier_name(name, country)` → normalized string
- `compute_similarity_score(name1, name2)` → float
- `resolve_suppliers(suppliers_df)` → canonical_df, linkage_df
- `validate_resolution(sample_size=500)` → precision, recall report

## References

- Christen, P. (2012). Data Matching: Concepts and Techniques for Record Linkage, Entity Resolution, and Duplicate Detection. Springer.
- Fellegi, I. P., & Sunter, A. B. (1969). A Theory for Record Linkage. JASA.
- Open Contracting Partnership. (2023). Analyzing open contracting data. https://www.open-contracting.org/data-standard/
