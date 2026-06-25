# Data Folder Catalog — `Data/`

**Generated:** 2026-06-20 · **Total:** 204 files, **18.44 GB** · machine-readable profile: `results/audit/data_folder_catalog_deep.json` (script: `scripts/diagnostics/catalog_data_folder_deep.py`).

This catalogs everything under `Data/`, grouped by function rather than folder, with structure, coverage, and notes on what is used vs. unused by the manuscript. **Bold = high-value / underused.**

---

## 0. Headline facts

- The analysis file (`gprd_with_carbon.parquet`, 21.6M contracts, 2012–2023) is a **filtered, carbon-mapped subset**. The repo also holds the **fuller upstream layers**: `gprd_master.parquet` (46.3M rows, retains `supplier_name`/`buyer_name`) and `eu_ted_harmonized.parquet` (34.3M raw TED rows).
- **Firm-level emissions are present and matchable**: EUTL (operator-level ETS verified emissions + names), full E-PRTR (facility CO₂ + names), plus SBTi firm targets with ISIN/LEI. This is what enabled the within-sector firm-emissions test (`results/within_sector/`).
- **Carbon reference is deep**: EXIOBASE 3.8.2 emission factors, Eurostat air-emission accounts + GVA + measured intensities, OWID country CO₂.
- **Procurement reach is far wider than used**: full US FPDS FY2024, AusTender, Colombia/UK/Peru/Honduras OCDS, World Bank, OECD — most unused.

---

## 1. Duplicates & redundant copies (safe to dedupe)

| Files (identical content) | Keep |
|---|---|
| `eu-ets.csv` = `eu_ets.csv` = `external/eu_ets/eu-ets.csv` = `raw/eu_ets_verified_emissions.csv` (9.4 MB each) | one copy |
| `external/sbti_companies.xlsx` = `processed/sbti_companies.xlsx` (2.0 MB) | one copy |
| `eu-ets-sector-emissions.csv` = `eu_ets_sectors.csv` (7 KB) | one copy |
| `external/chile_0_…FEBRERO OK 2026.csv.csv` = `external/chile_CSV_…FEBRERO OK 2026.csv.csv` | one copy |

~30+ MB reclaimable. (Also `sbti_companies.xlsx` at root duplicates external/processed copies but differs by sheet name.)

---

## 2. Primary procurement datasets (`processed/`)

### Harmonized master layers
| File | Rows | Coverage | Notes |
|---|---|---|---|
| **`gprd_master.parquet`** (2.6 GB) | 46.3M | yr 1938–2099 (dirty; analysis uses 2012–23) | **Full master with 55 cols incl. `supplier_name`, `buyer_name`, `supplier_country`, `supplier_is_sme`, `buyer_type`, `hhi_buyer`, `hhi_sector`, quality flags** — names dropped from carbon layer |
| `gprd_analysis.parquet` (1.55 GB) | 21.6M | 2012–23 | analysis-ready subset |
| **`gprd_with_carbon.parquet`** (832 MB) | 21.6M | 2012–23, 26 ctry | **the manuscript's main file** (21 cols, carbon-mapped) |
| `gprd_carbon_analysis.parquet` (762 MB) | 21.6M | 2012–23 | carbon-focused subset |
| `gprd_sample_10000.csv` | 10k | — | sample |

### Raw TED (`processed/eu_ted/`)
| File | Rows | Notes |
|---|---|---|
| **`eu_ted_harmonized.parquet`** (2.5 GB) | 34.3M | full harmonized TED 2006–2023 |
| `eu_ted/yearly/ted_YYYY_CAN.parquet` (2006–2023) | 0.3–6.2M/yr | **Contract Award Notices** (bidders, awards). `ted_2018_CAN`=6.2M = the **corrupted 2018 vintage** |
| `eu_ted/yearly/ted_YYYY_CN.parquet` (2006–2023) | 0.15–7.7M/yr | Contract Notices (tenders). `ted_2018_CN`=7.7M |
| `eu_ted/eu_ted_sample_10000.csv`, `eu_ted_summary.json` | — | sample/summary |

### OCDS / non-EU (`processed/ocds/` + JSON)
| File | Rows | Coverage |
|---|---|---|
| **`ocds/colombia_harmonized.parquet`** (1.95 GB) | 11.5M | Colombia SECOP (dirty years) |
| **`ocds/uk_harmonized.parquet`** (266 MB) | 570k | UK Contracts Finder 2016–2025 |
| `colombia_secop2_bulk.json`, `api_colombia_secop2.json` | — | SECOP API pulls |
| **`peru_oece_releases_bulk.json`** (6.3 MB) | — | **Peru OECE OCDS** (unused) |
| **`honduras_oncae.json`** (42 KB) | — | **Honduras ONCAE** (unused) |
| `ukraine_prozorro_bulk.json`, `prozorro_corroboration_raw.json` (4,320) | — | ProZorro (corroboration pull) |
| `ocp_global_south_data.json`, `ocp_publication_links.json` | — | Open Contracting Partnership links |
| `canada_control_panel.parquet` (15 rows) | 15 | Canada DiD control panel (2009–23) |

---

## 3. Firm- & facility-level emissions  ★ highest-value, mostly unused

### EUTL — EU Transaction Log (`eutl_data.zip`, 59 MB, 17 tables)
Operator/installation-level **ETS registry with company names + verified emissions**.
| Member | Size | Content |
|---|---|---|
| **`compliance.csv`** | 61 MB | **installation×year `verified` emissions, allocations, surrenders** (525k rows; 195,827 with verified>0; 2005–2023) |
| **`installation.csv`** | 5.1 MB | 19,625 installations: name, `parentCompany`, `eprtrID`, **`nace_id`**, lat/long, country |
| **`account_holder.csv`** | 3.0 MB | 20,407 **named companies** + `legalEntityIdentifier` (LEI) |
| `account.csv` | 10 MB | links installations↔holders; has **`bvdId` (ORBIS id)** for turnover linkage |
| `transaction.csv` | 164 MB | 2005+ unit transactions (allowance trades) |
| `surrender.csv` | 23 MB | surrendered units | 
| `nace_code.csv` | NACE hierarchy; `activity_type.csv`, `compliance_code.csv`, `country_code.csv`, `foha_matching.csv`, `project.csv`, lookup tables |

### E-PRTR / IED industrial dataset (`raw/eea_t_ied-eprtr_p_2007-2023_v15_r00/`)
Facility-level pollutant releases, **2007–2024, ~32 countries**. CSV (`User-friendly-CSV/`), Excel mirror, and a **2.0 GB MS-Access relational DB**.
| File | Rows | Content |
|---|---|---|
| **`F1_4_Air_Releases_Facilities.csv`** | 371k | **facility CO₂ & other air pollutants** (`facilityName`, sector, releases) — used for the firm-emissions corroboration |
| `F1_1/F1_2/F1_3_Air_Releases_National/Sector/AnnexIActivity.csv` | 14k/42k/74k | air releases aggregated |
| `F2_*_Water_Releases_*` | 13k–253k | water releases (facility→national) |
| `F3_*_Transfers_*`, `F4_*_WasteTransfers_*` | 8k–845k | off-site & waste transfers (facilities 845k) |
| **`F5_2_LCP_Energy_Emissions.csv`** | 396k | **Large Combustion Plant energy + emissions** (power-sector detail) |
| **`F6_1_IED_Installations.csv`** | 480k | IED installation permits |
| `F7_1_IED_WI_coWI.csv` | 11k | waste-incineration installations |
| `eprtr_v13.zip`, `eprtr_v16_csv.zip` (13 MB each) | — | older/alt E-PRTR snapshots |

### ETS sector aggregates (root + `external/eu_ets/`)
| File | Content |
|---|---|
| `eu_ets_verified_emissions.csv` (=`eu-ets.csv`) | 76k rows: verified emissions/allocations by country×**main activity sector**×year, 2005–2024, 36 ctry |
| `external/eu_ets/data_03.csv` | 128k rows ETS detail |
| `ETS_DataViewer_20250916.xlsx` | 97k rows (Country×Year×Size×Activity) |
| `ETS_cube_final_version78_2025-09-16.xlsx` | ETS cube |
| `eu-ets-sector-emissions.csv` / `eu_ets_sectors.csv` | sector×year emissions (Mt) |
| `Translation of activity codes May 2019.xlsx`, `EU ETS table definition.xlsx` | code lookups |

---

## 4. Carbon / emissions reference (sector & macro)

| File | Rows | Content |
|---|---|---|
| **`raw/EXIOBASE_3.8.2_2010-2022.xlsx`** | 128k | **EXIOBASE emission factors** (`EF IPCC AR5 [kg CO2e/€]`, water, land) by product category × region × year — the source of the paper's weights |
| `processed/exiobase/exiobase_emissions_detailed.parquet` | 274k | detailed EXIOBASE (49 regions, 1995–2010 sampled) |
| `processed/exiobase/cpv_carbon_factors.{parquet,csv}` | 97 | **CPV→carbon factor by year** |
| `processed/exiobase/carbon_factors_by_year.{parquet,csv}` | 28 | year factors |
| **`external/eurostat_emissions_intensity.csv`** | 1.07M | Eurostat air-emission intensity (OBS_VALUE) by NACE×country×pollutant, 1995–2024 |
| **`processed/eurostat_carbon_intensities.csv`** | 24k | **derived kg CO₂e/€ GVA by NACE×country×year (2012–23, 27 ctry)** — measured intensity |
| `raw/eurostat_aea_env_ac_ainah_r2.tsv` (+`.gz`, +`processed parquet 91k`) | 323k | Eurostat Air Emissions Accounts by NACE |
| `raw/eurostat_aea_ghg_by_nace_country_year.csv` / `eurostat_ghg_by_nace_sector.csv` | 54k/55k | GHG by NACE×country |
| **`raw/eurostat_gva_by_nace_country_year.csv`** | 109k | **Gross Value Added by NACE (intensity denominator)** |
| `raw/eurostat_nama_10_a64.tsv` (+`.gz`) | 305k | national accounts by 64 industries |
| `raw/eurostat_air_emissions.tsv` | 51 | air-emissions extract |
| **`external/owid_co2_data.csv`** | 50k | **Our World in Data**: CO₂, cement_co2, per-capita/per-GDP/per-energy, 254 ctry 1901–2024 (79 cols) |
| `reference/emission_factors.csv` | 15 | 15-sector intensity + scope1/2/3 + exiobase_code |

---

## 5. Firm climate-commitment data (`external/`, root)

| File | Rows | Content |
|---|---|---|
| **`external/sbti_targets.csv`** (28 MB) | 107k | **Science-Based Targets**: company_name, **ISIN, LEI**, sector, commitment/target detail, temperature alignment |
| **`external/sbti_companies.csv`** (8.9 MB) | 26k | SBTi companies: near/long-term/net-zero status + years |
| `sbti_companies.xlsx`, `sbti_targets.xlsx`, `sbti_eu_companies.json` (958 KB) | — | Excel/JSON mirrors (EU subset) |

→ Matchable to suppliers by name/LEI for a "does competition select target-setting firms" test (only the mechanical-draw caveat currently in SI).

---

## 6. Other-country procurement (mostly unused)

| File | Rows | Content / status |
|---|---|---|
| **`raw/us_fpds/FY2024_contracts_bulk.zip`** (1.38 GB) + `FY2024_All_Contracts_Full…zip` (450 MB) | — | **Full US FPDS FY2024 contract-level** (paper uses only 30-sector aggregates) |
| `raw/austender_2016_17.csv`, `austender_2017_18.csv`, `austender/austender_contracts.csv` | 66k–75k | Australian AusTender (paper uses 120k carbon-mapped) |
| `external/canada_Archived,_contract_history.csv` (109 MB) | 23.8M | ⚠️ **CORRUPT** — single column of small integers (80,75,3,…), not contract data. Manuscript's Canada (184k) came from CanadaBuys elsewhere |
| `external/canada_Contracting_overview.csv`, `canada_*summary.json`, `canada_csv_resources.json` | — | Canada metadata (mojibake encoding) |
| `external/chile_*` (5 small files) | 11–291 | Chile fragments (ENAMI repartitions, 2016 licitaciones) — not a usable panel |
| `raw/worldbank_procurement_notices.{json,csv}` | 2.1k | WB procurement notices |
| `external/gov_global_public_procurement.xlsx`, `gppd_bidder_analysis.json` | — | WB GPPD (22-country bidder analysis used in SI) |

---

## 7. Macro / government-spending reference

| File | Rows | Content |
|---|---|---|
| `raw/oecd_gov_at_a_glance_2023.csv` | 42k | OECD Government at a Glance 2023 |
| `raw/oecd_procurement_spending.csv` / `oecd_procurement_gdp.csv` | 2.1k/68 | OECD procurement (€2T benchmark source) |
| `external/wb_gov_expenditure.csv` / `wb_govt_expense.csv` / `raw/worldbank_govt_expenditure.csv` | 2–3k | WB govt consumption/expense %GDP |
| `external/eurostat_gov_expenditure.csv` | 336 | Eurostat intermediate consumption |
| `external/titl2025_cesifo.pdf`, `prozorro_cgdev.pdf` | — | reference papers |

---

## 8. Reference tables (`reference/`) — mostly the 3-country RDD analysis

| File | Notes |
|---|---|
| **`country_metadata.csv`** | 3 countries: incl. **`eprocurement_launch_date`**, WGI governance scores 2022, GDP/pop |
| `cpv_exiobase_crosswalk.csv` (40) | **CPV→EXIOBASE map** (corrected this round: CPV09→Coke/refined petroleum, CPV90→Waste mgmt) |
| `cpv_sectors.csv` (43) / `cpv_sectors.json` / `cpv_taxonomy.json` | CPV→sector + intensity |
| `emission_factors.csv` (15) | sector intensity + scope1/2/3 + exiobase_code |
| `country_thresholds.csv` (12) | EU threshold definitions by country/category (RDD) |
| `rd_estimates.csv`, `placebo_tests.csv`, `robustness_checks.csv`, `covariate_balance.csv`, `loocv_results.csv`, `rule_of_law_heterogeneity.csv`, `sector_analysis.csv`, `quarterly_summary.csv` | **outputs of the WITHDRAWN RDD analysis** (3 countries) — legacy |
| `gdp.csv`, `exchange_rates.csv` (+`_raw.json`) | FX/GDP for 3 countries |

---

## 9. Documentation & audit

- Root: `README.md`, `DATA_DOCUMENTATION.md`, `PROCUREMENT_DOWNLOAD.txt`
- `processed/`: `DATA_PROVENANCE.json`, `DATA_QUALITY_REPORT.json`, `gprd_summary_stats.json`, `carbon_analysis_summary.json`, `README.md`
- `external/`: `README.md`, `DOWNLOAD_REPORT.md`, `QUICK_REFERENCE.md`
- `audit/`: `README.md`, `coverage/coverage_by_{stage,field,year}.{md,csv}`, `entity_resolution/{policy.md, multinational_aliases.csv}`
- E-PRTR: `EEA_Industrial_Reporting_Metadata_v15.pdf`, `CompletenessOverview.png`, ISO metadata XML

---

## 10. Data-quality flags

1. **Corrupt:** `external/canada_Archived,_contract_history.csv` (single-int column; not contract data).
2. **Dirty year fields:** `gprd_master`/`colombia_harmonized` span 1938–2099 (parsing artifacts); always filter to 2012–2023.
3. **2018 TED vintage** (`ted_2018_CAN`=6.2M, `_CN`=7.7M) is the over-ingested corrupted vintage (≈7× adjacent years); inflates the single-bidder *rate*, not just volume.
4. **Mojibake:** several `external/canada_*` and Chile files have cp1252/UTF-8 encoding damage in headers.
5. **Duplicates:** see §1.
6. Sample-based year ranges in the JSON profile for parquets are unreliable (first-slice only); true ranges in §2.

---

## 11. Underused, high-value opportunities

| Opportunity | Data present | Status |
|---|---|---|
| **Firm-level within-sector emissions** | EUTL verified + E-PRTR facility + `supplier_name` | ✅ done (`results/within_sector/`) — overturns the E-PRTR null |
| **Firm carbon *intensity* (per €)** | EUTL `bvdId`→ORBIS turnover; Eurostat GVA | open — would upgrade magnitude→intensity |
| **SBTi supplier selection** | SBTi targets (ISIN/LEI) ↔ `supplier_name` | open |
| **Full US FPDS contract-level** | `us_fpds/FY2024_*.zip` | open (paper uses aggregates only) |
| **Global South panel** | Peru, Honduras, Colombia, UK OCDS | open (descriptive) |
| **EXIOBASE validation vs measured** | Eurostat intensity + GVA | attempted; CPV→NACE bridge flawed (discarded) |
| **Power-sector emissions detail** | E-PRTR `F5_2_LCP` (396k) | open |
