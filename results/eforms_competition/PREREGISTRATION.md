# Pre-registration — eForms "does competition select greener winners?" (committed before the battery)

Written **before** running the size/incumbency-controlled, firm-clustered, reweighted analysis,
so the decision cannot be rationalised after the fact. This project's track record (the −17 pp
artifact, the RDD) demands it.

## Primary test (ONE test)
**Continuous** within-tender interaction of bidder greenness × sector carbon intensity on the
probability of winning, identified within tender (choice-set fixed effects), **with bidder-level
controls for firm size and incumbency/prior-win history**, and **standard errors clustered by
firm**. Direction is **one-sided** (H1: greener bidder wins *more* as sector carbon rises).

NOT the high/low subset split (that is illustration only). NOT the overall effect (reported up
front; it is a null, OR≈1.02).

## Decision rule (committed)
- **If** the primary interaction is positive at **p < 0.05 (one-sided)** *after* bidder size +
  incumbency controls, firm-clustered SEs, **and** on a representativeness-reweighted sample,
  **and** it is not driven by a handful of firms/one country (leave-one-firm-out stable; ≥~30
  distinct firms in the green-win cell; not >50% from one country)
  → it becomes the **headline**; integrate across the manuscript; target Nature Communications.
- **Else (attenuates below p<0.05, or fails representativeness/concentration/placebo)**
  → reported **honestly as suggestive**; the paper stays Path C (JAERE/JPubE + Scientific Data);
  the eForms first-look becomes a "competition is green-neutral overall, suggestive in high-carbon"
  supporting result.

## Mandatory checks (all reported regardless of outcome)
1. Bidder-level **size** control (firm activity = # tenders the firm bids in) + **incumbency**
   (firm prior win-rate), within tender.
2. **Firm-clustered** SEs (linear within-tender model; repeated firms reduce effective N below
   the 2,601 tender count).
3. **Representativeness**: compare identified tenders vs all eForms award notices on country,
   CPV, value; reweight to the population and re-estimate.
4. **Concentration**: # distinct firms driving the SBTi green-win cell; leave-one-firm-out.
5. **Placebo** green attribute (random flag, same marginal rate) → must give ≈null.
6. **Signal sensitivity**: SBTi-only vs EUTL/E-PRTR-only.
7. **Disclosure provenance**: confirm the ranked bid set is *disclosed* in eForms (efac:LotTender
   / RankCode / TenderingParty parsed directly), not inferred; document country/time coverage.

## Scope honesty (stated in the paper regardless)
The within-tender design identifies **who wins among observed bidders in already-competitive
tenders**. It does **not** identify the counterfactual of *creating* competition in a currently
single-bidder Dead Zone. The policy reading ("opening Dead Zones would select greener suppliers")
is an extrapolation across the contestability margin and will be labelled as such.
