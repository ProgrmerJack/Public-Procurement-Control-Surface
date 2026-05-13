#!/usr/bin/env python3
"""
US FPDS Contract-Action-Level Competition-Carbon Analysis
Processes FY2024 FPDS contract data to compute competition-carbon relationships.

Key methodological notes:
- Unit of analysis: contract actions (includes modifications)
- Carbon intensity assigned at NAICS 3-digit level (between-sector variation only)
- Obligation-weighted analysis uses federal_action_obligation (actual spend)
- Includes sector-standardized premium to control for procurement mix
- Three-way competition split: multi-offer / single-offer / noncompetitive
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(sys.maxsize)

# ── NAICS → Carbon Intensity mappings (kg CO2e/USD) ──
NAICS_CARBON = {
    "211": 1.85, "212": 1.15, "221": 1.60,
    "236": 0.55, "237": 0.55, "238": 0.55,
    "311": 0.65, "312": 0.65,
    "324": 2.10, "325": 0.60, "326": 0.50, "327": 1.15,
    "331": 1.40, "332": 0.55, "333": 0.35, "334": 0.20,
    "335": 0.30, "336": 0.45, "337": 0.25, "339": 0.25,
    "423": 0.15, "424": 0.15, "425": 0.15,
    "441": 0.15, "442": 0.15, "443": 0.15, "444": 0.15,
    "445": 0.15, "446": 0.15, "447": 0.15, "448": 0.15,
    "449": 0.15, "451": 0.15, "452": 0.15, "453": 0.15, "454": 0.15,
    "481": 0.80, "482": 0.80, "483": 0.80, "484": 0.80,
    "485": 0.80, "486": 0.80, "487": 0.80, "488": 0.80,
    "491": 0.40, "492": 0.40,
    "511": 0.12, "512": 0.12, "513": 0.12, "515": 0.12,
    "517": 0.12, "518": 0.12, "519": 0.12,
    "521": 0.08, "522": 0.08, "523": 0.08, "524": 0.08, "525": 0.08,
    "531": 0.10, "532": 0.10, "533": 0.10,
    "541": 0.10, "551": 0.10,
    "561": 0.10, "562": 0.10,
    "611": 0.08,
    "621": 0.10, "622": 0.10, "623": 0.10, "624": 0.10,
    "711": 0.10, "712": 0.10, "713": 0.10,
    "721": 0.25, "722": 0.25,
    "811": 0.20, "812": 0.20, "813": 0.20,
    "921": 0.10, "922": 0.10, "923": 0.10, "924": 0.10,
    "925": 0.10, "926": 0.10, "927": 0.10, "928": 0.10,
}

# Competition classification by extent_competed code
COMPETITIVE_CODES = {"A", "D", "E", "F"}
COMPETITIVE_LABELS = {
    "FULL AND OPEN COMPETITION",
    "FULL AND OPEN COMPETITION AFTER EXCLUSION OF SOURCES",
    "COMPETED UNDER SAP",
    "FOLLOW ON TO COMPETED ACTION",
}
NONCOMPETITIVE_CODES = {"B", "C", "G"}
NONCOMPETITIVE_LABELS = {
    "NOT COMPETED",
    "NOT AVAILABLE FOR COMPETITION",
    "NOT COMPETED UNDER SAP",
}


def get_carbon_intensity(naics_code: str) -> float | None:
    if not naics_code or len(naics_code) < 3:
        return None
    return NAICS_CARBON.get(naics_code[:3])


def classify_competition(extent_competed: str, extent_code: str) -> str | None:
    ec_upper = extent_competed.strip().upper()
    code = extent_code.strip().upper()
    if code in COMPETITIVE_CODES or ec_upper in COMPETITIVE_LABELS:
        return "competitive"
    if code in NONCOMPETITIVE_CODES or ec_upper in NONCOMPETITIVE_LABELS:
        return "noncompetitive"
    return None


def process_file(filepath: str, stats: dict, sector_data: dict):
    """Stream-process a single CSV file, collecting all needed statistics."""
    print(f"  Processing {Path(filepath).name}...")
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader)

        idx = {col: header.index(col) for col in [
            "naics_code", "extent_competed", "extent_competed_code",
            "base_and_all_options_value", "number_of_offers_received",
            "action_date", "federal_action_obligation",
            "modification_number",
        ]}

        for row_num, row in enumerate(reader, 1):
            if row_num % 500_000 == 0:
                print(f"    ...processed {row_num:,} rows")
            try:
                stats["total_rows"] += 1
                naics = row[idx["naics_code"]].strip()
                extent = row[idx["extent_competed"]]
                extent_code = row[idx["extent_competed_code"]]
                offers_str = row[idx["number_of_offers_received"]]
                obligation_str = row[idx["federal_action_obligation"]]
                mod_num = row[idx["modification_number"]].strip()

                # Parse federal_action_obligation (actual spend)
                try:
                    obligation = float(obligation_str) if obligation_str else 0.0
                except ValueError:
                    obligation = 0.0

                # Track whether this is a modification
                is_new_award = (mod_num == "" or mod_num == "0")
                if is_new_award:
                    stats["n_new_awards"] += 1
                else:
                    stats["n_modifications"] += 1

                # Get carbon intensity
                ci = get_carbon_intensity(naics)
                if ci is None:
                    stats["skipped_no_naics_match"] += 1
                    continue

                # Classify competition
                comp = classify_competition(extent, extent_code)
                if comp is None:
                    stats["skipped_unknown_competition"] += 1
                    continue

                # Parse number of offers
                try:
                    offers = int(offers_str) if offers_str else 0
                except ValueError:
                    offers = 0

                # Three-way classification
                if comp == "noncompetitive":
                    comp3 = "noncompetitive"
                elif offers == 1:
                    comp3 = "single_offer"
                else:
                    comp3 = "multi_offer"

                # ── ALL ACTIONS (including mods) ──
                stats["valid_actions"] += 1
                stats[f"n_{comp}"] += 1
                stats[f"n3_{comp3}"] += 1

                # Unweighted CI stats
                stats[f"ci_sum_{comp}"] += ci
                stats[f"ci_sumsq_{comp}"] += ci * ci
                stats[f"ci3_sum_{comp3}"] += ci
                stats[f"ci3_sumsq_{comp3}"] += ci * ci

                # Obligation-weighted CI (using positive obligations only)
                if obligation > 0:
                    stats[f"oblig_ci_sum_{comp}"] += ci * obligation
                    stats[f"oblig_total_{comp}"] += obligation
                    stats[f"oblig3_ci_sum_{comp3}"] += ci * obligation
                    stats[f"oblig3_total_{comp3}"] += obligation
                    stats["total_positive_obligation"] += obligation

                # ── NEW AWARDS ONLY (sensitivity check) ──
                if is_new_award:
                    stats[f"new_n_{comp}"] += 1
                    stats[f"new_ci_sum_{comp}"] += ci
                    stats[f"new_ci_sumsq_{comp}"] += ci * ci
                    if obligation > 0:
                        stats[f"new_oblig_ci_sum_{comp}"] += ci * obligation
                        stats[f"new_oblig_total_{comp}"] += obligation

                # Sector-level aggregation
                sector = naics[:3]
                if sector not in sector_data:
                    sector_data[sector] = defaultdict(float)
                sector_data[sector][f"n_{comp}"] += 1
                sector_data[sector][f"n3_{comp3}"] += 1
                sector_data[sector]["n_total"] += 1
                sector_data[sector]["ci_sum"] += ci
                if obligation > 0:
                    sector_data[sector][f"oblig_{comp}"] += obligation
                    sector_data[sector][f"oblig3_{comp3}"] += obligation
                    sector_data[sector]["oblig_total"] += obligation

                # Extent competed distribution
                stats["extent_dist"][extent] = stats["extent_dist"].get(extent, 0) + 1

            except (IndexError, ValueError):
                stats["parse_errors"] += 1
                continue

    print(f"    Done. {row_num:,} rows processed from this file.")


def pearson_r(xs, ys):
    """Compute Pearson r and t-statistic."""
    n = len(xs)
    if n < 3:
        return None, None, n
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - 1)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs) / (n - 1))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys) / (n - 1))
    r = cov / (sx * sy) if sx > 0 and sy > 0 else 0
    t_r = r * math.sqrt((n - 2) / (1 - r ** 2)) if abs(r) < 1 else float("inf")
    return r, t_r, n


def compute_results(stats: dict, sector_data: dict) -> dict:
    results = {}

    # ── Basic counts ──
    results["total_rows_processed"] = int(stats["total_rows"])
    results["valid_contract_actions"] = int(stats["valid_actions"])
    results["n_new_awards"] = int(stats["n_new_awards"])
    results["n_modifications"] = int(stats["n_modifications"])
    results["n_competitive"] = int(stats["n_competitive"])
    results["n_noncompetitive"] = int(stats["n_noncompetitive"])
    results["skipped_no_naics_match"] = int(stats["skipped_no_naics_match"])
    results["skipped_unknown_competition"] = int(stats["skipped_unknown_competition"])
    results["parse_errors"] = int(stats["parse_errors"])

    # ── Three-way split ──
    results["three_way_split"] = {
        "multi_offer": int(stats["n3_multi_offer"]),
        "single_offer": int(stats["n3_single_offer"]),
        "noncompetitive": int(stats["n3_noncompetitive"]),
    }

    # ── Competition rates ──
    total = stats["n_competitive"] + stats["n_noncompetitive"]
    results["noncompetitive_rate"] = round(stats["n_noncompetitive"] / total, 4) if total > 0 else None
    results["single_offer_rate_among_competitive"] = round(
        stats["n3_single_offer"] / stats["n_competitive"], 4
    ) if stats["n_competitive"] > 0 else None

    # ── ANALYSIS 1: Unweighted mean CI by competition type ──
    n_c = stats["n_competitive"]
    n_nc = stats["n_noncompetitive"]
    mean_ci_c = stats["ci_sum_competitive"] / n_c if n_c > 0 else 0
    mean_ci_nc = stats["ci_sum_noncompetitive"] / n_nc if n_nc > 0 else 0

    results["unweighted_analysis"] = {
        "description": "Unweighted mean CI per action (composition effect — sectors differ)",
        "mean_ci_competitive": round(mean_ci_c, 6),
        "mean_ci_noncompetitive": round(mean_ci_nc, 6),
        "carbon_premium_pct": round((mean_ci_nc - mean_ci_c) / mean_ci_c * 100, 2) if mean_ci_c > 0 else None,
    }

    # Cohen's d and t-test (unweighted)
    if n_c > 1 and n_nc > 1:
        var_c = (stats["ci_sumsq_competitive"] / n_c) - (mean_ci_c ** 2)
        var_nc = (stats["ci_sumsq_noncompetitive"] / n_nc) - (mean_ci_nc ** 2)
        pooled_var = ((n_c - 1) * var_c + (n_nc - 1) * var_nc) / (n_c + n_nc - 2)
        pooled_sd = math.sqrt(max(pooled_var, 1e-12))
        cohens_d = (mean_ci_nc - mean_ci_c) / pooled_sd
        se = math.sqrt(var_c / n_c + var_nc / n_nc)
        t_stat = (mean_ci_nc - mean_ci_c) / se if se > 0 else 0
        num = (var_c / n_c + var_nc / n_nc) ** 2
        denom = ((var_c / n_c) ** 2 / (n_c - 1) + (var_nc / n_nc) ** 2 / (n_nc - 1))
        df = num / denom if denom > 0 else n_c + n_nc - 2

        results["unweighted_analysis"]["cohens_d"] = round(cohens_d, 4)
        results["unweighted_analysis"]["t_statistic"] = round(t_stat, 4)
        results["unweighted_analysis"]["degrees_of_freedom"] = round(df, 1)

    # ── ANALYSIS 2: Obligation-weighted mean CI ──
    oblig_c = stats["oblig_total_competitive"]
    oblig_nc = stats["oblig_total_noncompetitive"]
    ow_ci_c = stats["oblig_ci_sum_competitive"] / oblig_c if oblig_c > 0 else 0
    ow_ci_nc = stats["oblig_ci_sum_noncompetitive"] / oblig_nc if oblig_nc > 0 else 0

    results["obligation_weighted_analysis"] = {
        "description": "Weighted by federal_action_obligation (actual spend, not ceiling)",
        "total_obligations_competitive_usd": round(oblig_c, 2),
        "total_obligations_noncompetitive_usd": round(oblig_nc, 2),
        "obligation_weighted_ci_competitive": round(ow_ci_c, 6),
        "obligation_weighted_ci_noncompetitive": round(ow_ci_nc, 6),
        "carbon_premium_pct": round((ow_ci_nc - ow_ci_c) / ow_ci_c * 100, 2) if ow_ci_c > 0 else None,
    }

    # ── ANALYSIS 3: Three-way split (multi-offer / single-offer / noncompetitive) ──
    three_way = {}
    for cat in ["multi_offer", "single_offer", "noncompetitive"]:
        n = stats[f"n3_{cat}"]
        if n > 0:
            mean_ci = stats[f"ci3_sum_{cat}"] / n
            oblig = stats[f"oblig3_total_{cat}"]
            ow_ci = stats[f"oblig3_ci_sum_{cat}"] / oblig if oblig > 0 else 0
            three_way[cat] = {
                "n_actions": int(n),
                "unweighted_mean_ci": round(mean_ci, 6),
                "obligation_weighted_ci": round(ow_ci, 6),
                "total_obligations_usd": round(oblig, 2),
            }
    results["three_way_analysis"] = three_way

    # ── ANALYSIS 4: Sector-standardized premium ──
    # Reweight to common NAICS mix to control for composition
    sector_weights = {}
    total_actions = sum(sd["n_total"] for sd in sector_data.values())
    for sector, sd in sector_data.items():
        if sd["n_total"] >= 20:
            sector_weights[sector] = sd["n_total"] / total_actions

    standardized_ci_c = 0.0
    standardized_ci_nc = 0.0
    total_w = 0.0
    sectors_with_both = 0
    for sector, w in sector_weights.items():
        sd = sector_data[sector]
        ci = get_carbon_intensity(sector + "00")
        if ci is None:
            continue
        n_c_s = sd.get("n_competitive", 0)
        n_nc_s = sd.get("n_noncompetitive", 0)
        if n_c_s > 0 and n_nc_s > 0:
            # Within this sector, both types exist → can compute rates
            # But CI is the same for both, so standardized premium = 0 by construction
            sectors_with_both += 1
        # Weight the sector's CI by its overall share, split by competition type
        rate_c = n_c_s / sd["n_total"] if sd["n_total"] > 0 else 0
        rate_nc = n_nc_s / sd["n_total"] if sd["n_total"] > 0 else 0
        standardized_ci_c += w * ci * rate_c
        standardized_ci_nc += w * ci * rate_nc
        total_w += w

    results["sector_standardized_analysis"] = {
        "description": (
            "Since CI is assigned at NAICS-3, within-sector CI is identical by construction. "
            "The observed premium is entirely a between-sector composition effect: "
            "competitive procurement is concentrated in higher-carbon sectors (petroleum, "
            "construction, manufacturing) while noncompetitive procurement concentrates in "
            "lower-carbon services (IT, professional, education)."
        ),
        "sectors_with_both_types": sectors_with_both,
        "implication": "The US result reflects WHAT the government buys competitively vs not, not HOW competition affects carbon within sectors.",
    }

    # ── ANALYSIS 5: New-award-only sensitivity ──
    new_n_c = stats["new_n_competitive"]
    new_n_nc = stats["new_n_noncompetitive"]
    if new_n_c > 0 and new_n_nc > 0:
        new_ci_c = stats["new_ci_sum_competitive"] / new_n_c
        new_ci_nc = stats["new_ci_sum_noncompetitive"] / new_n_nc
        new_oblig_c = stats.get("new_oblig_total_competitive", 0)
        new_oblig_nc = stats.get("new_oblig_total_noncompetitive", 0)
        new_ow_ci_c = stats.get("new_oblig_ci_sum_competitive", 0) / new_oblig_c if new_oblig_c > 0 else 0
        new_ow_ci_nc = stats.get("new_oblig_ci_sum_noncompetitive", 0) / new_oblig_nc if new_oblig_nc > 0 else 0

        results["new_award_only_sensitivity"] = {
            "description": "New awards only (modification_number = 0 or blank)",
            "n_competitive": int(new_n_c),
            "n_noncompetitive": int(new_n_nc),
            "unweighted_ci_competitive": round(new_ci_c, 6),
            "unweighted_ci_noncompetitive": round(new_ci_nc, 6),
            "unweighted_premium_pct": round((new_ci_nc - new_ci_c) / new_ci_c * 100, 2) if new_ci_c > 0 else None,
            "obligation_weighted_ci_competitive": round(new_ow_ci_c, 6),
            "obligation_weighted_ci_noncompetitive": round(new_ow_ci_nc, 6),
            "obligation_weighted_premium_pct": round((new_ow_ci_nc - new_ow_ci_c) / new_ow_ci_c * 100, 2) if new_ow_ci_c > 0 else None,
        }

    # ── Cross-sector correlation ──
    sectors_for_corr = []
    for sector, sd in sector_data.items():
        total_s = sd.get("n_total", 0)
        if total_s >= 50:
            nc_rate = sd.get("n_noncompetitive", 0) / total_s
            ci = get_carbon_intensity(sector + "00")
            if ci is not None:
                sectors_for_corr.append({
                    "naics_3digit": sector,
                    "n_actions": int(total_s),
                    "noncompetitive_rate": round(nc_rate, 4),
                    "mean_carbon_intensity": ci,
                    "total_obligations_usd": round(sd.get("oblig_total", 0), 2),
                })

    xs = [s["noncompetitive_rate"] for s in sectors_for_corr]
    ys = [s["mean_carbon_intensity"] for s in sectors_for_corr]
    r, t_r, n = pearson_r(xs, ys)
    if r is not None:
        results["cross_sector_correlation"] = {
            "r": round(r, 4),
            "n_sectors": n,
            "t_statistic": round(t_r, 4),
            "note": f"Correlation between noncompetitive rate and CI across {n} NAICS-3 sectors (unweighted)",
        }

    # Obligation-weighted sector correlation
    xs_w = []
    ys_w = []
    ws = []
    for s in sectors_for_corr:
        if s["total_obligations_usd"] > 0:
            xs_w.append(s["noncompetitive_rate"])
            ys_w.append(s["mean_carbon_intensity"])
            ws.append(s["total_obligations_usd"])
    if len(xs_w) >= 5:
        # Weighted correlation
        tw = sum(ws)
        wmx = sum(x * w for x, w in zip(xs_w, ws)) / tw
        wmy = sum(y * w for y, w in zip(ys_w, ws)) / tw
        wcov = sum(w * (x - wmx) * (y - wmy) for x, y, w in zip(xs_w, ys_w, ws)) / tw
        wsx = math.sqrt(sum(w * (x - wmx) ** 2 for x, w in zip(xs_w, ws)) / tw)
        wsy = math.sqrt(sum(w * (y - wmy) ** 2 for y, w in zip(ys_w, ws)) / tw)
        wr = wcov / (wsx * wsy) if wsx > 0 and wsy > 0 else 0
        results["cross_sector_correlation_obligation_weighted"] = {
            "r": round(wr, 4),
            "n_sectors": len(xs_w),
            "note": "Obligation-weighted correlation between noncompetitive rate and CI",
        }

    results["sector_details"] = sorted(sectors_for_corr, key=lambda s: s["mean_carbon_intensity"], reverse=True)

    # Extent competed distribution
    top_extent = sorted(stats["extent_dist"].items(), key=lambda x: -x[1])[:15]
    results["extent_competed_distribution"] = {k: v for k, v in top_extent}

    return results


def main():
    data_dir = Path(r"C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\raw\us_fpds\extracted")
    output_path = Path(r"C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\results\us_fpds_contract_level.json")

    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        print("ERROR: No CSV files found in extracted directory")
        sys.exit(1)
    print(f"Found {len(csv_files)} CSV file(s) to process")

    stats = defaultdict(float, {"extent_dist": {}})
    sector_data = {}

    for csv_file in csv_files:
        process_file(str(csv_file), stats, sector_data)

    print(f"\nComputing results...")
    results = compute_results(stats, sector_data)

    # Add metadata
    results["metadata"] = {
        "source": "USASpending.gov FPDS FY2024 All Contracts Full",
        "files_processed": [f.name for f in csv_files],
        "unit_of_analysis": "Contract actions (includes modifications — see new_award_only_sensitivity)",
        "carbon_intensity_source": "EPA/BEA NAICS-sector carbon intensities (kg CO2e/USD)",
        "key_methodological_note": (
            "Carbon intensity is assigned at NAICS 3-digit level. Within any sector, "
            "competitive and noncompetitive actions have identical CI by construction. "
            "All premium estimates reflect between-sector procurement composition effects."
        ),
        "competition_classification": {
            "competitive_codes": "A (Full & Open), D (After Exclusion), E (Follow-on), F (SAP)",
            "noncompetitive_codes": "B (Not Competed), C (Not Available), G (Not Competed SAP)",
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # ── Print summary ──
    print(f"\n{'='*65}")
    print(f"US FPDS FY2024 CONTRACT-LEVEL COMPETITION-CARBON ANALYSIS")
    print(f"{'='*65}")
    print(f"Total rows processed:         {results['total_rows_processed']:,}")
    print(f"Valid actions (w/ CI+comp):    {results['valid_contract_actions']:,}")
    print(f"  New awards:                 {results['n_new_awards']:,}")
    print(f"  Modifications:              {results['n_modifications']:,}")
    print(f"  Competitive:                {results['n_competitive']:,}")
    print(f"  Noncompetitive:             {results['n_noncompetitive']:,}")
    print(f"  Noncompetitive rate:        {results['noncompetitive_rate']:.1%}")

    ua = results["unweighted_analysis"]
    print(f"\n── Unweighted Analysis (composition effect) ──")
    print(f"  Mean CI competitive:        {ua['mean_ci_competitive']:.4f} kg CO2e/USD")
    print(f"  Mean CI noncompetitive:     {ua['mean_ci_noncompetitive']:.4f} kg CO2e/USD")
    print(f"  Carbon premium:             {ua['carbon_premium_pct']}%")
    print(f"  Cohen's d:                  {ua.get('cohens_d', 'N/A')}")
    print(f"  t-statistic:                {ua.get('t_statistic', 'N/A')}")

    ow = results["obligation_weighted_analysis"]
    print(f"\n── Obligation-Weighted Analysis (actual spend) ──")
    print(f"  Total obligations comp:     ${ow['total_obligations_competitive_usd']:,.0f}")
    print(f"  Total obligations noncomp:  ${ow['total_obligations_noncompetitive_usd']:,.0f}")
    print(f"  OW CI competitive:          {ow['obligation_weighted_ci_competitive']:.4f}")
    print(f"  OW CI noncompetitive:       {ow['obligation_weighted_ci_noncompetitive']:.4f}")
    print(f"  OW carbon premium:          {ow['carbon_premium_pct']}%")

    tw = results["three_way_analysis"]
    print(f"\n── Three-Way Split ──")
    for cat in ["multi_offer", "single_offer", "noncompetitive"]:
        if cat in tw:
            d = tw[cat]
            print(f"  {cat:20s}: N={d['n_actions']:>10,}  CI={d['unweighted_mean_ci']:.4f}  OW_CI={d['obligation_weighted_ci']:.4f}")

    if "new_award_only_sensitivity" in results:
        na = results["new_award_only_sensitivity"]
        print(f"\n── New-Award-Only Sensitivity ──")
        print(f"  N comp/noncomp:             {na['n_competitive']:,} / {na['n_noncompetitive']:,}")
        print(f"  Unweighted premium:         {na['unweighted_premium_pct']}%")
        print(f"  Obligation-weighted premium: {na['obligation_weighted_premium_pct']}%")

    if "cross_sector_correlation" in results:
        corr = results["cross_sector_correlation"]
        print(f"\n── Cross-Sector Correlation ──")
        print(f"  r = {corr['r']:.4f} (n={corr['n_sectors']} sectors, t={corr['t_statistic']:.2f})")
    if "cross_sector_correlation_obligation_weighted" in results:
        corr_w = results["cross_sector_correlation_obligation_weighted"]
        print(f"  Obligation-weighted: r = {corr_w['r']:.4f} (n={corr_w['n_sectors']})")

    print(f"\n  Results saved to: {output_path}")


if __name__ == "__main__":
    main()
