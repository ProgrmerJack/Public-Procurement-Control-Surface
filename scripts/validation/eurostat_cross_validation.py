#!/usr/bin/env python3
"""
Cross-validate EXIOBASE sector carbon intensities with Eurostat air emissions accounts.
Downloads Eurostat env_ac_aeint_r2 (GHG intensity by NACE sector) and compares
with the 37 EXIOBASE sector values used in our manuscript.
"""
import urllib.request
import json
import os
import sys
import numpy as np

os.makedirs('Data/external', exist_ok=True)

# ============================================================
# Step 1: Download Eurostat GHG intensity by NACE sector (EU27)
# ============================================================
print("=" * 60)
print("DOWNLOADING Eurostat GHG intensity by NACE sector")
print("=" * 60)

# GHG intensity in grams per EUR of gross value added
url = ('https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/'
       'env_ac_aeint_r2?geo=EU27_2020&airpol=GHG&unit=G_EUR_CP&freq=A'
       '&time=2019&na_item=B1G&lang=en')
print(f"URL: {url[:80]}...")
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=30) as response:
    data = json.loads(response.read())

# Parse NACE dimension
nace_dim = data['dimension']['nace_r2']
nace_idx = nace_dim['category']['index']
nace_labels = nace_dim['category']['label']
vals = data['value']

print(f"\nNACE sectors available: {len(nace_idx)}")
print(f"Data points: {len(vals)}")

# Extract sector intensities
eurostat = {}
print(f"\n{'NACE':<12} {'Sector':<55} {'g GHG/EUR':>10} {'kg GHG/USD':>11}")
print("-" * 90)

for code in sorted(nace_idx.keys(), key=lambda x: nace_idx[x]):
    idx = nace_idx[code]
    val = vals.get(str(idx))
    if val is not None:
        label = nace_labels.get(code, code)
        kg_per_usd = val / 1000 * 1.12  # g/EUR -> kg/EUR -> kg/USD (approx 1EUR=1.12USD rate)
        # Actually: g/EUR → kg/EUR = val/1000
        # We want kg CO2e per USD of output to compare with EXIOBASE
        # EXIOBASE uses kg/USD. Eurostat uses g/EUR of value added.
        # Convert: g/EUR × (1kg/1000g) = kg/EUR
        # EUR to USD: multiply by ~0.9 (1 USD buys ~0.9 EUR in 2019)
        # So kg/EUR × (1 EUR/1.12 USD) = kg/USD
        kg_per_eur = val / 1000
        kg_per_usd_approx = kg_per_eur / 1.12  # approximate conversion
        eurostat[code] = {
            'label': label,
            'g_per_eur': val,
            'kg_per_eur': kg_per_eur,
            'kg_per_usd': kg_per_usd_approx
        }
        if len(label) > 55:
            label = label[:52] + "..."
        print(f"  {code:<10} {label:<55} {val:>8.1f}  {kg_per_usd_approx:>9.4f}")

# ============================================================
# Step 2: Create EXIOBASE-to-NACE concordance
# ============================================================
print("\n" + "=" * 60)
print("EXIOBASE-to-NACE CONCORDANCE")
print("=" * 60)

# EXIOBASE sector -> approximate NACE mapping and our assigned CI values
# Based on EXIOBASE 3.8.2 sector definitions and CPV crosswalk
exiobase_to_nace = {
    'Cultivation of crops': ('A01', 0.85),
    'Forestry': ('A02', 0.85),
    'Fishing': ('A03', 0.65),
    'Mining and quarrying': ('B', 1.20),
    'Food products': ('C10-C12', 0.65),
    'Textiles': ('C13-C15', 0.45),
    'Wood products': ('C16', 0.40),
    'Paper products': ('C17', 0.55),
    'Printing': ('C18', 0.30),
    'Petroleum products': ('C19', 0.90),
    'Chemical products': ('C20', 0.90),
    'Pharmaceutical products': ('C21', 0.60),
    'Rubber and plastic': ('C22', 0.55),
    'Non-metallic minerals': ('C23', 1.20),
    'Basic metals': ('C24', 0.75),
    'Fabricated metals': ('C25', 0.45),
    'Computer/electronic': ('C26', 0.25),
    'Electrical equipment': ('C27', 0.35),
    'Machinery': ('C28', 0.35),
    'Motor vehicles': ('C29', 0.45),
    'Other transport equip': ('C30', 0.45),
    'Furniture/other mfg': ('C31_C32', 0.30),
    'Repair/installation': ('C33', 0.25),
    'Electricity/gas': ('D', 0.60),
    'Water supply': ('E', 0.60),
    'Construction': ('F', 0.50),
    'Wholesale/retail': ('G', 0.20),
    'Transport/storage': ('H', 0.75),
    'Accommodation/food': ('I', 0.30),
    'Information/comms': ('J', 0.12),
    'Financial services': ('K', 0.08),
    'Real estate': ('L', 0.15),
    'Professional services': ('M', 0.15),
    'Admin/support': ('N', 0.20),
    'Public administration': ('O', 0.25),
    'Education': ('P', 0.10),
    'Health/social work': ('Q', 0.20),
}

# ============================================================
# Step 3: Cross-validate
# ============================================================
print("\n" + "=" * 60)
print("CROSS-VALIDATION: EXIOBASE vs Eurostat")
print("=" * 60)

matched = []
print(f"\n{'EXIOBASE Sector':<25} {'NACE':>6} {'EXIO (kg/USD)':>14} {'Eurostat (kg/USD)':>18} {'Ratio':>8}")
print("-" * 75)

for exio_name, (nace_code, exio_ci) in sorted(exiobase_to_nace.items()):
    if nace_code in eurostat:
        euro_ci = eurostat[nace_code]['kg_per_usd']
        ratio = exio_ci / euro_ci if euro_ci > 0 else float('inf')
        matched.append((exio_ci, euro_ci))
        print(f"  {exio_name:<23} {nace_code:>6}  {exio_ci:>12.3f}  {euro_ci:>16.4f}  {ratio:>7.2f}x")

if matched:
    exio_vals = np.array([m[0] for m in matched])
    euro_vals = np.array([m[1] for m in matched])
    
    # Pearson correlation
    corr = np.corrcoef(exio_vals, euro_vals)[0, 1]
    
    # Spearman rank correlation
    from scipy.stats import spearmanr, pearsonr
    spearman_r, spearman_p = spearmanr(exio_vals, euro_vals)
    pearson_r, pearson_p = pearsonr(exio_vals, euro_vals)
    
    print(f"\n{'=' * 60}")
    print(f"CORRELATION RESULTS ({len(matched)} matched sectors)")
    print(f"{'=' * 60}")
    print(f"  Pearson r  = {pearson_r:.4f}  (p = {pearson_p:.2e})")
    print(f"  Spearman ρ = {spearman_r:.4f}  (p = {spearman_p:.2e})")
    print(f"  Mean EXIOBASE: {exio_vals.mean():.4f} kg/USD")
    print(f"  Mean Eurostat: {euro_vals.mean():.4f} kg/USD") 
    print(f"  EXIOBASE/Eurostat ratio: {(exio_vals.mean()/euro_vals.mean()):.2f}x")
    
    # Rank agreement
    exio_ranks = np.argsort(np.argsort(exio_vals))
    euro_ranks = np.argsort(np.argsort(euro_vals))
    rank_diff = np.abs(exio_ranks - euro_ranks)
    print(f"  Mean rank difference: {rank_diff.mean():.1f} positions")
    print(f"  Max rank difference: {rank_diff.max():.0f} positions")
    
    # Top/bottom agreement
    n = len(matched)
    top5_exio = set(np.argsort(exio_vals)[-5:])
    top5_euro = set(np.argsort(euro_vals)[-5:])
    bot5_exio = set(np.argsort(exio_vals)[:5])
    bot5_euro = set(np.argsort(euro_vals)[:5])
    print(f"  Top-5 overlap: {len(top5_exio & top5_euro)}/5")
    print(f"  Bottom-5 overlap: {len(bot5_exio & bot5_euro)}/5")
    
    results = {
        'pearson_r': round(pearson_r, 4),
        'pearson_p': float(pearson_p),
        'spearman_r': round(spearman_r, 4),
        'spearman_p': float(spearman_p),
        'n_matched': len(matched),
        'mean_exiobase': round(exio_vals.mean(), 4),
        'mean_eurostat': round(euro_vals.mean(), 4),
        'top5_overlap': len(top5_exio & top5_euro),
        'bottom5_overlap': len(bot5_exio & bot5_euro),
    }
    
    with open('Data/external/eurostat_cross_validation.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to Data/external/eurostat_cross_validation.json")
    
    # Interpretation
    print(f"\n{'=' * 60}")
    print("INTERPRETATION FOR MANUSCRIPT")
    print(f"{'=' * 60}")
    if spearman_r > 0.7:
        print("STRONG cross-validation: EXIOBASE sector rankings match Eurostat")
        print("well. The relative ordering of sectors (which drives our premium)")
        print("is validated by an independent EU statistical source.")
    elif spearman_r > 0.5:
        print("MODERATE cross-validation: EXIOBASE sector rankings partially")
        print("match Eurostat. Key sectors agree on relative carbon intensity.")
    else:
        print("WEAK cross-validation. EXIOBASE and Eurostat rankings diverge.")
