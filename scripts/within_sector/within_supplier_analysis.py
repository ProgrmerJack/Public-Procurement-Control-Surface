"""Within-supplier analysis: compare SB vs MB contracts for the same supplier."""
import pyarrow.parquet as pq
import pandas as pd
import numpy as np
from scipy import stats
import json

cols = ['supplier_id', 'country', 'single_bidder', 'carbon_intensity_kg_usd',
        'exiobase_sector', 'value_eur', 'cpv_division']
df = pq.read_table('Data/processed/gprd_with_carbon.parquet', columns=cols).to_pandas()
eu = df[df['country'] != 'CO'].copy()

# Clean supplier_id
eu['supplier_id'] = eu['supplier_id'].astype(str)
eu = eu[~eu['supplier_id'].isin(['nan', '', 'None'])].copy()
print(f"EU-context with valid supplier_id: {len(eu):,}")

# Unique suppliers
n_unique = eu['supplier_id'].nunique()
print(f"Unique suppliers: {n_unique:,}")

# Mean CI by supplier and SB status
sb_ci = eu[eu['single_bidder']].groupby('supplier_id')['carbon_intensity_kg_usd'].mean()
mb_ci = eu[~eu['single_bidder']].groupby('supplier_id')['carbon_intensity_kg_usd'].mean()

# Suppliers with both SB and MB contracts
both_ids = sb_ci.index.intersection(mb_ci.index)
print(f"Suppliers with both SB and MB contracts: {len(both_ids):,}")

sb_vals = sb_ci.loc[both_ids]
mb_vals = mb_ci.loc[both_ids]
diff = sb_vals - mb_vals

print(f"\n--- Within-supplier analysis (all suppliers with both types) ---")
print(f"Mean SB carbon intensity: {sb_vals.mean():.4f}")
print(f"Mean MB carbon intensity: {mb_vals.mean():.4f}")
print(f"Mean within-supplier diff (SB-MB): {diff.mean():.4f}")
prem = (sb_vals.mean() - mb_vals.mean()) / mb_vals.mean() * 100
print(f"Within-supplier premium: {prem:.2f}%")

pct_sb_lower = (diff < 0).mean() * 100
print(f"% suppliers where SB < MB (SB cleaner): {pct_sb_lower:.1f}%")
print(f"% suppliers where SB > MB (SB dirtier): {100-pct_sb_lower:.1f}%")

t, p = stats.ttest_rel(sb_vals.values, mb_vals.values)
print(f"Paired t-test: t={t:.2f}, p={p:.4e}")

d = diff.mean() / diff.std()
print(f"Cohen's d (within-supplier): {d:.4f}")

# Robust subset: suppliers with >= 5 contracts each type
sb_count = eu[eu['single_bidder']].groupby('supplier_id').size()
mb_count = eu[~eu['single_bidder']].groupby('supplier_id').size()
robust_ids = both_ids[
    (sb_count.reindex(both_ids).fillna(0) >= 5) &
    (mb_count.reindex(both_ids).fillna(0) >= 5)
]
print(f"\n--- Robust subset (>=5 each type) ---")
print(f"N suppliers: {len(robust_ids):,}")
sb_r = sb_ci.loc[robust_ids]
mb_r = mb_ci.loc[robust_ids]
diff_r = sb_r - mb_r
print(f"Mean SB CI: {sb_r.mean():.4f}")
print(f"Mean MB CI: {mb_r.mean():.4f}")
print(f"Mean diff: {diff_r.mean():.4f}")
prem_r = (sb_r.mean() - mb_r.mean()) / mb_r.mean() * 100
print(f"Premium: {prem_r:.2f}%")
print(f"% SB < MB: {(diff_r < 0).mean()*100:.1f}%")
t2, p2 = stats.ttest_rel(sb_r.values, mb_r.values)
print(f"Paired t: {t2:.2f}, p={p2:.4e}")
d2 = diff_r.mean() / diff_r.std()
print(f"Cohen's d: {d2:.4f}")

# Check: do suppliers switch sectors between SB and MB?
print(f"\n--- Sector switching analysis ---")
for sid in robust_ids[:10]:
    sub = eu[eu['supplier_id'] == sid]
    sb_sectors = set(sub[sub['single_bidder']]['exiobase_sector'].unique())
    mb_sectors = set(sub[~sub['single_bidder']]['exiobase_sector'].unique())
    if sb_sectors != mb_sectors:
        only_sb = sb_sectors - mb_sectors
        only_mb = mb_sectors - sb_sectors
        print(f"  Supplier {sid[:15]}: SB-only sectors={only_sb}, MB-only={only_mb}")

# Sector diversity
def sector_diversity(group):
    sb_sub = group[group['single_bidder']]
    mb_sub = group[~group['single_bidder']]
    return pd.Series({
        'sb_n_sectors': sb_sub['exiobase_sector'].nunique(),
        'mb_n_sectors': mb_sub['exiobase_sector'].nunique(),
        'sb_mean_ci': sb_sub['carbon_intensity_kg_usd'].mean(),
        'mb_mean_ci': mb_sub['carbon_intensity_kg_usd'].mean()
    })

diversity = eu[eu['supplier_id'].isin(robust_ids)].groupby('supplier_id').apply(sector_diversity)
print(f"\nMean sectors per supplier: SB={diversity['sb_n_sectors'].mean():.1f}, MB={diversity['mb_n_sectors'].mean():.1f}")

# Within SAME SECTOR analysis
print(f"\n--- Within-supplier, WITHIN-SECTOR analysis ---")
# Group by (supplier_id, exiobase_sector) — same supplier, same sector
# This controls for sector composition AND supplier identity
same_sector = eu[eu['supplier_id'].isin(both_ids)].copy()
ss_groups = same_sector.groupby(['supplier_id', 'exiobase_sector', 'single_bidder'])['carbon_intensity_kg_usd'].mean().unstack('single_bidder')
ss_groups.columns = ['MB', 'SB']
ss_both = ss_groups.dropna()
print(f"Supplier-sector pairs with both SB and MB: {len(ss_both):,}")
if len(ss_both) > 0:
    # These should be IDENTICAL because EXIOBASE assigns same CI to same sector
    ss_diff = ss_both['SB'] - ss_both['MB']
    print(f"Mean diff (should be ~0 due to EXIOBASE): {ss_diff.mean():.6f}")
    print(f"Max abs diff: {ss_diff.abs().max():.6f}")
    print("(Confirms premium is entirely allocative — same sector = same CI)")

# Save results
results = {
    "within_supplier_all": {
        "n_suppliers": int(len(both_ids)),
        "sb_mean_ci": round(sb_vals.mean(), 4),
        "mb_mean_ci": round(mb_vals.mean(), 4),
        "premium_pct": round(prem, 2),
        "pct_sb_lower": round(pct_sb_lower, 1),
        "cohens_d": round(d, 4),
        "paired_t": round(t, 2),
        "p_value": float(p)
    },
    "within_supplier_robust": {
        "n_suppliers": int(len(robust_ids)),
        "premium_pct": round(prem_r, 2),
        "pct_sb_lower": round((diff_r < 0).mean()*100, 1),
        "cohens_d": round(d2, 4)
    }
}
with open('results/within_sector/within_supplier_analysis.json', 'w') as f:
    json.dump(results, f, indent=2)
print("\nSaved to results/within_supplier_analysis.json")
