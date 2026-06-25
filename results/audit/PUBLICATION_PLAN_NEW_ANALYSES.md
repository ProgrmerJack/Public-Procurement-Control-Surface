# New Analyses for the Publication Plan (Items 1, 3, 4, 6)

**Date:** 2026-06-11. All scripts run from repo root against deposited data.

These four analyses determine the paper's claims and venue. Bottom line: the surviving
contribution is **competition-first** — the measured-carbon link and the RDD do not survive,
which (per the plan's fallback ladder) points to **Nature Communications / a field split**, not
Nature Sustainability, unless a global atlas (Item 5) carries the sustainability framing.

## Item 1 — TED reconciliation (gate) — PASSED
`scripts/reanalysis/ted_reconciliation.py` → `results/audit/ted_reconciliation.json`
- The 2018 surge originates in the **raw harmonized TED layer** (13.9M rows / 9.37M distinct OCIDs
  vs ~1.4M in 2017, ~2.3M in 2019 = 7.4× adjacent) — a corrupted bulk-load vintage.
- **Headline EU premium is stable when 2018 is dropped:** pooled −4.31%→−4.39%; country-FE
  −4.76%→−4.70% (cluster-robust t≈−3.1 both). The headline does not depend on the corrupted vintage.
- Action: publish the annual-count table (official TED CAN column to be filled from ted.europa.eu);
  report headline on the 2018-dropped panel as primary robustness.

## Item 3 — E-PRTR size-stratified intensity — NULL (decision-critical)
`scripts/within_sector/eprtr_size_stratified_intensity.py` → `results/within_sector/eprtr_size_stratified_intensity.json`
- Absolute (published-style) premium reproduces and is large: **+149.9%** (t=30.4).
- **Within emission deciles: −0.1%. Within sector×decile: +0.3%. Within-decile log-CO₂ SB
  coefficient: +0.4%.** The gap collapses to zero once facility size is controlled.
- **The "+65.3% directly validates in measured emissions" claim is a facility-size composition
  artifact.** Single-bidding does not select dirtier facilities of comparable scale. There is no
  measured within-sector carbon link. → Remove the claim; paper stays competition-first.

## Item 4 — Legally-correct RDD (buyer-type) + diff-in-disc — RDD DEAD
`scripts/rdd/rdd_buyer_type_year_specific.py`, `scripts/rdd/diff_in_disc_threshold_move.py`
- The harmonized TED **does** carry `buyer_type` and `contract_type` (correcting the earlier "no
  buyer-type field" note). Central-government vs sub-central RDDs at year-specific cutoffs were run.
- **Every cutoff — real and placebo — is significant, with inconsistent signs** (central at central
  cutoff: MSE +0.03 ns; central at sub-central placebo: −1.03 sig; sub-central at its own cutoff:
  −1.35 sig). The local-linear RDD picks up bidder-count-vs-value curvature, not a legal jump.
- The diff-in-discontinuities on the 2019→2020 threshold move (€144k→€139k) has tiny bands
  (~1,200 contracts), inconsistent signs, and data-quality outliers (a control band's mean bidder
  count jumps to 30.8). DiD vs always-above: +3.7pp (p=0.09, wrong sign); vs never-below: null.
- **Verdict: no clean second causal design is recoverable. Drop the RDD entirely.** The paper rests
  on one causal design (the coverage-stable DiD on single-bidding).

## Item 6 — Supplier analyses on valid IDs — PARTIALLY SURVIVE
`scripts/reanalysis/supplier_valid_id_rerun.py` → `results/audit/supplier_valid_id_rerun.json`
- Valid-ID EU-context contracts = 2.59M (19.0%; non-random — caveat).
- **Within-supplier premium reproduces: −0.85%** (published −0.87%), 39,375 suppliers, p=3e-9. It
  was never contaminated (the both-regimes requirement already excluded the "nan" pseudo-supplier).
- **Relationship lock-in survives but attenuates: +34.5%** (published +54.5%), t=209. Real but the
  +54.5% headline was inflated by placeholder IDs.
- Action: return both to the SI with the valid-ID caveat; correct the lock-in magnitude to +34.5%.

## Net effect on the paper
- **Keep:** coverage-stable DiD (competition), Dead Zone descriptive map, within-supplier −0.85%,
  attenuated lock-in +34.5%, premium as allocative composition (country-FE robust in sign).
- **Cut:** RDD entirely; E-PRTR-as-measured-validation; governance-gradient narrative (refuted,
  ρ=+0.33); "95% CI < ±0.2 pp" precision.
- **Venue:** competition-first → Nature Communications most realistic (fallback #2); a genuinely
  global Dead Zone atlas (Item 5) would be required to re-target Nature Sustainability.
