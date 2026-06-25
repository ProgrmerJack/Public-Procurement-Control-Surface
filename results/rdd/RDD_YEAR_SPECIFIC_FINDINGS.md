# RDD Reanalysis with Year-Specific Thresholds — Response to Desk Review M4

**Script:** `scripts/rdd/rdd_year_specific_thresholds.py`
**Output:** `results/rdd/rdd_year_specific_thresholds.json`
**Date:** 2026-06-11

The reviewer showed the published RDD cutoff (fixed €139,000, 2012–2023) is **legally
incorrect**: the EU central-government supplies/services threshold is revised biennially and
€139,000 was operative for only two of twelve sample years; it also applies only to central-
government supplies/services (sub-central ≈ €214k; works ≈ €5.35M). I rebuilt the design with
year-specific thresholds and tested the competing cutoffs.

## Bidder-count discontinuity (additional bidders at cutoff)

| Design | Primary τ (±0.10) | MSE-optimal τ | Grid sign | N (primary) |
|--------|------------------:|--------------:|-----------|------------:|
| **Published** (fixed €139k, incl. works) | +0.324 (p<0.001) | +0.148 (p=0.029) | 0/26 neg, 25/26 sig | 553,293 |
| **Corrected** (year-specific central, S&S only) | +0.249 (p<0.001) | **+0.046 (p=0.60, ns)** | 0/26 neg, 22/26 sig | 491,440 |
| Sub-central cutoff (year-specific ≈€214k band) | **−0.410 (p<0.001)** | −0.502 (p<0.001) | 26/26 neg | 539,598 |
| Placebo (fixed €139k, S&S only) | +0.333 (p<0.001) | +0.280 (p<0.001) | 0/26 neg, 24/26 sig | 488,777 |

**Reading.**
1. The published harness is reproduced exactly (row 1 matches manuscript M82/M82a).
2. Under the **correct year-specific central threshold**, the MSE-optimal (data-preferred)
   bidder effect **collapses to +0.046 and loses significance** (p=0.60). The headline +0.32 was
   inflated by the misplaced fixed cutoff.
3. At the **sub-central cutoff** — which an unknown share of contracts actually face, because the
   data carry no buyer-type field — the discontinuity is **negative** (−0.41 to −0.50). Two legal
   cutoffs with opposite-signed jumps are superimposed in a single running variable.
4. A **placebo fixed €139k cutoff** is itself "significant" in years when €139k was *not* the legal
   threshold, indicating the contrast reflects value-composition/heaping near the data's mass
   rather than a sharp legal discontinuity.

## Carbon-intensity discontinuity

Remains small and bandwidth-/design-sensitive throughout (year-specific central: τ≈−0.012 but this
flips and shrinks under other cutoffs; sub-central: ns). No stable causal carbon effect at any
threshold.

## Conclusion and action

The RDD is **not identified as a disclosure-threshold design** given the data:
- the legally correct year-specific cutoff yields an insignificant data-preferred bidder effect;
- the unobserved central/sub-central split superimposes opposite-signed discontinuities;
- a placebo cutoff is also significant.

**Recommended action (matching the reviewer):** demote the RDD from a headline causal "first-stage"
result to, at most, a descriptive near-threshold sensitivity — or drop it. The abstract's
"+0.32 additional bidders" claim should be removed. If retained, it must (a) use year-specific
thresholds, (b) restrict to supplies/services, and (c) state explicitly that buyer-type is
unobserved so the estimate is not a clean threshold effect.
