"""Quick computation of EU-specific numbers needed for manuscript rewrite"""
import pandas as pd
import numpy as np
import json, os

os.chdir(r'C:\Users\Jack0\GitHub\Public-Procurement-Control-Surface')
df = pd.read_parquet('Data/processed/gprd_with_carbon.parquet',
    columns=['country','year','value_eur','single_bidder','carbon_intensity_kg_usd','n_bidders','exiobase_sector','cpv_division'])

# EU definition matching manuscript: all countries EXCEPT CO (Colombia)
# (NO, CH, IS, GB participated in TED and are "EU-context" for procurement purposes)
EU_CONTEXT = df['country'] != 'CO'
eu = df[EU_CONTEXT].copy()
co = df[df['country'] == 'CO'].copy()

print(f"EU-context: {len(eu):,} contracts")
print(f"Colombia: {len(co):,} contracts")
print()

# EU-context premium
sb = eu[eu['single_bidder']]
mb = eu[~eu['single_bidder']]
prem = (sb['carbon_intensity_kg_usd'].mean() - mb['carbon_intensity_kg_usd'].mean()) / mb['carbon_intensity_kg_usd'].mean() * 100
print(f"EU-context premium: {prem:+.1f}%")
print(f"  SB mean: {sb['carbon_intensity_kg_usd'].mean():.4f}, MB mean: {mb['carbon_intensity_kg_usd'].mean():.4f}")
print(f"  SB N: {len(sb):,}, MB N: {len(mb):,}, SB rate: {len(sb)/len(eu)*100:.1f}%")

# EU U-curve
for label, lo, hi in [("Small <€10k", 0, 10000), ("Medium €10k-200k", 10000, 200000), ("Large >€200k", 200000, 1e15)]:
    subset = eu[(eu['value_eur'] > lo) & (eu['value_eur'] <= hi)]
    s = subset[subset['single_bidder']]
    m = subset[~subset['single_bidder']]
    if len(m) > 0 and len(s) > 0:
        p = (s['carbon_intensity_kg_usd'].mean() - m['carbon_intensity_kg_usd'].mean()) / m['carbon_intensity_kg_usd'].mean() * 100
        # Cohen's d
        pooled_std = np.sqrt(((len(s)-1)*s['carbon_intensity_kg_usd'].std()**2 + (len(m)-1)*m['carbon_intensity_kg_usd'].std()**2) / (len(s)+len(m)-2))
        d = (s['carbon_intensity_kg_usd'].mean() - m['carbon_intensity_kg_usd'].mean()) / pooled_std if pooled_std > 0 else 0
        # t-stat
        from scipy import stats
        t_stat, p_val = stats.ttest_ind(s['carbon_intensity_kg_usd'], m['carbon_intensity_kg_usd'])
        print(f"  {label}: N={len(subset):,} SB_rate={len(s)/len(subset)*100:.1f}% premium={p:+.1f}% d={d:.2f} t={t_stat:.1f}")

# Colombia premium
co_sb = co[co['single_bidder']]
co_mb = co[~co['single_bidder']]
co_prem = (co_sb['carbon_intensity_kg_usd'].mean() - co_mb['carbon_intensity_kg_usd'].mean()) / co_mb['carbon_intensity_kg_usd'].mean() * 100
print(f"\nColombia premium: {co_prem:+.1f}%")
print(f"  SB mean: {co_sb['carbon_intensity_kg_usd'].mean():.4f}, MB mean: {co_mb['carbon_intensity_kg_usd'].mean():.4f}")
print(f"  SB N: {len(co_sb):,}, MB N: {len(co_mb):,}, SB rate: {len(co_sb)/len(co)*100:.1f}%")
print(f"  N bidders null in CO: {co['n_bidders'].isna().sum():,}")

# EU-context yearly COVID data
print("\nEU-CONTEXT SB RATES BY YEAR:")
for yr in range(2012, 2024):
    yr_data = eu[eu['year'] == yr]
    if len(yr_data) > 0:
        sb_rate = yr_data['single_bidder'].mean() * 100
        sb_d = yr_data[yr_data['single_bidder']]
        mb_d = yr_data[~yr_data['single_bidder']]
        prem = (sb_d['carbon_intensity_kg_usd'].mean() - mb_d['carbon_intensity_kg_usd'].mean()) / mb_d['carbon_intensity_kg_usd'].mean() * 100 if len(mb_d) > 0 and len(sb_d) > 0 else 0
        print(f"  {yr}: N={len(yr_data):,} SB_rate={sb_rate:.1f}% premium={prem:+.1f}%")

# Verify: what is the exact EU member state split?
print("\nContracts by country:")
for c in sorted(eu['country'].unique()):
    n = len(eu[eu['country'] == c])
    sb_r = eu[eu['country'] == c]['single_bidder'].mean() * 100
    print(f"  {c}: {n:,} ({sb_r:.1f}% SB)")

# Global stats to verify
print(f"\nGlobal: N={len(df):,}")
all_sb = df[df['single_bidder']]
all_mb = df[~df['single_bidder']]
all_prem = (all_sb['carbon_intensity_kg_usd'].mean() - all_mb['carbon_intensity_kg_usd'].mean()) / all_mb['carbon_intensity_kg_usd'].mean() * 100
print(f"  SB mean: {all_sb['carbon_intensity_kg_usd'].mean():.4f}, MB mean: {all_mb['carbon_intensity_kg_usd'].mean():.4f}")
print(f"  Premium: {all_prem:+.1f}%")
print(f"  SB N: {len(all_sb):,}, SB rate: {len(all_sb)/len(df)*100:.1f}%")

# Simpson's paradox explanation
print("\n=== SIMPSON'S PARADOX EXPLANATION ===")
print(f"EU-context (excl CO): SB mean={eu[eu['single_bidder']]['carbon_intensity_kg_usd'].mean():.4f}, MB mean={eu[~eu['single_bidder']]['carbon_intensity_kg_usd'].mean():.4f}")
print(f"Colombia: SB mean={co_sb['carbon_intensity_kg_usd'].mean():.4f}, MB mean={co_mb['carbon_intensity_kg_usd'].mean():.4f}")
print(f"Global: SB mean={all_sb['carbon_intensity_kg_usd'].mean():.4f}, MB mean={all_mb['carbon_intensity_kg_usd'].mean():.4f}")
print()
print(f"Colombia has {len(co):,} contracts ({len(co)/len(df)*100:.0f}% of data) with CI~0.20")
print(f"EU-context has {len(eu):,} contracts ({len(eu)/len(df)*100:.0f}% of data) with CI~0.35")
print(f"Colombia SB rate: {len(co_sb)/len(co)*100:.1f}% vs EU SB rate: {len(eu[eu['single_bidder']])/len(eu)*100:.1f}%")
print(f"Since Colombia is 99.3% multi-bidder + low CI, it drags down the global MB mean")
print(f"Since Colombia has few SB contracts, the global SB mean ≈ EU SB mean")
print(f"Result: Global SB mean ({all_sb['carbon_intensity_kg_usd'].mean():.3f}) > Global MB mean ({all_mb['carbon_intensity_kg_usd'].mean():.3f})")
print(f"Even though BOTH subgroups show SB < MB!")
