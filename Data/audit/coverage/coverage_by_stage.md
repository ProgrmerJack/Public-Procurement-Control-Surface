# OCDS Field Coverage by Contracting Stage

This table documents field availability across the five OCDS stages for each country.

## Stage Coverage Matrix

### Legend
- ✓ = Available (>90% coverage)
- ◐ = Partial (50-90% coverage)  
- ○ = Sparse (<50% coverage)
- ✗ = Not available

## Ukraine (ProZorro)

| Field | Planning | Tender | Award | Contract | Implementation |
|-------|----------|--------|-------|----------|----------------|
| `ocid` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `id` (release) | ✓ | ✓ | ✓ | ✓ | ✓ |
| `date` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `tag` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `initiationType` | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Buyer** | | | | | |
| `buyer.id` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `buyer.name` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `buyer.address` | ◐ | ◐ | ◐ | ◐ | ◐ |
| **Tender** | | | | | |
| `tender.id` | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.title` | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.description` | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.status` | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.value.amount` | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.value.currency` | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.procurementMethod` | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.procurementMethodDetails` | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.numberOfTenderers` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `tender.tenderPeriod` | ✗ | ✓ | ✓ | ✓ | ✓ |
| **Items** | | | | | |
| `tender.items.id` | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.items.description` | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.items.classification.scheme` | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.items.classification.id` (CPV) | ✗ | ✓ | ✓ | ✓ | ✓ |
| `tender.items.quantity` | ✗ | ◐ | ◐ | ◐ | ◐ |
| `tender.items.unit` | ✗ | ◐ | ◐ | ◐ | ◐ |
| **Award** | | | | | |
| `awards.id` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `awards.status` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `awards.date` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `awards.value.amount` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `awards.suppliers.id` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `awards.suppliers.name` | ✗ | ✗ | ✓ | ✓ | ✓ |
| **Contract** | | | | | |
| `contracts.id` | ✗ | ✗ | ✗ | ✓ | ✓ |
| `contracts.awardID` | ✗ | ✗ | ✗ | ✓ | ✓ |
| `contracts.status` | ✗ | ✗ | ✗ | ✓ | ✓ |
| `contracts.value.amount` | ✗ | ✗ | ✗ | ✓ | ✓ |
| `contracts.dateSigned` | ✗ | ✗ | ✗ | ✓ | ✓ |
| **Implementation** | | | | | |
| `contracts.implementation.transactions` | ✗ | ✗ | ✗ | ✗ | ◐ |
| `contracts.implementation.milestones` | ✗ | ✗ | ✗ | ✗ | ○ |

### Ukraine-Specific Extensions
- `bids` extension: Full bid details including prices (✓)
- `complaints` extension: Appeal/complaint data (✓)
- `qualificationRequirements`: Tender requirements (◐)

---

## Colombia (SECOP II)

| Field | Planning | Tender | Award | Contract | Implementation |
|-------|----------|--------|-------|----------|----------------|
| `ocid` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `id` (release) | ✓ | ✓ | ✓ | ✓ | ✓ |
| `date` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `tag` | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Buyer** | | | | | |
| `buyer.id` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `buyer.name` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `buyer.address.region` | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Tender** | | | | | |
| `tender.id` | ◐ | ✓ | ✓ | ✓ | ✓ |
| `tender.title` | ◐ | ✓ | ✓ | ✓ | ✓ |
| `tender.description` | ◐ | ✓ | ✓ | ✓ | ✓ |
| `tender.value.amount` | ◐ | ✓ | ✓ | ✓ | ✓ |
| `tender.procurementMethod` | ◐ | ✓ | ✓ | ✓ | ✓ |
| `tender.numberOfTenderers` | ✗ | ○ | ◐ | ◐ | ◐ |
| **Items** | | | | | |
| `tender.items.classification.id` (UNSPSC) | ◐ | ✓ | ✓ | ✓ | ✓ |
| `tender.items.description` | ◐ | ✓ | ✓ | ✓ | ✓ |
| **Award** | | | | | |
| `awards.id` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `awards.status` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `awards.value.amount` | ✗ | ✗ | ✓ | ✓ | ✓ |
| `awards.suppliers.id` | ✗ | ✗ | ◐ | ◐ | ◐ |
| `awards.suppliers.name` | ✗ | ✗ | ✓ | ✓ | ✓ |
| **Contract** | | | | | |
| `contracts.id` | ✗ | ✗ | ✗ | ✓ | ✓ |
| `contracts.value.amount` | ✗ | ✗ | ✗ | ✓ | ✓ |
| `contracts.dateSigned` | ✗ | ✗ | ✗ | ✓ | ✓ |
| **Implementation** | | | | | |
| `contracts.implementation.transactions` | ✗ | ✗ | ✗ | ✗ | ○ |

### Colombia Notes
- Uses UNSPSC classification (mapped to CPV for harmonization)
- Currency: COP (Colombian Peso)
- Regional breakdown available via `buyer.address.region`

---

## UK (Contracts Finder)

| Field | Planning | Tender | Award | Contract | Implementation |
|-------|----------|--------|-------|----------|----------------|
| `ocid` | ✗ | ✓ | ✓ | ✓ | ✗ |
| `id` (release) | ✗ | ✓ | ✓ | ✓ | ✗ |
| `date` | ✗ | ✓ | ✓ | ✓ | ✗ |
| **Buyer** | | | | | |
| `buyer.id` | ✗ | ✓ | ✓ | ✓ | ✗ |
| `buyer.name` | ✗ | ✓ | ✓ | ✓ | ✗ |
| `buyer.address` | ✗ | ◐ | ◐ | ◐ | ✗ |
| **Tender** | | | | | |
| `tender.id` | ✗ | ✓ | ✓ | ✓ | ✗ |
| `tender.title` | ✗ | ✓ | ✓ | ✓ | ✗ |
| `tender.description` | ✗ | ✓ | ✓ | ✓ | ✗ |
| `tender.value.amount` | ✗ | ◐ | ◐ | ◐ | ✗ |
| `tender.procurementMethod` | ✗ | ✓ | ✓ | ✓ | ✗ |
| `tender.numberOfTenderers` | ✗ | ✗ | ○ | ○ | ✗ |
| **Items** | | | | | |
| `tender.items.classification.id` (CPV) | ✗ | ✓ | ✓ | ✓ | ✗ |
| **Award** | | | | | |
| `awards.id` | ✗ | ✗ | ✓ | ✓ | ✗ |
| `awards.status` | ✗ | ✗ | ✓ | ✓ | ✗ |
| `awards.value.amount` | ✗ | ✗ | ◐ | ◐ | ✗ |
| `awards.suppliers.name` | ✗ | ✗ | ✓ | ✓ | ✗ |
| `awards.suppliers.id` | ✗ | ✗ | ○ | ○ | ✗ |
| **Contract** | | | | | |
| `contracts.id` | ✗ | ✗ | ✗ | ◐ | ✗ |
| `contracts.value.amount` | ✗ | ✗ | ✗ | ◐ | ✗ |

### UK Notes
- No planning stage data in OCDS format
- No implementation data published via Contracts Finder
- Threshold: £12,000 for publication (lower contracts not in system)
- Supplier identifiers inconsistent (Companies House numbers not always present)

---

## Cross-Country Comparison: Key Fields for Analysis

| Field | Ukraine | Colombia | UK | Notes |
|-------|---------|----------|-----|-------|
| Contract value | ✓ | ✓ | ◐ | UK has gaps |
| Number of bidders | ✓ | ◐ | ○ | UK rarely reports |
| Supplier identifier | ✓ | ◐ | ○ | Entity resolution needed |
| CPV/UNSPSC | ✓ | ✓ | ✓ | Colombia needs mapping |
| Award date | ✓ | ✓ | ✓ | Consistent |
| Tender description | ✓ | ✓ | ✓ | Text analysis viable |
| Procurement method | ✓ | ✓ | ✓ | Consistent |

## Implications for Analysis

### RDD (Threshold) Analysis
- **Feasible**: All three countries report tender/contract values
- **Limitation**: UK value coverage is partial (~70%)
- **Mitigation**: Sensitivity analysis excluding missing values

### DiD (Policy Reform) Analysis
- **Ukraine**: Full timeline from 2016 ProZorro launch
- **Colombia**: SECOP II adoption well-documented
- **UK**: Brexit-related rule changes identifiable

### Mechanism Index
- **Text availability**: ✓ All countries provide tender descriptions
- **Language**: UA (Ukrainian), CO (Spanish), UK (English)
- **Cross-lingual strategy required**

### Competition Outcomes
- **n_bidders**: Primary outcome, but coverage varies
- **Ukraine**: Best coverage (mandatory reporting)
- **Colombia**: Partial (reconstruct from bids extension)
- **UK**: Poor (alternative: single-bid rate proxy)

---

## Data Sources

### Ukraine (ProZorro)
- **Registry Entry**: https://data.open-contracting.org/en/publication/154
- **API Documentation**: https://api.prozorro.gov.ua/api/2.5/docs
- **OCDS Extensions**: bids, complaints, qualificationRequirements
- **Access Date**: [TO BE FILLED ON DOWNLOAD]

### Colombia (SECOP II)
- **Registry Entry**: https://data.open-contracting.org/en/publication/29
- **Data Portal**: https://www.colombiacompra.gov.co/transparencia
- **Classification**: UNSPSC → CPV mapping required
- **Access Date**: [TO BE FILLED ON DOWNLOAD]

### UK (Contracts Finder)
- **Implementation Guide**: https://assets.publishing.service.gov.uk/media/5e99b67dd3bf7f0318cff3b8/Guide-to-Open-Contracting-Data-Standard-implementation-on-Contracts-Finder-V.2.1.pdf
- **API Endpoint**: https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS
- **Threshold**: £12,000 (contracts below not published)
- **Access Date**: [TO BE FILLED ON DOWNLOAD]
