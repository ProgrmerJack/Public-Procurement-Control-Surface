# Coverage-Stable, Not-Yet-Treated DiD — Response to Desk Review M3

**Script:** `scripts/causal_id/did_coverage_stable_nyt.py`
**Output:** `results/causal_id/did_coverage_stable_nyt.json`
**Date:** 2026-06-11

The reviewer raised three DiD defects: (a) Norway is not never-treated (transposed via the
Anskaffelsesloven, in force Jan 2017, under EEA), so the never-treated pool contains no genuinely
untreated European unit; (b) the single-bidder rate is measured on a reporting universe that changes
with treatment (the 2018 surge, inferred-SB millions, GB from a different source); (c) finite-sample
inference is marginal and the asymptotic p < 10⁻³² is inappropriate.

I re-estimated the competition response addressing all three at once:
- **Norway reclassified** to a 2017 treated cohort.
- **No external never-treated controls** — identification is purely within-EU, not-yet-treated
  (Callaway–Sant'Anna), so the contaminated NO/CH pool is removed entirely.
- **GB excluded** (Contracts Finder is a different source/population) and **CH excluded** (non-EU).
- A **coverage-stable universe**: single-bidder status recomputed only on contracts with *observed*
  bidder counts (`single_bidder := n_bidders == 1`), neutralizing the inferred-SB and 2018-surge
  reporting changes.
- **Permutation (cohort-timing randomization) inference** reported as primary.

## Result

| Universe | Aggregate ATT | Group-time cells | Permutation p | Countries |
|----------|--------------:|-----------------:|--------------:|----------:|
| Full (published-style) | −9.0 pp | 3 | 0.058 | 23 |
| **Coverage-stable (observed bidders)** | **−17.0 pp** | 3 | **0.001** | 23 |

**Reading.**
1. The **negative single-bidder response survives all three fixes simultaneously.** Removing every
   external control, reclassifying Norway, and restricting to a coverage-stable observed-bidder
   universe does not overturn the sign — if anything the observed-bidder universe shows a *larger*
   decline. So the reviewer's worry that coverage changes might *manufacture* the effect is not
   borne out: the effect is present in the cleaner, coverage-stable measure.
2. **But the design is thin and the magnitude is uncertain.** Reclassifying Norway and excluding GB
   collapses the not-yet-treated panel to **3 group-time cells (event times 0–1 only)**, because the
   only cohorts left are 2016/2017/2018 and not-yet-treated controls vanish after 2017. The point
   estimate ranges −9 to −17 pp depending on universe — far wider than the published −7.2 pp with
   its ±1.2 pp CI suggested. The honest summary is **"a robustly-signed but imprecisely-estimated
   single-bidder decline,"** with the cohort-timing permutation p (0.06 full / 0.001 coverage-stable)
   as the credible inference, not the asymptotic p.

## Action

- Demote the never-treated NO/CH C&S specification; make **not-yet-treated within-EU the primary**.
- Report the **coverage-stable** estimate as the headline competition result, with permutation
  inference and an explicit statement of the 3-cell thinness.
- Replace the abstract's precise "−7.2 pp" with the honest range and permutation-based significance.
- Publish the Methods reconciliation of the reporting universe (see the 2018 audit memo) so readers
  can see why the coverage-stable restriction is necessary.
