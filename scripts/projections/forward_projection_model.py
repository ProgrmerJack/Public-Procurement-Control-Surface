"""
Forward-looking scenario model for procurement decarbonisation (2025–2035).

Builds three reform scenarios grounded in measured procurement parameters and
OECD-calibrated procurement spending data.  The conservative scenario uses the
attenuated conventional TWFE sensitivity (-0.71 pp), while the primary
staggered DiD estimate (-7.2 pp) remains separate from scenario calibration.

References
----------
- OECD Government at a Glance 2023
- Eurostat National Accounts (nama_10_gdp)
- EEA National GHG Inventories (UNFCCC)
- Authors' GPRD analysis (oecd_calibrated_numbers.json)
"""

import json
import warnings
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

warnings.filterwarnings("ignore")
# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / "pyproject.toml").exists() and _d != _d.parent:
    _d = _d.parent
ROOT = _d

# ═══════════════════════════════════════════════════════════════════════
# 1. OECD PROCUREMENT DATA — attempt download, fall back to published values
# ═══════════════════════════════════════════════════════════════════════


def fetch_oecd_procurement_data() -> Dict[str, Dict[str, float]]:
    """Try to pull procurement-as-%-of-GDP from OECD SDMX or .Stat APIs.

    Falls back to hardcoded values from OECD Government at a Glance 2023,
    Table 9.1: General government procurement spending as % of GDP (2021).
    """
    oecd_data = None

    # --- Attempt 1: OECD SDMX REST API (Government at a Glance) ---
    try:
        import requests

        url = (
            "https://sdmx.oecd.org/public/rest/data/"
            "OECD.GOV.GPP,DSD_GOV@DF_GOV_PROC,1.0/"
            "..GG_PROC_GDP..?format=jsondata&lastNObservations=1"
        )
        resp = requests.get(url, timeout=15, headers={"Accept": "application/json"})
        if resp.status_code == 200:
            payload = resp.json()
            print("✓ Downloaded OECD procurement data via SDMX API")
            oecd_data = _parse_sdmx_json(payload)
    except Exception as e:
        print(f"  SDMX API unavailable ({type(e).__name__}), trying .Stat…")

    # --- Attempt 2: OECD .Stat (legacy JSON-stat) ---
    if oecd_data is None:
        try:
            import requests

            url = (
                "https://stats.oecd.org/SDMX-JSON/data/GOV_PROC/"
                "GG_PROC_GDP.../all?startTime=2020&endTime=2022"
            )
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                payload = resp.json()
                print("✓ Downloaded OECD procurement data via .Stat API")
                oecd_data = _parse_oecd_stat_json(payload)
        except Exception as e:
            print(
                f"  .Stat API unavailable ({type(e).__name__}), using published values…"
            )

    # --- Fallback: hardcoded from OECD Government at a Glance 2023 ---
    if oecd_data is None:
        print("  Using hardcoded OECD Government at a Glance 2023 data (Table 9.1)")
        oecd_data = _hardcoded_oecd_data()

    return oecd_data


def _parse_sdmx_json(payload: dict) -> Dict[str, Dict[str, float]] | None:
    """Parse OECD SDMX JSON response into {country: {pct_gdp: float}}."""
    try:
        ds = payload["data"]["dataSets"][0]
        obs = ds.get("observations", ds.get("series", {}))
        dims = payload["data"]["structure"]["dimensions"]["observation"]
        country_dim = next(d for d in dims if "REF_AREA" in d.get("id", ""))
        result = {}
        for key, vals in obs.items():
            idx = int(key.split(":")[country_dim["keyPosition"]])
            iso = country_dim["values"][idx]["id"]
            value = vals[0] if isinstance(vals, list) else vals.get("value", None)
            if value is not None:
                result[iso] = {"pct_gdp": float(value) / 100.0}
        if len(result) >= 10:
            return result
    except Exception:
        pass
    return None


def _parse_oecd_stat_json(payload: dict) -> Dict[str, Dict[str, float]] | None:
    """Parse legacy OECD .Stat JSON-stat response."""
    try:
        ds = payload["dataSets"][0]
        dims = payload["structure"]["dimensions"]["series"]
        country_dim = dims[0]
        result = {}
        for key, series in ds["series"].items():
            idx = int(key.split(":")[0])
            iso = country_dim["values"][idx]["id"]
            obs = series.get("observations", {})
            if obs:
                last_key = max(obs.keys(), key=int)
                value = obs[last_key][0]
                if value is not None:
                    result[iso] = {"pct_gdp": float(value) / 100.0}
        if len(result) >= 10:
            return result
    except Exception:
        pass
    return None


def _hardcoded_oecd_data() -> Dict[str, Dict[str, float]]:
    """OECD Government at a Glance 2023: procurement as % of GDP (2021).

    Source: Table 9.1.  Values cross-checked with Eurostat gov_10a_main.
    G20 members marked with *.  EU-27 and associated countries included.
    """
    return {
        # --- EU-27 ---
        "DE": {"pct_gdp": 0.135, "gdp_eurB": 4121, "ghg_mt": 810, "ndc_pct": 0.40},
        "FR": {"pct_gdp": 0.145, "gdp_eurB": 2803, "ghg_mt": 376, "ndc_pct": 0.35},
        "IT": {"pct_gdp": 0.115, "gdp_eurB": 2085, "ghg_mt": 352, "ndc_pct": 0.40},
        "ES": {"pct_gdp": 0.105, "gdp_eurB": 1462, "ghg_mt": 270, "ndc_pct": 0.35},
        "NL": {"pct_gdp": 0.137, "gdp_eurB": 1008, "ghg_mt": 160, "ndc_pct": 0.40},
        "PL": {"pct_gdp": 0.105, "gdp_eurB": 688, "ghg_mt": 355, "ndc_pct": 0.45},
        "BE": {"pct_gdp": 0.120, "gdp_eurB": 582, "ghg_mt": 115, "ndc_pct": 0.35},
        "AT": {"pct_gdp": 0.120, "gdp_eurB": 477, "ghg_mt": 80, "ndc_pct": 0.35},
        "SE": {"pct_gdp": 0.160, "gdp_eurB": 552, "ghg_mt": 50, "ndc_pct": 0.20},
        "DK": {"pct_gdp": 0.135, "gdp_eurB": 382, "ghg_mt": 45, "ndc_pct": 0.40},
        "FI": {"pct_gdp": 0.155, "gdp_eurB": 275, "ghg_mt": 53, "ndc_pct": 0.30},
        "PT": {"pct_gdp": 0.105, "gdp_eurB": 268, "ghg_mt": 60, "ndc_pct": 0.30},
        "CZ": {"pct_gdp": 0.115, "gdp_eurB": 291, "ghg_mt": 130, "ndc_pct": 0.40},
        "RO": {"pct_gdp": 0.085, "gdp_eurB": 318, "ghg_mt": 115, "ndc_pct": 0.20},
        "HU": {"pct_gdp": 0.105, "gdp_eurB": 189, "ghg_mt": 64, "ndc_pct": 0.35},
        "IE": {"pct_gdp": 0.095, "gdp_eurB": 502, "ghg_mt": 60, "ndc_pct": 0.40},
        "BG": {"pct_gdp": 0.080, "gdp_eurB": 99, "ghg_mt": 60, "ndc_pct": 0.25},
        "SK": {"pct_gdp": 0.105, "gdp_eurB": 116, "ghg_mt": 42, "ndc_pct": 0.35},
        "HR": {"pct_gdp": 0.100, "gdp_eurB": 71, "ghg_mt": 24, "ndc_pct": 0.30},
        "LT": {"pct_gdp": 0.100, "gdp_eurB": 67, "ghg_mt": 20, "ndc_pct": 0.30},
        "LV": {"pct_gdp": 0.105, "gdp_eurB": 40, "ghg_mt": 12, "ndc_pct": 0.25},
        "EE": {"pct_gdp": 0.115, "gdp_eurB": 36, "ghg_mt": 16, "ndc_pct": 0.35},
        "SI": {"pct_gdp": 0.120, "gdp_eurB": 61, "ghg_mt": 17, "ndc_pct": 0.30},
        # --- EEA / associated ---
        "GB": {"pct_gdp": 0.130, "gdp_eurB": 2943, "ghg_mt": 398, "ndc_pct": 0.45},
        "NO": {"pct_gdp": 0.155, "gdp_eurB": 434, "ghg_mt": 50, "ndc_pct": 0.40},
        "CH": {"pct_gdp": 0.085, "gdp_eurB": 700, "ghg_mt": 46, "ndc_pct": 0.40},
        "IS": {"pct_gdp": 0.120, "gdp_eurB": 26, "ghg_mt": 4, "ndc_pct": 0.35},
        # --- G20 non-EU ---
        "US": {"pct_gdp": 0.120, "gdp_eurB": 23_500, "ghg_mt": 5222, "ndc_pct": 0.50},
        "CN": {"pct_gdp": 0.165, "gdp_eurB": 16_300, "ghg_mt": 12_100, "ndc_pct": 0.30},
        "JP": {"pct_gdp": 0.150, "gdp_eurB": 3_700, "ghg_mt": 1_066, "ndc_pct": 0.46},
        "IN": {"pct_gdp": 0.140, "gdp_eurB": 3_050, "ghg_mt": 3_400, "ndc_pct": 0.33},
        "BR": {"pct_gdp": 0.130, "gdp_eurB": 1_800, "ghg_mt": 2_170, "ndc_pct": 0.43},
        "KR": {"pct_gdp": 0.145, "gdp_eurB": 1_480, "ghg_mt": 616, "ndc_pct": 0.40},
        "AU": {"pct_gdp": 0.130, "gdp_eurB": 1_400, "ghg_mt": 488, "ndc_pct": 0.43},
        "MX": {"pct_gdp": 0.100, "gdp_eurB": 1_250, "ghg_mt": 665, "ndc_pct": 0.35},
        "ID": {"pct_gdp": 0.080, "gdp_eurB": 1_150, "ghg_mt": 1_700, "ndc_pct": 0.32},
        "SA": {"pct_gdp": 0.120, "gdp_eurB": 950, "ghg_mt": 672, "ndc_pct": 0.19},
        "TR": {"pct_gdp": 0.085, "gdp_eurB": 860, "ghg_mt": 506, "ndc_pct": 0.41},
        "AR": {"pct_gdp": 0.070, "gdp_eurB": 580, "ghg_mt": 366, "ndc_pct": 0.26},
        "ZA": {"pct_gdp": 0.090, "gdp_eurB": 330, "ghg_mt": 477, "ndc_pct": 0.28},
        "RU": {"pct_gdp": 0.100, "gdp_eurB": 1_700, "ghg_mt": 2_120, "ndc_pct": 0.30},
    }


# ═══════════════════════════════════════════════════════════════════════
# 2. VERIFIED PARAMETERS (from GPRD analysis)
# ═══════════════════════════════════════════════════════════════════════

PARAMS = {
    # EU procurement base (OECD-calibrated)
    "eu_procurement_eurB": 2552,
    "eu_sb_rate": 0.170,  # 17.0% single-bidder rate
    "eu_sb_spending_eurB": 434,  # = 2552 × 0.170
    "eu_carbon_intensity": 0.34,  # kg CO₂e per USD (SB mean)
    "eur_usd": 1.09,  # EUR→USD conversion
    # Causal estimates
    "did_att_pp": -0.71,  # Conventional TWFE sensitivity: -0.71 pp
    "did_att_se": 1.24,  # standard error
    "eu_premium_pct": -4.3,  # SB vs MB premium (EU context)
    # Nordic benchmark
    "nordic_sb_rate": 0.08,  # Denmark, Finland, Sweden avg
    "nordic_countries": ["SE", "DK", "FI"],
    # Financial parameters
    "monopoly_tax_lo": 0.07,  # 7% lower bound
    "monopoly_tax_hi": 0.10,  # 10% upper bound
    "monopoly_tax_central": 0.085,  # 8.5% central estimate
    "green_premium_lo": 0.10,  # 10% lower bound
    "green_premium_hi": 0.20,  # 20% upper bound
    "green_premium_central": 0.15,  # 15% central estimate
    # Dead zone and green substitution parameters
    "dz_val_share": 0.059,  # DZ sectors as share of procurement
    "dz_procurement_eurB": 151,  # DZ OECD-calibrated procurement
    "dz_sb_spending_eurB": 27,  # DZ SB spending
    "green_sub_fraction_lo": 0.059,  # conservative: only DZ sectors
    "green_sub_fraction_hi": 0.40,  # upper: broader carbon-int. sectors
    "green_sub_fraction_central": 0.20,  # central: ~20% of procurement
    # G20 baseline
    "g20_procurement_usdT": 11.0,
    "g20_sb_rate": 0.17,
    # Climate context
    "eu_total_carbon_mt": 983,  # total procurement carbon
    "eu_sb_carbon_mt": 161,  # SB procurement carbon
    "eu_national_ghg_mt": 3577,  # EU-context national GHG
}


# ═══════════════════════════════════════════════════════════════════════
# 3. SCENARIO DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════

SCENARIOS = {
    "conservative": {
        "label": "Conservative — attenuated TWFE sensitivity",
        "description": (
            "All EU Member States implement reforms achieving the attenuated "
            "conventional TWFE sensitivity (-0.71 pp) over 5 years. This is an "
            "illustrative lower-bound scenario; the primary staggered DiD "
            "estimate is -7.2 pp but is not used for this conservative input."
        ),
        "sb_reduction_pp": 0.71,  # percentage points
        "phase_in_years": 5,
        "reform_start": 2025,
        "reform_end": 2030,
        "scope": "eu",
        "confidence": "illustrative lower-bound — TWFE is attenuated and imprecise",
    },
    "moderate": {
        "label": "Moderate — Full e-procurement + transparency",
        "description": (
            "Comprehensive digital reform combining e-procurement mandates, "
            "open contracting data standards, and proactive market engagement. "
            "Assumes a 5 pp reduction over 10 years as a broader reform "
            "scenario rather than a direct extrapolation from the attenuated "
            "TWFE sensitivity."
        ),
        "sb_reduction_pp": 5.0,
        "phase_in_years": 10,
        "reform_start": 2025,
        "reform_end": 2035,
        "scope": "eu",
        "confidence": "medium — extrapolated from multiple reform cases",
    },
    "ambitious": {
        "label": "Ambitious — Nordic-level governance",
        "description": (
            "Convergence to Nordic governance standards (Denmark, Finland, "
            "Sweden average SB rate ≈ 8%).  Requires institutional reform, "
            "professionalised procurement, and sustained political commitment."
        ),
        "sb_reduction_pp": None,  # computed: current − 8%
        "target_sb_rate": 0.08,
        "phase_in_years": 15,
        "reform_start": 2025,
        "reform_end": 2040,
        "scope": "eu",
        "confidence": "lower — requires systemic governance change",
    },
}


# ═══════════════════════════════════════════════════════════════════════
# 4. PROJECTION ENGINE
# ═══════════════════════════════════════════════════════════════════════


def compute_sb_trajectory(
    baseline_sb: float,
    reduction_pp: float,
    phase_in_years: int,
    start_year: int = 2025,
    end_year: int = 2035,
) -> Dict[int, float]:
    """Compute year-by-year SB rate trajectory assuming linear phase-in.

    The SB rate decreases linearly during the phase-in window and stays
    constant afterwards (structural reforms are durable).
    """
    trajectory = {}
    annual_decrease = reduction_pp / 100.0 / phase_in_years  # as fraction
    for year in range(start_year, end_year + 1):
        years_elapsed = min(year - start_year, phase_in_years)
        sb_rate = max(baseline_sb - annual_decrease * years_elapsed, 0.01)
        trajectory[year] = round(sb_rate, 5)
    return trajectory


def compute_scenario_metrics(
    scenario_key: str,
    scenario: dict,
    oecd_data: Dict[str, Dict[str, float]],
    projection_end: int = 2035,
) -> Dict[str, Any]:
    """Compute full metrics for one scenario."""

    baseline_sb = PARAMS["eu_sb_rate"]
    procurement_eurB = PARAMS["eu_procurement_eurB"]
    ci_kg_usd = PARAMS["eu_carbon_intensity"]
    eur_usd = PARAMS["eur_usd"]

    # Determine SB reduction
    if scenario.get("sb_reduction_pp") is not None:
        reduction_pp = scenario["sb_reduction_pp"]
    else:
        target = scenario["target_sb_rate"]
        reduction_pp = (baseline_sb - target) * 100  # in pp

    phase_in = scenario["phase_in_years"]
    start = scenario["reform_start"]
    end = min(scenario.get("reform_end", projection_end), projection_end)

    # Year-by-year SB trajectory
    trajectory = compute_sb_trajectory(
        baseline_sb, reduction_pp, phase_in, start, projection_end
    )

    # Compute annual metrics
    annual_metrics = {}
    cumulative_spending = 0.0
    cumulative_carbon = 0.0
    cumulative_savings_lo = 0.0
    cumulative_savings_hi = 0.0

    for year in range(start, projection_end + 1):
        sb_rate = trajectory[year]
        sb_change = baseline_sb - sb_rate  # fraction, positive = improvement

        # Spending newly opened to competition
        newly_competitive_eurB = procurement_eurB * sb_change
        cumulative_spending += newly_competitive_eurB

        # Carbon footprint now accessible to GPP
        newly_competitive_usdB = newly_competitive_eurB * eur_usd
        carbon_accessible_mt = newly_competitive_usdB * ci_kg_usd
        cumulative_carbon += carbon_accessible_mt

        # Monopoly Tax savings (range)
        savings_lo = newly_competitive_eurB * PARAMS["monopoly_tax_lo"]
        savings_hi = newly_competitive_eurB * PARAMS["monopoly_tax_hi"]
        savings_central = newly_competitive_eurB * PARAMS["monopoly_tax_central"]
        cumulative_savings_lo += savings_lo
        cumulative_savings_hi += savings_hi

        # Green Premium cost — only the carbon-intensive fraction of newly
        # competitive spending requires low-carbon substitution.
        # Central estimate: ~20% of procurement has viable green alternatives.
        green_sub = PARAMS["green_sub_fraction_central"]
        green_premium_cost = (
            newly_competitive_eurB * green_sub * PARAMS["green_premium_central"]
        )

        annual_metrics[year] = {
            "sb_rate": round(sb_rate, 4),
            "sb_rate_pct": round(sb_rate * 100, 2),
            "newly_competitive_eurB": round(newly_competitive_eurB, 1),
            "carbon_accessible_mt": round(carbon_accessible_mt, 1),
            "savings_central_eurB": round(savings_central, 1),
            "savings_range_eurB": [round(savings_lo, 1), round(savings_hi, 1)],
            "green_premium_cost_eurB": round(green_premium_cost, 1),
            "self_funding_ratio": round(savings_central / green_premium_cost, 2)
            if green_premium_cost > 0
            else None,
            "cumulative_spending_eurB": round(cumulative_spending, 1),
            "cumulative_carbon_mt": round(cumulative_carbon, 1),
        }

    # Milestone snapshots
    snap_2030 = annual_metrics.get(2030, {})
    snap_2035 = annual_metrics.get(2035, {})

    # EU aggregate carbon in NDC context
    national_ghg = PARAMS["eu_national_ghg_mt"]
    final_carbon = snap_2035.get(
        "carbon_accessible_mt", snap_2030.get("carbon_accessible_mt", 0)
    )

    # G20 extrapolation (assuming same proportional SB reduction)
    g20_proc_eurB = PARAMS["g20_procurement_usdT"] * 1000 / eur_usd
    g20_factor = g20_proc_eurB / procurement_eurB
    g20_spending_2035 = snap_2035.get("newly_competitive_eurB", 0) * g20_factor
    g20_carbon_2035 = snap_2035.get("carbon_accessible_mt", 0) * g20_factor

    return {
        "scenario": scenario_key,
        "label": scenario["label"],
        "description": scenario["description"],
        "confidence": scenario["confidence"],
        "parameters": {
            "baseline_sb_rate": baseline_sb,
            "sb_reduction_pp": round(reduction_pp, 2),
            "phase_in_years": phase_in,
            "reform_window": f"{start}–{end}",
            "final_sb_rate": round(trajectory[projection_end], 4),
            "final_sb_rate_pct": round(trajectory[projection_end] * 100, 2),
        },
        "milestones": {
            "2030": {
                "sb_rate_pct": snap_2030.get("sb_rate_pct"),
                "newly_competitive_eurB": snap_2030.get("newly_competitive_eurB"),
                "carbon_accessible_mt": snap_2030.get("carbon_accessible_mt"),
                "savings_central_eurB": snap_2030.get("savings_central_eurB"),
                "cumulative_spending_eurB": snap_2030.get("cumulative_spending_eurB"),
                "cumulative_carbon_mt": snap_2030.get("cumulative_carbon_mt"),
            },
            "2035": {
                "sb_rate_pct": snap_2035.get("sb_rate_pct"),
                "newly_competitive_eurB": snap_2035.get("newly_competitive_eurB"),
                "carbon_accessible_mt": snap_2035.get("carbon_accessible_mt"),
                "savings_central_eurB": snap_2035.get("savings_central_eurB"),
                "cumulative_spending_eurB": snap_2035.get("cumulative_spending_eurB"),
                "cumulative_carbon_mt": snap_2035.get("cumulative_carbon_mt"),
            },
        },
        "g20_extrapolation_2035": {
            "spending_newly_competitive_eurB": round(g20_spending_2035, 0),
            "carbon_accessible_mt": round(g20_carbon_2035, 0),
        },
        "ndc_context": {
            "eu_national_ghg_mt": national_ghg,
            "final_carbon_pct_national": round(final_carbon / national_ghg * 100, 2)
            if national_ghg > 0
            else None,
        },
        "annual_trajectory": annual_metrics,
    }


def compute_sensitivity(
    base_reduction_pp: float = 0.71,
    se: float = 1.24,
) -> Dict[str, Any]:
    """±1 SE and ±2 SE sensitivity bounds on the conservative scenario."""
    procurement = PARAMS["eu_procurement_eurB"]
    ci = PARAMS["eu_carbon_intensity"]
    eur_usd = PARAMS["eur_usd"]

    variants = {}
    for label, pp in [
        ("lower_2se", base_reduction_pp - 2 * se),
        ("lower_1se", base_reduction_pp - 1 * se),
        ("central", base_reduction_pp),
        ("upper_1se", base_reduction_pp + 1 * se),
        ("upper_2se", base_reduction_pp + 2 * se),
    ]:
        effective_pp = max(pp, 0)
        delta_frac = effective_pp / 100.0
        newly_comp = procurement * delta_frac
        carbon = newly_comp * eur_usd * ci
        savings = newly_comp * PARAMS["monopoly_tax_central"]
        variants[label] = {
            "sb_reduction_pp": round(pp, 2),
            "effective_sb_reduction_pp": round(effective_pp, 2),
            "newly_competitive_eurB": round(newly_comp, 1),
            "carbon_accessible_mt": round(carbon, 1),
            "savings_eurB": round(savings, 1),
        }
    return {
        "note": "Sensitivity of conservative scenario to ±1 SE and ±2 SE of the attenuated TWFE sensitivity; negative reductions are clipped to zero for projection magnitudes",
        "twfe_att_pp": -base_reduction_pp,
        "twfe_att_se": se,
        "base_sb_reduction_pp": base_reduction_pp,
        "variants": variants,
    }


def compute_self_funding_analysis() -> Dict[str, Any]:
    """Show that Monopoly Tax savings can fund the Green Premium.

    Key insight: Monopoly Tax applies to ALL newly competitive spending,
    but the Green Premium only applies to the carbon-intensive fraction
    that needs low-carbon substitution.  At EU level, the Dead Zones
    (high-CI ∩ high-SB sectors) represent ~6% of procurement, while
    broader carbon-intensive sectors represent ~20–40%.
    """
    procurement = PARAMS["eu_procurement_eurB"]

    results = {}
    for scenario_label, newly_comp_frac in [
        ("conservative_5yr", 0.71 / 100),
        ("moderate_10yr", 5.0 / 100),
        ("ambitious_15yr", 9.0 / 100),
    ]:
        newly_comp = procurement * newly_comp_frac
        for mt_pct in [0.07, 0.085, 0.10]:
            for gp_pct in [0.10, 0.15, 0.20]:
                for gs_frac, gs_label in [
                    (PARAMS["green_sub_fraction_lo"], "dz_only"),
                    (PARAMS["green_sub_fraction_central"], "central"),
                    (PARAMS["green_sub_fraction_hi"], "broad"),
                ]:
                    case = f"mt{int(mt_pct * 100)}_gp{int(gp_pct * 100)}_gs{gs_label}"
                    savings = newly_comp * mt_pct
                    green_cost = newly_comp * gs_frac * gp_pct
                    results[f"{scenario_label}_{case}"] = {
                        "newly_competitive_eurB": round(newly_comp, 1),
                        "monopoly_tax_pct": mt_pct,
                        "green_premium_pct": gp_pct,
                        "green_sub_fraction": gs_frac,
                        "green_sub_label": gs_label,
                        "savings_eurB": round(savings, 1),
                        "green_premium_cost_eurB": round(green_cost, 1),
                        "self_funding_ratio": round(savings / green_cost, 2)
                        if green_cost > 0
                        else None,
                        "net_fiscal_eurB": round(savings - green_cost, 1),
                    }

    # Summary: central estimates across scenarios
    summary = {}
    for scenario_label, newly_comp_frac in [
        ("conservative", 0.71 / 100),
        ("moderate", 5.0 / 100),
        ("ambitious", 6.0 / 100),
    ]:
        nc = procurement * newly_comp_frac
        mt = nc * PARAMS["monopoly_tax_central"]
        gp_dz = nc * PARAMS["green_sub_fraction_lo"] * PARAMS["green_premium_central"]
        gp_central = (
            nc * PARAMS["green_sub_fraction_central"] * PARAMS["green_premium_central"]
        )
        gp_broad = (
            nc * PARAMS["green_sub_fraction_hi"] * PARAMS["green_premium_central"]
        )
        summary[scenario_label] = {
            "monopoly_tax_eurB": round(mt, 1),
            "green_cost_dz_only_eurB": round(gp_dz, 1),
            "green_cost_central_eurB": round(gp_central, 1),
            "green_cost_broad_eurB": round(gp_broad, 1),
            "self_funding_dz_only": round(mt / gp_dz, 2) if gp_dz > 0 else None,
            "self_funding_central": round(mt / gp_central, 2)
            if gp_central > 0
            else None,
            "self_funding_broad": round(mt / gp_broad, 2) if gp_broad > 0 else None,
        }
    return {"detail": results, "summary": summary}


# ═══════════════════════════════════════════════════════════════════════
# 5. MANUSCRIPT TEXT GENERATION
# ═══════════════════════════════════════════════════════════════════════


def generate_manuscript_text(results: Dict[str, Any]) -> str:
    """Format key findings as a brief Results subsection."""

    cons = results["scenarios"]["conservative"]
    mod = results["scenarios"]["moderate"]
    amb = results["scenarios"]["ambitious"]

    c30 = cons["milestones"]["2030"]
    c35 = cons["milestones"]["2035"]
    m30 = mod["milestones"]["2030"]
    m35 = mod["milestones"]["2035"]
    a30 = amb["milestones"]["2030"]
    a35 = amb["milestones"]["2035"]

    sens = results["sensitivity"]["variants"]
    sf = results["self_funding"]["summary"]

    text = f"""
==========================================================================
  MANUSCRIPT TEXT — Forward-looking scenario projections (2025–2035)
==========================================================================

--- Suggested Results subsection (≈300 words) ---

Forward-looking projections.  To assess the aggregate policy potential of
reducing single-bidder procurement, we project three reform scenarios
over 2025–2035, using the attenuated conventional TWFE sensitivity
(ATT = -0.71 pp; reported as a directional lower-bound sensitivity) and
calibrated to OECD procurement spending data (€{PARAMS["eu_sb_spending_eurB"]}B single-bidder spending on a
€{PARAMS["eu_procurement_eurB"]:,}B base at a {PARAMS["eu_sb_rate"] * 100:.1f}%
baseline rate; OECD Government at a Glance 2023).

Under the Conservative scenario — applying the attenuated TWFE point estimate
of -0.71 pp over five years — €{c30["newly_competitive_eurB"]}B in annual procurement
spending is newly opened to competition by 2030, unlocking
{c30["carbon_accessible_mt"]} Mt CO₂e in procurement carbon for Green
Public Procurement (GPP) eligibility.  Cumulative competitive spending
opened over 2025–2030 totals €{c30["cumulative_spending_eurB"]:,.0f}B,
with Monopoly Tax savings of €{c30["savings_central_eurB"]}B annually
(8.5% central; range 7–10%). Because the TWFE sensitivity is imprecise,
the lower uncertainty bounds include zero; this conservative scenario is
therefore illustrative and should be interpreted alongside the primary
staggered DiD estimate rather than as a standalone forecast.

The Moderate scenario (-5.0 pp over 10 years, representing a broader
e-procurement and transparency reform package) opens €{m35["newly_competitive_eurB"]}B
annually by 2035, accessing {m35["carbon_accessible_mt"]} Mt CO₂e.  The
Ambitious scenario reaches an 11% SB rate by 2035 on the path toward the
Nordic-level 8% benchmark, opening €{a35["newly_competitive_eurB"]}B
and {a35["carbon_accessible_mt"]} Mt CO₂e.

The fiscal case for reform is compelling.  Monopoly Tax savings (8.5%
central estimate applied to all newly competitive spending) substantially
exceed Green Premium costs (10–20% applied only to the carbon-intensive
fraction requiring low-carbon substitution).  At the central estimate,
the self-funding ratio is {sf["conservative"]["self_funding_central"]:.1f}×
for the Conservative scenario and {sf["ambitious"]["self_funding_central"]:.1f}×
for the Ambitious scenario — taxpayer savings from eliminating monopoly
rents can finance green transition in public purchasing with fiscal
headroom to spare.

--- End of suggested text ---
"""
    return text


# ═══════════════════════════════════════════════════════════════════════
# 6. MAIN
# ═══════════════════════════════════════════════════════════════════════


def main():
    print("=" * 70)
    print("FORWARD PROJECTION MODEL — Procurement Decarbonisation (2025–2035)")
    print("=" * 70)

    # Step 1: Fetch OECD data
    print("\n[Step 1] Fetching OECD procurement data…")
    oecd_data = fetch_oecd_procurement_data()
    print(f"  Loaded data for {len(oecd_data)} countries")

    # Verify EU total matches calibration
    eu_countries = [
        "DE",
        "FR",
        "IT",
        "ES",
        "NL",
        "PL",
        "BE",
        "AT",
        "SE",
        "DK",
        "FI",
        "PT",
        "CZ",
        "RO",
        "HU",
        "IE",
        "BG",
        "SK",
        "HR",
        "LT",
        "LV",
        "EE",
        "SI",
        "GB",
        "NO",
        "CH",
        "IS",
    ]
    eu_total = sum(
        oecd_data[c]["gdp_eurB"] * oecd_data[c]["pct_gdp"]
        for c in eu_countries
        if c in oecd_data
    )
    print(
        f"  EU-context procurement total: €{eu_total:,.0f}B "
        f"(calibration target: €{PARAMS['eu_procurement_eurB']:,}B)"
    )

    # G20 verification
    g20_countries = [
        "US",
        "CN",
        "JP",
        "DE",
        "GB",
        "FR",
        "IN",
        "IT",
        "BR",
        "CA",
        "KR",
        "AU",
        "MX",
        "ID",
        "SA",
        "TR",
        "AR",
        "ZA",
        "RU",
        "ES",
    ]
    g20_total_eurB = sum(
        oecd_data[c]["gdp_eurB"] * oecd_data[c]["pct_gdp"]
        for c in g20_countries
        if c in oecd_data
    )
    g20_total_usdT = g20_total_eurB * PARAMS["eur_usd"] / 1000
    print(
        f"  G20 procurement total: ~${g20_total_usdT:,.1f}T "
        f"(reference: ${PARAMS['g20_procurement_usdT']}T)"
    )

    # Step 2: Run scenarios
    print(f"\n[Step 2] Computing scenario projections…")
    scenario_results = {}
    for key, scenario in SCENARIOS.items():
        result = compute_scenario_metrics(key, scenario, oecd_data)
        scenario_results[key] = result
        m30 = result["milestones"]["2030"]
        m35 = result["milestones"]["2035"]
        print(f"\n  ■ {result['label']}")
        print(
            f"    SB reduction: {result['parameters']['sb_reduction_pp']:.2f} pp "
            f"over {result['parameters']['phase_in_years']} years"
        )
        print(
            f"    2030: SB rate → {m30['sb_rate_pct']:.1f}%, "
            f"€{m30['newly_competitive_eurB']}B competitive, "
            f"{m30['carbon_accessible_mt']} Mt CO₂e accessible"
        )
        print(
            f"    2035: SB rate → {m35['sb_rate_pct']:.1f}%, "
            f"€{m35['newly_competitive_eurB']}B competitive, "
            f"{m35['carbon_accessible_mt']} Mt CO₂e accessible"
        )
        print(
            f"    Cumulative by 2035: "
            f"€{m35['cumulative_spending_eurB']:,.0f}B spending, "
            f"{m35['cumulative_carbon_mt']:,.0f} Mt CO₂e"
        )

    # Step 3: Sensitivity
    print(f"\n[Step 3] Sensitivity analysis (Conservative scenario ± SE)…")
    sensitivity = compute_sensitivity()
    for label, v in sensitivity["variants"].items():
        print(
            f"  {label:>12s}: raw ΔSB={v['sb_reduction_pp']:+.2f} pp "
            f"(effective {v['effective_sb_reduction_pp']:.2f} pp) → "
            f"€{v['newly_competitive_eurB']}B competitive, "
            f"{v['carbon_accessible_mt']} Mt CO₂e"
        )

    # Step 4: Self-funding analysis
    print(f"\n[Step 4] Self-funding analysis (Monopoly Tax vs Green Premium)…")
    self_funding = compute_self_funding_analysis()
    print("  Central estimates (MT 8.5%, GP 15%, green sub fraction varies):")
    for key, v in self_funding["summary"].items():
        print(
            f"  ■ {key}: MT savings €{v['monopoly_tax_eurB']}B; "
            f"GP cost €{v['green_cost_dz_only_eurB']}B (DZ only) / "
            f"€{v['green_cost_central_eurB']}B (central) / "
            f"€{v['green_cost_broad_eurB']}B (broad)"
        )
        print(
            f"    Self-funding ratio: "
            f"{v['self_funding_dz_only']:.1f}× (DZ) / "
            f"{v['self_funding_central']:.1f}× (central) / "
            f"{v['self_funding_broad']:.1f}× (broad)"
        )

    # Aggregate output
    full_results = {
        "metadata": {
            "model": "Forward Projection Model v1.0",
            "projection_window": "2025–2035",
            "data_source": "OECD Government at a Glance 2023; authors' GPRD analysis",
            "eu_procurement_eurB": PARAMS["eu_procurement_eurB"],
            "eu_sb_rate": PARAMS["eu_sb_rate"],
            "did_att_pp": PARAMS["did_att_pp"],
            "did_att_se": PARAMS["did_att_se"],
            "carbon_intensity_kg_usd": PARAMS["eu_carbon_intensity"],
            "eur_usd": PARAMS["eur_usd"],
            "n_oecd_countries": len(oecd_data),
        },
        "scenarios": scenario_results,
        "sensitivity": sensitivity,
        "self_funding": self_funding,
        "oecd_data_summary": {
            "eu_total_procurement_eurB": round(eu_total),
            "g20_total_procurement_usdT": round(g20_total_usdT, 1),
            "n_eu_countries": len([c for c in eu_countries if c in oecd_data]),
            "n_g20_countries": len([c for c in g20_countries if c in oecd_data]),
        },
    }

    # Step 5: Save results
    out_path = ROOT / "results" / "projections" / "forward_projections.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(full_results, f, indent=2)
    print(f"\n[Step 5] Results saved to {out_path.relative_to(ROOT)}")

    # Step 6: Manuscript text
    print(generate_manuscript_text(full_results))

    # Summary table
    print("=" * 70)
    print("SUMMARY TABLE — Three scenarios for manuscript")
    print("=" * 70)
    header = (
        f"{'Scenario':<16} {'SB Δ (pp)':<10} {'Phase-in':<10} "
        f"{'€B/yr (2035)':<14} {'Mt CO₂e/yr':<12} "
        f"{'Cum. Mt (2035)':<15} {'Self-fund':<10}"
    )
    print(header)
    print("-" * len(header))
    for key in ["conservative", "moderate", "ambitious"]:
        r = scenario_results[key]
        m35 = r["milestones"]["2035"]
        sf_ratio = self_funding["summary"][key]["self_funding_central"]
        print(
            f"{key:<16} {r['parameters']['sb_reduction_pp']:<10.2f} "
            f"{r['parameters']['phase_in_years']:<10} "
            f"€{m35['newly_competitive_eurB']:<13} "
            f"{m35['carbon_accessible_mt']:<12} "
            f"{m35['cumulative_carbon_mt']:<15,.0f} "
            f"{sf_ratio:<10.1f}×"
        )

    print("\n✓ Forward projection model complete.")
    return full_results


if __name__ == "__main__":
    main()
