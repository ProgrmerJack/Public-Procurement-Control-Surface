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
| [`verification/`](verification/) | 6 | Legacy verification scripts (use `verify_all_claims.py` instead) |
| [`reanalysis/`](reanalysis/) | 12 | Sequential numbered robustness checks (`01_simple_sanity_check.py` – `12_final_validation_report.py`) |
| [`lib/`](lib/) | 4 | Reusable library modules (`causal_analysis`, `data_acquisition`, `mechanism_index`); imported by tests as `scripts.lib.*` |

## Running Scripts

All scripts should be run from the **repository root**:

```bash
cd Public-Procurement-Control-Surface
python scripts/causal_id/staggered_did.py
python scripts/projections/forward_projection_model.py
```

## Quick Reference: Key Scripts by Manuscript Section

| Manuscript Section | Key Scripts | Result Files |
|-------------------|-------------|-------------|
| Simpson's Paradox | `core_stats/analyze_all_procurement_data.py` | `results/core_stats/` |
| Causal DiD | `causal_id/staggered_did.py`, `causal_id/callaway_santanna.py` | `results/causal_id/` |
| RDD | `rdd/eprtr_rdd_analysis.py` | `results/rdd/` |
| Within-Sector | `within_sector/eprtr_within_sector.py`, `within_sector/within_supplier_analysis.py` | `results/within_sector/` |
| Dead Zones | `dead_zones/eu_dead_zones_recompute.py` | `results/dead_zones/` |
| Cross-Continental | `cross_continental/us_procurement_analysis.py` | `results/cross_continental/` |
| Forward Projections | `projections/forward_projection_model.py`, `projections/monte_carlo_uncertainty.py` | `results/projections/` |

## Unified Verification

To verify all claims from the manuscript:

```bash
python verify_all_claims.py
# Expected: 36/36 PASS (100%)
```

See [`CLAIMS_INDEX.md`](../CLAIMS_INDEX.md) for complete mapping of every claim to its source script and result file.
