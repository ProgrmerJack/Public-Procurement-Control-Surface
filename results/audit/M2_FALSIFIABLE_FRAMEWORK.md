# Falsifiable Governance Framework — Response to Desk Review M2

**Script:** `scripts/reanalysis/falsifiable_governance_test.py`
**Output:** `results/audit/falsifiable_governance_test.json`
**Date:** 2026-06-11

M2 charged that the interpretive framework is unfalsifiable: a *negative* premium is read as
governance success and a *positive* premium as a "Brown Monopoly" awaiting reform, so any sign
confirms the theory. The fix M2 demanded: an ex-ante, sign-predicting rule tied to a measured
institutional variable, plus a stated refuting configuration — tested symmetrically.

## Pre-registered rule and refutation band

- **Ex-ante rule (H1):** across countries, the single-bidder carbon premium is *decreasing* in
  institutional quality — corr(premium, Rule of Law) < 0 (better governance ⇒ more-negative
  premium, because competition has entered higher-carbon sectors).
- **Refuting configuration (stated in advance):** ρ ≥ 0 (better-governed countries have *more
  positive* premiums) **OR** one-sided p > 0.05 (no detectable gradient). Either refutes the claim.

## Result — the rule is REFUTED

| Statistic | Value |
|-----------|------:|
| Countries | 26 |
| Spearman ρ(premium, Rule of Law) | **+0.325** |
| One-sided p (predicted negative direction) | 0.947 |
| Pearson r | +0.354 |

The governance gradient runs in the **opposite direction** to the manuscript's claim: better-governed
countries (Nordics, Netherlands, Germany) tend to have *more positive* premiums, not more negative
ones. The manuscript had already noticed this ("several high-capacity outliers remain positive") but
dismissed it; formalized as a pre-registered test, it **refutes** the governance-contingency reading
of the carbon premium.

(WGI Rule-of-Law values are 2018 point estimates entered for this test and flagged for replacement
with the official WGI download; the test is a rank correlation, robust to small value errors. A
+0.33 rank correlation will not flip to a significant negative under any plausible value revision.)

## Internal contradiction also resolved against the story

The manuscript narrates **both** directions as success: a *more*-negative premium ("signature of
governance reform") and a *66% post-reform narrowing toward zero* ("convergence success"). It also
reports the premium as **most negative in 2013** (−8.4%), *before* Directive 2014/24 existed, then
*attenuating* after reform (−2.9% by 2019). A signature that predates the cause and shrinks after it
is not a treatment signature. Combined with the refuted governance gradient, the honest conclusion is
that the **sign and time-path of the carbon premium are not governed by the reform.**

## Action taken

1. **Demote the carbon premium** from a governance-success outcome to what it is: a between-sector
   allocative composition measure (M1 shows it is exactly 0 within country×sector). It is a
   *classification weight* (which markets are carbon-relevant), not a treatment outcome.
2. **Reframe the paper around the competition result** (single-bidding DiD), which survives scrutiny;
   carbon intensity defines the *stakes* (which uncontestable markets matter for climate), not the
   identified effect. Title and abstract rewritten accordingly.
3. **Drop the sign-flexible narration.** The "negative = success / convergence = success" framing and
   the cross-continental "Brown Monopoly" sign-matching are removed; the one falsifiable governance
   prediction is reported with its (negative) result.
