import csv, json, collections
import numpy as np

f = r'Data/raw/eea_t_ied-eprtr_p_2007-2023_v15_r00/User-friendly-CSV/F1_4_Air_Releases_Facilities.csv'
print("Loading E-PRTR...")

# GHG pollutants with GWP100
ghg_gwp = {
    'Carbon dioxide (CO2)': 1.0,
    'Carbon dioxide (CO2) excluding biomass': 1.0,
    'Methane (CH4)': 28.0,
    'Nitrous oxide (N2O)': 265.0,
}

sector_to_dz = {
    '1': ('Energy→CPV09/31', '09'),
    '3': ('Mineral/Construction→CPV45', '45'),
    '4': ('Chemical→CPV24', '24'),
    '5': ('Waste/Water→CPV65', '65'),
    '7': ('Livestock→CPV77', '77'),
    '8': ('Food→CPV15', '15'),
}

# Collect CO2e per facility-year-sector
facility_co2e = collections.defaultdict(float)  # (sector, country, facility, year) -> CO2e kg
n = 0
for row in csv.DictReader(open(f, 'r', encoding='utf-8-sig')):
    n += 1
    pollutant = row.get('Pollutant', '')
    if pollutant not in ghg_gwp:
        continue
    sector = row.get('EPRTR_SectorCode', '')
    country = row.get('countryName', '')
    facility = row.get('FacilityInspireId', '')
    year = row.get('reportingYear', '')
    releases = row.get('Releases', '')
    try:
        em = float(releases) * ghg_gwp[pollutant]
    except:
        continue
    if em > 0:
        facility_co2e[(sector, country, facility, year)] += em

print(f"Total records: {n:,}, GHG facility-years: {len(facility_co2e):,}")

# Group by sector
sector_emissions = collections.defaultdict(list)
for (sec, country, fac, yr), co2e in facility_co2e.items():
    sector_emissions[sec].append(co2e)

print(f"\n{'Sector':>5} {'Name':>25} {'N':>7} {'P10':>12} {'P25':>12} {'P50':>12} {'P75':>12} {'P90':>12} {'IQR%':>7} {'CV':>6}")
results = {}
for sec_num in sorted(sector_to_dz.keys()):
    name, cpv = sector_to_dz[sec_num]
    vals = sector_emissions.get(sec_num, [])
    if len(vals) < 20:
        print(f"{sec_num:>5} {name:>25} insufficient data")
        continue
    arr = np.array(vals)
    p10, p25, p50, p75, p90 = np.percentile(arr, [10, 25, 50, 75, 90])
    iqr_pct = (p75 - p25) / p75 * 100 if p75 > 0 else 0
    p1090_pct = (p90 - p10) / p90 * 100 if p90 > 0 else 0
    cv = np.std(arr) / np.mean(arr)
    results[cpv] = {
        'name': name, 'n': len(vals), 'cv': round(cv, 2),
        'p25': round(p25), 'p50': round(p50), 'p75': round(p75),
        'iqr_variation_pct': round(iqr_pct, 1),
        'p10_90_variation_pct': round(p1090_pct, 1),
        'max_min_ratio': round(max(arr) / max(min(arr), 1))
    }
    print(f"{sec_num:>5} {name:>25} {len(vals):>7,} {p10:>12,.0f} {p25:>12,.0f} {p50:>12,.0f} {p75:>12,.0f} {p90:>12,.0f} {iqr_pct:>6.1f}% {cv:>6.2f}")

print(f"\n=== KEY FINDING: Within-Sector Selection Potential ===")
for cpv, r in sorted(results.items()):
    print(f"CPV {cpv} ({r['name']}): IQR variation = {r['iqr_variation_pct']}%, P10-P90 = {r['p10_90_variation_pct']}%, CV = {r['cv']}")

avg_iqr = np.mean([r['iqr_variation_pct'] for r in results.values()])
avg_p1090 = np.mean([r['p10_90_variation_pct'] for r in results.values()])
print(f"\nMean IQR variation across Dead Zone sectors: {avg_iqr:.0f}%")
print(f"Mean P10-P90 variation: {avg_p1090:.0f}%")
print(f"Interpretation: If procurement selected from the 25th vs 75th percentile")
print(f"of facility emissions within each sector, the within-sector carbon")
print(f"selection potential would be ~{avg_iqr:.0f}% — {avg_iqr/4.3:.0f}x the measured allocative premium.")

with open(r'results/eprtr_variation_potential.json', 'w') as f:
    json.dump(results, f, indent=2)
