import json

with open(r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface\results\eprtr_within_sector_variation.json', 'r') as f:
    data = json.load(f)

dz_sectors = {'4': 'Chemical→CPV24', '5': 'Waste/Water→CPV65', '7': 'Livestock→CPV77', '8': 'Food→CPV15'}
energy_construction = {'1': 'Energy→CPV09/31', '2': 'Metals→CPV14/44', '3': 'Mineral→CPV45'}

print("=== E-PRTR Dead Zone sectors (direct procurement relevance) ===")
dz_groups = [g for g in data['top_groups'] if g['sector'] in dz_sectors]
for g in dz_groups:
    cn = g['country'][:15]
    sn = g['sector_name'][:25]
    mapping = dz_sectors[g['sector']]
    ratio = g['max'] / max(g['min'], 1)
    print(f"  {cn:15s} S{g['sector']} ({sn:25s}) → {mapping:20s} N={g['n']:4d} CV={g['cv']:.2f} Max/Min={ratio:,.0f}x")

print("\n=== E-PRTR High-carbon sectors (construction/energy) ===")
hc_groups = [g for g in data['top_groups'] if g['sector'] in energy_construction]
for g in hc_groups:
    cn = g['country'][:15]
    sn = g['sector_name'][:25]
    mapping = energy_construction[g['sector']]
    ratio = g['max'] / max(g['min'], 1)
    print(f"  {cn:15s} S{g['sector']} ({sn:25s}) → {mapping:20s} N={g['n']:4d} CV={g['cv']:.2f} Max/Min={ratio:,.0f}x")

print(f"\nSummary: {len(dz_groups)} DZ-sector groups, {len(hc_groups)} high-carbon groups in top 30")
print(f"All sectors: {data['groups_with_variation']}/{data['country_sector_groups_5plus']} = {data['pct_with_variation']}% have variation")
