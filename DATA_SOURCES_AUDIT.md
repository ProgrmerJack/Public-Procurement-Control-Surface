# DATA SOURCES FOUND IN PUBLIC-PROCUREMENT-CONTROL-SURFACE REPOSITORY

## 1. NATIONAL DETERMINED CONTRIBUTIONS (NDCs) & NATIONAL EMISSIONS DATA
**Status: NOT FOUND IN REPOSITORY**

### What was searched for:
- NDC targets, national emissions data, carbon budgets
- Any scripts downloading NDC data
- References to UNFCCC, national emissions registries

### Findings:
- No NDC data is present in this repository
- No files downloading national-level emissions data
- The repository does NOT include country-level emissions budgets to contextualize procurement emissions

### Alternative approach needed:
- Would need to source NDCs from UNFCCC (https://unfccc.int/process-and-meetings/the-paris-agreement/nationally-determined-contributions-ndcs)
- IEA (https://www.iea.org/) for national energy/emissions data
- Our World in Data (https://ourworldindata.org/co2-emissions) for historical emissions

---

## 2. SBTi (SCIENCE BASED TARGETS INITIATIVE) DATA
**Status: NOT FOUND IN REPOSITORY**

### What was searched for:
- SBTi registry data, firm-level ESG data
- UK PPN 06/21 Carbon Reduction Plan data
- ESG emissions or climate target data

### Findings:
- NO SBTi registry data
- NO UK PPN 06/21 CRP data
- NO firm-level ESG data
- The repository focuses on PROCUREMENT CONTRACTS, not supplier-level climate commitments

---

## 3. UK CONSTRUCTION PROCUREMENT (CPV 45)
**Status: PARTIALLY FOUND - Basic mappings, NO UK-specific analysis**

### What was found:
- **CPV 45 mapping in code**: "Construction work" - mapped to 1.85 kg CO2e/USD (emission factor)
- **UK Contracts Finder data**: 819,000 UK contracts (2016-2023)
- **File**: C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\scripts\process_uk_only.py
- **UK data location**: Data/processed/ocds/uk_harmonized.parquet

### What is NOT present:
- NO UK-specific construction analysis in the codebase
- NO UK PPN (Procurement Policy Notes) integration
- NO UK Green Construction Code data
- The process_uk_only.py script only processes UK OCDS data format, does NOT analyze construction uniquely

### CPV 45 Carbon Factor:
From Data/reference/cpv_sectors.csv:
- CPV 45 (Construction works): 0.50 kg CO2e/USD in baseline
- CPV 44 (Construction materials): 1.45 kg CO2e/USD
- CPV 45 is classified as "CONSTRUCTION" sector: 1.85 kg CO2e/USD total

---

## 4. GREEN PREMIUM DATA (Green Steel, Low-Carbon Cement)
**Status: NOT FOUND IN REPOSITORY**

### What was searched for:
- Green steel prices/premiums
- Low-carbon cement cost differentials
- Material cost premiums for sustainable products

### Findings:
- NO green premium data
- NO green steel cost data
- NO low-carbon cement pricing
- NO material-level cost data for specific products
- The repository uses EXIOBASE sector-level carbon factors, NOT material-specific prices

### Repository limitation:
- Can identify HIGH-carbon procurement (construction, chemicals, transport)
- BUT CANNOT quantify green premium costs
- Would need external data sources for material cost premiums

---

## 5. COUNTRY-LEVEL EMISSIONS DATA
**Status: PARTIALLY FOUND - World Bank WGI data only**

### What was found:

#### A. World Governance Indicators (WGI) - Control of Corruption
**Location**: C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\analysis\dead_zones_did_analysis.py

**Data included (2019 estimates)**:
- Estonia: 1.27
- Denmark: 2.33
- Finland: 2.28
- Germany: 1.81
- Sweden: 2.06
- Norway: 2.18
- Netherlands: 1.93
- Luxembourg: 1.87
- Austria: 1.67
- UK: 1.68
- Switzerland: 2.16
- France: 1.30
- Belgium: 1.42
- Iceland: 2.19
- Ireland: 1.51
- Portugal: 1.10
- Spain: 0.83
- Czech Republic: 0.81
- Lithuania: 0.50
- Latvia: 0.62
- Poland: 0.41
- Slovenia: 0.71
- Slovakia: 0.25
- Hungary: -0.14
- Greece: 0.12
- Italy: 0.20
- Colombia: -0.34

**Source**: World Bank World Governance Indicators
**Range**: -2.5 (worst) to +2.5 (best)
**What it measures**: Control of Corruption (inverse proxy for governance quality)

### What is NOT in the repository:
- NO national total emissions data
- NO country energy consumption data
- NO historical CO2 emissions trends
- NO sectoral breakdown of national emissions
- NO GHG inventory data

### Why this is a GAP:
The paper identifies "Decarbonization Dead Zones" (51.5% of €165.9T in procurement)
BUT cannot contextualize how much this represents as % of national emissions

---

## ACTUAL DATA SOURCES IN REPOSITORY (FULLY DOCUMENTED)

### 1. PROCUREMENT DATA (21.6M contracts)

**EU Tenders Electronic Daily (TED)**
- Countries: 26 EU/EEA members
- Period: 2012-2023
- Contracts: 13.6M
- URL: https://ted.europa.eu/
- Data format: OCDS (Open Contracting Data Standard)
- License: EU Open Data

**Colombia SECOP II**
- Country: Colombia
- Period: 2015-2023 (SECOP II), 2012-2023 (historical)
- Contracts: 7.9M
- URL: https://www.datos.gov.co/
- Data format: OCDS
- License: CC-BY 4.0

**UK Contracts Finder**
- Country: United Kingdom
- Period: 2016-2023
- Contracts: 819K
- URL: https://www.gov.uk/contracts-finder
- Data format: OCDS
- License: Open Government Licence

### 2. CARBON INTENSITY DATA

**EXIOBASE 3.8.2 Input-Output Tables**
- Source: https://zenodo.org/records/5589597
- DOI: 10.5281/zenodo.5589597
- Coverage: 163 sectors × 49 regions × 28 years (1995-2022)
- Citation: Stadler, K. et al. (2018). EXIOBASE 3. J. Ind. Ecol. 22, 502-515.

**Methodology**:
- Carbon intensity calculated from air emissions satellite accounts
- Uses Leontief inverse to capture supply chain emissions (Scopes 1, 2, 3)
- Mapped to CPV codes via NACE Rev.2 crosswalk
- 100% of contracts linked to carbon factors

**Carbon Intensity Range**:
- Lowest: 0.05 kg CO2e/USD (professional services)
- Highest: 1.85 kg CO2e/USD (construction, utilities)

### 3. REFERENCE TABLES INCLUDED

| File | Purpose |
|------|---------|
| cpv_sectors.csv | CPV divisions mapped to sectors + baseline carbon factors |
| mission_factors.csv | Sector-level carbon intensities by EXIOBASE |
| country_thresholds.csv | Procurement thresholds by country |
| country_metadata.csv | Country codes, currencies, data sources |

### 4. KEY PROCESSED DATASETS

**Main file**: gprd_with_carbon.parquet (794 MB)
- 21.6M contracts with all variables needed for analysis
- Columns: contract ID, CPV code, value, bidder count, carbon intensity

**Supporting files**:
- gprd_master.parquet (2.5 GB): Unprocessed procurement data
- gprd_analysis.parquet (1.5 GB): Analysis-ready subset
- gprd_carbon_analysis.parquet (727 MB): Carbon-focused version

---

## CONCEPT: "DECARBONIZATION DEAD ZONES"

**Definition**: Procurement sectors with BOTH:
1. High carbon intensity (>67th percentile, 0.25 kg CO2e/USD)
2. High single-bidder rate (>median 7.4%)

**Key findings**:
- 22 sectors identified as Dead Zones
- €85.4T of €165.9T (51.5%) total procurement value
- €1.58T in single-bidder contracts structurally locked in high-carbon supply chains

**Top 5 Dead Zones by leverage**:
1. CPV 24 (Chemicals): 0.90 kg/$ carbon, 14.4% single-bidder rate
2. CPV 77 (Agri services): 0.85 kg/$ carbon, 15.0% single-bidder rate
3. CPV 65 (Water supply): 0.60 kg/$ carbon, 21.2% single-bidder rate
4. CPV 35 (Defense/security): 0.60 kg/$ carbon, 20.4% single-bidder rate
5. CPV 15 (Food products): 0.65 kg/$ carbon, 15.9% single-bidder rate

---

## SUMMARY: WHAT'S MISSING FOR YOUR ANALYSIS

### To calculate "Procurement emissions as % of national emissions", you need:

1. **National emissions data** from:
   - UNFCCC (https://unfccc.int/process/the-paris-agreement/nationally-determined-contributions-ndcs)
   - IEA Energy Database (https://www.iea.org/data-and-statistics)
   - Our World in Data (https://ourworldindata.org/co2-emissions)
   - World Bank Climate Change Portal

2. **Sectoral breakdowns** of national emissions (UNFCCC Table 2)

3. **UK-specific** construction emissions from:
   - UK National Emissions Inventory (https://naei.beis.gov.uk/)
   - UK Committee on Climate Change reports

4. **Green premium data**:
   - UK Construction Products Association
   - Material cost escalation indices (cement, steel)
   - Green procurement certification costs

---

## CODE LOCATIONS FOR REFERENCE

- Dead Zones definition: scripts/dead_zones/analyze_dead_zones.py
- Carbon factor mapping: scripts/pipeline/link_carbon_intensity.py (lines 54-115)
- EXIOBASE parsing: scripts/pipeline/parse_exiobase.py (entire file)
- UK processing: scripts/pipeline/process_uk_only.py
- Configuration: config/config.yaml, config/countries.yaml
- CPV mappings: Data/reference/cpv_sectors.csv, Data/reference/emission_factors.csv

