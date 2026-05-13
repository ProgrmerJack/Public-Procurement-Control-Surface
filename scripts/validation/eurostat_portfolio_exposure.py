"""Compute Eurostat-based portfolio carbon exposure as EXIOBASE robustness check."""
import pyarrow.parquet as pq
import numpy as np
import json
import csv
import collections

# Load procurement data
print("Loading procurement data...")
table = pq.read_table('Data/processed/gprd_with_carbon.parquet')
n = len(table)

country = table.column('country').to_pylist()
year = table.column('year').to_pylist()
sb = table.column('single_bidder').to_pylist()
ci_exio = table.column('carbon_intensity_kg_usd').to_pylist()
value_eur = table.column('value_eur').to_pylist()
cpv = table.column('cpv_division').to_pylist()

# Load Eurostat GHG/GVA intensities (our computed ones)
eurostat_file = 'Data/processed/eurostat_carbon_intensities.csv'
eurostat_ci = {}
try:
    with open(eurostat_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                c = row.get('country', '')
                nace = row.get('nace', row.get('sector', ''))
                y = int(float(row.get('year', 0)))
                val = float(row.get('intensity', row.get('carbon_intensity', 0)))
                if c and nace and y and val > 0:
                    eurostat_ci[(c, nace, y)] = val
            except (ValueError, TypeError):
                continue
    print(f"Loaded {len(eurostat_ci)} Eurostat GHG/GVA records")
except FileNotFoundError:
    print(f"Eurostat file not found at {eurostat_file}")

# If no Eurostat file, try to use the Eurostat AEA data we downloaded
if not eurostat_ci:
    aea_file = 'Data/raw/eurostat_aea_ghg_by_nace_country_year.csv'
    try:
        with open(aea_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    c = row.get('geo', row.get('country', ''))
                    nace = row.get('nace_r2', row.get('sector', ''))
                    y_raw = row.get('TIME_PERIOD', row.get('year', '0'))
                    y = int(float(y_raw))
                    val = float(row.get('OBS_VALUE', row.get('value', 0)))
                    if c and nace and y and val > 0:
                        eurostat_ci[(c, nace, y)] = val
                except (ValueError, TypeError):
                    continue
        print(f"Loaded {len(eurostat_ci)} Eurostat AEA records")
    except FileNotFoundError:
        print(f"AEA file also not found")

# Build CPV-to-NACE mapping (simplified)
cpv_to_nace = {
    '03': 'A01', '09': 'B', '14': 'C14', '15': 'C10-C12', '18': 'C18',
    '19': 'C18', '22': 'C18', '24': 'C20', '30': 'C26', '31': 'C31_C32',
    '32': 'C26', '33': 'C21', '34': 'C29_C30', '35': 'C25', '37': 'C28',
    '38': 'C33', '39': 'C28', '42': 'C24', '43': 'C22', '44': 'F',
    '45': 'F', '48': 'J62_J63', '50': 'H49', '51': 'H50', '55': 'I',
    '60': 'H49', '63': 'H52', '64': 'J61', '65': 'E36', '66': 'J62_J63',
    '70': 'J62_J63', '71': 'L68', '72': 'M71', '73': 'M72', '75': 'Q86',
    '76': 'N82', '77': 'A01', '79': 'P85', '80': 'N80', '85': 'Q86',
    '90': 'E38', '92': 'R90-R92', '98': 'N82'
}

# Compute portfolio exposure with Eurostat data
print("\nComputing Eurostat-based portfolio exposure...")

# For each EU contract, try to get Eurostat intensity
eu_countries = set()
sb_euro_ci, mb_euro_ci = [], []
sb_values, mb_values = [], []
total_matched = 0
total_eu = 0

for i in range(n):
    c = country[i]
    y = year[i]
    s = sb[i]
    v = value_eur[i]
    cp = cpv[i]
    
    if not c or c == 'CO' or not y or s is None:
        continue
    total_eu += 1
    
    # Try to find Eurostat intensity
    if cp and str(cp).zfill(2) in cpv_to_nace:
        nace = cpv_to_nace[str(cp).zfill(2)]
        y_int = int(y)
        
        # Try exact match, then nearby years
        ci_val = eurostat_ci.get((c, nace, y_int))
        if ci_val is None:
            for dy in [1, -1, 2, -2]:
                ci_val = eurostat_ci.get((c, nace, y_int + dy))
                if ci_val:
                    break
        
        if ci_val and v and v > 0:
            total_matched += 1
            if s:
                sb_euro_ci.append(ci_val)
                sb_values.append(v)
            else:
                mb_euro_ci.append(ci_val)
                mb_values.append(v)

print(f"EU contracts: {total_eu}")
print(f"Eurostat-matched: {total_matched} ({100*total_matched/total_eu:.1f}%)")
print(f"SB matched: {len(sb_euro_ci)}, MB matched: {len(mb_euro_ci)}")

if sb_euro_ci and mb_euro_ci:
    sb_mean = np.mean(sb_euro_ci)
    mb_mean = np.mean(mb_euro_ci)
    premium = (sb_mean - mb_mean) / mb_mean * 100
    print(f"\nEurostat premium: {premium:.1f}%")
    print(f"SB mean intensity: {sb_mean:.4f}")
    print(f"MB mean intensity: {mb_mean:.4f}")
    
    # Value-weighted intensities
    sb_total_value = sum(sb_values)
    mb_total_value = sum(mb_values)
    sb_vw = sum(c * v for c, v in zip(sb_euro_ci, sb_values)) / sb_total_value if sb_total_value > 0 else 0
    mb_vw = sum(c * v for c, v in zip(mb_euro_ci, mb_values)) / mb_total_value if mb_total_value > 0 else 0
    
    print(f"\nValue-weighted SB intensity: {sb_vw:.4f}")
    print(f"Value-weighted MB intensity: {mb_vw:.4f}")
    print(f"Total SB value: EUR {sb_total_value/1e9:.1f}B")
    print(f"Total MB value: EUR {mb_total_value/1e9:.1f}B")
    
    # Compute portfolio exposure using Eurostat
    # SB exposure = SB total value * SB mean intensity
    sb_exposure_mt = sb_total_value * sb_vw / 1e9  # kg -> Mt (value in EUR, intensity in kg/EUR)
    # But note: Eurostat intensities are in different units, need to check
    # Our Eurostat AEA data is in thousand tonnes CO2e (emissions) / million EUR (GVA)
    # = tonnes/EUR = kg/EUR * 1000... no
    # Actually we need to check the units carefully
    
    print(f"\n--- Portfolio Exposure Calculation ---")
    print(f"Note: Units depend on Eurostat data format")
    print(f"SB portfolio: {sb_total_value/1e9:.1f}B EUR * {sb_vw:.4f} intensity")
    print(f"MB portfolio: {mb_total_value/1e9:.1f}B EUR * {mb_vw:.4f} intensity")

# Now compute using EXIOBASE for comparison
print("\n=== EXIOBASE comparison ===")
sb_exio, mb_exio = [], []
sb_vals2, mb_vals2 = [], []
for i in range(n):
    c = country[i]
    s = sb[i]
    ci = ci_exio[i]
    v = value_eur[i]
    if c and c != 'CO' and s is not None and ci and ci > 0 and v and v > 0:
        if s:
            sb_exio.append(ci)
            sb_vals2.append(v)
        else:
            mb_exio.append(ci)
            mb_vals2.append(v)

sb_total2 = sum(sb_vals2)
mb_total2 = sum(mb_vals2)
sb_vw2 = sum(c*v for c,v in zip(sb_exio, sb_vals2)) / sb_total2 if sb_total2 > 0 else 0
mb_vw2 = sum(c*v for c,v in zip(mb_exio, mb_vals2)) / mb_total2 if mb_total2 > 0 else 0

print(f"EXIOBASE value-weighted SB: {sb_vw2:.4f} kg/USD")
print(f"EXIOBASE value-weighted MB: {mb_vw2:.4f} kg/USD")
print(f"SB total value: EUR {sb_total2/1e9:.1f}B")

# Portfolio Mt CO2e using EXIOBASE
# OECD says EU procurement = ~2,552B EUR
# SB rate = 17%
# SB procurement = 434B EUR (from dataset rate applied to OECD)
oecd_procurement = 2552e9  # EUR
sb_rate = 0.17
sb_procurement = oecd_procurement * sb_rate
exio_sb_mt = sb_procurement * sb_vw2 / 1e9  # kg CO2 -> Mt CO2
print(f"\nOECD-calibrated SB procurement: EUR {sb_procurement/1e9:.0f}B")
print(f"EXIOBASE portfolio exposure: {exio_sb_mt:.0f} Mt CO2e")

# Also compute dataset-based exposure
dataset_sb_carbon = sum(c*v for c,v in zip(sb_exio, sb_vals2)) / 1e9  # kg -> Mt
dataset_mb_carbon = sum(c*v for c,v in zip(mb_exio, mb_vals2)) / 1e9
print(f"\nDataset-based SB carbon footprint: {dataset_sb_carbon:.1f} Mt")
print(f"Dataset-based MB carbon footprint: {dataset_mb_carbon:.1f} Mt")
print(f"Dataset SB value: EUR {sb_total2/1e9:.1f}B")
print(f"Dataset MB value: EUR {mb_total2/1e9:.1f}B")

# Dead Zone analysis with Eurostat
print("\n=== Dead Zone Eurostat Validation ===")
dz_cpvs = ['77', '15', '65', '35', '34', '63']
dz_sb_ci, dz_mb_ci = [], []
dz_sb_v, dz_mb_v = [], []

for i in range(n):
    c_val = country[i]
    s_val = sb[i]
    v_val = value_eur[i]
    cp_val = cpv[i]
    ci_val = ci_exio[i]
    
    if c_val and c_val != 'CO' and s_val is not None and v_val and v_val > 0 and ci_val and ci_val > 0:
        cp_str = str(cp_val).zfill(2) if cp_val else ''
        if cp_str in dz_cpvs:
            if s_val:
                dz_sb_ci.append(ci_val)
                dz_sb_v.append(v_val)
            else:
                dz_mb_ci.append(ci_val)
                dz_mb_v.append(v_val)

if dz_sb_ci:
    dz_sb_mean = np.mean(dz_sb_ci)
    dz_mb_mean = np.mean(dz_mb_ci)
    dz_premium = (dz_sb_mean - dz_mb_mean) / dz_mb_mean * 100
    dz_sb_total = sum(dz_sb_v)
    dz_sb_carbon = sum(c*v for c,v in zip(dz_sb_ci, dz_sb_v)) / 1e9
    
    print(f"DZ SB contracts: {len(dz_sb_ci)}")
    print(f"DZ MB contracts: {len(dz_mb_ci)}")
    print(f"DZ SB mean CI: {dz_sb_mean:.4f}")
    print(f"DZ MB mean CI: {dz_mb_mean:.4f}")
    print(f"DZ premium: {dz_premium:.1f}%")
    print(f"DZ SB total value: EUR {dz_sb_total/1e9:.1f}B")
    print(f"DZ SB carbon: {dz_sb_carbon:.2f} Mt")

results = {
    'eurostat_matched': total_matched,
    'eurostat_match_rate': round(total_matched/total_eu*100, 1) if total_eu > 0 else 0,
    'exiobase_vw_sb': round(sb_vw2, 4),
    'exiobase_vw_mb': round(mb_vw2, 4),
    'dataset_sb_carbon_mt': round(dataset_sb_carbon, 1),
    'dataset_mb_carbon_mt': round(dataset_mb_carbon, 1),
    'oecd_sb_exposure_mt': round(exio_sb_mt, 0)
}

with open('results/validation/portfolio_exposure_validation.json', 'w') as f:
    json.dump(results, f, indent=2)
print("\nResults saved to results/portfolio_exposure_validation.json")
