# Global Contestability Atlas (Publication Plan Item 5)

**Script:** `scripts/figures/global_contestability_atlas.py`
**Figure:** `NC_Submission/Main_Figures/Fig5_global_atlas.{pdf,png}`
**Data:** `results/cross_continental/global_atlas_data.json`

Addresses the plan's Item 5 (global scope / equity gap; the lever for re-targeting Nature
Sustainability) at the descriptive level the plan envisioned.

- **Panel A — global contestability landscape:** single-bidder rates for **43 countries across 6
  world regions** (OECD Government at a Glance 2023), sorted and region-coloured. Places the EU
  result in a genuinely global context: the contestability deficit is highest in Turkey (45%),
  Poland (42%), Italy (40%), Mexico (38%) and lowest in Chile (15%), Finland/Germany (16%). This
  directly answers the "why 26 of 27 European" critique.
- **Panel B — carbon-weighted single-bidder exposure:** for the 27 systems with carbon microdata,
  the share of carbon-intensity-weighted public spending that is single-sourced
  ($\sum_s \text{value}_s\,\text{carbon}_s\,\text{SB}_s / \sum_s \text{value}_s\,\text{carbon}_s$),
  ranging Poland 30.7% to Colombia 1.2%. This is the quantity GPP cannot reach.

**Live acquisition (scaled).** Contract-level data were streamed directly from the **Ukraine ProZorro**
OCDS API and aggregated on the fly (disk-safe; no bulk storage, host 93% full). Pilot script:
`scripts/pipeline/acquire_global_streaming.py`; scaled (concurrent) script:
`scripts/pipeline/acquire_prozorro_scaled.py`; output `results/cross_continental/acquired_global_systems.json`.
- **Ukraine (scaled): 60,001 contracts** across 46 CPV divisions, overall non-competitive rate 73.8%
  (procurement-method proxy: `reporting`/`negotiation`/`priceQuotation` = non-competitive),
  **carbon-weighted non-competitive exposure 60.0%** — plotted in Panel B (hatched, marked `*`). The
  2,161-contract pilot's 33% was unrepresentative; the 60k sample is the reliable figure.
- Paraguay (DNCP) attempted; its OCDS release-package endpoint needs deeper per-OCID integration. The
  scaled extractor (ThreadPool, time-boxed, disk-safe) is reusable for further systems (Chile, Mexico,
  Moldova, Georgia, …): one parser function + one FX entry each.

**Honest limitation.** Full carbon microdata still covers mainly EU systems + Colombia + (now) Ukraine,
so Panel B remains EU-weighted and the Ukraine point is a method proxy (direct/`reporting` awards), not
a like-for-like single-bidder rate. The global breadth in Panel A is the OECD aggregate indicator. A
full NS-grade global carbon atlas would harmonise more Global South OCDS systems (Chile, Mexico,
Moldova, Georgia, Kenya, Nigeria, India, …) via the same streaming extractor.

**Venue implication.** With the measured-carbon link null (Item 3) and the atlas descriptive, the
realistic targets remain Nature Communications or One Earth; a fully carbon-harmonised global atlas
would be the strongest single addition to re-open the Nature Sustainability route.

**HELD BACK from the NC submission (2026-06-12).** The atlas is deliberately NOT integrated into the
Nature Communications manuscript: it is not load-bearing for the competition-first NC paper, Panel B is
still EU-weighted with one method-proxy non-EU system, and it is the Nature Sustainability lever, better
done across many systems in a follow-up. The figure therefore lives at
`results/cross_continental/figures/Fig5_global_atlas.{pdf,png}` (moved out of `NC_Submission/Main_Figures/`),
and the atlas script writes there, not into the submission bundle. The NC cover letter and presubmission
inquiry do not mention it, so the submission package is self-consistent. To integrate it later (for an NS
submission) requires: a figure block, a Cross-Context paragraph, a Methods acquisition note, and a
ProZorro entry in Data Availability.
