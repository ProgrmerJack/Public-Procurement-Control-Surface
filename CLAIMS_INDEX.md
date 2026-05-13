# Claims Index: Manuscript & SI Claim Traceability

The principal quantitative claims in the manuscript and all 30 substantive SI sections are traced below to their
producing script and result file. Reviewers can independently verify each mapped finding by running
the indicated script or inspecting the indicated JSON key. External literature claims and scenario assumptions
are mapped to their cited source or parameter file where no repository computation is expected.

**Unified verification**: run `python verify_all_claims.py` from repository root to
check 36 core claims automatically (36/36 PASS). Claims beyond those 36 are traceability-mapped
to scripts/result files below, but are not all asserted by the unified verifier.

---

## Master Quick Reference

| Domain | Manuscript § | SI § | Primary Script(s) | Result File(s) |
|--------|-------------|------|-------------------|----------------|
| Sample & descriptives | Results ¶1-2 | 1-4 | `verify_all_claims.py` | Direct from parquet |
| Carbon premium (EU) | Results ¶1-2 | 4, 23 | `verify_all_claims.py` | Direct computation |
| U-curve (size bands) | Results ¶3 | 4 (Table S4) | `verify_all_claims.py` | Direct computation |
| Country heterogeneity | Results ¶2 | 4 (Table S5) | `scripts/mechanism/comprehensive_final_analysis.py` | `results/core_stats/comprehensive_analysis_results.json` |
| Dead zones | Results ¶4-5 | 9 | `scripts/dead_zones/analyze_dead_zones.py`, `scripts/dead_zones/eu_dead_zones_recompute.py` | `results/dead_zones/dead_zones_reform_analysis.json`, `results/dead_zones/dead_zone_sensitivity.json`, `results/dead_zones/eu_context_dead_zones.json` |
| DiD (staggered) | Results ¶6 | 7 | `scripts/causal_id/staggered_did.py`, `scripts/causal_id/callaway_santanna.py`, `scripts/causal_id/cs_not_yet_treated.py` | `results/causal_id/staggered_did.json`, `results/causal_id/callaway_santanna.json`, `results/causal_id/cs_not_yet_treated.json` |
| Dose-response placebo | Results ¶6 | 7 | `scripts/causal_id/dose_response_placebo.py` | `results/causal_id/dose_response_placebo.json` |
| Synthetic control | Results ¶6 | 7 | `scripts/causal_id/synthetic_control_did.py`, `scripts/causal_id/sc_permutation_inference.py` | `results/causal_id/synthetic_control_did.json`, `results/causal_id/sc_permutation_inference.json` |
| COVID & temporal | Results ¶7 | 5, 14 | `verify_all_claims.py` | Direct + `results/eu_ets/eu_context_si_tables.json` |
| RDD | Results ¶8 | 6 | `reproduce_data_comprehensive.py`, `verify_all_claims.py` | `results/core_stats/verified_statistics.json` + direct |
| Cross-context + Canada control | Results ¶9, SI §7 | 25 | `scripts/cross_continental/us_procurement_analysis.py`, `scripts/cross_continental/non_eu_procurement_analysis.py`, `scripts/robustness/control_expansion_analysis.py` | `results/cross_continental/us_procurement_analysis.json`, `results/cross_continental/australia_analysis.json`, `results/robustness/control_expansion_analysis.json` |
| Within-sector (Eurostat FDR) | Discussion ¶5 | 7, 26 | `scripts/mechanism/bridge_analysis.py` | `results/mechanism/bridge_analysis.json` |
| Within-supplier | Discussion ¶5 | 26 | `scripts/within_sector/within_supplier_analysis.py` | `results/within_sector/within_supplier_analysis.json` |
| E-PRTR facility | Discussion ¶5 | 7, 26 | `scripts/within_sector/eprtr_within_sector.py`, `scripts/within_sector/eprtr_procurement_matching.py` | `results/within_sector/eprtr_within_sector.json`, `results/within_sector/eprtr_procurement_matching.json` |
| EU ETS validation | Discussion ¶5 | 26 | `scripts/eu_ets/analyze_eu_ets.py` | `results/within_sector/eu_ets_within_sector_analysis.json` |
| SBTi selection | Discussion ¶8 | — | `scripts/validation/sbti_winner_matching.py` | `results/validation/sbti_winner_matching.json`, `results/other/sbti_selection_probability.json` |
| Mediation & confounding | Discussion ¶4 | — | `scripts/mechanism/mediation_trap_analysis.py` | `results/mechanism/mediation_trap_analysis.json` |
| Firm-level validation | Discussion ¶6 | — | `scripts/validation/firm_level_validation.py` | `results/validation/firm_level_validation.json` |
| Forward projections | Conclusion | 30 | `scripts/projections/forward_projection_model.py` | `results/projections/forward_projections.json` |
| Monte Carlo uncertainty | Conclusion | 30 | `scripts/projections/monte_carlo_uncertainty.py` | `results/projections/monte_carlo_uncertainty.json` |
| Monopoly tax / green premium | Discussion ¶7 | 28 | `scripts/projections/oecd_calibration.py` | `results/projections/oecd_calibrated_numbers.json` |

---

## Section 1: Sample and Basic Statistics

### Claim 1.1: Sample Size
- **Manuscript text**: "21.6 million contracts across 27 countries (2012-2023)"
- **Location**: Results, paragraph 1
- **Verification**: Direct count from `Data/processed/gprd_with_carbon.parquet`
- **Code**: `verify_all_claims.py`, function `verify_from_data()`, claim `1.1_sample_size`

---

# PART A: MANUSCRIPT CLAIMS

## A1. Sample & Descriptive Statistics

| # | Claim | Value | Manuscript Location | Script | Result File / Key |
|---|-------|-------|-------------------|--------|-------------------|
| M1 | Total contracts | 21,612,129 | Abstract; Results ¶1; Methods | `verify_all_claims.py` | Direct count from `Data/processed/gprd_with_carbon.parquet` |
| M2 | Countries | 27 | Abstract; Results ¶1 | `verify_all_claims.py` | Unique `iso_code` count |
| M3 | Time period | 2012–2023 | Abstract; Results ¶1 | `verify_all_claims.py` | Min/max `award_date.year` |
| M4 | EU-context contracts | 13,638,933 | Results ¶1 | `verify_all_claims.py` | Filter `iso_code != 'CO'` |
| M5 | EU-context countries | 26 | Results ¶1 | `verify_all_claims.py` | Unique non-CO iso_code |
| M6 | Colombia contracts | 7,973,196 | Results ¶2 | `verify_all_claims.py` | Filter `iso_code == 'CO'` |
| M7 | Colombia % of dataset | 37% | Results ¶2 | `verify_all_claims.py` | 7.97M / 21.6M |
| M8 | Procurement sectors (CPV) | 75 | Results ¶1 | `verify_all_claims.py` | Unique CPV division count |
| M9 | Global single-bidder rate | 11.0% | SI Table S2 | `verify_all_claims.py` | `single_bidder.mean()` |
| M10 | Bidder count missing rate | 28% (6.1M) | Methods | `verify_all_claims.py` | Null count in `n_bidders` |
| M11 | Colombian zero-bidder-count | 96.5% | Methods | `verify_all_claims.py` | CO contracts where `n_bidders==0` |

## A2. Carbon-Competition Gap (Global & EU)

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M12 | Global premium | +14.8% | Results ¶2 | `verify_all_claims.py` | T-test: SB vs MB carbon intensity, full dataset |
| M13 | Global t-statistic | 333.7 | Results ¶2 | `verify_all_claims.py` | `scipy.stats.ttest_ind` |
| M14 | Global Cohen's d | 0.23 | Results ¶2 | `verify_all_claims.py` | `(mean_sb - mean_mb) / pooled_sd` |
| M15 | EU-context premium | −4.3% | Results ¶1 | `verify_all_claims.py` | T-test excluding Colombia |
| M16 | EU t-statistic | −110 | Results ¶1 | `verify_all_claims.py` | T-test EU-only |
| M17 | EU Cohen's d | −0.08 | Abstract; Results ¶1 | `verify_all_claims.py` | EU-only effect size |
| M18 | SB carbon (EU) | 0.3405 kg CO₂e/USD | Results ¶1; SI Table S10 | `verify_all_claims.py` | Mean of `carbon_intensity_kgco2_per_usd` where `single_bidder==True` & non-CO; four-decimal SI display from `results/eu_ets/eu_context_si_tables.json` |
| M19 | MB carbon (EU) | 0.3558 kg CO₂e/USD | Results ¶1; SI Table S10 | `verify_all_claims.py` | Mean where `single_bidder==False` & non-CO; four-decimal SI display from `results/eu_ets/eu_context_si_tables.json` |
| M20 | Colombia SB premium | −2.3% | Results ¶2 | `verify_all_claims.py` | T-test CO-only |
| M21 | Colombia carbon intensity | 0.20 kg CO₂e/USD | Results ¶2 | `verify_all_claims.py` | Mean CO carbon |
| M22 | Colombia multi-bidder rate | 99.3% | Results ¶2 | `verify_all_claims.py` | 1 - SB_rate for CO |
| M23 | I² heterogeneity | 99.3% | Results ¶2 | `scripts/mechanism/comprehensive_final_analysis.py` | `results/core_stats/comprehensive_analysis_results.json` |

## A3. U-Curve (Contract Size Effect)

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M24 | Large contracts premium | −7.8% | Results ¶3 | `verify_all_claims.py` | Filter `contract_value > 200000`, non-CO, T-test |
| M25 | Large contracts d | −0.13 | Results ¶3 | `verify_all_claims.py` | Cohen's d for large |
| M26 | Small contracts premium | −2.8% | Results ¶3 | `verify_all_claims.py` | Filter `contract_value < 10000`, non-CO |
| M27 | Small contracts d | −0.05 | Results ¶3 | `verify_all_claims.py` | Cohen's d for small |
| M28 | Global small premium | +50.2% | SI Table S4 | `verify_all_claims.py` | Full-dataset, <10k |
| M29 | Global small d | +0.75 | SI Table S4 | `verify_all_claims.py` | Full-dataset effect size |
| M30 | Global large premium | −7.1% | SI Table S4 | `verify_all_claims.py` | Full-dataset, >200k |
| M31 | Crossover point | ~EUR 200,000 | SI Table S4 | `verify_all_claims.py` | Sign flip at 200k |

## A4. Dead Zones

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M32 | Carbon threshold (percentile) | 67th | Results ¶4 | `scripts/dead_zones/analyze_dead_zones.py` | `results/dead_zones/dead_zones_reform_analysis.json` |
| M33 | Carbon threshold (kg) | 0.25 kg CO₂e/USD | Results ¶4 | Same | `dead_zones.carbon_threshold` key |
| M34 | Cross-sector median SB rate | 7.4% | Results ¶4 | Same | `dead_zones.sb_rate_threshold` key |
| M35 | Dead zones (global thresholds) | 22 | Results ¶4 | `scripts/dead_zones/analyze_dead_zones.py` | `results/dead_zones/dead_zones_reform_analysis.json` → `dead_zones.n_dead_zone_sectors` |
| M36 | Dead zones (EU-context) | 6 | Results ¶4 | `scripts/dead_zones/eu_dead_zones_recompute.py` | `results/dead_zones/eu_context_dead_zones.json` → `eu_context.dead_zone_sectors` |
| M37 | Threshold combinations tested | 25 | Results ¶4 | `scripts/dead_zones/analyze_dead_zones.py` | Grid of 5×5 thresholds |
| M38 | DZ % of total spending | 51.5% | Results ¶4 | `scripts/dead_zones/analyze_dead_zones.py` | `results/dead_zones/dead_zones_reform_analysis.json` → `dead_zones.dead_zone_pct_of_total` |
| M39 | DZ % of contracts by count | 66% | Results ¶4 | Same | `dead_zones` sector counts / contract-count aggregation |
| M40 | Annual DZ spending (SB) | €190–250B | Results ¶4; Conclusion | `scripts/projections/oecd_calibration.py` | `results/projections/oecd_calibrated_numbers.json` |
| M41 | OECD EU procurement benchmark | €2 trillion | Results ¶4 | `scripts/projections/oecd_calibration.py` | OECD 2022 factbook |
| M42 | Strictest thresholds remaining | 2 sectors | SI §9 Table S14 | `scripts/dead_zones/analyze_dead_zones.py` | 80th/75th row in `results/dead_zones/dead_zone_sensitivity.json` |

### Dead Zone Sector Table (Results Table 1)

| CPV | Sector | Carbon (kg/$) | SB Rate | Value | Script |
|-----|--------|--------------|---------|-------|--------|
| 24 | Chemicals | 0.90 | 14.4% | €368B | `scripts/dead_zones/eu_dead_zones_recompute.py` |
| 77 | Ag/forestry | 0.85 | 15.0% | €1.32T | Same |
| 65 | Water | 0.60 | 21.2% | €972B | Same |
| 35 | Defence | 0.60 | 20.4% | €665B | Same |
| 15 | Food | 0.65 | 15.9% | €1.52T | Same |
| 33 | Medical | 0.30 | 24.0% | — | Same (Dead Zone under global thresholds; cited in manuscript table note as largest SB lock-in by reported value rather than top-five leverage) |

## A5. Causal Identification — Difference-in-Differences

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M43 | C&S aggregate ATT (contract-count weighted primary) | −7.2 pp | Results ¶6; Conclusion; SI §7 | `scripts/causal_id/callaway_santanna.py` | `results/causal_id/callaway_santanna.json` → `aggregate.att` |
| M43a | C&S aggregate ATT (same 30 cells, equal-weight) | −5.76 pp | SI §7 | `scripts/causal_id/cs_loo_controls.py` | `results/robustness/cs_loo_controls.json` → `both_controls.aggregate.att_pp` |
| M43b | C&S comparator bound excluding Switzerland | −4.75 pp | Results ¶6; SI §7 | `scripts/causal_id/cs_loo_controls.py` | `results/robustness/cs_loo_controls.json` → `norway_only.aggregate.att_pp` |
| M43c | C&S comparator bound excluding Norway | −8.46 pp | Results ¶6; SI §7 | `scripts/causal_id/cs_loo_controls.py` | `results/robustness/cs_loo_controls.json` → `switzerland_only.aggregate.att_pp` |
| M44 | C&S model-based p-value | 1.0×10⁻¹² | Results ¶6; SI §7 | Same | `aggregate.p_value` (reported with finite-sample RMSPE p in M62) |
| M45 | C&S 95% CI | [−8.4, −6.0] | SI §7 | Same | `aggregate.ci_lower/ci_upper` |
| M46 | Group-time cells | 30 | Results ¶6 | Same | `aggregate.n_cells` |
| M47 | Pre-trend slope | +0.02 pp/yr | Results ¶6 | `scripts/causal_id/staggered_did.py` | `results/causal_id/staggered_did.json` → `pre_trend_test.slope` |
| M48 | Pre-trend p | 0.71 | Results ¶6 | Same | `pre_trend_test.p_value` |
| M49 | Joint F-test | F=1.32, p=0.27 | Results ¶6 | Same | `pre_trend_test.f_stat/f_p` |
| M50 | Conventional TWFE ATT (NO/CH controls) | −0.71 pp | Results ¶6; SI §7 | `scripts/causal_id/staggered_did.py` | `results/causal_id/staggered_did.json` → `twfe_staggered.att_pp` |
| M51 | Conventional TWFE p | 0.57 | Results ¶6; SI §7 | Same | `twfe_staggered.att_p` |
| M52 | Conventional TWFE 95% CI | [−3.13, +1.72] | Results ¶6; SI §7 | Same | `twfe_staggered.ci_lower_pp/ci_upper_pp` |
| M55 | E-procurement mandate | Oct 18, 2018 | Results ¶6 | Same | `e_procurement.date` |
| M56 | E-procurement discontinuity | −0.8 pp | Results ¶6 | Same | `e_procurement.effect` |
| M57 | 2015 cohort countries | 1 (GB) | SI §7 | `scripts/causal_id/callaway_santanna.py` | `sample.treated_countries`; `group_time_att` |
| M58 | 2016 cohort countries | 13 | Results ¶6; SI §7 | Same | Group-time array filter |
| M59 | 2016 cohort effect range | −5.5 to −10.3 pp | Results ¶6; SI §7 | Same | Event-study coefficients |
| M60 | 2017 cohort countries | 6 | Results ¶6; SI §7 | Same | Group-time array filter |
| M60a | 2017 cohort initial effect | −4.1 pp | Results ¶6; SI §7 | Same | Event time 0 for 2017 cohort |
| M60b | 2018 cohort countries | 3 | SI §7 | Same | Group-time array filter |
| M60c | 2018 cohort effect range | −6.4 to −11.0 pp | SI §7 | Same | Event-study coefficients |
| M61 | RMSPE permutation rank | 1 of 24 | Methods; Conclusion | `scripts/causal_id/sc_permutation_inference.py` | `results/causal_id/sc_permutation_inference.json` → `eu_rmspe_rank`, `rmspe_n_total` |
| M62 | RMSPE permutation p | 0.042 | Abstract; Conclusion | Same | `rmspe_p_value` |
| M62a | Not-yet-treated C&S ATT (zero external controls) | −8.60 pp | Introduction ¶3; Results §DiD; Discussion (Limitations); SI §7 | `scripts/causal_id/cs_not_yet_treated.py` | `results/causal_id/cs_not_yet_treated.json` → `aggregate.att_pp` |
| M62b | Not-yet-treated C&S p-value | 0.012 | Introduction ¶3; Results §DiD; Discussion (Limitations); SI §7 | Same | `aggregate.p_value` |
| M62c | Not-yet-treated equal-weight ATT | −6.84 pp (p=0.004) | Results §DiD; SI §7 | Same | `equal_weight_aggregate.att_pp` |
| M62d | Not-yet-treated group-time cells | 6 | Results §DiD; SI §7 | Same | `aggregate.n_cells` |
| M62e | Not-yet-treated same-sign confirmation | True (−8.60 pp vs −7.18 pp) | Discussion (Limitations); SI §7 | Same | `comparison_to_primary.same_sign` |

### Dose-Response Placebo (Causal Identification)

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M63 | Post-treatment dose-response r | −0.560 | Results ¶6; SI §7 | `scripts/causal_id/dose_response_placebo.py` | `results/causal_id/dose_response_placebo.json` → `post_treatment.pearson_r` |
| M64 | Post-treatment p | 0.0029 | Results ¶6; SI §7 | Same | `post_treatment.pearson_p` |
| M65 | Pre-treatment placebo r | 0.065 | Results ¶6; SI §7 | Same | `pre_treatment_placebo.pearson_r` |
| M66 | Pre-treatment placebo p | 0.75 | Results ¶6; SI §7 | Same | `pre_treatment_placebo.pearson_p` |
| M67 | Fisher Z structural break p | 0.018 | Results ¶6; SI §7 | Same | `fisher_z_test.p` |

## A6. COVID & Temporal Patterns

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M68 | EU-context SB rate 2019 | 16.1% | Results ¶7 | `results/eu_ets/eu_context_si_tables.json`; `verify_all_claims.py` | `temporal_eu[year=2019].SB_rate` |
| M69 | EU-context SB rate 2020 | 15.4% | Results ¶7 | Same | `temporal_eu[year=2020].SB_rate` |
| M70 | EU-context SB rate 2022 | 16.8% | Results ¶7 | Same | `temporal_eu[year=2022].SB_rate` |
| M71 | EU-context SB rate 2023 | 18.6% | Results ¶7 | Same | `temporal_eu[year=2023].SB_rate` |
| M72 | SB increase 2019→2023 | +2.5 pp | Abstract; Results ¶7 | Same | 18.6% − 16.1% |
| M73 | EU-context premium 2019 | −2.9% | Results ¶7 | Same | `temporal_eu[year=2019].premium_pct` |
| M74 | EU-context premium 2020 | −1.6% | Results ¶7 | Same | `temporal_eu[year=2020].premium_pct` |
| M75 | EU-context premium 2023 | −3.5% | Results ¶7 | Same | `temporal_eu[year=2023].premium_pct` |
| M76 | Global premium pre-pandemic | +7.0% | Results ¶7 | Same | Period-filtered global T-test |
| M77 | Global premium acute crisis | +20.1% | Results ¶7 | Same | 2020-2021 period |
| M78 | Global premium post-pandemic | +0.3% | Results ¶7 | Same | 2022-2023 period |
| M79 | Composition effect | 100% of change | Results ¶7 | Same | Oaxaca-Blinder decomposition |

## A7. Regression Discontinuity Design

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M80 | EU threshold | €139,000 | Results ¶8 | `reproduce_data_comprehensive.py`, `verify_all_claims.py` | `results/core_stats/verified_statistics.json` |
| M81 | Primary log-window N | 553,293 contracts with observed bidder counts | Results ¶8 | `scripts/rdd/formal_rdd_estimator.py` | ±0.10 log10(value) window, local-linear |
| M81a | MSE-optimal bandwidth N | 380,938 contracts | Results ¶8 | Same | `results/rdd/formal_rdd_estimates.json` → `mse_optimal.bidder_count.n` |
| M82 | Local-linear RDD bidder count (primary) | τ = +0.324 (SE=0.056, p<0.001) | Results ¶8 | Same | `formal_rdd_estimates.json` → `primary.bidder_count` |
| M82a | Local-linear RDD bidder count (MSE-optimal) | τ = +0.148 (SE=0.068, p=0.029) | Results ¶8 | Same | `formal_rdd_estimates.json` → `mse_optimal.bidder_count` |
| M82b | Sign stability across grid | 0/26 bandwidths negative; 25/26 significant | Results ¶8 | Same | `formal_rdd_estimates.json` → `sensitivity_grid` |
| M83 | [LEGACY] Welch t-test bidder p | 7.5×10⁻²⁰ | SI (windowed comparison) | Same | Moved to SI; superseded by local-linear |
| M84 | [LEGACY] Primary carbon effect (Welch) | −0.33% | SI (windowed comparison) | Same | Moved to SI; superseded by local-linear |
| M85 | Local-linear carbon (primary, ns) | τ = +0.00073 kg/USD (p=0.538) | Results ¶8 | Same | `formal_rdd_estimates.json` → `primary.carbon_intensity` |
| M85a | Local-linear carbon (MSE-optimal) | τ = +0.00628 kg/USD (t=3.74, p=0.0002) | Results ¶8 | Same | `formal_rdd_estimates.json` → `mse_optimal.carbon_intensity` |
| M85b | Carbon sign stability | 19/26 bandwidths negative (mixed) | Results ¶8 | Same | bandwidth-sensitive carbon signal |
| M86 | Density-ratio stability test (manipulation check) | Ratio=1.12 at ±0.10 vs 1.48 at ±0.50 log-EUR; ratio decreases toward cutoff | Results ¶8 | `scripts/rdd/mccrary_density_test.py` | `results/rdd/mccrary_test.json` → `voluntary_disclosure_diagnostic.window_ratios`; decreasing ratio toward cutoff = opposite of manipulation spike |
| M86a | Raw above/below count ratio (±0.10 window) | 1.1210 (457,883 vs 408,443 within ±0.10 bandwidth) | Results ¶8 | Same | `mccrary_test.json` → `voluntary_disclosure_diagnostic.window_ratios[1]`; NOT a manipulation indicator |
| M87 | [LEGACY] Narrow bandwidth N | 408,928 | SI | Same | Moved to SI robustness |
| M88 | [LEGACY] Narrow bidder increase | +27.1% (+1.30) | SI | Same | Moved to SI |
| M89 | [LEGACY] Narrow bidders p | 2.7×10⁻³⁸ | SI | Same | Moved to SI |
| M90 | [LEGACY] Narrow carbon effect | −0.87% | SI | Same | Moved to SI |
| M91 | [LEGACY] Narrow carbon p | 1.2×10⁻⁵ | SI | Same | Moved to SI |
| M92 | McCrary density diagnostic | Density ratio 1.12 (±0.10) vs 1.48 (±0.50) — ratio declines toward cutoff; voluntary-disclosure artifact, not sorting | Results ¶8; Methods §RDD; SI §4 | `scripts/rdd/mccrary_density_test.py` | `results/rdd/mccrary_test.json` → `voluntary_disclosure_diagnostic` |
| M93 | Placebo thresholds | Null diagnostic pattern | Results ¶8 | `scripts/reanalysis/06_comprehensive_robustness_tests.py` | Placebo-threshold diagnostics |
| M94 | Placebo interpretation | No cutoff manipulation indicated | Results ¶8 | Same | Qualitative diagnostic summary |

## A8. Cross-Continental Corroboration

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M95 | US NAICS sectors | 30 | Results ¶9 | `scripts/cross_continental/us_procurement_analysis.py` | `results/cross_continental/us_procurement_analysis.json` → `correlation_analysis.n_sectors` |
| M96 | US correlation r | 0.555 | Results ¶9 | Same | `correlation_analysis.single_offer_vs_carbon` |
| M97 | US p | 0.002 | Results ¶9 | Same | `correlation_analysis.p_value` |
| M98 | US R² | 0.31 | Results ¶9 | Same | r² |
| M99 | Australia contracts | 120,139 | Results ¶9 | `scripts/cross_continental/non_eu_procurement_analysis.py` | `results/cross_continental/australia_analysis.json` → `n_contracts` |
| M100 | Australia premium | +24.8% | Results ¶9 | Same | `carbon_premium.premium` |
| M101 | Australia d | 0.19 | Results ¶9 | Same | `carbon_premium.cohens_d` |
| M102 | Australia p | <10⁻⁶ | Results ¶9 | Same | `carbon_premium.p_value` |
| M103 | CanadaBuys observed-method awards | 109,123 | Results ¶9; SI §7 | `scripts/robustness/control_expansion_analysis.py` | `results/robustness/control_expansion_analysis.json` → `external_control_expansion_canada.canada_data_source.contracts_with_observed_method_2012_2023` |
| M104 | Expanded NO+CH+CA ATT | −3.6 pp | Results ¶9; SI §7 | Same | `external_control_expansion_canada.expanded_controls.att` |
| M105 | Canada-only proxy ATT | −4.8 pp | Results ¶9; SI §7 | Same | `external_control_expansion_canada.canada_only_control.att` |
| M106 | World Bank paired countries | 22 | Results ¶9 | Same | `world_bank.n_countries` |
| M107 | World Bank t | 2.63 | Results ¶9 | Same | `world_bank.t_stat` |
| M108 | World Bank p | 0.016 | Results ¶9 | Same | `world_bank.p_value` |
| M109 | Consistency | 20 of 22 | Results ¶9 | Same | `world_bank.consistent_countries` |

## A9. Discussion — Within-Sector Channel

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M110 | Eurostat NACE sectoral granularity | 648-sector | Discussion ¶5 | `scripts/mechanism/bridge_analysis.py` | `results/mechanism/bridge_analysis.json` → `within_sector_fdr` |
| M111 | Eurostat country-sector groups | 542 | Discussion ¶5 | Same | `within_sector_fdr.n_groups` |
| M112 | Significant groups | 246 (45.4%) | Discussion ¶5 | Same | `within_sector_fdr.n_sig_fdr` |
| M113 | Negative:positive ratio | 3.2:1 | Discussion ¶5 | Same | `within_sector_fdr.neg_pos_ratio_fdr` |
| M114 | Sign test p | 1.3×10⁻¹³ | Discussion ¶5 | Same | `within_sector_fdr.sign_test_p` |
| M115 | Weighted within-sector premium | −0.55% | Discussion ¶5 | Same | `within_sector_fdr.weighted_within_premium_pct` |
| M116 | Within-supplier firms | 39,410 | Discussion ¶5 | `scripts/within_sector/within_supplier_analysis.py` | `results/within_sector/within_supplier_analysis.json` → `within_supplier_all.n_suppliers` |
| M117 | Within-supplier premium | −0.87% | Discussion ¶5 | Same | `within_supplier_all.premium_pct` |
| M118 | Within-supplier t | −6.04 | Discussion ¶5 | Same | `within_supplier_all.paired_t` |
| M119 | Within-supplier p | 1.6×10⁻⁹ | Discussion ¶5 | Same | `within_supplier_all.p_value` |
| M120 | Within-supplier d | −0.03 | Discussion ¶5 | Same | `within_supplier_all.cohens_d` |
| M121 | E-PRTR country-sector groups | 37 | Discussion ¶5 | `scripts/within_sector/eprtr_within_sector.py` | `results/within_sector/eprtr_within_sector.json` → `within_country_sector.n_groups` |
| M122 | E-PRTR significantly lower | 12 groups | Discussion ¶5 | Same | `within_country_sector.n_negative` |
| M123 | E-PRTR significantly higher | 5 groups | Discussion ¶5 | Same | `within_country_sector.n_positive` |
| M124 | E-PRTR ratio | 2.4:1 | Discussion ¶5 | Same | 12/5 |
| M125 | E-PRTR variance Energy | 76% within | Discussion ¶5 | Same | `variance_decomposition.Energy` |
| M126 | E-PRTR variance Waste | 89% within | Discussion ¶5 | Same | `variance_decomposition.Waste` |
| M127 | E-PRTR variance Chemicals | 63% within | Discussion ¶5 | Same | `variance_decomposition.Chemicals` |
| M128 | E-PRTR matched sample | 22,583 contracts, 646 facilities, 23 countries | Discussion ¶5; SI §26 | `scripts/rdd/eprtr_rdd_analysis.py` | `results/rdd/eprtr_rdd_analysis.json` → `match_summary`, `summary_interpretation` |
| M129 | E-PRTR overall SB emissions gap | +65.3%, p<0.001 | Discussion ¶5; SI §26 | Same | `rdd_analysis.did_complement.overall_sb_vs_mb` |
| M130 | E-PRTR within-sector SB emissions gap | Energy +131.6%, Mineral +36.0% | Discussion ¶5; SI §26 | Same | `within_sector_analysis` |
| M130a | E-PRTR FE-residualized threshold | $\tau = +0.068$, p=0.455 | SI §26 | Same | `rdd_analysis.fe_residualized_medium_50k` |
| M130b | Annual E-PRTR reform-window bridge | 10,804 contract-years, 415 facilities | Introduction ¶4; Discussion ¶5; SI §26 | Same | `annual_eprtr_reform_linkage.n_contract_year_matches`, `n_unique_facilities` |
| M130c | Annual E-PRTR raw SB premium narrowing | +58.5% pre to +57.4% post | Discussion ¶5; SI §26 | Same | `annual_eprtr_reform_linkage.raw_gap_change` |
| M131 | EU ETS records | 195,603 facility-year | Discussion ¶5 | `scripts/eu_ets/analyze_eu_ets.py` | `results/within_sector/eu_ets_within_sector_analysis.json` → `total_records` |
| M132 | EU ETS groups | 5,999 | Discussion ¶5 | Same | `n_groups` |
| M133 | EU ETS P25-median reduction | 43% | Discussion ¶5 | Same | `reduction_potential` |
| M134 | EU ETS d | −0.37 | Discussion ¶5 | Same | `cohens_d` |
| M135 | EU ETS vs EXIOBASE ratio | 5× larger | Discussion ¶5 | Same | 0.37/0.08 |
| M136 | RDD high-variance carbon | −1.71%, p=6.9×10⁻⁷ | Discussion ¶5 | `scripts/rdd/eprtr_variance_rdd.py` | `results/rdd/eprtr_within_sector_variance.json` → `rdd_interaction.HIGH variance sectors` |
| M137 | RDD low-variance carbon | −1.91%, p=2.1×10⁻⁶¹ | Discussion ¶5 | Same | `rdd_interaction.LOW variance sectors` |
| M138 | RDD variance-strata direction | Negative in both strata | Discussion ¶5 | Same | HIGH and LOW `pct_diff` values |
| M139 | Eurostat temporal pre-reform gap | 12.4% | Discussion ¶5 | `scripts/validation/eurostat_carbon_did.py` | `results/causal_id/carbon_did_panel.json` → `eurostat_its.pre_gap` |
| M140 | Eurostat temporal post-reform gap | 4.3% | Discussion ¶5 | Same | `eurostat_its.post_gap` |
| M141 | Reform-driven gap reduction | 66% | Discussion ¶5 | Same | (12.4−4.3)/12.4 |
| M142 | Eurostat temporal t | 4.17 | Discussion ¶5 | Same | `eurostat_its.t_stat` |
| M143 | Eurostat temporal p | <0.001 | Discussion ¶5 | Same | `eurostat_its.p_value` |
| M143a | Multi-source validation sources | 6 | Abstract; Introduction ¶4; Discussion ¶5; Conclusion | `results/validation/firm_level_validation.json` | `multi_source_convergence.n_validation_sources` |
| M143b | Combined premium (conservative) | −5.18% | Discussion ¶5; Conclusion | Same | `headline_findings.combined_premium_conservative_pct` |
| M143c | Combined premium (technical channel) | −9.31% | Discussion ¶5; Conclusion | Same | `headline_findings.combined_premium_with_technical_pct` |
| M143d | EXIOBASE C&S DiD ATT | +0.061 kg CO₂e/USD (SE=0.007, t=8.24) | Discussion ¶5 | `scripts/causal_id/exiobase_carbon_cs_did.py` | `results/causal_id/exiobase_carbon_cs_did.json` → `overall_att.att` |
| M143d2 | Sun-Abraham ATT (cross-validation) | −7.177 pp (95% CI [−8.3, −6.1]; p<10⁻³⁵, since JSON p=2.856×10⁻³⁶>10⁻³⁶) | Results ¶6; SI §7 | `scripts/causal_id/sun_abraham.py` | `results/causal_id/sun_abraham.json` → `aggregate.att_pp`; C&S≈S-A is algebraically expected under same comparison groups |
| M143d3 | Rambachan-Roth M* breakdown | M*=1.54 (violations must be 1.54× pre-period to explain away ATT) | Results ¶6; SI §7 | `scripts/causal_id/rambachan_roth_sensitivity.py` | `results/robustness/rambachan_roth_sensitivity.json` → `breakdown.M_star` |
| M143d4 | Dead Zone vs Live Zone premium | Dead Zone −8.8%; Live Zone −0.5% | Results ¶4; SI §9 | `scripts/dead_zones/analyze_dead_zones.py` | `results/dead_zones/dead_zones_reform_analysis.json` → `dead_zone_premium_pct`, `live_zone_premium_pct` |
| M143e | EXIOBASE C&S DiD bootstrap p | <0.001 (bootstrap p=0.0) | Discussion ¶5 | Same | `results/causal_id/exiobase_carbon_cs_did.json` → `overall_att.bootstrap_p` |
| M143f | EXIOBASE C&S DiD 95% CI | [0.028, 0.124] | Discussion ¶5 | Same | `results/causal_id/exiobase_carbon_cs_did.json` → `overall_att.bootstrap_ci` |
| M143g | EXIOBASE C&S DiD pre-trend slope p | 0.111 (parallel trends supported) | Discussion ¶5 | Same | `results/causal_id/exiobase_carbon_cs_did.json` → `pre_trend_test.p_value` |
| M143h | EXIOBASE C&S DiD control countries | Norway, Switzerland (never-treated) | Discussion ¶5 | Same | Cohort map: GB→2015, most EU→2016-2018 |

## A10. Discussion — Governance & Mechanisms

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M144 | Repeat-supplier higher carbon | 54.5% | Discussion ¶4 | `verify_all_claims.py` | Buyer-supplier relationship analysis |
| M145 | Buyer learning premium decrease | −8.6% | Discussion ¶6 | `scripts/validation/firm_level_validation.py` | `results/validation/firm_level_validation.json` |
| M146 | Small-supplier t-statistic (6-20 contracts) | 224.7 | SI §15 | Same | Supplier market position |
| M147 | Small-supplier premium (6-20 contracts) | +67.5% | Discussion ¶6; SI §15 | Same | Supplier market position |
| M148 | Dominant suppliers d | −0.03 | Discussion ¶6 | Same | Large supplier analysis |
| M149 | Dominant suppliers premium | −2.5% | Discussion ¶6 | Same | 500+ contracts |
| M150 | Difference SME vs dominant | 27× | Discussion ¶6 | Same | 67.5 / 2.5 |
| M151 | Deterrence premium | 1.9% (d=0.04) | Discussion ¶6 | Same | Competitive vs non-competitive buyers |
| M152 | Bidder paradox: 2-bidder higher | +5.4% | Discussion ¶7 | `verify_all_claims.py` | 2-bidder vs 1-bidder carbon |
| M153 | Extensive margin share | 89.2% | Discussion ¶7 | Same | Decomposition |
| M154 | Intensive margin share | 10.8% | Discussion ¶7 | Same | Decomposition |
| M155 | Measurement attenuation λ | 0.67 | Discussion ¶5 | `scripts/mechanism/comprehensive_final_analysis.py` | Attenuation calculation |
| M156 | Corrected between-sector effect | ~−6.4% | Discussion ¶5 | Same | −4.3% / 0.67 |

## A11. Discussion — SBTi Selection Mechanism

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M157 | SBTi firms in Dead Zones | 5,026 | Discussion ¶8 | `scripts/validation/sbti_winner_matching.py` | `results/validation/sbti_winner_matching.json` |
| M158 | SBTi EU Dead Zone firms | 2,327 | Discussion ¶8 | Same | EU subset |
| M159 | SBTi construction firms | 1,131 | Discussion ¶8 | Same | Sector filter |
| M160 | SBTi construction 1.5°C | 63% | Discussion ¶8 | Same | Target type breakdown |
| M161 | Construction SBTi prob (1-bidder) | 0.82% | Discussion ¶8 | Same | `results/other/sbti_selection_probability.json` → `Construction.single_bidder` |
| M162 | Construction SBTi prob (5-bidder) | 4.04% | Discussion ¶8 | Same | `Construction.five_bidder` |
| M163 | ~5-fold probability increase | 4.04/0.82 | Discussion ¶8 | Same | Ratio |
| M164 | Medical SBTi prob (1-bidder) | 1.16% | Discussion ¶8 | Same | `Medical/Pharma.single_bidder` |
| M165 | Medical SBTi prob (5-bidder) | 5.68% | Discussion ¶8 | Same | `Medical/Pharma.five_bidder` |

## A12. Discussion — Monopoly Tax & Green Premium

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M166 | Green materials premium | 10–20% | Discussion ¶7 | Literature (Ecologic, SEI) | External citations |
| M167 | SB financial premium | 7–10% | Discussion ¶7 | Literature (Fazekas, Coviello) | External citations |
| M168 | DZ SB spending | €190–250B | Discussion ¶7 | `scripts/projections/oecd_calibration.py` | `results/projections/oecd_calibrated_numbers.json` |
| M169 | Monopoly Tax estimate | €13–25B/year | Discussion ¶7 | Same | spending × premium |
| M170 | Switchable to low-carbon | 40–60% | Discussion ¶7 | Same | Scenario parameter |
| M171 | Coverage ratio under full rent recovery | 80–114% | Conclusion; SI §28 | Same | Tax / Green Premium |
| M172 | Conservative 50% rent-recovery | 40–57% | Conclusion; SI §28 | Same | Sensitivity |

## A13. Conclusion — Forward Projections

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M173 | Conservative newly competitive | ~€18B | Conclusion | `scripts/projections/forward_projection_model.py` | `results/projections/forward_projections.json` → `scenarios.conservative.milestones.2030.newly_competitive_eurB` |
| M174 | Conservative carbon by 2030 | 7 Mt CO₂e | Conclusion | Same | `scenarios.conservative.milestones.2030.carbon_accessible_mt` |
| M175 | Ambitious carbon by 2035 | 57 Mt CO₂e | Conclusion | Same | `scenarios.ambitious.carbon_mt` |
| M176 | NDC range | 3–6% (DZ only); 7–12% (all SB) | Conclusion | `scripts/projections/monte_carlo_uncertainty.py` | `results/monte_carlo_uncertainty.json` → `ndc_pct.mean` |
| M177 | Competition savings offset | 80–114% | Conclusion | `scripts/projections/oecd_calibration.py` | Coverage ratio under full rent recovery |

## A14. Methods Section

| # | Claim | Value | Location | Script | Result / Key |
|---|-------|-------|----------|--------|-------------|
| M178 | Data time span | 2006–2023 (analysis: 2012–2023) | Methods | `verify_all_claims.py` | Date range |
| M179 | Final analysis sample | 21,612,129 | Methods | Same | Row count |
| M180 | SB status missing | 0% | Methods | Same | Null check |
| M181 | Contract value missing | <1% | Methods | Same | Null check |
| M182 | Database-to-OECD ratio | ~7× | Methods | `scripts/projections/oecd_calibration.py` | 14T/2T |
| M183 | EXIOBASE scope | 1, 2, upstream 3 | Methods | `scripts/pipeline/parse_exiobase.py` | EXIOBASE 3.8 documentation |
| M184 | EXIOBASE sectors | 163 | Methods | Same | Sector count |
| M185 | EXIOBASE countries | 49 | Methods | Same | Country count |
| M186 | EU member-state countries in primary DiD | 23 | Methods | `scripts/causal_id/callaway_santanna.py` | `sample.treated_countries` |
| M187 | Non-EU comparators | 2 (NO, CH) | Methods | Same | Control group |
| M188 | Pre-treatment period | 2012–2015 | Methods | Same | Period definition |
| M189 | Post-treatment period | 2017–2023 | Methods | Same | Period definition |
| M190 | Max clusters | 27 | Methods | Same | Country-level clustering |
| M191 | Placebo units | 24 | Methods | `scripts/causal_id/sc_permutation_inference.py` | Donor pool |
| M192 | Bootstrap replications | 10,000 | Methods | `scripts/causal_id/staggered_did.py` | Bootstrap parameter |
| M193 | Python version | 3.12 | Methods | `environment.yml` | Runtime |

---

# PART B: SUPPLEMENTARY INFORMATION CLAIMS

## B1. SI §1: Data Sources and Sample Construction

| # | Claim | Value | SI Section | Script | Result / Key |
|---|-------|-------|-----------|--------|-------------|
| S1 | EU TED countries | 26 | 1.1 | `scripts/pipeline/parse_eu_ted.py` | Unique countries in TED |
| S2 | Colombia SECOP contracts | 7.97M | 1.1 | `scripts/pipeline/parse_ocds_jsonl.py` | OCDS Colombia parsing |
| S3 | Initial contracts before cleaning | ~28.5M | 1.2, Table S1 | `scripts/pipeline/harmonize_data.py` | Pre-dedup count |
| S4 | After deduplication | ~25.1M | 1.2, Table S1 | Same | Post-dedup |
| S5 | After dropping missing | ~22.9M | 1.2, Table S1 | Same | Post-filter |
| S6 | Final sample | 21,612,129 | 1.2, Table S1 | `scripts/pipeline/link_carbon_intensity.py` | Final parquet row count |
| S7 | RDD subsample (with bidder count) | 15,538,905 | 1.2, Table S1 | `verify_all_claims.py` | Non-null `n_bidders` |

### SI Table S2: Country Coverage (all 27 countries)

All 27 country-level N and SB rates are produced by:
- **Script**: `verify_all_claims.py` or `scripts/mechanism/comprehensive_final_analysis.py`
- **Method**: Group-by `iso_code`, compute `single_bidder.mean()` and `count()`
- **Result**: `results/core_stats/comprehensive_analysis_results.json` → `country_results`

## B2. SI §2: Carbon Intensity Assignment

| # | Claim | Value | SI Section | Script | Result / Key |
|---|-------|-------|-----------|--------|-------------|
| S8 | Carbon range | 0.05–1.8 kg CO₂e/USD | 2.2 | `scripts/pipeline/parse_exiobase.py` | EXIOBASE factor range |
| S9 | CPV coverage | 100% | 2.2 | `scripts/pipeline/link_carbon_intensity.py` | CPV-to-EXIOBASE linkage |
| S9a | Full CPV-to-EXIOBASE crosswalk published | 40 mappings | 2.2; Table S2a | `scripts/pipeline/link_carbon_intensity.py` | `Data/reference/cpv_exiobase_crosswalk.csv` |

## B3. SI §4: Primary Results (Tables S3-S5)

### Table S3: Carbon Intensity by Competition Status
- **Script**: `verify_all_claims.py` → direct T-test computation
- **All values**: N_SB=2,378,511; N_MB=19,233,618; SB_mean=0.337; MB_mean=0.294; diff=+0.043; premium=+14.8%; t=333.7; d=0.228

### Table S4: U-Curve by Size Band
- **Script**: `verify_all_claims.py` → size-band-filtered T-tests
- **Values**: <10k: +50.2% (d=0.75); 10k-200k: +12.5% (d=0.20); >200k: −7.1% (d=−0.12)

### Table S5: Country-Specific Effects (27 countries)
- **Script**: `scripts/mechanism/comprehensive_final_analysis.py`
- **Result**: `results/core_stats/comprehensive_analysis_results.json` → per-country breakdown
- Covers all 27 country premiums and t-statistics (see SI claims extraction above)

## B4. SI §5: Temporal Patterns and COVID-19 (Tables S6-S8)

### Table S6: Premium by Year (12 years)
- **Script**: `verify_all_claims.py` → year-filtered T-tests
- **Key values**: 2012 (+24.6%) through 2023 (−3.5%); trend slope −2.46%/yr (R²=0.55, p=0.006)

### Table S7: EU-Context Premium & SB Rate by Year
- **Result**: `results/eu_ets/eu_context_si_tables.json` → `temporal_eu`; cross-checked by `verify_all_claims.py`
- **Key values**: Pre-reform SB ~20%; post-reform 15-17%; 2023 rebound 18.6%

### Table S8: COVID Impact
- **Script**: `verify_all_claims.py` → period-filtered T-tests
- **Key values**: Pre-COVID +7.0%; During +20.1%; Post +0.3%

## B5. SI §6: Regression Discontinuity (Table S9)

### Table S9: RDD at €139k
- **Script**: `verify_all_claims.py` (direct), `reproduce_data_comprehensive.py`
- **Result**: `results/core_stats/verified_statistics.json`
- **All specifications**: primary ±0.1 log-value window (N=866,326 contracts; 634,566 with bidder counts); 30% value band (N=1,178,011); narrow €120k-160k (N=408,928 bidder-observed contracts)
- Each specification has bidder effect + carbon effect with t-stats and p-values

## B6. SI §7: Robustness Checks (Tables S10-S12)

### Table S10: Event-Study Pre-Trend Testing
- **Script**: `scripts/causal_id/callaway_santanna.py`
- **Result**: `results/causal_id/callaway_santanna.json` → `group_time_atts` array
- **Key**: 2016 cohort event times −4 to +7; 2017 cohort event times 0 to +6
- All ATT, SE, t, p values per event time

### Finite-Sample Inference
| Method | Script | Result | Value |
|--------|--------|--------|-------|
| RMSPE permutation | `scripts/causal_id/sc_permutation_inference.py` | `results/causal_id/sc_permutation_inference.json` | Rank 1/24, p=0.042 |
| Wild cluster bootstrap (NO+CH) | `scripts/causal_id/staggered_did.py` | `results/causal_id/staggered_did.json` | p=0.32 |
| Wild cluster bootstrap (+CO) | Same | Same | p=0.36 |

### Table S11: SB Rate by Carbon Decile
- **Script**: `verify_all_claims.py`
- **Values**: Bottom 10% SB=6.2%; Top 10% SB=13.9%; ratio 2.24×

### Table S12: Premium by Geographic Region
- **Script**: `scripts/mechanism/comprehensive_final_analysis.py`
- **Values**: Eastern EU −5.6%; Southern EU −4.8%; Western EU −4.3%; Latin America −2.3%; Northern EU −0.3%

## B7. SI §7: Measurement Error & Temporal Stability (within Robustness Checks)

| # | Claim | Value | Script | Result |
|---|-------|-------|--------|--------|
| S10 | Within-CPV t-stat | −75.1 | `scripts/mechanism/comprehensive_final_analysis.py` | Sector-controlled regression |
| S11 | Attenuation λ | 0.67 | Same | Measurement error model |
| S12 | Corrected effect | −6.4% | Same | −4.3% / 0.67 |
| S13 | EXIOBASE vintage decline | −24.8% | `scripts/pipeline/parse_exiobase.py` | 2011 vs 2022 comparison |
| S14 | DZ surviving 2022 vintage | 5 of 6 | `scripts/dead_zones/eu_dead_zones_recompute.py` | Vintage robustness |

## B8. SI §8: Conservative Lower Bound (Within-Sector Decomposition)

| # | Claim | Value | Script | Result |
|---|-------|-------|--------|--------|
| S15 | Between-sector premium | −4.3% (100% of observed) | `scripts/mechanism/comprehensive_final_analysis.py` | Oaxaca-Blinder decomposition |
| S16 | Within-sector (by design) | 0.0% | Same | EXIOBASE assigns identical carbon to same-sector |
| S17 | Literature within-sector variation | 5–10× | External | Marin & Palma (2017); Martin et al. (2012) |

## B9. SI §9: Dead Zone Sensitivity (Table S14)

### Table S14: 25 Threshold Combinations
- **Script**: `scripts/dead_zones/analyze_dead_zones.py`
- **Result**: `results/dead_zones/dead_zone_sensitivity.json`
- **Grid**: Carbon pctl {50th,67th,75th,80th,90th} × SB pctl {25th,50th,75th,80th,90th}
- **Baseline** (67th/50th): 6 DZ, 0.72T locked, 100% of baseline

## B10. SI §10: Combined Financial and Carbon Costs

- **Script**: `scripts/projections/oecd_calibration.py`
- **Result**: `results/projections/oecd_calibrated_numbers.json`
- Literature financial premiums: Fazekas 7-10%; Coviello 8-12%; OECD 10.5%
- DZ carbon: ~280 Mt CO₂e

## B11. SI §11: Deterrence Effect

| Claim | Value | Script | Result |
|-------|-------|--------|--------|
| SB from competitive buyers | 0.342 kg CO₂e/USD | `scripts/validation/firm_level_validation.py` | `results/validation/firm_level_validation.json` |
| SB from non-competitive buyers | 0.336 kg CO₂e/USD | Same | Same |
| Deterrence premium | 1.9% (t=22.9, p<10⁻¹⁶) | Same | Same |

## B12. SI §12: Buyer Learning Effect

| Claim | Value | Script | Result |
|-------|-------|--------|--------|
| Early SB premium | 0.047 kg CO₂e/USD | `scripts/validation/firm_level_validation.py` | `results/validation/firm_level_validation.json` |
| Late SB premium | 0.043 kg CO₂e/USD | Same | Same |
| Learning reduction | 8.6% | Same | Same |

## B13. SI §13: Size × COVID Interaction (Table S16)

- **Script**: `verify_all_claims.py` → period × size-band filtered T-tests
- **Key**: Small pre-COVID +46.1%, COVID +57.8%, post +26.1%; Large stable at −7.1% to −8.2%

## B14. SI §14: Fiscal Calendar Effect (Table S17)

- **Script**: `scripts/mechanism/comprehensive_final_analysis.py`
- **Key**: Q1 premium +28.8% (d=0.40); Q4 +8.5% (d=0.14); Q1/Q4 ratio 3.4×

## B15. SI §15: Supplier Market Power (Table S18)

- **Script**: `scripts/validation/firm_level_validation.py`
- **Result**: `results/validation/firm_level_validation.json`
- **Key**: New +56.9%; Small +67.5%; Dominant −2.5%; 27× difference

## B16. SI §16: Policy Matrix (Table S19)

- **Script**: `scripts/projections/oecd_calibration.py`, `verify_all_claims.py`
- Zone A (routine <€10k): −2.8%, d=−0.05, SB=37.7%
- Zone B (strategic >€200k): −7.8%, d=−0.13, SB=8.5%
- External validation: Ecologic (cement ≥21%, steel ≥18%); SEI (~15% of global GHG)

## B17. SI §17: Procurement Method Heterogeneity (Table S20)

- **Script**: `scripts/mechanism/comprehensive_final_analysis.py`
- **Key**: Open +3.4%; Limited +2.4%; Direct +6.4%; Selective −12.7% (d=−0.25)

## B18. SI §18: Supply Chain Complexity (Table S21)

- **Script**: `scripts/mechanism/comprehensive_final_analysis.py`
- **Key**: Subcontracted +27% higher baseline; SB premium (subcontracted) −17.5% vs (non) −12.9%

## B19. SI §19: SME Winner Carbon Paradox (Table S22)

- **Script**: `scripts/mechanism/comprehensive_final_analysis.py`
- **Key**: SME winners +9.5% higher carbon (t=71.0, p<10⁻¹⁶)

## B20. SI §20: Bidder Count Paradox (Table S23)

- **Script**: `verify_all_claims.py`
- **Key**: 1-bidder=0.337; 2-bidder=0.355 (+5.4%); 10+=0.347 (+3.0%); 15+=0.339 (+0.6%)
- Extensive margin 89.2%; intensive 10.8%

## B21. SI §21: Colombia Mechanism / Simpson's Paradox (Table S24)

- **Script**: `verify_all_claims.py`
- **Key**: n_bidders=0 (CO): mean=0.208; n_bidders=1 (EU): mean=0.337; n_bidders≥2 (EU): mean=0.356

## B22. SI §22: EU-Only Analysis (Table S25)

- **Script**: `verify_all_claims.py`
- **Key**: Full dataset +14.8%; EU-context −4.3%; Colombia −2.3%
- Sector concentration: Construction +8.3pp; Chemicals +3.1pp; Consulting −6.2pp; IT −4.8pp

## B23. SI §23: Buyer-Supplier Relationships (Table S26)

- **Script**: `scripts/validation/firm_level_validation.py`
- **Key**: First-time 0.217; Dependent (11+) 0.335 (+54.5% higher)

## B24. SI §24: Buyer Scale Effect (Table S27)

- **Script**: `scripts/validation/firm_level_validation.py`
- **Key**: Q1 (smallest) +15.0%; Q3 (medium) +26.9% (peak); Q4 (largest) +3.3%

## B25. SI §25: Cross-Continental Corroboration (Table S28)

| System | Script | Result File | Key Claims |
|--------|--------|-------------|------------|
| US FPDS | `scripts/cross_continental/us_procurement_analysis.py` | `results/cross_continental/us_procurement_analysis.json` | r=0.555, p=0.002, 30 sectors |
| CanadaBuys control | `scripts/robustness/control_expansion_analysis.py` | `results/robustness/control_expansion_analysis.json` | 109,123 observed-method original awards; expanded NO+CH+CA ATT −3.6 pp; Canada-only ATT −4.8 pp |
| Australia | Same | `results/cross_continental/australia_analysis.json` | +24.8%, d=0.19, 120,139 contracts |
| World Bank GPPD | Same | `results/cross_continental/australia_analysis.json` (embedded) | t=2.63, p=0.016, 20/22 countries |

## B26. SI §26: Evidence Convergence

This section aggregates results from multiple analyses — no new computation:

| Evidence Line | Source Script | Source Result |
|---------------|-------------|--------------|
| EU ETS 195,603 records | `scripts/eu_ets/analyze_eu_ets.py` | `results/within_sector/eu_ets_within_sector_analysis.json` |
| P25 vs median: 43%, d=−0.37 | Same | Same |
| E-PRTR variance decomposition | `scripts/within_sector/eprtr_within_sector.py` | `results/within_sector/eprtr_within_sector.json` |
| E-PRTR matched facility emissions | `scripts/rdd/eprtr_rdd_analysis.py` | `results/rdd/eprtr_rdd_analysis.json` |
| Annual E-PRTR facility-year bridge | Same | Same; 10,804 contract-year matches, raw SB premium +58.5% pre to +57.4% post |
| Eurostat 542 groups, 3.2:1 ratio | `scripts/mechanism/bridge_analysis.py` | `results/mechanism/bridge_analysis.json` |
| Within-supplier 39,410 firms | `scripts/within_sector/within_supplier_analysis.py` | `results/within_sector/within_supplier_analysis.json` |
| RDD negative in high- and low-variance strata | `scripts/rdd/eprtr_variance_rdd.py` | `results/rdd/eprtr_within_sector_variance.json` |

## B27. SI §27: UK PPN 06/21 Micro-Validation

- **Script**: `scripts/validation/firm_level_validation.py` (UK subset)
- **Key**: £5M threshold, September 2021, 180+ UK firms with SBTs

## B28. SI §28: Monopoly Tax and Green Premium Calculation

- **Script**: `scripts/projections/oecd_calibration.py`
- **Result**: `results/projections/oecd_calibrated_numbers.json`
- Monopoly Tax: €13–25B/yr; Green Premium: 8.75% of DZ SB; Coverage ratio: 80–114%

## B29. SI §29: NDC Mapping (Table S29)

- **Script**: `scripts/projections/forward_projection_model.py`, `scripts/projections/monte_carlo_uncertainty.py`
- **Result**: `results/projections/forward_projections.json`, `results/monte_carlo_uncertainty.json`
- Germany: 17.8 Mt (5.8%); Poland: 6.5 Mt (4.4%); UK: 4.2 Mt (3.1%); etc.
- Range: 3–6% (DZ only); 7–12% (all SB); 90% CI [7.2%, 11.8%]

## B30. SI §30: Forward Projections

| Scenario | Key Metrics | Script | Result Key |
|----------|------------|--------|-----------|
| Conservative (2025-2030) | TWFE sensitivity −0.71pp; €18.1B newly competitive; 6.7 Mt CO₂e | `scripts/projections/forward_projection_model.py` | `results/projections/forward_projections.json` → `scenarios.conservative` |
| Moderate (2025-2035) | Scenario reduction −5.0pp; €127.6B; 47.3 Mt | Same | `scenarios.moderate` |
| Ambitious (convergence) | Nordic SB ~8%; €153.1B; 56.7 Mt | Same | `scenarios.ambitious` |
| G20 extrapolation | US$10.4T procurement; >US$1T intervention surface | Same | `scenarios.global` |

---

# PART C: DATA FILES REQUIRED

| File | Description | Size | Used By |
|------|-------------|------|---------|
| `Data/processed/gprd_with_carbon.parquet` | Main dataset: 21.6M contracts with carbon intensity | ~2GB | All analyses |
| `Data/eu_ets.csv` | EU ETS installation emissions (195,603 facility-year records) | ~50MB | EU ETS analysis (M131-M135) |
| `Data/external/sbti_companies.csv` | SBTi company registry | ~2MB | SBTi matching (M157-M165) |
| `Data/external/eurostat_emissions_intensity.csv` | Eurostat NACE emissions | ~5MB | Eurostat within-sector (M110-M115, M139-M143) |
| `Data/eprtr/` | E-PRTR facility emissions data | ~100MB | E-PRTR matching (M121-M130) |
| `Data/processed/gprd_master.parquet` | Pre-carbon-linkage dataset | ~1.5GB | E-PRTR matching |
| `results/*.json` | 82 pre-computed JSON result files | ~50MB | `verify_all_claims.py` |

---

# PART D: VERIFICATION WORKFLOW

```bash
# Verify all 36 core claims (pre-computed results)
python verify_all_claims.py

# Re-run all analysis scripts before verification
python verify_all_claims.py --rerun

# Verify specific section
python verify_all_claims.py --section 3  # DiD claims only

# Verbose output
python verify_all_claims.py -v
```

Output: `VERIFICATION_RESULTS.json` with PASS/FAIL for each claim.

---

# PART E: SCRIPT DIRECTORY GUIDE

## scripts/ — All Analysis & Pipeline Scripts (~130 files, 20 subfolders)

| Subfolder | Count | Key Scripts | Purpose |
|-----------|-------|-------------|---------|
| **causal_id/** | 10 | `callaway_santanna.py`, `staggered_did.py`, `sc_permutation_inference.py`, `dose_response_placebo.py` | DiD, synthetic control, permutation inference |
| **rdd/** | 2 | `eprtr_rdd_analysis.py`, `eprtr_variance_rdd.py` | Regression discontinuity at €139k |
| **within_sector/** | 7 | `eprtr_within_sector.py`, `within_supplier_analysis.py`, `within_sector_validation.py`, `eurostat_within_sector.py` | Facility-level and supplier-level effects |
| **dead_zones/** | 4 | `eu_dead_zones_recompute.py`, `analyze_dead_zones.py`, `dz_within_sector.py` | Dead zone classification and sensitivity |
| **eu_ets/** | 2 | `analyze_eu_ets.py`, `analyze_eu_ets_facility.py` | EU ETS facility-level analysis |
| **cross_continental/** | 5 | `us_procurement_analysis.py`, `non_eu_procurement_analysis.py`, `australia_carbon_analysis.py` | US, Canada, Australia, World Bank |
| **validation/** | 16 | `eurostat_carbon_did.py`, `eurostat_cross_validation.py`, `firm_level_validation.py`, `sbti_winner_matching_v2.py` | External data triangulation |
| **projections/** | 4 | `forward_projection_model.py`, `monte_carlo_uncertainty.py`, `oecd_calibration.py` | Policy scenarios and uncertainty |
| **robustness/** | 8 | `cs_did_sensitivity.py`, `greece_exclusion_robustness.py`, `robustness_and_alternatives.py`, `cross_validation.py` | Robustness and sensitivity tests |
| **mechanism/** | 3 | `mediation_trap_analysis.py`, `comprehensive_final_analysis.py`, `bridge_analysis.py` | Mediation and mechanism analysis |
| **core_stats/** | 7 | `eu_specific_numbers.py`, `load_and_analyze.py`, `verify_exact_numbers.py` | Core descriptive statistics |
| **pipeline/** | 9 | `parse_eu_ted.py`, `parse_exiobase.py`, `harmonize_data.py`, `run_full_pipeline.py` | Raw → processed data |
| **download/** | 5 | `download_data.py`, `download_ocds_global_data.py`, `download_us_fpds.py` | Acquire raw data |
| **figures/** | 6 | `generate_manuscript_figures.py`, `generate_accurate_figures.py`, `generate_tables.py` | Publication figures and tables |
| **diagnostics/** | 10 | `check_nulls.py`, `inspect_parquet.py`, `comprehensive_data_validation.py` | Data quality checks |
| **zenodo/** | 1 | `upload_to_zenodo.py` | Zenodo archive upload |
| **exploratory/** | 8 | `deep_breakthrough_analysis.py`, `fatal_flaw_analysis.py` | Development/exploration (not directly cited) |
| **verification/** | 6 | `verify_dz.py`–`verify_dz5.py`, `verify_eu_vs_full.py` | Internal verification scripts |
| **reanalysis/** | 12 | `01_simple_sanity_check.py` through `12_final_validation_report.py` | Sequential numbered robustness checks |
| **lib/** | 4 | `__init__.py`, `causal_analysis.py`, `data_acquisition.py`, `mechanism_index.py` | Reusable library modules (imported by tests as `scripts.lib.*`) |

---

**Contact**: For questions about specific analyses, see docstrings in each script. All scripts are self-contained and run independently from repository root.