# Scripts Directory

All ~130 analysis and processing scripts, organized in 20 subfolders. Each subfolder contains related scripts with a consistent purpose.

## Directory Structure

| Folder | Count | Purpose |
|--------|-------|---------|
| [`causal_id/`](causal_id/) | 10 | Difference-in-differences, synthetic control, dose-response, permutation inference |
| [`rdd/`](rdd/) | 2 | Regression discontinuity design at EU transparency threshold |
| [`within_sector/`](within_sector/) | 7 | Within country-sector and within-supplier analyses |
| [`dead_zones/`](dead_zones/) | 4 | Dead zone classification, sensitivity, and within-sector decomposition |
| [`eu_ets/`](eu_ets/) | 2 | EU Emissions Trading System facility-level analysis |
| [`cross_continental/`](cross_continental/) | 5 | US, Australia, Canada, and non-EU procurement analysis |
| [`validation/`](validation/) | 16 | External data triangulation (Eurostat, E-PRTR, SBTi, firm-level) |
| [`projections/`](projections/) | 4 | Forward policy scenarios, Monte Carlo uncertainty, OECD calibration |
| [`robustness/`](robustness/) | 8 | Sensitivity tests, Greece exclusion, exact matching, leave-one-out |
| [`mechanism/`](mechanism/) | 3 | Mediation analysis, bridge analysis, comprehensive statistics |
| [`core_stats/`](core_stats/) | 7 | Basic statistics, carbon regression, EU-specific numbers |
| [`pipeline/`](pipeline/) | 9 | Raw → processed data pipeline (TED, EXIOBASE, OCDS, harmonization) |
| [`download/`](download/) | 5 | Data acquisition scripts |
| [`figures/`](figures/) | 6 | Publication-ready figures and tables |
| [`diagnostics/`](diagnostics/) | 10 | Data quality checks, validation, parquet inspection |
| [`zenodo/`](zenodo/) | 1 | Zenodo archive upload |
| [`exploratory/`](exploratory/) | 8 | Development/exploration scripts (not cited in manuscript) |
| [`verification/`](verification/) | 6 | Legacy verification scripts (descriptor uses `../scripts/descriptor/verify_claims.py`) |
| [`reanalysis/`](reanalysis/) | 12 | Sequential numbered robustness checks (`01_simple_sanity_check.py` – `12_final_validation_report.py`) |
| [`lib/`](lib/) | 4 | Reusable library modules (`causal_analysis`, `data_acquisition`, `mechanism_index`); imported by tests as `scripts.lib.*` |

## Running Scripts

All scripts should be run from the **repository root**:

```bash
cd Public-Procurement-Control-Surface
python scripts/causal_id/staggered_did.py
python scripts/projections/forward_projection_model.py
```

## Current output: the *Scientific Data* Data Descriptor

The repository's current output is the Data Descriptor in
[`../Scientific_Data_Descriptor/`](../Scientific_Data_Descriptor/). Scripts it relies on:

| Step | Script |
|---|---|
| Raw-TED parsing + schema handling | `pipeline/parse_eu_ted.py`, `pipeline/ted_bulk_stream_extract.py` |
| Carbon linkage (CPV→EXIOBASE weights) | `pipeline/link_carbon_intensity.py` |
| eForms full-bid-set extraction | `eforms_competition/extract_eforms_bids.py` |
| eForms within-tender result + battery | `eforms_competition/within_tender_green_wins.py`, `robustness_battery.py` |
| Carbon validation vs Eurostat | `within_sector/exiobase_eurostat_validation_v2.py` |
| 2018 reconciliation | `reanalysis/ted_reconciliation.py` |
| Descriptor panel + figures + verification | `scripts/descriptor/*.py` |
| Zenodo deposit | `zenodo/zenodo_stage_deposit.py` |

## Earlier causal analysis (superseded)

The `causal_id/`, `rdd/`, `dead_zones/`, `projections/`, `mechanism/`, and parts of `cross_continental/`
folders implement the earlier (withdrawn) competition–carbon causal study; the manuscript is in
[`../archive/old_manuscript_NC/`](../archive/old_manuscript_NC/). They are retained for provenance.

## Verification

Claims in the descriptor are verified against the deposited data by
[`../scripts/descriptor/verify_claims.py`](../scripts/descriptor/verify_claims.py)
and traced in
[`../Scientific_Data_Descriptor/CLAIMS_INDEX.md`](../Scientific_Data_Descriptor/CLAIMS_INDEX.md).
