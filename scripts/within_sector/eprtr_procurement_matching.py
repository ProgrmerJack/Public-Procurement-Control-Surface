#!/usr/bin/env python3
"""
E-PRTR × Procurement Facility-Level Matching
=============================================
Links E-PRTR facility-level CO2 emissions to procurement contract suppliers
to validate the within-sector technical efficiency channel.

If competitive contracts go to lower-CO2 facilities WITHIN the same sector,
this proves the technical channel that EXIOBASE cannot capture.
"""

import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd
import numpy as np

DATA_DIR = Path("Data")
EPRTR_DIR = DATA_DIR / "raw" / "eea_t_ied-eprtr_p_2007-2023_v15_r00" / "User-friendly-CSV"
RESULTS_DIR = Path("results")

# Country name mapping: E-PRTR -> procurement data
COUNTRY_MAP = {
    "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR",
    "Cyprus": "CY", "Czechia": "CZ", "Denmark": "DK", "Estonia": "EE",
    "Finland": "FI", "France": "FR", "Germany": "DE", "Greece": "GR",
    "Hungary": "HU", "Iceland": "IS", "Ireland": "IE", "Italy": "IT",
    "Latvia": "LV", "Lithuania": "LT", "Luxembourg": "LU", "Malta": "MT",
    "Netherlands": "NL", "Poland": "PL", "Portugal": "PT", "Romania": "RO",
    "Slovakia": "SK", "Slovenia": "SI", "Spain": "ES", "Sweden": "SE",
    "United Kingdom": "GB", "Norway": "NO", "Switzerland": "CH",
    "Czech Republic": "CZ",
}

# Legal suffix patterns to strip
LEGAL_SUFFIXES = re.compile(
    r'\b(s\.?a\.?s?|s\.?r\.?l\.?|s\.?p\.?a\.?|gmbh|ag|ltd\.?|plc|inc\.?|'
    r'corp\.?|co\.?|pty|bv|nv|ab|oy|as|a\.?s\.?|hf\.?|ehf\.?|'
    r'd\.?o\.?o\.?|sp\.?\s*z\.?\s*o\.?\s*o\.?|uab|sia|ou|'
    r'aps|ivs|kmg|oü|tov|limited|company|group|holding|'
    r'societe|société|gesellschaft|aktiengesellschaft)\b',
    re.IGNORECASE
)

# E-PRTR sector -> EXIOBASE sector
EPRTR_TO_EXIO = {
    "Energy sector": "Electricity, gas and water supply",
    "Mineral industry": "Other non-metallic mineral products",
    "Chemical industry": "Chemicals and chemical products",
    "Production and processing of metals": "Basic metals and fabricated metal products",
    "Paper and wood production and processing": "Pulp, paper and paper products",
    "Waste and wastewater management": "Other business activities",
    "Intensive livestock production and aquaculture": "Food products, beverages and tobacco",
    "Animal and vegetable products from the food and beverage sector": "Food products, beverages and tobacco",
}


def normalize_name(name):
    """Normalize company name for matching."""
    if not name or pd.isna(name):
        return ""
    # Convert to string
    name = str(name)
    # Normalize unicode
    name = unicodedata.normalize("NFKD", name)
    # Lowercase
    name = name.lower().strip()
    # Remove legal suffixes
    name = LEGAL_SUFFIXES.sub("", name)
    # Remove punctuation except spaces
    name = re.sub(r'[^\w\s]', ' ', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def load_eprtr_co2():
    """Load E-PRTR facility CO2 data with latest year per facility."""
    print("Loading E-PRTR CO2 data...")
    facilities = {}
    filepath = EPRTR_DIR / "F1_4_Air_Releases_Facilities.csv"
    
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Pollutant"] != "Carbon dioxide (CO2)":
                continue
            try:
                co2 = float(row["Releases"])
            except (ValueError, TypeError):
                continue
            if co2 <= 0:
                continue
            
            fid = row["FacilityInspireId"]
            year = int(row["reportingYear"])
            country = row["countryName"]
            country_code = COUNTRY_MAP.get(country, "")
            
            # Keep latest year per facility, or average
            if fid not in facilities:
                facilities[fid] = {
                    "facility_id": fid,
                    "name": row["facilityName"],
                    "name_norm": normalize_name(row["facilityName"]),
                    "country": country,
                    "country_code": country_code,
                    "city": row["city"],
                    "sector": row["EPRTR_SectorName"],
                    "exio_sector": EPRTR_TO_EXIO.get(row["EPRTR_SectorName"], ""),
                    "co2_values": [co2],
                    "years": [year],
                }
            else:
                facilities[fid]["co2_values"].append(co2)
                facilities[fid]["years"].append(year)
    
    # Compute mean CO2 per facility
    for fid, data in facilities.items():
        data["co2_mean_kg"] = np.mean(data["co2_values"])
        data["co2_latest_kg"] = data["co2_values"][-1]  # last reported
        data["n_years"] = len(data["years"])
    
    print(f"  {len(facilities):,} unique facilities with CO2 data")
    return facilities


def load_procurement_suppliers():
    """Load unique suppliers from procurement data."""
    print("Loading procurement supplier data...")
    parquet_path = DATA_DIR / "processed" / "gprd_master.parquet"
    
    # Read only needed columns
    cols = ["supplier_name", "supplier_country", "country", "single_bidder", 
            "sector", "value_eur"]
    
    df = pd.read_parquet(parquet_path, columns=cols)
    
    print(f"  {len(df):,} total contracts")
    
    # Filter to contracts with real supplier names (>2 chars)
    df = df[df["supplier_name"].notna() & (df["supplier_name"].str.len() > 2)].copy()
    print(f"  {len(df):,} with real supplier names")
    
    # Rename sector for consistency
    if "exiobase_sector" not in df.columns and "sector" in df.columns:
        df["exiobase_sector"] = df["sector"]
    
    # Use supplier_country if available, else country
    if "supplier_country" in df.columns:
        df["match_country"] = df["supplier_country"].fillna(df["country"])
    else:
        df["match_country"] = df["country"]
    
    df["name_norm"] = df["supplier_name"].apply(normalize_name)
    
    return df


def match_eprtr_to_procurement(eprtr_facilities, proc_df):
    """Match E-PRTR facilities to procurement suppliers using vectorized operations."""
    print("\nMatching E-PRTR facilities to procurement suppliers...")
    
    # Build E-PRTR DataFrame
    eprtr_rows = []
    for fid, data in eprtr_facilities.items():
        if data["name_norm"] and data["country_code"]:
            eprtr_rows.append({
                "eprtr_name": data["name"],
                "eprtr_name_norm": data["name_norm"],
                "eprtr_country": data["country_code"],
                "eprtr_sector": data["sector"],
                "exio_sector": data["exio_sector"],
                "co2_mean_kg": data["co2_mean_kg"],
            })
    eprtr_df = pd.DataFrame(eprtr_rows).drop_duplicates(subset=["eprtr_country", "eprtr_name_norm"])
    print(f"  E-PRTR facilities with names: {len(eprtr_df):,}")
    
    # Build unique procurement suppliers per country  
    proc_suppliers = (proc_df.groupby(["match_country", "name_norm"])
                      .agg(n_contracts=("name_norm", "size"))
                      .reset_index())
    proc_suppliers = proc_suppliers[proc_suppliers["name_norm"].str.len() > 0]
    print(f"  Unique procurement supplier-country pairs: {len(proc_suppliers):,}")
    
    # Tier 1: Exact merge on country + normalized name
    merged = proc_suppliers.merge(
        eprtr_df,
        left_on=["match_country", "name_norm"],
        right_on=["eprtr_country", "eprtr_name_norm"],
        how="inner"
    )
    
    matches = []
    for _, row in merged.iterrows():
        matches.append({
            "procurement_name_norm": row["name_norm"],
            "eprtr_name": row["eprtr_name"],
            "country": row["match_country"],
            "eprtr_sector": row["eprtr_sector"],
            "exio_sector": row["exio_sector"],
            "co2_mean_kg": row["co2_mean_kg"],
            "n_contracts": row["n_contracts"],
            "match_tier": 1,
        })
    
    matched_names = set(merged["name_norm"].unique())
    print(f"  Tier 1 (exact country+name): {len(matches)} matches")
    
    # Tier 2: For unmatched E-PRTR facilities, try substring matching per country
    # Iterate over E-PRTR names (small: ~3K) per country, not procurement names (large: ~4M)
    unmatched_eprtr = eprtr_df[~eprtr_df["eprtr_name_norm"].isin(
        set(merged["eprtr_name_norm"].unique()) if len(merged) > 0 else set()
    )]
    print(f"  Unmatched E-PRTR for Tier 2: {len(unmatched_eprtr):,}")
    
    t2_count = 0
    for country in unmatched_eprtr["eprtr_country"].unique():
        country_eprtr = unmatched_eprtr[unmatched_eprtr["eprtr_country"] == country]
        country_proc = proc_suppliers[
            (proc_suppliers["match_country"] == country) & 
            (proc_suppliers["name_norm"].str.len() >= 8) &
            (~proc_suppliers["name_norm"].isin(matched_names))
        ]
        if len(country_proc) == 0 or len(country_eprtr) == 0:
            continue
        
        # Index procurement names for this country
        proc_name_list = country_proc["name_norm"].tolist()
        proc_contracts = dict(zip(country_proc["name_norm"], country_proc["n_contracts"]))
        
        for _, erow in country_eprtr.iterrows():
            en = erow["eprtr_name_norm"]
            if len(en) < 8:
                continue
            for pn in proc_name_list:
                if en in pn or pn in en:
                    matches.append({
                        "procurement_name_norm": pn,
                        "eprtr_name": erow["eprtr_name"],
                        "country": country,
                        "eprtr_sector": erow["eprtr_sector"],
                        "exio_sector": erow["exio_sector"],
                        "co2_mean_kg": erow["co2_mean_kg"],
                        "n_contracts": proc_contracts.get(pn, 0),
                        "match_tier": 2,
                    })
                    matched_names.add(pn)
                    t2_count += 1
                    break
    
    print(f"  Tier 2 (substring match): {t2_count} matches")
    print(f"  Total matches: {len(matches)}")
    
    return matches


def analyze_technical_channel(matches, proc_df):
    """
    For matched E-PRTR facilities, compare CO2 emissions 
    between single-bidder and multi-bidder procurement contracts.
    Uses vectorized merge instead of row-by-row apply.
    """
    print("\nAnalyzing technical efficiency channel...")
    
    if not matches:
        print("  No matches found!")
        return {}
    
    # Create match DataFrame
    match_df = pd.DataFrame(matches)[["procurement_name_norm", "country", "co2_mean_kg"]]
    match_df = match_df.rename(columns={"procurement_name_norm": "name_norm", "country": "match_country"})
    match_df = match_df.drop_duplicates(subset=["match_country", "name_norm"])
    
    # Merge with procurement data
    proc_matched = proc_df.merge(
        match_df,
        on=["match_country", "name_norm"],
        how="inner"
    )
    
    n_total = len(proc_matched)
    n_sb = int(proc_matched["single_bidder"].sum())
    n_mb = n_total - n_sb
    
    print(f"  Matched contracts: {n_total:,} (SB: {n_sb:,}, MB: {n_mb:,})")
    
    if n_sb < 10 or n_mb < 10:
        print("  Too few contracts for analysis")
        return {"error": "insufficient_data", "n_total": n_total, "n_sb": n_sb, "n_mb": n_mb}
    
    # Overall comparison
    sb_co2 = proc_matched[proc_matched["single_bidder"] == True]["co2_mean_kg"]
    mb_co2 = proc_matched[proc_matched["single_bidder"] == False]["co2_mean_kg"]
    
    overall = {
        "n_contracts": n_total,
        "n_sb": n_sb,
        "n_mb": n_mb,
        "sb_mean_co2": float(sb_co2.mean()),
        "mb_mean_co2": float(mb_co2.mean()),
        "premium_pct": float((sb_co2.mean() - mb_co2.mean()) / mb_co2.mean() * 100),
    }
    
    # t-test
    from scipy import stats
    t_stat, p_val = stats.ttest_ind(sb_co2.dropna(), mb_co2.dropna(), equal_var=False)
    overall["t_stat"] = float(t_stat)
    overall["p_value"] = float(p_val)
    
    print(f"  Overall: SB mean={sb_co2.mean():.0f} kg, MB mean={mb_co2.mean():.0f} kg")
    print(f"  Premium: {overall['premium_pct']:.1f}%, t={t_stat:.2f}, p={p_val:.4f}")
    
    # Within-sector comparison (KEY TEST)
    sector_col = "exiobase_sector" if "exiobase_sector" in proc_matched.columns else "sector"
    sector_results = []
    for sector in proc_matched[sector_col].dropna().unique():
        sec_data = proc_matched[proc_matched[sector_col] == sector]
        sec_sb = sec_data[sec_data["single_bidder"] == True]["co2_mean_kg"]
        sec_mb = sec_data[sec_data["single_bidder"] == False]["co2_mean_kg"]
        
        if len(sec_sb) < 5 or len(sec_mb) < 5:
            continue
        
        premium = (sec_sb.mean() - sec_mb.mean()) / sec_mb.mean() * 100
        t, p = stats.ttest_ind(sec_sb.dropna(), sec_mb.dropna(), equal_var=False)
        
        sector_results.append({
            "sector": sector,
            "n_sb": len(sec_sb),
            "n_mb": len(sec_mb),
            "sb_mean_co2": float(sec_sb.mean()),
            "mb_mean_co2": float(sec_mb.mean()),
            "premium_pct": float(premium),
            "t_stat": float(t),
            "p_value": float(p),
        })
        
        direction = "SB HIGHER" if premium > 0 else "MB HIGHER"
        sig = "*" if p < 0.05 else ""
        print(f"    {sector}: {premium:+.1f}% ({direction}){sig}, n={len(sec_sb)+len(sec_mb)}")
    
    # Within-country comparison
    country_results = []
    for country in proc_matched["match_country"].dropna().unique():
        c_data = proc_matched[proc_matched["match_country"] == country]
        c_sb = c_data[c_data["single_bidder"] == True]["co2_mean_kg"]
        c_mb = c_data[c_data["single_bidder"] == False]["co2_mean_kg"]
        
        if len(c_sb) < 5 or len(c_mb) < 5:
            continue
        
        premium = (c_sb.mean() - c_mb.mean()) / c_mb.mean() * 100
        t, p = stats.ttest_ind(c_sb.dropna(), c_mb.dropna(), equal_var=False)
        
        country_results.append({
            "country": country,
            "n_sb": len(c_sb),
            "n_mb": len(c_mb),
            "sb_mean_co2": float(c_sb.mean()),
            "mb_mean_co2": float(c_mb.mean()),
            "premium_pct": float(premium),
            "t_stat": float(t),
            "p_value": float(p),
        })
    
    if country_results:
        print("\n  Within-country results:")
        for cr in sorted(country_results, key=lambda x: -abs(x["premium_pct"])):
            direction = "SB HIGHER" if cr["premium_pct"] > 0 else "MB HIGHER"
            sig = "*" if cr["p_value"] < 0.05 else ""
            print(f"    {cr['country']}: {cr['premium_pct']:+.1f}% ({direction}){sig}")
    
    return {
        "overall": overall,
        "within_sector": sorted(sector_results, key=lambda x: -abs(x["premium_pct"])),
        "within_country": sorted(country_results, key=lambda x: -abs(x["premium_pct"])),
        "n_sectors_tested": len(sector_results),
        "n_countries_tested": len(country_results),
        "interpretation": (
            "Positive premium = SB contracts go to higher-CO2 facilities (technical channel exists). "
            "Negative premium = MB contracts go to higher-CO2 facilities. "
            "Within-sector analysis controls for the allocative channel."
        ),
    }


def main():
    # Load data
    eprtr = load_eprtr_co2()
    proc_df = load_procurement_suppliers()
    
    # Match
    matches = match_eprtr_to_procurement(eprtr, proc_df)
    
    # Analyze technical channel
    results = analyze_technical_channel(matches, proc_df)
    
    # Match summary
    match_summary = {
        "n_eprtr_facilities": len(eprtr),
        "n_matches_tier1": sum(1 for m in matches if m["match_tier"] == 1),
        "n_matches_tier2": sum(1 for m in matches if m["match_tier"] == 2),
        "n_matches_total": len(matches),
        "total_contracts_matched": sum(m["n_contracts"] for m in matches),
        "sectors_represented": list(set(m["eprtr_sector"] for m in matches)),
        "countries_represented": list(set(m["country"] for m in matches)),
    }
    
    print(f"\n{'='*60}")
    print("MATCH SUMMARY:")
    print(f"  E-PRTR facilities: {match_summary['n_eprtr_facilities']:,}")
    print(f"  Tier 1 matches: {match_summary['n_matches_tier1']}")
    print(f"  Tier 2 matches: {match_summary['n_matches_tier2']}")
    print(f"  Total contracts covered: {match_summary['total_contracts_matched']:,}")
    print(f"  Sectors: {match_summary['sectors_represented']}")
    print(f"  Countries: {match_summary['countries_represented']}")
    
    full_results = {
        "match_summary": match_summary,
        "technical_channel_analysis": results,
        "sample_matches": matches[:20],
    }
    
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "eprtr_procurement_matching.json", "w") as f:
        json.dump(full_results, f, indent=2, default=str)
    
    print(f"\nResults saved to {RESULTS_DIR / 'eprtr_procurement_matching.json'}")


if __name__ == "__main__":
    main()
