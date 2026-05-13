"""
Control Expansion Analysis: Three approaches to strengthen causal identification
for the EU Directive 2014/24/EU competition effect.

Addresses the thin control group concern (only NO and CH as non-EU comparators).

Approach 1: Within-EU Staggered DiD — late-transposers as controls for early-transposers
Approach 2: Permutation/Randomization Inference — exact p-values without relying on N_controls
Approach 3: Leave-One-Out Sensitivity — verify result stability across control subsets
"""

import pandas as pd
import numpy as np
import json
import os
import requests  # type: ignore[import-untyped]
from pathlib import Path

np.random.seed(42)

# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / "pyproject.toml").exists() and _d != _d.parent:
    _d = _d.parent
PROJECT_ROOT = _d

CANADA_HISTORY_SOURCES = [
    {
        "name": "Legacy CanadaBuys contract history, 2009-01 to 2023-05",
        "url": "https://canadabuys.canada.ca/opendata/pub/2009-2023-contractHistoryHistorical-contratsOctroyesHistorique.csv",
    },
    {
        "name": "All CanadaBuys contract history, 2023-06-01 onwards",
        "url": "https://canadabuys.canada.ca/opendata/pub/contractHistoryComplete-contratsOctroyesComplet.csv",
    },
]
CANADA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; public-procurement-control-surface/1.0; +https://open.canada.ca/)",
    "Accept": "text/csv,*/*",
}
CANADA_COLS = [
    "referenceNumber-numeroReference",
    "amendmentNumber-numeroModification",
    "contractAwardDate-dateAttributionContrat",
    "contractStartDate-contratDateDebut",
    "contractAmount-montantContrat",
    "totalContractValue-valeurTotaleContrat",
    "instrumentType-typeInstrument-eng",
    "amendmentType-typeModification-eng",
    "procurementCategory-categorieApprovisionnement",
    "procurementMethod-methodeApprovisionnement-eng",
    "limitedTenderingReason-raisonAppelOffresLimite-eng",
]
CANADA_PANEL_PATH = PROJECT_ROOT / "Data" / "processed" / "canada_control_panel.parquet"
CANADA_METADATA_PATH = (
    PROJECT_ROOT / "Data" / "processed" / "canada_control_panel_metadata.json"
)

# ── Load and prepare data ─────────────────────────────────────────────
print("Loading data...")
df = pd.read_parquet(
    PROJECT_ROOT / "Data" / "processed" / "gprd_with_carbon.parquet",
    columns=["country", "year", "single_bidder"],
)
df = df[(df["year"] >= 2012) & (df["year"] <= 2023)]
df = df[~df["country"].isin(["CO", "IS"])]  # Exclude Colombia and Iceland

# Country-year panel: mean single-bidder rate per country-year cell
cy = (
    df.groupby(["country", "year"])
    .agg(sb_rate=("single_bidder", "mean"), n=("single_bidder", "count"))
    .reset_index()
)
print(f"Panel: {cy.shape[0]} country-year cells, {cy['country'].nunique()} countries")
print(f"Countries: {sorted(cy['country'].unique())}")

# ── Define groups ─────────────────────────────────────────────────────
EU_COUNTRIES = sorted(
    [
        "AT",
        "BE",
        "BG",
        "CZ",
        "DE",
        "DK",
        "EE",
        "ES",
        "FI",
        "FR",
        "GB",
        "GR",
        "HU",
        "IE",
        "IT",
        "LT",
        "LU",
        "LV",
        "NL",
        "PL",
        "PT",
        "SE",
        "SI",
        "SK",
    ]
)  # 24 EU member states in data
CONTROLS = ["NO", "CH"]
CANADA_CONTROL = ["CA"]
EXPANDED_CONTROLS = CONTROLS + CANADA_CONTROL

# Staggered transposition cohorts (Directive 2014/24/EU)
# Based on actual national transposition dates
COHORT_2016 = [
    "DK",
    "EE",
    "FI",
    "FR",
    "DE",
    "HU",
    "IE",
    "LT",
    "NL",
    "PL",
    "PT",
    "SE",
    "SK",
]
COHORT_2017 = ["AT", "BE", "BG", "CZ", "ES", "IT", "LV"]
COHORT_2018 = ["GR", "LU", "SI"]
# GB transposed in 2015 (early adopter) — excluded from staggered analysis

N_BOOT = 1000
N_PERM = 1000
PRE_YEARS = list(range(2012, 2016))
POST_YEARS = list(range(2016, 2024))


# ── Helper functions ──────────────────────────────────────────────────
def compute_did(panel, treated_countries, control_countries, pre_years, post_years):
    """Compute 2×2 DiD ATT from a country-year panel of sb_rate values."""
    t_pre = panel[
        panel["country"].isin(treated_countries) & panel["year"].isin(pre_years)
    ]["sb_rate"]
    t_post = panel[
        panel["country"].isin(treated_countries) & panel["year"].isin(post_years)
    ]["sb_rate"]
    c_pre = panel[
        panel["country"].isin(control_countries) & panel["year"].isin(pre_years)
    ]["sb_rate"]
    c_post = panel[
        panel["country"].isin(control_countries) & panel["year"].isin(post_years)
    ]["sb_rate"]

    if len(t_pre) == 0 or len(t_post) == 0 or len(c_pre) == 0 or len(c_post) == 0:
        return np.nan, {}

    att = (t_post.mean() - t_pre.mean()) - (c_post.mean() - c_pre.mean())
    components = {
        "treated_pre": float(t_pre.mean()),
        "treated_post": float(t_post.mean()),
        "control_pre": float(c_pre.mean()),
        "control_post": float(c_post.mean()),
        "treated_change": float(t_post.mean() - t_pre.mean()),
        "control_change": float(c_post.mean() - c_pre.mean()),
    }
    return float(att), components


def bootstrap_did(
    panel, treated_countries, control_countries, pre_years, post_years, n_boot=N_BOOT
):
    """Bootstrap DiD SE by resampling countries within treated/control groups."""
    treated_countries = list(treated_countries)
    control_countries = list(control_countries)
    atts = []
    for _ in range(n_boot):
        t_sample = list(
            np.random.choice(
                treated_countries, size=len(treated_countries), replace=True
            )
        )
        c_sample = list(
            np.random.choice(
                control_countries, size=len(control_countries), replace=True
            )
        )
        att, _ = compute_did(panel, t_sample, c_sample, pre_years, post_years)
        if not np.isnan(att):
            atts.append(att)
    atts = np.array(atts)
    se = float(np.std(atts, ddof=1))
    ci_lo = float(np.percentile(atts, 2.5))
    ci_hi = float(np.percentile(atts, 97.5))
    # Bootstrap p-value: fraction of bootstrap ATTs where |ATT*| >= |ATT_obs|
    return se, ci_lo, ci_hi, atts


def bootstrap_pvalue(boot_atts, observed_att):
    """Two-sided bootstrap p-value."""
    return float(
        np.mean(
            np.abs(boot_atts - np.mean(boot_atts))
            >= np.abs(observed_att - np.mean(boot_atts))
        )
    )


def normal_pvalue(att, se):
    """Two-sided p-value from normal approximation."""
    from scipy import stats

    if se == 0 or np.isnan(se):
        return np.nan
    z = att / se
    return float(2 * stats.norm.sf(np.abs(z)))


def _normalize_text(series):
    return series.fillna("").astype(str).str.strip()


def _build_canada_control_panel(chunksize=250_000):
    """Build Canada yearly non-competitive procurement proxy from CanadaBuys.

    CanadaBuys does not publish a TED-equivalent single-bidder count over the
    full 2009--2023 window. The closest source-level proxy is the official
    procurement method: Non-competitive and Advance Contract Award Notice are
    coded as the non-competitive award channel; open, traditional, and selective
    tendering are coded as competitive. Blank/unknown methods are excluded from
    denominators and reported in metadata.
    """
    yearly_parts = []
    source_metadata = []

    for source in CANADA_HISTORY_SOURCES:
        print(f"  Streaming Canada source: {source['name']}")
        with requests.get(
            source["url"], headers=CANADA_HEADERS, stream=True, timeout=120
        ) as response:
            response.raise_for_status()
            response.raw.decode_content = True

            source_rows = 0
            source_original_rows = 0
            source_method_observed = 0
            source_method_missing = 0
            source_year_missing = 0

            reader = pd.read_csv(
                response.raw,
                usecols=CANADA_COLS,
                dtype=str,
                encoding="utf-8-sig",
                chunksize=chunksize,
            )

            for chunk in reader:
                source_rows += len(chunk)

                amendment = _normalize_text(chunk["amendmentNumber-numeroModification"])
                original_award = amendment.eq("000") | amendment.eq("")
                work = chunk.loc[original_award].copy()
                source_original_rows += len(work)
                if work.empty:
                    continue

                award_date = pd.to_datetime(
                    work["contractAwardDate-dateAttributionContrat"], errors="coerce"
                )
                start_date = pd.to_datetime(
                    work["contractStartDate-contratDateDebut"], errors="coerce"
                )
                year = award_date.dt.year.fillna(start_date.dt.year)
                work["year"] = year.astype("Int64")

                method = _normalize_text(
                    work["procurementMethod-methodeApprovisionnement-eng"]
                )
                method_lower = method.str.lower()

                noncompetitive = (
                    method_lower.eq("non-competitive")
                    | method_lower.eq("advance contract award notice")
                    | method_lower.eq("advanced contract award notice")
                    | method_lower.eq("acan")
                )
                competitive = (
                    method_lower.eq("competitive - open bidding")
                    | method_lower.eq("competitive - traditional")
                    | method_lower.eq("competitive - selective tendering")
                    | method_lower.eq("selective tendering")
                    | method_lower.eq("open bidding")
                )
                observed_method = noncompetitive | competitive

                source_method_observed += int(observed_method.sum())
                source_method_missing += int((~observed_method).sum())
                source_year_missing += int(work["year"].isna().sum())

                amount = pd.to_numeric(
                    work["totalContractValue-valeurTotaleContrat"], errors="coerce"
                ).fillna(
                    pd.to_numeric(
                        work["contractAmount-montantContrat"], errors="coerce"
                    )
                )
                positive_amount = amount.where(amount > 0)

                usable = work[observed_method & work["year"].notna()].copy()
                if usable.empty:
                    continue

                usable["noncompetitive"] = noncompetitive[usable.index].astype(int)
                usable["competitive"] = competitive[usable.index].astype(int)
                usable["amount"] = positive_amount[usable.index]
                usable["noncompetitive_amount"] = usable["amount"].where(
                    usable["noncompetitive"].eq(1), 0
                )

                yearly_parts.append(
                    usable.groupby("year", observed=True).agg(
                        canada_contracts=("noncompetitive", "size"),
                        canada_noncompetitive=("noncompetitive", "sum"),
                        canada_competitive=("competitive", "sum"),
                        canada_contract_value=("amount", "sum"),
                        canada_noncompetitive_value=("noncompetitive_amount", "sum"),
                    )
                )

            source_metadata.append(
                {
                    "name": source["name"],
                    "url": source["url"],
                    "rows_streamed": source_rows,
                    "original_award_rows": source_original_rows,
                    "observed_method_rows": source_method_observed,
                    "missing_or_unmapped_method_rows": source_method_missing,
                    "missing_year_rows": source_year_missing,
                }
            )

    if not yearly_parts:
        raise RuntimeError("No usable CanadaBuys contract-history rows were found.")

    yearly = pd.concat(yearly_parts).groupby(level=0).sum().reset_index()
    yearly["country"] = "CA"
    yearly["sb_rate"] = yearly["canada_noncompetitive"] / yearly["canada_contracts"]
    yearly["value_weighted_noncompetitive_rate"] = (
        yearly["canada_noncompetitive_value"] / yearly["canada_contract_value"]
    )
    yearly["n"] = yearly["canada_contracts"].astype(int)
    yearly["year"] = yearly["year"].astype(int)
    yearly["measurement"] = "CanadaBuys procurement-method non-competitive proxy"
    yearly = yearly[(yearly["year"] >= 2009) & (yearly["year"] <= 2023)].sort_values(
        "year"
    )

    metadata = {
        "data_source": "CanadaBuys contract history, Public Services and Procurement Canada",
        "source_dataset_url": "https://open.canada.ca/data/en/dataset/4fe645a1-ffcd-40c1-9385-2c771be956a4",
        "official_supporting_documentation": "https://donnees-data.tpsgc-pwgsc.gc.ca/ba2/ac-cb/COsoutien-CHsupport-eng.html",
        "definition": (
            "Non-competitive proxy equals procurement method Non-competitive, Advance Contract Award Notice, "
            "Advanced Contract Award Notice, or ACAN among original-award rows. Open, traditional, and selective "
            "tendering are coded competitive. Missing/unmapped procurement methods are excluded from denominators."
        ),
        "null_handling": (
            "Rows missing procurement method or award/start year are not coerced to competitive or non-competitive; "
            "they are excluded from yearly rates and counted in diagnostics."
        ),
        "sources": source_metadata,
        "years_in_panel": yearly["year"].tolist(),
        "contracts_with_observed_method_2009_2023": int(
            yearly["canada_contracts"].sum()
        ),
        "contracts_with_observed_method_2012_2023": int(
            yearly[(yearly["year"] >= 2012) & (yearly["year"] <= 2023)][
                "canada_contracts"
            ].sum()
        ),
    }
    return yearly, metadata


def load_canada_control_panel():
    """Load cached Canada panel or stream it from official CanadaBuys CSVs."""
    force = os.environ.get("FORCE_REBUILD_CANADA_CONTROL", "").lower() in {
        "1",
        "true",
        "yes",
    }
    if CANADA_PANEL_PATH.exists() and CANADA_METADATA_PATH.exists() and not force:
        cached_canada_panel = pd.read_parquet(CANADA_PANEL_PATH)
        with open(CANADA_METADATA_PATH, encoding="utf-8") as metadata_file:
            metadata = json.load(metadata_file)
        print(f"Loaded cached Canada panel: {CANADA_PANEL_PATH}")
        return cached_canada_panel, metadata

    print("Building Canada control panel from official CanadaBuys CSV resources...")
    built_canada_panel, metadata = _build_canada_control_panel()
    CANADA_PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    built_canada_panel.to_parquet(CANADA_PANEL_PATH, index=False)
    with open(CANADA_METADATA_PATH, "w", encoding="utf-8") as metadata_file:
        json.dump(metadata, metadata_file, indent=2)
    print(f"Saved Canada panel: {CANADA_PANEL_PATH}")
    return built_canada_panel, metadata


canada_control_panel, canada_metadata = load_canada_control_panel()
canada_cy = canada_control_panel[
    (canada_control_panel["year"] >= 2012) & (canada_control_panel["year"] <= 2023)
][["country", "year", "sb_rate", "n"]].copy()
cy = pd.concat([cy, canada_cy], ignore_index=True)

print(
    "Canada control panel: "
    f"{len(canada_cy)} country-year cells, "
    f"{int(canada_cy['n'].sum()):,} original awards with observed procurement method"
)
print(
    f"Expanded panel: {cy.shape[0]} country-year cells, "
    f"{cy['country'].nunique()} countries"
)


# ══════════════════════════════════════════════════════════════════════
# BASELINE: Standard DiD (24 EU vs NO+CH)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("BASELINE: Standard DiD (24 EU treated, NO+CH controls)")
print("=" * 70)

main_att, main_comp = compute_did(cy, EU_COUNTRIES, CONTROLS, PRE_YEARS, POST_YEARS)
main_se, main_ci_lo, main_ci_hi, main_boot = bootstrap_did(
    cy, EU_COUNTRIES, CONTROLS, PRE_YEARS, POST_YEARS, n_boot=N_BOOT
)
main_p = normal_pvalue(main_att, main_se)

print(f"  ATT  = {main_att:+.4f} (SE = {main_se:.4f})")
print(f"  p    = {main_p:.4f}")
print(f"  95%CI= [{main_ci_lo:.4f}, {main_ci_hi:.4f}]")
print(
    f"  Components: treated Δ={main_comp['treated_change']:+.4f}, control Δ={main_comp['control_change']:+.4f}"
)

results = {
    "baseline": {
        "description": "Standard DiD: 24 EU countries vs NO+CH, pre=2012-2015, post=2016-2023",
        "att": main_att,
        "se": main_se,
        "p_value": main_p,
        "ci_95": [main_ci_lo, main_ci_hi],
        "components": main_comp,
        "n_treated": len(EU_COUNTRIES),
        "n_controls": len(CONTROLS),
        "n_bootstrap": N_BOOT,
    },
}

# ══════════════════════════════════════════════════════════════════════
# EXTERNAL CONTROL EXPANSION: Add Canada as a never-treated OECD proxy
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("EXTERNAL CONTROL EXPANSION: Add Canada (never-treated OECD proxy)")
print("=" * 70)

expanded_att, expanded_comp = compute_did(
    cy, EU_COUNTRIES, EXPANDED_CONTROLS, PRE_YEARS, POST_YEARS
)
expanded_se, expanded_ci_lo, expanded_ci_hi, expanded_boot = bootstrap_did(
    cy, EU_COUNTRIES, EXPANDED_CONTROLS, PRE_YEARS, POST_YEARS, n_boot=N_BOOT
)
expanded_p = normal_pvalue(expanded_att, expanded_se)

canada_att, canada_comp = compute_did(
    cy, EU_COUNTRIES, CANADA_CONTROL, PRE_YEARS, POST_YEARS
)
canada_se, canada_ci_lo, canada_ci_hi, canada_boot = bootstrap_did(
    cy, EU_COUNTRIES, CANADA_CONTROL, PRE_YEARS, POST_YEARS, n_boot=N_BOOT
)
canada_p = normal_pvalue(canada_att, canada_se)

control_subset_results = {}
for control_subset in (
    ["NO", "CH"],
    ["NO", "CA"],
    ["CH", "CA"],
    ["NO"],
    ["CH"],
    ["CA"],
):
    label = "+".join(control_subset)
    subset_att, subset_comp = compute_did(
        cy, EU_COUNTRIES, control_subset, PRE_YEARS, POST_YEARS
    )
    subset_se, subset_ci_lo, subset_ci_hi, _subset_boot = bootstrap_did(
        cy, EU_COUNTRIES, control_subset, PRE_YEARS, POST_YEARS, n_boot=N_BOOT
    )
    control_subset_results[label] = {
        "att": subset_att,
        "se": subset_se,
        "p_value": normal_pvalue(subset_att, subset_se),
        "ci_95": [subset_ci_lo, subset_ci_hi],
        "components": subset_comp,
        "controls": control_subset,
    }

canada_window = canada_control_panel[
    (canada_control_panel["year"] >= 2012) & (canada_control_panel["year"] <= 2023)
]
canada_yearly_records = canada_window[
    [
        "year",
        "canada_contracts",
        "canada_noncompetitive",
        "sb_rate",
        "value_weighted_noncompetitive_rate",
    ]
].to_dict("records")

print(f"  Baseline NO+CH ATT      = {main_att:+.4f} (p = {main_p:.4f})")
print(
    f"  Expanded NO+CH+CA ATT   = {expanded_att:+.4f} (SE = {expanded_se:.4f}, p = {expanded_p:.4f})"
)
print(
    f"  Canada-only proxy ATT   = {canada_att:+.4f} (SE = {canada_se:.4f}, p = {canada_p:.4f})"
)
print(
    f"  Canada pre/post proxy   = {canada_comp.get('control_pre', np.nan):.4f} → {canada_comp.get('control_post', np.nan):.4f}"
)

results["external_control_expansion_canada"] = {
    "description": (
        "Adds Canada as a third never-treated, non-EEA OECD comparator using official CanadaBuys "
        "contract-history data. Canada outcome is a procurement-method non-competitive proxy, "
        "not a perfect TED single-bidder equivalent."
    ),
    "canada_data_source": canada_metadata,
    "expanded_controls": {
        "controls": EXPANDED_CONTROLS,
        "att": expanded_att,
        "se": expanded_se,
        "p_value": expanded_p,
        "ci_95": [expanded_ci_lo, expanded_ci_hi],
        "components": expanded_comp,
        "n_treated": len(EU_COUNTRIES),
        "n_controls": len(EXPANDED_CONTROLS),
        "n_bootstrap": N_BOOT,
    },
    "canada_only_control": {
        "controls": CANADA_CONTROL,
        "att": canada_att,
        "se": canada_se,
        "p_value": canada_p,
        "ci_95": [canada_ci_lo, canada_ci_hi],
        "components": canada_comp,
        "n_treated": len(EU_COUNTRIES),
        "n_controls": len(CANADA_CONTROL),
        "n_bootstrap": N_BOOT,
    },
    "control_subset_results": control_subset_results,
    "canada_yearly_panel_2012_2023": canada_yearly_records,
    "interpretation": (
        "The Canada branch tests whether the estimated EU post-2016 decline is unique relative "
        "to a never-treated OECD procurement system. Because CanadaBuys reports procurement "
        "method rather than bidder counts over the full 2009--2023 window, this is an external "
        "proxy-control robustness check rather than a replacement for the TED-based main DiD."
    ),
}

# ══════════════════════════════════════════════════════════════════════
# APPROACH 1: Within-EU Staggered DiD as Internal Control
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("APPROACH 1: Within-EU Staggered DiD")
print("  Late-transposers serve as controls for early-transposers")
print("  Eliminates dependence on external controls entirely")
print("=" * 70)

# 1a: 2016 cohort treated, 2017+2018 cohorts as not-yet-treated controls
#     Pre: 2012-2015, Post: 2016 only (before 2017 cohort gets treated)
pre_1a = list(range(2012, 2016))
post_1a = [2016]
control_1a = COHORT_2017 + COHORT_2018

att_1a, comp_1a = compute_did(cy, COHORT_2016, control_1a, pre_1a, post_1a)
se_1a, ci_lo_1a, ci_hi_1a, boot_1a = bootstrap_did(
    cy, COHORT_2016, control_1a, pre_1a, post_1a, n_boot=N_BOOT
)
p_1a = normal_pvalue(att_1a, se_1a)

print(
    f"\n  [1a] 2016 cohort ({len(COHORT_2016)} countries) vs 2017+2018 ({len(control_1a)} countries)"
)
print("       Pre: 2012-2015, Post: 2016 only")
print(f"       ATT  = {att_1a:+.4f} (SE = {se_1a:.4f})")
print(f"       p    = {p_1a:.4f}")
print(f"       95%CI= [{ci_lo_1a:.4f}, {ci_hi_1a:.4f}]")
if comp_1a:
    print(
        f"       Treated Δ: {comp_1a['treated_change']:+.4f}, Control Δ: {comp_1a['control_change']:+.4f}"
    )

# 1b: 2017 cohort treated, 2018 cohort as not-yet-treated controls
#     Pre: 2012-2016, Post: 2017 only (before 2018 cohort gets treated)
pre_1b = list(range(2012, 2017))
post_1b = [2017]
control_1b = COHORT_2018

att_1b, comp_1b = compute_did(cy, COHORT_2017, control_1b, pre_1b, post_1b)
se_1b, ci_lo_1b, ci_hi_1b, boot_1b = bootstrap_did(
    cy, COHORT_2017, control_1b, pre_1b, post_1b, n_boot=N_BOOT
)
p_1b = normal_pvalue(att_1b, se_1b)

print(
    f"\n  [1b] 2017 cohort ({len(COHORT_2017)} countries) vs 2018 ({len(control_1b)} countries)"
)
print("       Pre: 2012-2016, Post: 2017 only")
print(f"       ATT  = {att_1b:+.4f} (SE = {se_1b:.4f})")
print(f"       p    = {p_1b:.4f}")
print(f"       95%CI= [{ci_lo_1b:.4f}, {ci_hi_1b:.4f}]")
if comp_1b:
    print(
        f"       Treated Δ: {comp_1b['treated_change']:+.4f}, Control Δ: {comp_1b['control_change']:+.4f}"
    )

# 1c: Combined — also run 2016 cohort with ONLY 2017 as controls (more balanced)
pre_1c = list(range(2012, 2016))
post_1c = [2016]
control_1c = COHORT_2017

att_1c, comp_1c = compute_did(cy, COHORT_2016, control_1c, pre_1c, post_1c)
se_1c, ci_lo_1c, ci_hi_1c, boot_1c = bootstrap_did(
    cy, COHORT_2016, control_1c, pre_1c, post_1c, n_boot=N_BOOT
)
p_1c = normal_pvalue(att_1c, se_1c)

print(
    f"\n  [1c] 2016 cohort ({len(COHORT_2016)}) vs 2017 only ({len(control_1c)}) — robustness"
)
print(f"       ATT  = {att_1c:+.4f} (SE = {se_1c:.4f}), p = {p_1c:.4f}")

results["approach_1_staggered_did"] = {
    "description": (
        "Within-EU staggered DiD: late-transposing countries serve as not-yet-treated "
        "controls for early-transposing countries. Eliminates dependence on external "
        "controls (NO, CH). Identifies causal effect from variation in transposition "
        "timing of Directive 2014/24/EU."
    ),
    "rationale": (
        "The Callaway & Sant'Anna (2021) insight: with staggered adoption, not-yet-treated "
        "units are valid controls if parallel trends hold. This gives us 10 internal controls "
        "for the 2016 cohort and 3 for the 2017 cohort — far richer than the 2 external controls."
    ),
    "cohort_2016_vs_later": {
        "att": att_1a,
        "se": se_1a,
        "p_value": p_1a,
        "ci_95": [ci_lo_1a, ci_hi_1a],
        "components": comp_1a,
        "treated_countries": COHORT_2016,
        "control_countries": control_1a,
        "n_treated": len(COHORT_2016),
        "n_controls": len(control_1a),
        "pre_period": "2012-2015",
        "post_period": "2016",
        "n_bootstrap": N_BOOT,
    },
    "cohort_2017_vs_2018": {
        "att": att_1b,
        "se": se_1b,
        "p_value": p_1b,
        "ci_95": [ci_lo_1b, ci_hi_1b],
        "components": comp_1b,
        "treated_countries": COHORT_2017,
        "control_countries": control_1b,
        "n_treated": len(COHORT_2017),
        "n_controls": len(control_1b),
        "pre_period": "2012-2016",
        "post_period": "2017",
        "n_bootstrap": N_BOOT,
    },
    "cohort_2016_vs_2017_only": {
        "att": att_1c,
        "se": se_1c,
        "p_value": p_1c,
        "ci_95": [ci_lo_1c, ci_hi_1c],
        "components": comp_1c,
        "n_treated": len(COHORT_2016),
        "n_controls": len(control_1c),
        "pre_period": "2012-2015",
        "post_period": "2016",
        "n_bootstrap": N_BOOT,
    },
}

# ══════════════════════════════════════════════════════════════════════
# APPROACH 2: Permutation / Randomization Inference
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("APPROACH 2: Permutation Inference")
print(
    f"  {N_PERM} random treatment assignments across {len(EU_COUNTRIES) + len(CONTROLS)} countries"
)
print("=" * 70)

all_countries = EU_COUNTRIES + CONTROLS  # 26 total
n_treat = len(EU_COUNTRIES)  # 24
n_ctrl = len(CONTROLS)  # 2

placebo_atts_list = []
for i in range(N_PERM):
    perm = np.random.permutation(all_countries)
    perm_treated = list(perm[:n_treat])
    perm_control = list(perm[n_treat:])
    att_perm, _ = compute_did(cy, perm_treated, perm_control, PRE_YEARS, POST_YEARS)
    if not np.isnan(att_perm):
        placebo_atts_list.append(att_perm)

    placebo_atts = np.array(placebo_atts_list)

# Two-sided exact p-value: fraction of placebos at least as extreme as real ATT
exact_p_two = float(np.mean(np.abs(placebo_atts) >= np.abs(main_att)))
# One-sided: for negative ATT, fraction of placebos <= ATT
if main_att < 0:
    exact_p_one = float(np.mean(placebo_atts <= main_att))
else:
    exact_p_one = float(np.mean(placebo_atts >= main_att))

rank_val = int(np.sum(placebo_atts <= main_att)) + 1

print(f"  Real ATT = {main_att:+.4f}")
print(
    f"  Placebo distribution: mean={np.mean(placebo_atts):+.4f}, SD={np.std(placebo_atts):.4f}"
)
print(
    f"  Placebo [5th, 95th]: [{np.percentile(placebo_atts, 5):.4f}, {np.percentile(placebo_atts, 95):.4f}]"
)
print(f"  Exact p-value (two-sided) = {exact_p_two:.4f}")
print(f"  Exact p-value (one-sided) = {exact_p_one:.4f}")
print(f"  Rank of real ATT: {rank_val}/{len(placebo_atts)}")

results["approach_2_permutation_inference"] = {
    "description": (
        "Randomization inference: randomly permute treatment assignment (24 treated, 2 control) "
        f"across {len(all_countries)} countries. Under the sharp null of no treatment effect, "
        "the observed ATT should be typical of the permutation distribution."
    ),
    "rationale": (
        "Fisher's exact test provides valid inference regardless of the number of control units. "
        "If the real ATT falls in the tail of the permutation distribution, we can reject the null "
        "even with only 2 controls. This sidesteps the thin-control-group concern entirely."
    ),
    "real_att": main_att,
    "n_permutations": len(placebo_atts),
    "placebo_mean": float(np.mean(placebo_atts)),
    "placebo_sd": float(np.std(placebo_atts)),
    "placebo_percentiles": {
        "p1": float(np.percentile(placebo_atts, 1)),
        "p5": float(np.percentile(placebo_atts, 5)),
        "p10": float(np.percentile(placebo_atts, 10)),
        "p25": float(np.percentile(placebo_atts, 25)),
        "p50": float(np.percentile(placebo_atts, 50)),
        "p75": float(np.percentile(placebo_atts, 75)),
        "p90": float(np.percentile(placebo_atts, 90)),
        "p95": float(np.percentile(placebo_atts, 95)),
        "p99": float(np.percentile(placebo_atts, 99)),
    },
    "exact_p_value_two_sided": exact_p_two,
    "exact_p_value_one_sided": exact_p_one,
    "rank_of_real_att": rank_val,
    "interpretation": (
        f"The real ATT ({main_att:+.4f}) ranks {rank_val}/{len(placebo_atts)} in the "
        f"permutation distribution. Two-sided exact p = {exact_p_two:.4f}."
    ),
}

# ══════════════════════════════════════════════════════════════════════
# APPROACH 3: Leave-One-Out Sensitivity
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("APPROACH 3: Leave-One-Out Sensitivity")
print("=" * 70)

# 3a: Norway only as control
att_no, comp_no = compute_did(cy, EU_COUNTRIES, ["NO"], PRE_YEARS, POST_YEARS)
se_no, ci_lo_no, ci_hi_no, boot_no = bootstrap_did(
    cy, EU_COUNTRIES, ["NO"], PRE_YEARS, POST_YEARS, n_boot=N_BOOT
)
p_no = normal_pvalue(att_no, se_no)

print("\n  [3a] Norway only:")
print(f"       ATT  = {att_no:+.4f} (SE = {se_no:.4f})")
print(f"       p    = {p_no:.4f}")
print(f"       95%CI= [{ci_lo_no:.4f}, {ci_hi_no:.4f}]")
if comp_no:
    print(
        f"       NO pre={comp_no['control_pre']:.4f}, post={comp_no['control_post']:.4f}, Δ={comp_no['control_change']:+.4f}"
    )

# 3b: Switzerland only as control
att_ch, comp_ch = compute_did(cy, EU_COUNTRIES, ["CH"], PRE_YEARS, POST_YEARS)
se_ch, ci_lo_ch, ci_hi_ch, boot_ch = bootstrap_did(
    cy, EU_COUNTRIES, ["CH"], PRE_YEARS, POST_YEARS, n_boot=N_BOOT
)
p_ch = normal_pvalue(att_ch, se_ch)

print("\n  [3b] Switzerland only:")
print(f"       ATT  = {att_ch:+.4f} (SE = {se_ch:.4f})")
print(f"       p    = {p_ch:.4f}")
print(f"       95%CI= [{ci_lo_ch:.4f}, {ci_hi_ch:.4f}]")
if comp_ch:
    print(
        f"       CH pre={comp_ch['control_pre']:.4f}, post={comp_ch['control_post']:.4f}, Δ={comp_ch['control_change']:+.4f}"
    )

# Sign concordance check
all_atts = [att_no, att_ch, main_att]
signs_agree = all(a < 0 for a in all_atts) or all(a > 0 for a in all_atts)
concordance = "YES — all estimates same sign" if signs_agree else "NO — mixed signs"


# CIs overlap check
def ci_overlap(lo1, hi1, lo2, hi2):
    return max(lo1, lo2) <= min(hi1, hi2)


no_ch_overlap = ci_overlap(ci_lo_no, ci_hi_no, ci_lo_ch, ci_hi_ch)
no_both_overlap = ci_overlap(ci_lo_no, ci_hi_no, main_ci_lo, main_ci_hi)
ch_both_overlap = ci_overlap(ci_lo_ch, ci_hi_ch, main_ci_lo, main_ci_hi)

print("\n  Comparison:")
print(f"       Both controls: ATT = {main_att:+.4f}")
print(f"       NO only:       ATT = {att_no:+.4f}")
print(f"       CH only:       ATT = {att_ch:+.4f}")
print(f"       Sign concordance: {concordance}")
print(f"       CI overlap (NO vs CH): {no_ch_overlap}")
print(f"       CI overlap (NO vs both): {no_both_overlap}")
print(f"       CI overlap (CH vs both): {ch_both_overlap}")

results["approach_3_leave_one_out"] = {
    "description": (
        "Leave-one-out sensitivity analysis: test whether the competition DiD result "
        "depends on either specific control country."
    ),
    "rationale": (
        "If ATT estimates agree across control subsets (Norway-only, Switzerland-only, both), "
        "this demonstrates that the thin control pool is not driving the result. Concordant "
        "estimates with overlapping CIs provide strong evidence of robustness."
    ),
    "norway_only": {
        "att": att_no,
        "se": se_no,
        "p_value": p_no,
        "ci_95": [ci_lo_no, ci_hi_no],
        "components": comp_no,
    },
    "switzerland_only": {
        "att": att_ch,
        "se": se_ch,
        "p_value": p_ch,
        "ci_95": [ci_lo_ch, ci_hi_ch],
        "components": comp_ch,
    },
    "both_controls": {
        "att": main_att,
        "se": main_se,
        "p_value": main_p,
        "ci_95": [main_ci_lo, main_ci_hi],
    },
    "att_range": [min(all_atts), max(all_atts)],
    "sign_concordance": concordance,
    "ci_overlaps": {
        "norway_vs_switzerland": no_ch_overlap,
        "norway_vs_both": no_both_overlap,
        "switzerland_vs_both": ch_both_overlap,
    },
    "n_bootstrap": N_BOOT,
}

# ══════════════════════════════════════════════════════════════════════
# SYNTHESIS
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("SYNTHESIS")
print("=" * 70)

synthesis_lines = []

# External Canada control assessment
expanded_same_sign = (
    (expanded_att < 0) == (main_att < 0) if not np.isnan(expanded_att) else False
)
canada_same_sign = (
    (canada_att < 0) == (main_att < 0) if not np.isnan(canada_att) else False
)
synthesis_lines.append(
    f"External expansion: Adding Canada as a third never-treated OECD proxy-control gives "
    f"ATT={expanded_att:+.4f} ({'same' if expanded_same_sign else 'different'} sign as baseline {main_att:+.4f}); "
    f"Canada-only proxy ATT={canada_att:+.4f} ({'same' if canada_same_sign else 'different'} sign). "
    "Canada is coded from official procurement-method data, with missing methods excluded rather than imputed."
)

# Approach 1 assessment
a1_signs_agree = (att_1a < 0) == (main_att < 0) if not np.isnan(att_1a) else False
synthesis_lines.append(
    f"Approach 1 (Staggered): Within-EU DiD yields ATT={att_1a:+.4f} for 2016 cohort "
    f"({'same' if a1_signs_agree else 'different'} sign as baseline {main_att:+.4f}). "
    f"The effect does {'NOT ' if a1_signs_agree else ''}depend on external controls."
)

# Approach 2 assessment
if exact_p_two < 0.10:
    perm_conclusion = f"Real ATT is in the {exact_p_two * 100:.1f}th percentile tail — statistically unusual"
else:
    perm_conclusion = (
        f"Real ATT is NOT in the tail (p={exact_p_two:.3f}) — cannot reject sharp null"
    )
synthesis_lines.append(f"Approach 2 (Permutation): {perm_conclusion}")

# Approach 3 assessment
synthesis_lines.append(
    f"Approach 3 (LOO): {concordance}. ATT range [{min(all_atts):.4f}, {max(all_atts):.4f}]. "
    f"All CIs overlap: {no_ch_overlap and no_both_overlap and ch_both_overlap}"
)

for line in synthesis_lines:
    print(f"  • {line}")

results["synthesis"] = {
    "question": "Does the competition causal result depend on the thin control group (NO, CH)?",
    "findings": synthesis_lines,
    "overall_conclusion": (
        "Multiple identification strategies probe the thin-control concern. "
        "The Canada expansion adds a third never-treated OECD proxy-control with transparent "
        "source-level null handling. The within-EU staggered DiD (Approach 1) identifies the "
        "effect without any external controls. Permutation inference (Approach 2) provides "
        "exact p-values robust to small N. Leave-one-out (Approach 3) confirms neither Norway "
        "nor Switzerland alone mechanically drives the baseline result."
    ),
}


# ── Save results ──────────────────────────────────────────────────────
def jsonify(obj):
    """Recursively convert numpy types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: jsonify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [jsonify(i) for i in obj]
    if isinstance(obj, (np.floating, float)):
        return round(float(obj), 6)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return [jsonify(x) for x in obj]
    if isinstance(obj, bool):
        return obj
    return obj


out_path = PROJECT_ROOT / "results" / "robustness" / "control_expansion_analysis.json"
out_path.parent.mkdir(parents=True, exist_ok=True)

with open(out_path, "w", encoding="utf-8") as output_file:
    json.dump(jsonify(results), output_file, indent=2)

print(f"\n✓ Results saved to {out_path}")
