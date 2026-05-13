# Reanalysis Scripts

This folder contains development and diagnostic scripts used during the research process. These are **not required for reproduction** - use `reproduce_manuscript_claims.py` in the root directory instead.

## Purpose

These scripts were used during development to:
- Diagnose RDD threshold effects
- Investigate bandwidth sensitivity
- Perform comprehensive robustness checks
- Validate meta-analysis methodology

## Scripts

| Script | Purpose |
|--------|---------|
| `01_simple_sanity_check.py` | Basic data loading and statistics |
| `02_rdd_diagnostic.py` | RDD threshold diagnostics |
| `03_minimal_rdd_test.py` | Minimal RDD implementation test |
| `04_bandwidth_investigation.py` | Bandwidth sensitivity analysis |
| `05_final_definitive_test.py` | Final validation tests |
| `06_comprehensive_robustness_tests.py` | Full robustness suite |
| `07_post_fix_verification.py` | Post-correction verification |
| `08_deep_robustness_analysis.py` | Extended robustness |
| `09_meta_analysis_verification.py` | Meta-analysis validation |
| `10_mediation_analysis.py` | Mediation pathway analysis |
| `11_heterogeneity_deep_dive.py` | Country heterogeneity investigation |
| `12_final_validation_report.py` | Final validation summary |

## Note

For official reproduction, use:
```bash
python reproduce_manuscript_claims.py
```

This will verify all 6 manuscript claims against the processed data.
