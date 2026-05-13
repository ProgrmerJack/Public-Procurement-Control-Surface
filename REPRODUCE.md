# Reproducibility Guide

Companion to: **"Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement"** (Nature Sustainability, submitted 2026).

This document maps every quantitative claim in the manuscript and Supplementary Information to the script, result file, and verification command that produces it. All result files are included in the Zenodo deposit.

## Quick Start

```bash
git clone https://github.com/ProgrmerJack/Public-Procurement-Control-Surface.git
cd Public-Procurement-Control-Surface

python -m venv .venv
# .venv\Scripts\activate    # Windows
source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt

# Download Data.zip from Zenodo and extract it at repository root
# https://doi.org/10.5281/zenodo.20098951
# The archive recreates the Data/ directory expected by the scripts

# UNIFIED VERIFICATION: Verify ALL 36 claims in one command
python verify_all_claims.py

# Optional: Re-run original analysis scripts
python verify_all_claims.py --rerun

# Legacy scripts (still work but less comprehensive)
python reproduce_manuscript_claims.py
```

Expected runtime: ~2 min (verification), ~45 min (full recomputation with --rerun).

---

## New Verification Infrastructure

### Single Script Verification

The new `verify_all_claims.py` script verifies **all 36 quantitative claims** in the manuscript against:
1. Direct computations from the data (for basic statistics)
2. Pre-computed result JSON files (for complex analyses)

```bash
# Basic verification
python verify_all_claims.py

# Re-run all analysis scripts first
python verify_all_claims.py --rerun

# Verify specific section (1-8)
python verify_all_claims.py --section 3

# Verbose output
python verify_all_claims.py -v
```

### Claims Index

See [`CLAIMS_INDEX.md`](CLAIMS_INDEX.md) for comprehensive mapping of **every** claim — 193 manuscript claims (M1–M193) and 30 SI sections (B1–B30, 500+ claims) — to source code, result files, and JSON keys.

---

## System Requirements

- **Python:** 3.10+ (tested on 3.12)
- **RAM:** 16 GB minimum, 32 GB recommended
- **Disk:** 15 GB (processed data + results)
- **OS:** Linux, macOS 12+, or Windows 10+

### Dependencies

All listed in `requirements.txt`. Core packages:

| Package | Version | Purpose |
|---------|---------|---------|
| pandas | ≥2.0 | Data manipulation |
| numpy | ≥1.24 | Numerical computing |
| scipy | ≥1.10 | Statistical tests (t-tests, Welch, Fisher) |
| pyarrow | ≥14.0 | Parquet I/O |
| statsmodels | ≥0.14 | DiD, RDD, mediation |
| matplotlib | ≥3.8 | Figure generation |

---

## Data Access

**Zenodo DOI:** [10.5281/zenodo.20098951](https://doi.org/10.5281/zenodo.20098951)

| Artifact | Size | Contents |
|------|------|----------|
| `Data.zip` | 12.73 GB | Repository-aligned archive that recreates `Data/` in place |
| `Data/processed/gprd_with_carbon.parquet` | 793 MB | Main analysis dataset after extraction |
| `Data/processed/gprd_master.parquet` | 2.5 GB | Full dataset with auxiliary fields after extraction |
| `Data/external/*` | Included in `Data.zip` | External validation inputs and reference files after extraction |
| `Data/raw/*` | Included in `Data.zip` where redistributable | Raw-source derivatives and supporting inputs after extraction |

`Data.zip` is the authoritative public archive. Download it from Zenodo, extract it at repository root, and the scripts will resolve the same `Data/processed/gprd_with_carbon.parquet` path used throughout the repository.

Raw EU TED XML (>90 GB) must be downloaded separately from https://ted.europa.eu.The processing pipeline (`scripts/pipeline/run_full_pipeline.py`) converts raw XML to the parquet files above.

---

## Claim-to-Source Mapping

### Table 1: Primary Results (Manuscript Section 1)

| Manuscript Claim | Value | Result File | Producing Script |
|-----------------|-------|-------------|-----------------|
| EU-context N | 13,638,933 | `results/eu_ets/eu_context_si_tables.json` | `reproduce_manuscript_claims.py` |
| EU SB premium | −4.3% | `results/eu_ets/eu_context_si_tables.json` | `reproduce_manuscript_claims.py` |
| Cohen's d | −0.08 | `results/eu_ets/eu_context_si_tables.json` | `reproduce_manuscript_claims.py` |
| t-statistic | −110 | `results/eu_ets/eu_context_si_tables.json` | `reproduce_manuscript_claims.py` |
| Global premium | +14.8% | `results/core_stats/verified_statistics.json` | `reproduce_manuscript_claims.py` |
| I² heterogeneity | 99.3% | `results/core_stats/verified_statistics.json` | `reproduce_manuscript_claims.py` |
| Total contracts | 21,612,129 | `results/core_stats/verified_statistics.json` | `reproduce_manuscript_claims.py` |

### Table 2: Causal Identification

| Manuscript Claim | Value | Result File | Producing Script |
|-----------------|-------|-------------|-----------------|
| C&S staggered ATT | −7.2 pp | `results/causal_id/callaway_santanna.json` | `scripts/causal_id/callaway_santanna.py` |
| Permutation p-value | 0.042 | `results/causal_id/sc_permutation_inference.json` | `scripts/causal_id/sc_permutation_inference.py` |
| Pre-trend F-test | F=1.32, p=0.27 | `results/causal_id/staggered_did.json` | `scripts/causal_id/staggered_did.py` |
| Event-study leads | −0.06, +1.88, +1.77 pp | `results/causal_id/staggered_did.json` | `scripts/causal_id/staggered_did.py` |
| Wild cluster bootstrap | p=0.32–0.36 | `results/robustness/wild_bootstrap_did.json` | `scripts/causal_id/staggered_did.py` |
| RDD bidder effect | +15.2% (+0.77 bidders) | `results/core_stats/verified_statistics.json` | `reproduce_manuscript_claims.py` |
| RDD carbon effect | −0.33% | `results/core_stats/verified_statistics.json` | `reproduce_manuscript_claims.py` |
| McCrary density | p=0.24 | `results/core_stats/verified_statistics.json` | `reproduce_manuscript_claims.py` |
| C&S excl. 2018 | ATT=−4.67 pp | `results/robustness/cs_did_sensitivity.json` | `scripts/causal_id/cs_did_sensitivity.py` |
| Greece exclusion | SB ATT=−6.60 pp | `results/robustness/greece_exclusion_sensitivity.json` | `scripts/robustness/greece_exclusion_robustness.py` |
| Leave-one-out | All ATTs negative | `results/robustness/leave_one_out_did.json` | `scripts/causal_id/staggered_did.py` |

### Table 3: Within-Sector Triangulation

| Manuscript Claim | Value | Result File | Producing Script |
|-----------------|-------|-------------|-----------------|
| Eurostat 542 groups, 3.2:1 ratio | FDR-corrected | `results/mechanism/bridge_analysis.json` | `scripts/within_sector/eurostat_within_sector.py` |
| Eurostat weighted premium | −0.55% | `results/mechanism/bridge_analysis.json` | `scripts/within_sector/eurostat_within_sector.py` |
| Within-supplier paired | −0.87%, d=−0.03 | `results/within_sector/within_supplier_analysis.json` | `scripts/within_sector/within_supplier_analysis.py` |
| E-PRTR 12:5 ratio | 37 groups | `results/within_sector/eprtr_within_sector.json` | `scripts/within_sector/eprtr_within_sector.py` |
| E-PRTR facility RDD | 646 facilities | `results/rdd/eprtr_rdd_analysis.json` | `scripts/within_sector/eprtr_procurement_matching.py` |
| EU ETS variance | CV 2.3×–6.5× | `results/within_sector/eu_ets_within_sector_analysis.json` | `scripts/within_sector/within_sector_validation.py` |
| Firm-level combined | −5.18% conservative | `results/validation/firm_level_validation.json` | `scripts/validation/firm_level_validation.py` |

### Table 4: Policy Magnitudes and Dead Zones

| Manuscript Claim | Value | Result File | Producing Script |
|-----------------|-------|-------------|-----------------|
| Dead Zone spending | €190–250B | `results/projections/oecd_calibrated_numbers.json` | `scripts/projections/oecd_calibration.py` |
| Monte Carlo SB CI | [339, 425] €B | `results/projections/monte_carlo_uncertainty.json` | `scripts/projections/monte_carlo_uncertainty.py` |
| NDC share | 3–6% | `results/projections/monte_carlo_uncertainty.json` | `scripts/projections/monte_carlo_uncertainty.py` |
| DZ threshold sensitivity | 2–16 sectors | `results/dead_zones/dead_zone_sensitivity.json` | `scripts/robustness/robustness_and_alternatives.py` |
| 6 EU-context DZ sectors | 5/6 survive 2022 | `results/validation/exiobase_382_vintage_validation.json` | `scripts/within_sector/within_sector_validation.py` |
| Dose-response placebo | r=0.06 pre, r=−0.56 post | `results/causal_id/dose_response_placebo.json` | `scripts/causal_id/staggered_did.py` |

### Table 5: Cross-Continental Corroboration

| Manuscript Claim | Value | Result File | Producing Script |
|-----------------|-------|-------------|-----------------|
| US single-offer correlation | r=0.555, p=0.002 | `results/cross_continental/us_procurement_analysis.json` | `scripts/cross_continental/us_procurement_analysis.py` |
| CanadaBuys external-control expansion | ATT −3.6 pp, p=0.0068 | `results/robustness/control_expansion_analysis.json` | `scripts/robustness/control_expansion_analysis.py` |
| Australia premium | +24.8%, d=0.19 | `results/cross_continental/australia_analysis.json` | `scripts/cross_continental/non_eu_procurement_analysis.py` |
| World Bank GPPD | paired t=2.63, p=0.016 | `results/cross_continental/global_south_procurement.json` | `scripts/cross_continental/non_eu_procurement_analysis.py` |
| SBTi matching | 9 firms matched | `results/validation/sbti_winner_matching.json` | `scripts/validation/sbti_winner_matching_v2.py` |

---

## Verification Commands

```bash
# Verify primary EU-context statistics
python -c "
import json
d = json.load(open('results/eu_ets/eu_context_si_tables.json'))
assert d['N'] == 13638933
assert d['premium_pct'] == -4.3
assert abs(d['d'] - (-0.076)) < 0.01
print('EU primary stats: PASS')
"

# Verify C&S DiD
python -c "
import json
d = json.load(open('results/causal_id/callaway_santanna.json'))
att = d['aggregate']['att']
assert abs(att - (-7.18)) < 0.1
assert d['aggregate']['p_value'] < 1e-8
print('C&S DiD: PASS (ATT=%.2f pp, p=%.2e)' % (att, d['aggregate']['p_value']))
"

# Verify E-PRTR 12:5 ratio
python -c "
import json
d = json.load(open('results/within_sector/eprtr_within_sector.json'))
g = d['within_country_sector']
neg = sum(1 for x in g if x['p_value'] < 0.05 and x['premium_pct'] < 0)
pos = sum(1 for x in g if x['p_value'] < 0.05 and x['premium_pct'] > 0)
assert neg == 12 and pos == 5
print('E-PRTR ratio: PASS (%d:%d)' % (neg, pos))
"

# Full verification suite
python reproduce_manuscript_claims.py
```

---

## Data Dictionary

See `Data/DATA_DOCUMENTATION.md` for complete variable descriptions.

Key columns in `gprd_with_carbon.parquet`:

| Column | Type | Description |
|--------|------|-------------|
| `country_code` | str | ISO 3166-1 alpha-2 country code |
| `n_bidders` | int | Number of bidders (0 = unknown, 1 = single-bidder) |
| `is_single_bidder` | bool | Binary competition status |
| `carbon_kg_per_usd` | float | EXIOBASE 3.8.2 sector-country carbon intensity |
| `value_usd` | float | Contract value (USD, reported amount) |
| `cpv_division` | str | CPV 2-digit procurement category |
| `year` | int | Award year (2012–2023) |
| `award_date` | date | Contract award date |

---

## Pipeline Architecture

```
Raw data (TED XML, SECOP, Contracts Finder, AusTender, Canada OD)
    │
    ├── scripts/pipeline/parse_eu_ted.py          → standardised contract records
    ├── scripts/pipeline/parse_ocds_jsonl.py      → Colombia OCDS harmonisation
    ├── scripts/pipeline/parse_exiobase.py        → carbon intensity coefficients
    └── scripts/pipeline/harmonize_data.py        → merge + deduplicate
            │
            ├── scripts/pipeline/link_carbon_intensity.py → Data/processed/gprd_with_carbon.parquet
            │
            ├── scripts/causal_id/callaway_santanna.py    → results/causal_id/callaway_santanna.json
            ├── scripts/causal_id/staggered_did.py        → results/causal_id/staggered_did.json
            ├── scripts/within_sector/eprtr_within_sector.py  → results/within_sector/eprtr_within_sector.json
            ├── scripts/projections/monte_carlo_uncertainty.py → results/projections/monte_carlo_uncertainty.json
            ├── ... (23 analysis scripts)        → results/*.json
            │
            └── scripts/figures/generate_manuscript_figures.py → NC_Submission/Main_Figures/
```

---

## Citation

```bibtex
@article{ashuraliyev2026governance_procurement,
  author  = {Ashuraliyev, Abduxoliq},
  title   = {Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement},
  journal = {Nature Sustainability},
  year    = {2026},
  note    = {Submitted}
}

@dataset{ashuraliyev2026replication_archive,
  author    = {Ashuraliyev, Abduxoliq},
  title     = {Replication Archive for: Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.20098951}
}
```

---

## Contact

- **Issues:** https://github.com/ProgrmerJack/Public-Procurement-Control-Surface/issues
- **Email:** jack00040008@outlook.com
