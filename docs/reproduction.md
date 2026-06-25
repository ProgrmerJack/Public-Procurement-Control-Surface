# Reproduction guide

Step-by-step reproduction of the *Scientific Data* Data Descriptor
(`Scientific_Data_Descriptor/`). All commands run from the repository root.

## 1. Environment

```bash
pip install -r requirements.txt          # pandas, pyarrow, numpy, scipy, statsmodels, matplotlib, requests
# LaTeX (pdflatex) is required to build the manuscript PDFs.
```

## 2. Data

The deposited files are at Zenodo (DOI **10.5281/zenodo.20823936**). The descriptor's verification
scripts read the copies in `deposit/`. The upstream source/processed data
(large, gitignored) can be rebuilt with the `workflow/` Snakemake pipeline or downloaded from Zenodo.

## 3. Reproduce the descriptor

```bash
# Part A panel + every Part A statistic (single-bidder series, reconciliation, panel counts)
python scripts/descriptor/build_partA_panel.py        # -> partA_validation.json, panel parquet

# Supplementary Information tables (per-country, per-CPV, eForms coverage, crosswalk, validation)
python scripts/descriptor/si_make_tables.py           # -> si_tables/*.tex, si_data.json

# Figures
python scripts/descriptor/make_figures.py             # -> figures/

# Claim-by-claim verification against the deposited data (prints PASS/FAIL, 42 checks)
python scripts/descriptor/verify_claims.py

# Build the PDFs
cd Scientific_Data_Descriptor
pdflatex descriptor.tex && pdflatex descriptor.tex            # 12 pp
pdflatex supplementary_information.tex && pdflatex supplementary_information.tex   # 16 pp
```

## 4. Reproduce the original analysis results (consumed by the descriptor)

These original pipeline scripts regenerate the result JSONs cited in the descriptor:

```bash
python scripts/within_sector/exiobase_eurostat_validation_v2.py            # carbon ρ=0.82
python scripts/eforms_competition/within_tender_green_wins.py results/eforms_competition/eforms_bids_2024_2025.jsonl   # OR 1.02, 2,601 tenders
python scripts/eforms_competition/robustness_battery.py results/eforms_competition/eforms_bids_2024_2025.jsonl         # battery (reweight, placebo, permutation)
```

## 5. Traceability

`Scientific_Data_Descriptor/CLAIMS_INDEX.md` maps every quantitative claim in the manuscript and SI
to (a) the original generating script, (b) the deposited data file, and (c) how it is recomputed,
with a provenance tag per claim (`[DATA]` / `[ORIG]` / `[NEW]` / `[EXT]`).
