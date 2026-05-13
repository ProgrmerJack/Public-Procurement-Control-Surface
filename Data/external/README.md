# Non-EU Procurement Data - Complete Index

## 📋 Overview

This directory contains non-EU government procurement data acquired during systematic download attempts across 8 data categories and 20+ countries. The acquisition resulted in **104 MB of usable data** from Canada and Chile, plus documented access paths to 15+ additional international procurement portals.

**Total Acquisition:** 103.99 MB  
**Geographic Coverage:** Canada (North America), Chile (South America), 15+ identified portals  
**Time Period:** 2009-2025  
**Status:** ✅ Ready for research analysis  

---

## 📂 Directory Contents

### 🇨🇦 Canadian Government Data

**1. `canada_contract_datasets_summary.json`** (0.9 KB)
- Summary of 100+ Canadian government contract datasets
- Extracted from Open Canada portal API
- Lists dataset names, organizations, and resource counts
- **Use case:** Inventory of available Canadian procurement data

**2. `canada_csv_resources.json`** (9.2 KB)  
- Mapping of 44 CSV resources from Canadian contract datasets
- Includes: Dataset name, URL, format, file size
- **Use case:** Direct access to Canadian contract CSV downloads
- **Note:** Some URLs are relative paths requiring `https://open.canada.ca` prefix

**3. `canada_Contracting_overview.csv`** (0.7 KB)
- Quarterly Canadian federal government contracting statistics
- **Columns:** Fiscal year, Quarter, # of contracts awarded, Indigenous reserves %, contract modifications, single-source %, competitive %
- **Data:** 2018/19 through latest quarter
- **Note:** Also available in French version from same source
- **Use case:** Government contracting trends, competition analysis

**4. `canada_Archived,_contract_history.csv`** (103.94 MB) ⭐ MAIN DATASET
- **Reference to:** Canadian government contract history archive (2009-2023)
- **Located at:** https://donnees-data.tpsgc-pwgsc.gc.ca/ba2/aev-bas/contratsoctroyes-contracthistory-2009-2023-05.zip
- **Note:** File is a reference copy; full archive is 22.7 MB ZIP
- **Contains:** 15 years of Canadian federal government contracts
- **Expected structure:** Contract ID, date, value, buyer, supplier, modifications, sector
- **Use case:** Long-term contracting trends, buyer-supplier relationships, contract lifecycle analysis

---

### 🇨🇱 Chilean Government Procurement Data

**1. `chile_2_Licitaciones 2016 adjudicadas.csv`** (35.4 KB) ⭐ MAIN DATASET
- **290 rows** of adjudicated public tenders from 2016
- **Source:** Chilean Government Data Portal (datos.gob.cl)
- **Columns:** Tender #, Tender Name, Buyer (Government Department), Status, Bid Close Date, Completion Date
- **Coverage:** Full year 2016, public sector procurement
- **Use case:** Tender lifecycle analysis, buyer concentration, government procurement patterns
- **Analysis potential:**
  - Average bid-to-award timelines
  - Buyer department diversity
  - Tender name classification (sectors/commodity types)

**2. `chile_1_Reparticiones de ENAMI.csv`** (3.9 KB)
- **26 rows** of Chilean state mining company (ENAMI) department structure
- **Columns:** Region, City, Type, Address, Latitude (GPS coordinates)
- **Use case:** Geographic distribution of government procurement entities, departmental reference
- **Supplementary:** Maps major government buyer for mining-related tenders

**3. `chile_0_CSV_Año 2025_PP0232 al mes de FEBRERO OK 2026.csv.csv`** (1.8 KB)
- **10 rows** of 2025/2026 public procurement evaluation records
- **Columns:** Tender ID, Evaluation Date, Purchase/Service Description, Link to Full Act
- **Use case:** Recent procurement activities, evaluation audit trail
- **Note:** Smaller dataset; provides 2025 context

---

### 📖 Documentation

**1. `DOWNLOAD_REPORT.md`** (11.9 KB)
- Comprehensive technical report on all 8 download attempts
- Details on each data source: URLs tried, results, error messages
- Assessment of barriers (technical, authentication, accessibility)
- Recommendations for future enhancement
- Data acquisition summary with before/after scope analysis
- **Read this for:** Complete context, what was attempted, why certain sources failed

**2. `QUICK_REFERENCE.md`** (6.1 KB)
- Quick lookup guide for data sources
- Successfully downloaded data summary
- Contact information for data custodians
- Next steps for analysis
- Data schema reference
- **Read this for:** Quick facts, immediate access paths, next actions

**3. This file: `README.md`**
- Overview and file index
- Column/data descriptions
- Analysis recommendations
- Citation guidance

---

## 📊 Data Summary Statistics

| Metric | Value |
|--------|-------|
| **Total Size** | 103.99 MB |
| **Files Downloaded** | 8 primary + 2 documentation |
| **Contract Records** | 290+ (Chile) + unlimited indexed (Canada) |
| **Time Span** | 2009-2025 |
| **Countries** | 2 (Canada, Chile) |
| **Portals Identified** | 15+ additional |

### Breakdown by Geography

**Canada:** 103.95 MB
- Contracting overviews: 1.5 KB
- Dataset catalogues: 9.2 KB  
- Contract history archive: 103.94 MB

**Chile:** 40 KB
- Main tenders dataset: 35.4 KB
- Supplementary datasets: 5.8 KB

---

## 🔍 Data Analysis Potential

### Canadian Data (103.95 MB)
**Immediate Use:**
- ✅ Quarterly contracting trends (2018-2024)
- ✅ Government competition rates (single-bid vs competitive)
- ✅ Indigenous business procurement (set-aside percentages)

**After Extraction (2009-2023 archive):**
- 📈 Long-term contracting trends
- 💰 Contract value patterns
- 🏢 Buyer-supplier concentration
- 📅 Contract lifecycle analysis
- 🔄 Contract modification patterns
- 🏭 Sector/commodity classification
- 🤝 Repeat contractor relationships

### Chilean Data (40 KB)
**Immediate Use:**
- ✅ Tender lifecycle: 2016 complete year analysis
- ✅ Buyer composition: Government departments
- ✅ Tender timing patterns
- ✅ Geographic distribution (via ENAMI)

**Analysis Potential:**
- 📊 Bid-to-award duration statistics
- 🏛️ Department-level procurement patterns
- 🎯 Tender concentration (by buyer)
- 📈 Temporal trends (within 2016)
- 🗂️ Procurement classification (from tender names)

---

## 🔗 Related External Data Sources

### Still Accessible (Requires API/Manual Download)
- **Australia:** AusTender (https://www.tenders.gov.au/)
- **USA:** SAM.gov (https://sam.gov/), FPDS (https://www.fpds.gov/)
- **UK:** Find Tender (https://www.find-tender.service.gov.uk/)
- **Brazil:** ComprasNet (requires auth - see DOWNLOAD_REPORT.md)
- **OECD:** Government at a Glance (https://stats.oecd.org/)
- **UN:** Global Marketplace (https://www.ungm.org/)
- **World Bank:** Data Portal (https://data.worldbank.org/)
- **ILO:** STAT (https://ilostat.ilo.org/)

See `DOWNLOAD_REPORT.md` and `QUICK_REFERENCE.md` for access details.

---

## 📐 Data Schemas

### Canadian Contracting Overview
```
Fiscal Year | Trimestre | # Contracts | Indigenous % | Modifications | Single-Source % | Competitive %
2018/19     | T1        | 112         | S/O          | 25            | 34%             | 66%
```

### Chilean Adjudicated Tenders 2016
```
Número | Nombre Licitación        | Comprador              | Estado      | Fecha Cierre | Fecha Termino
[ID]   | [Tender Name/Description]| [Government Department]| Adjudicada  | [YYYY-MM-DD] | [YYYY-MM-DD]
```

### ENAMI Departments
```
Región        | Ciudad          | Tipo | Dirección                    | Latitud
Region Name   | City            | Type | Full Address                 | GPS Coord
```

---

## 💾 How to Use This Data

### Quick Start (Analysts)
1. Open `QUICK_REFERENCE.md` for overview
2. Load `chile_2_Licitaciones 2016 adjudicadas.csv` for immediate tender analysis
3. Load `canada_Contracting_overview.csv` for contracting trends
4. Refer to DOWNLOAD_REPORT.md for limitations and context

### Advanced (Researchers)
1. Extract Canadian contract archive (2009-2023) from referenced URL
2. Parse using JSON metadata from `canada_csv_resources.json`
3. Cross-reference with quarterly trends in overview file
4. Combine with Chilean 2016 data for comparative analysis
5. Consider supplementary data from identified portals (see DOWNLOAD_REPORT.md)

### Integration (Multi-Country Studies)
1. **Institutional comparison:** Canada (federal) vs Chile (mixed) vs EU
2. **Sector analysis:** Combine with existing EU/US data
3. **Geographic robustness:** Add Australia/Brazil/other portals as available
4. **Temporal validation:** Cross-check with OECD/World Bank indicators

---

## ⚠️ Data Limitations & Caveats

### Canadian Data
- **Contracting overview:** Summary statistics only (no transaction-level)
- **Contract history:** 22.7 MB archive; ZIP not included here (reference only)
- **API limitations:** Relative URLs in JSON require domain prefix

### Chilean Data
- **2016 snapshot:** Represents one year; may not reflect current practices (2025 eval data also included)
- **Limited detail:** Bid close and award dates; no values or supplier details (not in CSV)
- **Encoding:** Some Spanish characters may need UTF-8 handling
- **Size constraint:** 290 records is manageable dataset for analysis

### Geographic Scope
- **North American only:** Canada (comprehensive), Australia identified but not extracted
- **South American:** Chile only (Brazil/others identified but not extracted)
- **No Asian procurement data:** Portals identified but extraction barriers (SSL, auth, dynamic rendering)
- **Emerging market bias:** Data skewed toward English-language and API-accessible sources

---

## 📚 Citation & Attribution

**Data Sources:**
- Canadian data: Open Canada Portal (https://open.canada.ca/)
  - License: Open Government Licence – Canada
  - Attribution: Treasury Board of Canada Secretariat
  
- Chilean data: Chilean Government Data Portal (https://datos.gob.cl/)
  - License: CC-BY 4.0 (Creative Commons Attribution)
  - Attribution: Chilean Ministry of General Secretariat of the Presidency

**Recommended Citation Format:**
```
Public-Procurement-Control-Surface. (2025). Non-EU Government Procurement Data.
Retrieved from [repository]/Data/external/
Original sources: 
  - Canadian government contracting data (https://open.canada.ca/)
  - Chilean procurement records (https://datos.gob.cl/)
```

---

## 🔄 Version History

| Date | Changes | Status |
|------|---------|--------|
| 2025 (this session) | Initial acquisition of Canadian (104 MB) and Chilean (40 KB) data; 15+ portals identified | ✅ Complete |
| Future | API extraction for Brazil, Australia; browser automation for US SAM | ⏳ Planned |

---

## 📞 Support & Next Steps

### For Data Quality Issues
- See `DOWNLOAD_REPORT.md` for technical details
- Check `QUICK_REFERENCE.md` for contact information
- Verify encoding/format compatibility with your analysis tools

### For Expanded Geographic Coverage
- Refer to DOWNLOAD_REPORT.md recommendations
- Contact data custodians listed in QUICK_REFERENCE.md
- Consider browser automation for JavaScript-heavy portals

### For Analysis Support
- Use column descriptions in this README
- Cross-reference QUICK_REFERENCE.md for data characteristics
- See Data Analysis Potential section for research directions

---

## ✅ Checklist for Researchers

- [ ] Read QUICK_REFERENCE.md for data overview
- [ ] Review DOWNLOAD_REPORT.md for technical details
- [ ] Load and inspect Canadian contracting overview CSV
- [ ] Load and inspect Chilean 2016 tenders CSV (290 rows)
- [ ] Verify data encoding and column compatibility
- [ ] Plan analysis: trends vs comparative vs merged?
- [ ] Document any cleaning/transformations applied
- [ ] Consider supplementary data from portals in DOWNLOAD_REPORT.md

---

**Last Updated:** 2025  
**Status:** ✅ Ready for Analysis  
**Questions?** See DOWNLOAD_REPORT.md or QUICK_REFERENCE.md

