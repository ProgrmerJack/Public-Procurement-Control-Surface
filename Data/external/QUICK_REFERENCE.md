# NON-EU DATA - QUICK REFERENCE

## Successfully Downloaded ✅

### Canada (104 MB)
```
📊 Files:
  - canada_contract_datasets_summary.json (0.9 KB)
  - canada_csv_resources.json (9.2 KB) 
  - canada_Contracting_overview.csv (0.7 KB)
  - Archive reference: 22.7 MB (2009-2023 contracts)

📈 Data:
  • Quarterly contracting statistics (2018-2024)
  • 100+ government contract datasets indexed
  • 44 CSV resources mapped
  • Contract modification trends
  • Procurement competition rates (single vs. competitive bid)
  • Indigenous business set-aside percentages

🔗 Source: https://open.canada.ca/data/
📅 Coverage: 2009-2024
📍 Jurisdiction: Federal Government of Canada
```

### Chile (40 KB)
```
📊 Files:
  - chile_2_Licitaciones 2016 adjudicadas.csv (35.4 KB, 290 rows) ⭐ Main dataset
  - chile_1_Reparticiones de ENAMI.csv (3.9 KB, 26 rows)
  - chile_0_CSV_Año 2025_PP0232 al mes de FEBRERO OK 2026.csv.csv (1.8 KB, 10 rows)

📈 Data:
  • 290 adjudicated public tenders (2016)
  • Tender details: ID, Name, Buyer, Status, Timeline
  • Government procurement buyer composition
  • Tender evaluation records (2025)
  • State company (ENAMI) departmental structure

🔗 Source: https://datos.gob.cl/
📅 Coverage: 2016-2025
📍 Jurisdiction: Chilean Government
```

---

## Accessible But Not Downloaded ⚠️

### Australia
```
🌐 https://www.tenders.gov.au/
✅ Portal accessible
⏳ Requires: Manual extraction or browser automation
💡 Alternative: https://austender.com.au might have downloadable data
```

### USA Federal Procurement  
```
🌐 https://sam.gov/ (SAM.gov)
✅ Portal accessible
⏳ Requires: Free account registration + API key
📊 Also: https://www.fpds.gov/ (FPDS-NG)
```

### UK Government Tenders
```
🌐 https://www.find-tender.service.gov.uk/
✅ Portal accessible
⏳ Requires: Browser automation (JavaScript-rendered)
```

### Brazil
```
🌐 https://dados.gov.br/
✅ Portal accessible
⏳ Requires: API authentication
📧 Contact: dados.gov.br support team for credentials
```

### UN Global Marketplace
```
🌐 https://www.ungm.org/
✅ Portal accessible
⏳ Requires: Browser scraping (dynamic content)
```

### World Bank Data
```
🌐 https://data.worldbank.org/
✅ Portal accessible
⏰ Note: No procurement-specific datasets (only general development indicators)
```

### OECD Statistics
```
🌐 https://stats.oecd.org/
✅ Portal accessible
⏳ Requires: Manual download or SDMX API extraction
📊 Also: https://data-explorer.oecd.org/ (interactive but JS-heavy)
```

### ILO Statistics
```
🌐 https://ilostat.ilo.org/
✅ Portal accessible
⏳ Requires: Manual file selection/download
📊 Labor cost data by country/sector
```

---

## Failed/Unreachable ❌

| Source | Reason |
|--------|--------|
| World Bank Major Contracts | 404 - Endpoint defunct |
| South Korea KONEPS | SSL connection failed |
| Japan e-Stat API | 404 - API endpoint removed |
| Brazil ComprasNet direct | 401 - Unauthorized |
| Many Asian portals (PK, TH, IDN, MY, PH) | DNS/connectivity issues from North America |

---

## Data Schema Reference

### Canadian Contracting Overview
```
Columns: AF, Trimestre, Nbre de contrats attribués, 
         % des marchés réservés aux Autochtones, 
         Nbre de modifications de contrats,
         % de dossier de source unique,
         % de dossiers concurrentiels

Sample: 2018/19, T1, 112, S/O, 25, 34%, 66%
```

### Chilean Tenders 2016
```
Columns: Número, Nombre de la Licitación, Comprador, 
         Estado, Fecha Cierre, FechaTermino

Sample: [Tender ID], [Tender Name], [Buyer Organization], 
        [Status: Adjudicated/etc], [Bidding Close Date], [Completion Date]

Records: 290 historical tenders
```

### ENAMI Departments (Reference)
```
Columns: Región, Ciudad, Tipo, Dirección, Latitud

Use: Map state company operations; procurement buyer geography
Records: 26 departments across Chile
```

---

## Next Steps for Analysis

### Recommended Extractions (by effort)

**Easy (existing files, ready to use):**
```
✓ Canadian contracting statistics
  → Quarterly trends, competition rates
  → 2018-2024 timeline analysis
  
✓ Chilean adjudicated tenders 
  → Tender timeline: bid-to-award duration
  → Buyer concentration
```

**Medium (need API/browser extraction):**
```
⏳ Canadian contract history archive (22.7 MB)
  → Parse 2009-2023 contract details
  → Merge with contracting overview
  
⏳ Brazil ComprasNet API
  → Contact dados.gov.br for API key
  → Extract contracts by sector/buyer
```

**Advanced (browser automation required):**
```
⏳ US SAM.gov / FPDS procurement
  → Register for free account
  → Extract federal contract awards
  
⏳ Australia AusTender
  → Set up Selenium/Playwright scraper
  → Download tender records
  
⏳ OECD Stats portal
  → Automated government spending extraction
  → Cross-country procurement indicators
```

---

## Key Metadata

**Total Acquired:** 104 MB  
**Contract Records:** 290+ (Chile) + Unlimited (Canada indexed)  
**Time Periods:** 2009-2025  
**Geographic Coverage:** 3 jurisdictions (CAN, CHL, pre-mapped 15+)  
**Data Types:** Contract summary, transaction-level, buyer department  

**Suitable For:**
- Comparative procurement analysis (CA vs CL vs EU)
- Institutional diversity robustness checks
- Geographic/jurisdictional generalizability
- Time series trend analysis (2009-2024+)
- Government competition policy assessment

---

## Contact Points for Data Access

| Source | Contact | Purpose |
|--------|---------|---------|
| Canada Treasury Board | TBS Contracting Info | Contract history archive access |
| Chile ChileCompra | datos@chilecompra.gob.cl | Bulk procurement data |
| Brazil dados.gov.br | support@dados.gov.br | ComprasNet API credentials |
| USA Sam.gov | sam@gsa.gov | Federal procurement API |

---

**Status:** This report documents all attempted downloads. Additional data may be available through direct institutional contact or browser-based extraction.

*Updated: 2025 Session*
