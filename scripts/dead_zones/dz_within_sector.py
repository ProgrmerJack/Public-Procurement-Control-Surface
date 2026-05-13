import pyarrow.parquet as pq
import csv, json, collections
import numpy as np

# Load procurement data
print("Loading procurement data...")
pf = pq.read_table(r'Data/processed/gprd_with_carbon.parquet',
    columns=['country', 'cpv_division', 'single_bidder', 'carbon_intensity_kg_usd', 'exiobase_sector', 'value_eur'])
countries = pf.column('country').to_pylist()
cpvs = pf.column('cpv_division').to_pylist()
sbs = pf.column('single_bidder').to_pylist()
cis = pf.column('carbon_intensity_kg_usd').to_pylist()
sectors = pf.column('exiobase_sector').to_pylist()
vals = pf.column('value_eur').to_pylist()

# EU countries
eu_countries = set(['AT','BE','BG','CY','CZ','DE','DK','EE','ES','FI','FR','GR','HR',
                    'HU','IE','IS','IT','LT','LU','LV','MT','NL','NO','PL','PT','RO',
                    'SE','SI','SK','UK','CH'])

# Dead Zone CPV sectors from manuscript
dead_zone_cpvs = {'77': 'Agri/forestry', '15': 'Food', '65': 'Water supply',
                  '35': 'Defence equip', '34': 'Transport equip', '63': 'Transport svcs'}

# Collect per-CPV within-sector premiums (EU only)
# Group by (country, cpv_division, exiobase_sector) to get within-sector SB vs MB
print("Computing per-CPV within-sector premiums...")
cpv_sb_ci = collections.defaultdict(list)
cpv_mb_ci = collections.defaultdict(list)

for i in range(len(countries)):
    c = countries[i]
    if c not in eu_countries:
        continue
    ci = cis[i]
    if ci is None or ci != ci:
        continue
    cpv = cpvs[i]
    if cpv is None:
        continue
    sb = sbs[i]
    if sb is None:
        continue
    
    key = str(cpv)[:2]
    if sb:
        cpv_sb_ci[key].append(ci)
    else:
        cpv_mb_ci[key].append(ci)

print("\n=== CPV-level EU premium (EXIOBASE, portfolio level) ===")
print(f"{'CPV':>5} {'Name':>20} {'N_SB':>8} {'N_MB':>8} {'SB_mean':>8} {'MB_mean':>8} {'Prem%':>8} {'DZ?':>4}")

results = []
for cpv in sorted(cpv_sb_ci.keys()):
    sb_vals = cpv_sb_ci[cpv]
    mb_vals = cpv_mb_ci.get(cpv, [])
    if len(sb_vals) < 100 or len(mb_vals) < 100:
        continue
    sb_mean = np.mean(sb_vals)
    mb_mean = np.mean(mb_vals)
    premium = (sb_mean - mb_mean) / mb_mean * 100 if mb_mean > 0 else 0
    dz = 'DZ' if cpv in dead_zone_cpvs else ''
    name = dead_zone_cpvs.get(cpv, '')[:20]
    results.append((cpv, name, len(sb_vals), len(mb_vals), sb_mean, mb_mean, premium, dz))
    print(f"{cpv:>5} {name:>20} {len(sb_vals):>8,} {len(mb_vals):>8,} {sb_mean:>8.4f} {mb_mean:>8.4f} {premium:>8.1f}% {dz:>4}")

# Now compute WITHIN-country-sector premiums for Dead Zone sectors
print("\n=== Dead Zone sectors: within-country-sector premium (EU, EXIOBASE) ===")
# Group by (country, cpv, exio_sector) 
within_groups = collections.defaultdict(lambda: {'sb': [], 'mb': []})
for i in range(len(countries)):
    c = countries[i]
    if c not in eu_countries:
        continue
    ci = cis[i]
    if ci is None or ci != ci:
        continue
    cpv = str(cpvs[i])[:2] if cpvs[i] is not None else None
    if cpv not in dead_zone_cpvs:
        continue
    sb = sbs[i]
    if sb is None:
        continue
    sector = sectors[i]
    if sector is None:
        continue
    
    key = (c, cpv, str(sector))
    if sb:
        within_groups[key]['sb'].append(ci)
    else:
        within_groups[key]['mb'].append(ci)

# For each DZ CPV, count groups with variation
for cpv in sorted(dead_zone_cpvs.keys()):
    name = dead_zone_cpvs[cpv]
    groups = [(k, v) for k, v in within_groups.items() if k[1] == cpv and len(v['sb']) >= 10 and len(v['mb']) >= 10]
    n_var = 0
    premiums = []
    for k, v in groups:
        sb_m = np.mean(v['sb'])
        mb_m = np.mean(v['mb'])
        if mb_m > 0:
            prem = (sb_m - mb_m) / mb_m * 100
            premiums.append(prem)
            if abs(sb_m - mb_m) > 1e-10:
                n_var += 1
    print(f"CPV {cpv} ({name}): {len(groups)} country-sector groups, {n_var} with variation")
    if premiums:
        print(f"  Premium range: {min(premiums):.1f}% to {max(premiums):.1f}%, median={np.median(premiums):.1f}%")
    
print("\nDone!")
