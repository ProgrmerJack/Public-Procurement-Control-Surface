"""Monte Carlo uncertainty propagation for manuscript headline claims."""

import numpy as np
import json

np.random.seed(42)
N_SIM = 100_000

# Parameters with uncertainty distributions
oecd_pct = np.random.uniform(0.12, 0.15, N_SIM)  # 12-15% of GDP
eu_gdp = 16.6e12  # EUR, Eurostat 2023
procurement = oecd_pct * eu_gdp

sb_rate = np.clip(np.random.normal(0.170, 0.005, N_SIM), 0.15, 0.20)

# Carbon intensity with +/-10% uncertainty
ci_sb = np.random.normal(0.3405, 0.3405 * 0.10, N_SIM)

# Single-bidder spending and carbon
sb_spending = procurement * sb_rate
sb_spending_bn = sb_spending / 1e9
sb_carbon_mt = sb_spending * ci_sb / 1e9

# NDC fraction: remaining EU reduction from 2019 to 2030 NDC target
# EU 2019 GHG ~3,600 Mt (26 countries incl UK at that time)
# EU 2030 target: 55% below 1990 → ~2,475 Mt (EU27) or lower with UK
# Remaining reduction: ~1,200-1,600 Mt depending on scope
ndc_reduction = np.random.uniform(1200, 1600, N_SIM)
ndc_pct = (sb_carbon_mt / ndc_reduction) * 100

# Reform scenario: attenuated conventional TWFE sensitivity.
# The lower uncertainty tail includes zero/positive ATT values, so projected
# spending opened to competition is clipped at zero for scenario magnitudes.
did_att = np.random.normal(-0.71, 1.24, N_SIM)
reform_spending = procurement * np.clip(-did_att / 100, 0, None)
reform_spending_bn = reform_spending / 1e9
reform_carbon_mt = reform_spending * ci_sb / 1e9


def stats(arr):
    return {
        "mean": round(float(np.mean(arr)), 1),
        "p5": round(float(np.percentile(arr, 5)), 1),
        "p50": round(float(np.percentile(arr, 50)), 1),
        "p95": round(float(np.percentile(arr, 95)), 1),
    }


results = {
    "n_simulations": N_SIM,
    "sb_spending_bn_eur": stats(sb_spending_bn),
    "sb_carbon_mt": stats(sb_carbon_mt),
    "ndc_pct": stats(ndc_pct),
    "reform_spending_bn_eur": stats(reform_spending_bn),
    "reform_carbon_mt": stats(reform_carbon_mt),
}

print("MONTE CARLO UNCERTAINTY PROPAGATION (100,000 simulations)")
print("=" * 60)
s = results["sb_spending_bn_eur"]
print(f"SB spending: EUR {s['p5']:.0f}-{s['p95']:.0f}B (90% CI), mean={s['mean']:.0f}B")
c = results["sb_carbon_mt"]
print(f"SB carbon: {c['p5']:.0f}-{c['p95']:.0f} Mt (90% CI), mean={c['mean']:.0f} Mt")
n = results["ndc_pct"]
print(f"NDC fraction: {n['p5']:.1f}-{n['p95']:.1f}% (90% CI), mean={n['mean']:.1f}%")
r = results["reform_spending_bn_eur"]
print(f"Reform spending: EUR {r['p5']:.0f}-{r['p95']:.0f}B (90% CI)")
rc = results["reform_carbon_mt"]
print(f"Reform carbon: {rc['p5']:.0f}-{rc['p95']:.0f} Mt (90% CI)")

print("\nMANUSCRIPT CLAIMS vs MONTE CARLO:")
print(f"  Claimed: EUR 350-434B    MC 90% CI: EUR {s['p5']:.0f}-{s['p95']:.0f}B")
print(f"  Claimed: 129-161 Mt      MC 90% CI: {c['p5']:.0f}-{c['p95']:.0f} Mt")
print(f"  Claimed: 9-12%           MC 90% CI: {n['p5']:.1f}-{n['p95']:.1f}%")

with open("results/projections/monte_carlo_uncertainty.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nSaved to results/monte_carlo_uncertainty.json")
