#!/usr/bin/env python3
"""Parse Eurostat air emissions intensity data and cross-validate with EXIOBASE."""
import urllib.request
import json
import os
import sys

os.makedirs('Data/external', exist_ok=True)

# Download EU27 CO2 intensity by NACE sector
url = ('https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/'
       'env_ac_aeint_r2?geo=EU27_2020&airpol=GHG_I_CO2&unit=KG_EUR&freq=A'
       '&time=2019&lang=en')
print("Downloading Eurostat CO2 intensity by NACE sector...")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=30) as response:
    data = json.loads(response.read())

# Print dimension info
for dim_name in data['id']:
    dim = data['dimension'][dim_name]
    cats = dim['category']['label']
    idx = dim['category']['index']
    n = len(cats)
    print(f"\n{dim_name}: {n} categories")
    for code in sorted(idx.keys(), key=lambda x: idx[x]):
        label = cats.get(code, "?")
        print(f"  [{idx[code]}] {code} = {label}")

# Get values
vals = data['value']
print(f"\n\nTotal values: {len(vals)}")

# Compute flat index mapping
sizes = data['size']  # list of dimension sizes
dims = data['id']     # list of dimension names
print(f"Dimensions: {dims}")
print(f"Sizes: {sizes}")

# Build index for each combination
nace_dim = data['dimension']['nace_r2']
nace_idx = nace_dim['category']['index']
nace_labels = nace_dim['category']['label']

na_item_dim = data['dimension']['na_item']
na_item_idx = na_item_dim['category']['index']

# For single-valued dimensions, the index is 0
# dims order: freq, airpol, nace_r2, na_item, unit, geo, time
# sizes: [1, 1, N_nace, N_na_item, 1, 1, 1]

print("\n=== EU27 CO2 Intensity by NACE (kg CO2/EUR value added, 2019) ===\n")
results = {}
for nace_code, ni in sorted(nace_idx.items(), key=lambda x: x[1]):
    label = nace_labels.get(nace_code, nace_code)
    for na_code, nai in na_item_idx.items():
        # flat_idx = ni * sizes[3]*sizes[4]*sizes[5]*sizes[6] + nai * sizes[4]*sizes[5]*sizes[6]
        # Since sizes[4]=sizes[5]=sizes[6]=1:
        flat_idx = ni * len(na_item_idx) + nai
        val = vals.get(str(flat_idx))
        if val is not None and na_code == 'B1G':  # gross value added
            results[nace_code] = {'label': label, 'co2_kg_eur': val}
            print(f"  {nace_code:12s} {label[:50]:50s} {val:8.4f}")

print(f"\nTotal NACE sectors with CO2/EUR data: {len(results)}")

# Save results
with open('Data/external/eurostat_co2_by_nace.json', 'w') as f:
    json.dump(results, f, indent=2)
print("Saved to Data/external/eurostat_co2_by_nace.json")
