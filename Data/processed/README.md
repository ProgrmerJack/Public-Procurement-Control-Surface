# Processed data

Intermediate parquet files for the *Scientific Data* Data Descriptor **"Recovered TED bidder counts
and full-bid-set eForms tenderers for European public procurement."** These are local build inputs
(large, gitignored); the published, citable dataset is on Zenodo (concept DOI
[10.5281/zenodo.19456216](https://doi.org/10.5281/zenodo.19456216)).

## Key files

| File | Role |
|------|------|
| `eu_ted/yearly/ted_{YEAR}_CAN.parquet` | Per-year TED contract-award-notice (CAN) parquet — the raw input to the rebuild. Note: these are ingestion *batches*, not notice years (a file may contain notices dispatched in other years); the rebuild dates each award by its dispatch date. |
| `eu_ted/eu_ted_harmonized.parquet` | Full harmonised TED layer (superseded as the flagship by the raw rebuild). |

## Building the deposited contract file

```bash
python scripts/descriptor/build_contract_file.py   # -> deposit/procurement_awards_2012_2023.parquet
python scripts/descriptor/build_partA_panel.py     # -> results/descriptor/ (panel + validation)
python scripts/descriptor/verify_claims.py         # 41/41 claim checks vs the deposit
```

The rebuild unions the yearly CAN files, de-duplicates on `notice_id × award_id`, dates by dispatch
date, attaches the CPV→EXIOBASE carbon weight, and merges the flagged non-TED sources — yielding
16.97M de-duplicated, carbon-mapped contracts (8.18M TED + 7.97M SECOP + 0.82M UK). This eliminates a
2018 ingestion vintage that inflated the earlier processed extract. See
[`../../Scientific_Data_Descriptor/DEPOSIT_README.md`](../../Scientific_Data_Descriptor/DEPOSIT_README.md)
for the full data dictionary and validation summary.

> **Note.** Earlier processed extracts (e.g. `gprd_with_carbon.parquet`) and the causal analysis
> scripts under `scripts/causal_id/` and `scripts/dead_zones/` are exploratory work that predates and
> is superseded by this Data Descriptor. They are not part of the deposited resource; the descriptor
> and `CLAIMS_INDEX.md` define the current, reproducible outputs.
