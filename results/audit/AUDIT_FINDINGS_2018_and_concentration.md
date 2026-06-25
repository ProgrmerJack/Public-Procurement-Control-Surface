# Data-Integrity Audit — Response to Desk Review M5(a) and M5(b)

**Scripts:** `scripts/reanalysis/audit_data_integrity.py`, `scripts/reanalysis/audit_data_integrity_stage2.py`
**Outputs:** `results/audit/data_integrity_audit.json`, `results/audit/data_integrity_audit_stage2.json`
**Dataset audited:** `Data/processed/gprd_with_carbon.parquet` (21,612,129 rows)
**Date:** 2026-06-11

The reviewer flagged the 2018 surge as "sufficient grounds for desk rejection" and the
supplier concentration as "symptomatic of supplier-identifier failures." Both concerns are
**confirmed**. This memo documents what the audit found and the corrective actions taken.

---

## M5(a) — The 2018 surge is real in the data and is largely an artifact

EU-context annual contract counts (country ≠ CO):

| Year | EU-context rows | Distinct-ocid (dedup ceiling) |
|------|----------------:|------------------------------:|
| 2012 | 354,958 | 515,153¹ |
| 2013 | 363,702 | 687,204 |
| 2014 | 357,805 | 831,935 |
| 2015 | 368,390 | 897,392 |
| 2016 | 506,762 | 1,062,532 |
| 2017 | 762,360 | 1,358,959 |
| **2018** | **5,793,300** | **4,209,206** |
| 2019 | 983,068 | 1,529,982 |
| 2020 | 994,896 | 1,520,016 |
| 2021 | 1,060,731 | 1,496,624 |
| 2022 | 1,057,338 | 839,578 |
| 2023 | 1,035,623 | 578,464 |

¹ Distinct-ocid counts are over all countries per year, so they can exceed the EU-context row count.

**Findings.**
- 2018 is **7.1× the mean of adjacent years** (2016/17/19/20) and accounts for **26.8% of the
  entire dataset**. This is implausible for genuine award volume: TED publishes on the order of
  a few hundred thousand to ~1M contract-award notices per year EU-wide, consistent with the
  non-2018 rows but not with 5.79M.
- The surge is **spread across many countries** (PL 1.17M, FR 1.02M, ES 0.64M, IT 0.41M,
  DE 0.35M, …), so it is not a single-country import bug.
- **`record_id` is unique** (no exact row duplication), but 2018 carries a **37.7% duplicate-`ocid`
  rate** (2.55M rows sharing an OCID) versus ~19–22% in 2017/2019.
- **Deduplicating by OCID does not resolve the surge:** 2018 still collapses to 4.21M distinct
  OCIDs versus ~1.0–1.5M in adjacent years (≈3–4× anomalous).
- The cause is not a single clean mechanism (it is not pure exact-duplication, nor pure
  OCID-duplication, nor pure date-snapshot multiplication — `tender_date` coverage is poor in
  *several* years, so date-null is not a 2018-specific signal). It is consistent with a **bulk
  back-load / lot-row explosion** affecting the 2018 vintage.

**Action taken / required.**
1. The N = 21.6M headline and every pooled (cross-year) estimate are **not trustworthy until the
   2018 vintage is reconciled against official TED annual CAN statistics.** This is precondition
   zero (agreeing with the reviewer).
2. All causal designs are being re-run on a **coverage-stable universe** that does not let the
   2018 vintage dominate the post-period (see DiD task: above-threshold CANs with observed bidder
   counts; year weighting; 2018 sensitivity drop).
3. The Methods/SI must publish the annual-count reconciliation table above against TED official
   statistics and state explicitly how 2018 is handled.

---

## M5(b) — Supplier concentration is an identifier-failure artifact, now corrected

The headline concentration figures ("57% of contracts to 500+-contract suppliers"; "65% to 11+
repeat pairs") are **artifacts of placeholder supplier identifiers**, chiefly the literal string
`"nan"`.

| Metric | As originally computed | After removing placeholder IDs |
|--------|-----------------------:|-------------------------------:|
| Contracts with **no usable** supplier_id | (under-counted: 20.7% via `isna` only) | **54.8%** (11,841,281 rows) |
| — of which the literal string `"nan"` | — | 7,307,469 rows (33.8% of dataset) |
| Contracts to **500+-contract** suppliers | 36.8% | **2.7%** of full dataset |
| Contracts in **11+ repeat** buyer–supplier pairs | 44.7% | **11.1%** of full dataset |

The single pseudo-supplier `"nan"` held **7.31M contracts** — more than any real firm by three
orders of magnitude. Once placeholders (`nan`, empty, `0`, `1`, ≤2-char codes) are excluded, real
supplier concentration is unremarkable (top valid supplier ≈ 11.7k contracts).

**Implication for downstream claims.** Every supplier-level result inherits this contamination and
must be re-estimated on the **valid-identifier subsample only** (≈45% of contracts,
non-randomly selected — a limitation that must be stated):
- relationship lock-in "+54.5%" (11+ repeat transactions),
- supplier experience / learning curve,
- within-supplier premium "−0.87%" (39,410 firms),
- supplier market-power gradient (SI Table S18).

Until re-run, these claims should be removed from the abstract/Discussion or explicitly flagged as
contaminated.

---

## Bottom line

Both M5(a) and M5(b) are upheld by direct inspection of the deposited data. The corrective program
is: (1) reconcile 2018 against official TED statistics and publish the table; (2) re-run all causal
designs on a coverage-stable universe; (3) re-run all supplier-level analyses on valid-ID contracts
only, with the 45% coverage caveat stated. Items (2) and (3) are addressed in the accompanying
reanalysis tasks.
