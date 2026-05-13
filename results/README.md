# Results Directory

Pre-computed analysis outputs organized by category. All files are JSON unless noted.

## Directory Structure

| Folder | Files | Contents |
|--------|-------|----------|
| [`causal_id/`](causal_id/) | 6 | Staggered DiD, Callaway-Sant'Anna, dose-response, synthetic control, permutation |
| [`rdd/`](rdd/) | 2 | Regression discontinuity at EU transparency threshold |
| [`within_sector/`](within_sector/) | 8 | E-PRTR, within-supplier, Eurostat, EU ETS within-sector |
| [`dead_zones/`](dead_zones/) | 3 | Dead zone sensitivity, reform analysis |
| [`cross_continental/`](cross_continental/) | 8 | US, Australia, Canada, Global South procurement |
| [`validation/`](validation/) | 15 | Eurostat, E-PRTR, SBTi, firm-level, portfolio exposure |
| [`projections/`](projections/) | 4 | Forward scenarios, Monte Carlo, OECD calibration |
| [`robustness/`](robustness/) | 10 | Greece exclusion, exact matching, wild bootstrap, FDR |
| [`mechanism/`](mechanism/) | 2 | Mediation trap, bridge analysis |
| [`core_stats/`](core_stats/) | 10 | Comprehensive statistics, carbon regression, global scope |
| [`eu_ets/`](eu_ets/) | 2 | EU ETS analysis, SI tables |
| [`csv/`](csv/) | 4 | Sector statistics, procurement premiums |
| [`other/`](other/) | 12 | Exploratory results, pipeline logs |
| [`figures/`](figures/) | — | Publication-ready figures |

## Headline Numbers

- Sample: **21,612,129** contracts (27 countries, 2012–2023)
- Single-bidder carbon premium: **+14.8%** (t = 333.7, p < 1e-300)
- U-curve: Small +50.2% | Large −7.1%
- RDD: Threshold increases bidders by **+0.77** (15.19%)
- Extensive margin: **89.2%** of effect
- Forward projection: **16 Mt CO₂e** by 2030

## Verification

```bash
python verify_all_claims.py     # 36/36 PASS
```

See [`CLAIMS_INDEX.md`](../CLAIMS_INDEX.md) for mapping every claim to its result file and JSON key.
