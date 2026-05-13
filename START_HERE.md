# START HERE: Quick Guide for Editors and Reviewers

**Paper:** Governance Reform Unlocks Decarbonization Dead Zones in Public Procurement

**Author:** Abduxoliq Ashuraliyev | jack00040008@outlook.com | ORCID: [0009-0003-5482-5526](https://orcid.org/0009-0003-5482-5526)

**Target:** Nature Sustainability (Article)

**Resources:**
- **GitHub:** https://github.com/ProgrmerJack/Public-Procurement-Control-Surface
- **Zenodo:** https://doi.org/10.5281/zenodo.20098951
- **License:** MIT (code) / CC-BY-4.0 (data)

---

## Verify All Claims in One Command

```bash
# Clone and setup
git clone https://github.com/ProgrmerJack/Public-Procurement-Control-Surface.git
cd Public-Procurement-Control-Surface
pip install -r requirements.txt

# Download Data.zip from Zenodo and extract it at repository root
# https://doi.org/10.5281/zenodo.20098951

# Verify ALL 36 claims
python verify_all_claims.py
```

**Expected output:**
```
VERIFICATION SUMMARY
================================================================================
Total claims verified: 36/36
Pass rate: 100.0%

✓ ALL CLAIMS VERIFIED - Results are reproducible
```

---

## Key Documents

| Document | Purpose |
|----------|---------|
| `verify_all_claims.py` | **Run this** - Verifies all 36 manuscript claims |
| `CLAIMS_INDEX.md` | Maps every claim to source code and result files |
| `VERIFICATION_RESULTS.json` | Detailed PASS/FAIL for each claim |
| `REPRODUCE.md` | Full reproduction guide |
| `README.md` | Complete documentation |

---

## The One-Sentence Summary

Single-bidder contracts exhibit **14.8% higher carbon intensity** globally but **-4.3% in reformed EU contexts** (N = 21.6 million, 27 countries), demonstrating that governance reform unlocks "decarbonization dead zones" where lack of competition locks in high-carbon suppliers.

---

## Key Claims and Verification

| Category | Key Claim | Verified By |
|----------|-----------|-------------|
| **Sample** | 21.6M contracts, 27 countries | `verify_all_claims.py` → Claim 1.1 |
| **Simpson's Paradox** | Global +14.8% vs EU -4.3% | `verify_all_claims.py` → Claims 1.2-1.4 |
| **U-Curve** | Small +50%, Large -7.8% | `verify_all_claims.py` → Claims 2.1-2.2 |
| **Causal (DiD)** | r=-0.55 dose-response, placebo passes | `verify_all_claims.py` → Claims 3.1-3.5 |
| **RDD** | +15.2% bidders, -0.33% carbon at threshold | `verify_all_claims.py` → Claims 4.1-4.3 |
| **Within-Sector** | Eurostat, E-PRTR, EU ETS all confirm | `verify_all_claims.py` → Claims 5.1-5.5 |
| **Cross-Continental** | US r=0.55, Canada d=-0.56, Australia d=0.19 | `verify_all_claims.py` → Claims 6.1-6.3 |
| **Policy** | Dead Zone carbon equals 3–6% of Paris-aligned reductions | `verify_all_claims.py` → Claims 8.1-8.2 |

---

## Comprehensive Claim Tracing

For detailed mapping of **every claim** to its source code, see [`CLAIMS_INDEX.md`](CLAIMS_INDEX.md):

- **Part A**: 193 manuscript claims (M1–M193) across 14 sections, each mapped to script + result file + JSON key
- **Part B**: 30 SI sections (B1–B30) covering 500+ supplementary claims with full traceability
- **Part C**: Data files required for reproduction
- **Part D**: Verification workflow (one-command verification)
- **Part E**: Complete script directory guide (137 scripts categorized)

---

## Project Structure

```
Public-Procurement-Control-Surface/
├── NC_Submission/                    # Nature Sustainability submission
│   ├── manuscript.tex                # Main manuscript
│   └── Supplementary_Information/    # Extended methods (30 SI sections)
│
├── Data/processed/
│   └── gprd_with_carbon.parquet      # Main dataset (21.6M contracts)
│
├── scripts/                          # ~130 scripts organized in 20 subfolders
│   ├── causal_id/                    # DiD, synthetic control (10)
│   ├── within_sector/                # Within-sector evidence (7)
│   ├── cross_continental/            # US, AU, CA analysis (5)
│   ├── projections/                  # Forward scenarios (4)
│   ├── reanalysis/                   # 12 numbered robustness checks
│   ├── lib/                          # Reusable library modules (4)
│   └── ...                           # 14 more categories
│
├── results/                          # 86 result files organized by category
│   ├── causal_id/                    # DiD results
│   ├── within_sector/                # Within-sector results
│   ├── figures/                      # Publication-ready figures
│   └── ...                           # 11 more categories
│
├── verify_all_claims.py              # ← RUN THIS (unified verification)
├── CLAIMS_INDEX.md                   # Claim → Code mapping
├── VERIFICATION_RESULTS.json         # Verification output
│
├── README.md                         # Full documentation
├── REPRODUCE.md                      # Detailed reproduction guide
└── START_HERE.md                     # This file
```

---

## For Any Questions

- **Issues:** https://github.com/ProgrmerJack/Public-Procurement-Control-Surface/issues
- **Email:** jack00040008@outlook.com

---

*All materials are publicly available without access restrictions.*
