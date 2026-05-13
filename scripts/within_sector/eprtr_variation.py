import csv, collections, json, math

path = r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\Data\raw\eea_t_ied-eprtr_p_2007-2023_v15_r00\User-friendly-CSV\F1_4_Air_Releases_Facilities.csv'

ghg_pollutants = {
    'Carbon dioxide (CO2)': 1.0,
    'Methane (CH4)': 28.0,
    'Nitrous oxide (N2O)': 265.0,
    'Hydro-fluorocarbons (HFCs)': 1000.0,
    'Perfluorocarbons (PFCs)': 7000.0,
    'Sulphur hexafluoride (SF6)': 23500.0,
}

facility_emissions = collections.defaultdict(lambda: collections.defaultdict(float))
sector_names = {}
country_sector_facilities = collections.defaultdict(set)
rows_total = 0
co2_rows = 0

with open(path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows_total += 1
        pollutant = row.get('Pollutant', '')
        if pollutant in ghg_pollutants:
            co2_rows += 1
            gwp = ghg_pollutants[pollutant]
            try:
                releases = float(row['Releases'])
            except:
                continue
            co2e = releases * gwp
            sector = row['EPRTR_SectorCode']
            country = row['countryName']
            facility = row['FacilityInspireId']
            year = row['reportingYear']
            key = (country, sector, facility, year)
            facility_emissions[key]['co2e'] += co2e
            facility_emissions[key]['country'] = country
            facility_emissions[key]['sector'] = sector
            facility_emissions[key]['year'] = year
            sector_names[sector] = row['EPRTR_SectorName']
            country_sector_facilities[(country, sector)].add(facility)

print(f'Total rows: {rows_total:,}')
print(f'GHG rows: {co2_rows:,}')
print(f'Unique facility-year combos: {len(facility_emissions):,}')
print(f'Unique country-sector groups: {len(country_sector_facilities):,}')

# Compute within-sector variation
sector_stats = collections.defaultdict(list)
for key, data in facility_emissions.items():
    sector = data['sector']
    country = data['country']
    sector_stats[(country, sector)].append(data['co2e'])

groups_with_variation = 0
total_groups = 0
variation_stats = []
for (country, sector), values in sector_stats.items():
    if len(values) >= 5:
        total_groups += 1
        mean_v = sum(values) / len(values)
        if mean_v > 0:
            std_v = (sum((x - mean_v)**2 for x in values) / len(values)) ** 0.5
            cv = std_v / mean_v
            variation_stats.append({
                'country': country,
                'sector': sector,
                'sector_name': sector_names.get(sector, '?'),
                'n': len(values),
                'mean': mean_v,
                'std': std_v,
                'cv': cv,
                'min': min(values),
                'max': max(values)
            })
            if std_v > 0:
                groups_with_variation += 1

print(f'\n{total_groups} groups with >=5 facilities')
print(f'{groups_with_variation} with nonzero variation ({100*groups_with_variation/max(1,total_groups):.1f}%)')

variation_stats.sort(key=lambda x: -x['n'])
print('\nTop 15 groups by size:')
for vs in variation_stats[:15]:
    ratio = vs['max']/max(vs['min'], 1)
    cn = vs['country'][:12]
    sn = vs['sector_name'][:30]
    print(f'  {cn:12s} S{vs["sector"]:2s} ({sn:30s}) N={vs["n"]:5d} CV={vs["cv"]:.2f} MaxMin={ratio:,.0f}x')

cvs = [v['cv'] for v in variation_stats if v['cv'] > 0]
if cvs:
    print(f'\nCV stats across {len(cvs)} groups:')
    print(f'  Mean: {sum(cvs)/len(cvs):.2f}, Median: {sorted(cvs)[len(cvs)//2]:.2f}')
    print(f'  Min: {min(cvs):.2f}, Max: {max(cvs):.2f}')
    print(f'  >1.0: {sum(1 for c in cvs if c > 1.0)}/{len(cvs)} ({100*sum(1 for c in cvs if c > 1.0)/len(cvs):.0f}%)')

results = {
    'total_rows': rows_total,
    'ghg_rows': co2_rows,
    'unique_facility_years': len(facility_emissions),
    'country_sector_groups_5plus': total_groups,
    'groups_with_variation': groups_with_variation,
    'pct_with_variation': round(100*groups_with_variation/max(1,total_groups), 1),
    'mean_cv': round(sum(cvs)/len(cvs), 3) if cvs else 0,
    'median_cv': round(sorted(cvs)[len(cvs)//2], 3) if cvs else 0,
    'top_groups': variation_stats[:30]
}
with open(r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\results\eprtr_within_sector_variation.json', 'w') as f:
    json.dump(results, f, indent=2, default=str)
print('\nSaved results')
