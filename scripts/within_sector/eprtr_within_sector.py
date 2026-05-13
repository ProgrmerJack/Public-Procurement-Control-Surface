"""
Within-country-within-sector E-PRTR analysis.
Uses E-PRTR sector classification (not procurement sector) to control for 
both country (energy mix) and industry (allocative channel).
"""
import pandas as pd
import numpy as np
import json
from pathlib import Path
from scipy import stats

DATA_DIR = Path(__file__).parent.parent / "Data"
RESULTS_DIR = Path(__file__).parent.parent / "results"

def main():
    # Load E-PRTR matching results (full match list)
    # Re-run matching to get E-PRTR sector per contract
    
    # Load the match json for the 779 matches
    with open(RESULTS_DIR / "eprtr_procurement_matching.json") as f:
        r = json.load(f)
    
    # We only have sample_matches (20) in the JSON. Need to re-derive from the matching.
    # Let's load E-PRTR data and re-match quickly using the approach from the main script.
    
    # Load E-PRTR CO2 data
    air = pd.read_csv(
        DATA_DIR / "raw" / "eea_t_ied-eprtr_p_2007-2023_v15_r00" / 
        "User-friendly-CSV" / "F1_4_Air_Releases_Facilities.csv",
        low_memory=False
    )
    co2 = air[air["Pollutant"] == "Carbon dioxide (CO2)"].copy()
    co2["Releases"] = pd.to_numeric(co2["Releases"], errors="coerce")
    co2 = co2[co2["Releases"] > 0]
    
    # Mean CO2 per facility
    fac_co2 = co2.groupby("FacilityInspireId").agg(
        co2_mean_kg=("Releases", "mean"),
        co2_years=("reportingYear", "nunique"),
        sector=("EPRTR_SectorName", "first"),
        country=("countryName", "first"),
        name=("facilityName", "first")
    ).reset_index()
    
    # Country name mapping
    country_map = {
        "Austria": "AT", "Belgium": "BE", "Bulgaria": "BG", "Croatia": "HR",
        "Cyprus": "CY", "Czech Republic": "CZ", "Czechia": "CZ",
        "Denmark": "DK", "Estonia": "EE", "Finland": "FI", "France": "FR",
        "Germany": "DE", "Greece": "GR", "Hungary": "HU", "Ireland": "IE",
        "Italy": "IT", "Latvia": "LV", "Lithuania": "LT", "Luxembourg": "LU",
        "Malta": "MT", "Netherlands": "NL", "Poland": "PL", "Portugal": "PT",
        "Romania": "RO", "Slovakia": "SK", "Slovenia": "SI", "Spain": "ES",
        "Sweden": "SE", "Norway": "NO", "Switzerland": "CH",
        "United Kingdom": "GB",
    }
    fac_co2["country_code"] = fac_co2["country"].map(country_map)
    
    # Normalize names
    import re
    def normalize_name(name):
        if pd.isna(name) or not name:
            return ""
        name = str(name).lower().strip()
        suffixes = [
            r'\b(gmbh|ag|ltd|plc|sa|srl|spa|as|ab|oy|bv|nv|se|co|inc|corp|llc)\b',
            r'\b(limited|company|group|holding|aktiengesellschaft)\b',
        ]
        for pattern in suffixes:
            name = re.sub(pattern, '', name)
        name = re.sub(r'[^a-z0-9\s]', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        return name
    
    fac_co2["name_norm"] = fac_co2["name"].apply(normalize_name)
    
    # Load procurement
    proc = pd.read_parquet(
        DATA_DIR / "processed" / "gprd_master.parquet",
        columns=["supplier_name", "supplier_country", "country", "single_bidder", "sector"]
    )
    proc = proc[proc["supplier_name"].notna() & (proc["supplier_name"].str.len() > 2)].copy()
    proc["match_country"] = proc["supplier_country"].fillna(proc["country"])
    proc["name_norm"] = proc["supplier_name"].apply(normalize_name)
    
    print(f"E-PRTR facilities: {len(fac_co2)}")
    print(f"Procurement contracts: {len(proc)}")
    
    # Build unique procurement suppliers
    proc_suppliers = proc.groupby(["match_country", "name_norm"]).size().reset_index(name="n")
    proc_suppliers = proc_suppliers[proc_suppliers["name_norm"].str.len() > 0]
    
    # Merge Tier 1
    eprtr_for_merge = fac_co2[fac_co2["name_norm"].str.len() > 0][
        ["name_norm", "country_code", "co2_mean_kg", "sector"]
    ].drop_duplicates(subset=["country_code", "name_norm"])
    
    merged = proc_suppliers.merge(
        eprtr_for_merge,
        left_on=["match_country", "name_norm"],
        right_on=["country_code", "name_norm"],
        how="inner"
    )
    
    print(f"Tier 1 matched supplier-country pairs: {len(merged)}")
    
    # Now merge matched facilities back to full procurement data
    # Tag procurement contracts with E-PRTR sector and CO2
    match_lookup = merged[["match_country", "name_norm", "co2_mean_kg", "sector"]].rename(
        columns={"sector": "eprtr_sector"}
    )
    
    proc_tagged = proc.merge(
        match_lookup,
        on=["match_country", "name_norm"],
        how="inner"
    )
    
    print(f"Tagged contracts: {len(proc_tagged)}")
    n_sb = int(proc_tagged["single_bidder"].sum())
    n_mb = len(proc_tagged) - n_sb
    print(f"  SB: {n_sb}, MB: {n_mb}")
    
    # WITHIN-COUNTRY-WITHIN-SECTOR analysis
    print("\n=== WITHIN-COUNTRY-WITHIN-SECTOR ANALYSIS ===")
    results = []
    
    for (country, eprtr_sector), group in proc_tagged.groupby(["match_country", "eprtr_sector"]):
        sb = group[group["single_bidder"] == True]["co2_mean_kg"]
        mb = group[group["single_bidder"] == False]["co2_mean_kg"]
        
        if len(sb) < 3 or len(mb) < 3:
            continue
        
        prem = (sb.mean() - mb.mean()) / mb.mean() * 100
        t, p = stats.ttest_ind(sb.dropna(), mb.dropna(), equal_var=False)
        
        results.append({
            "country": country,
            "eprtr_sector": eprtr_sector, 
            "n_sb": len(sb),
            "n_mb": len(mb),
            "sb_mean": float(sb.mean()),
            "mb_mean": float(mb.mean()),
            "premium_pct": float(prem),
            "t_stat": float(t),
            "p_value": float(p),
        })
    
    if not results:
        print("  No country-sector groups with sufficient data!")
        # Fall back to just within-sector
        print("\n=== WITHIN-SECTOR (E-PRTR sector) ANALYSIS ===")
        for eprtr_sector, group in proc_tagged.groupby("eprtr_sector"):
            sb = group[group["single_bidder"] == True]["co2_mean_kg"]
            mb = group[group["single_bidder"] == False]["co2_mean_kg"]
            if len(sb) < 5 or len(mb) < 5:
                continue
            prem = (sb.mean() - mb.mean()) / mb.mean() * 100
            t, p = stats.ttest_ind(sb.dropna(), mb.dropna(), equal_var=False)
            sig = "*" if p < 0.05 else ""
            print(f"  {eprtr_sector}: {prem:+.1f}%{sig} (SB n={len(sb)}, MB n={len(mb)})")
            results.append({
                "country": "ALL",
                "eprtr_sector": eprtr_sector,
                "n_sb": len(sb), "n_mb": len(mb),
                "sb_mean": float(sb.mean()), "mb_mean": float(mb.mean()),
                "premium_pct": float(prem), "t_stat": float(t), "p_value": float(p),
            })
    else:
        pos = sum(1 for r in results if r["premium_pct"] > 0)
        neg = sum(1 for r in results if r["premium_pct"] <= 0)
        sig_pos = sum(1 for r in results if r["premium_pct"] > 0 and r["p_value"] < 0.05)
        sig_neg = sum(1 for r in results if r["premium_pct"] <= 0 and r["p_value"] < 0.05)
        
        print(f"  Groups tested: {len(results)}")
        print(f"  SB higher: {pos} ({sig_pos} sig), MB higher: {neg} ({sig_neg} sig)")
        
        # Weighted average
        total_n = sum(r["n_sb"] + r["n_mb"] for r in results)
        if total_n > 0:
            wtd = sum(r["premium_pct"] * (r["n_sb"] + r["n_mb"]) / total_n for r in results)
            print(f"  Weighted average premium: {wtd:+.1f}%")
        
        # Show top results
        for r in sorted(results, key=lambda x: -abs(x["premium_pct"]))[:15]:
            sig = "*" if r["p_value"] < 0.05 else ""
            print(f"  {r['country']}/{r['eprtr_sector']}: {r['premium_pct']:+.1f}%{sig} "
                  f"(SB n={r['n_sb']}, MB n={r['n_mb']})")
    
    # Also do pure within-sector across all countries
    print("\n=== WITHIN-SECTOR (pooled across countries) ===")
    sector_results = []
    for eprtr_sector, group in proc_tagged.groupby("eprtr_sector"):
        sb = group[group["single_bidder"] == True]["co2_mean_kg"]
        mb = group[group["single_bidder"] == False]["co2_mean_kg"]
        if len(sb) < 5 or len(mb) < 5:
            continue
        prem = (sb.mean() - mb.mean()) / mb.mean() * 100
        t, p = stats.ttest_ind(sb.dropna(), mb.dropna(), equal_var=False)
        sig = "*" if p < 0.05 else ""
        print(f"  {eprtr_sector}: {prem:+.1f}%{sig} (SB n={len(sb)}, MB n={len(mb)})")
        sector_results.append({
            "eprtr_sector": eprtr_sector,
            "n_sb": int(len(sb)), "n_mb": int(len(mb)),
            "premium_pct": float(prem), "t_stat": float(t), "p_value": float(p),
        })
    
    # Save results
    output = {
        "within_country_sector": results,
        "within_sector_pooled": sector_results,
        "summary": {
            "n_matched_contracts": len(proc_tagged),
            "n_sb": n_sb,
            "n_mb": n_mb,
            "n_groups_tested": len(results),
        }
    }
    
    with open(RESULTS_DIR / "eprtr_within_sector.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to {RESULTS_DIR / 'eprtr_within_sector.json'}")

if __name__ == "__main__":
    main()
