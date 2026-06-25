# Results Directory

Pre-computed analysis outputs (JSON/CSV). The current output of this repository is the *Scientific
Data* Data Descriptor (`../Scientific_Data_Descriptor/`); the result files it consumes are listed
under "Used by the descriptor" below. The remaining folders hold outputs from the earlier causal
analysis (superseded; the manuscript is in `../archive/old_manuscript_NC/`).

## Used by the descriptor

| File | Produced by | Used for |
|---|---|---|
| `within_sector/exiobase_eurostat_validation_v2.json` | `scripts/within_sector/exiobase_eurostat_validation_v2.py` | Carbon-weight validation (ρ=0.82) |
| `eforms_competition/within_tender_green_wins.json` | `scripts/eforms_competition/within_tender_green_wins.py` | eForms within-tender result (OR 1.02, 2,601 tenders) |
| `eforms_competition/robustness_battery.json`, `BATTERY_VERDICT.json` | `scripts/eforms_competition/robustness_battery.py` | Pre-registered robustness battery |
| `eforms_competition/PREREGISTRATION.md` | — | Pre-registered protocol |
| `eforms_competition/eforms_bids_2024_2025.jsonl` | `scripts/eforms_competition/extract_eforms_bids.py` | Full-bid-set corpus (302,555 notices) |
| `audit/ted_reconciliation.json` | `scripts/reanalysis/ted_reconciliation.py` | 2018 ingestion reconciliation (13.9M / 5.79M / official 232,989) |
| `causal_id/did_coverage_stable_nyt.json`, `fix1_canonical_cs.json` | `scripts/causal_id/` | The −9/−17pp coverage artifact vs raw-source rebuild |

## Other folders (earlier causal analysis — superseded)

`causal_id/`, `rdd/`, `within_sector/`, `dead_zones/`, `cross_continental/`, `validation/`,
`projections/`, `robustness/`, `mechanism/`, `core_stats/`, `eu_ets/`, `csv/`, `other/`. These hold
the outputs of the earlier (withdrawn) competition–carbon causal study and are retained for
provenance; they are not claims of the current descriptor.

## Verification

Every claim in the descriptor is verified against the deposited data by
`../scripts/descriptor/verify_claims.py` and traced in
`../Scientific_Data_Descriptor/CLAIMS_INDEX.md`.
