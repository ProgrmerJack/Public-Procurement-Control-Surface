"""Synthetic Control permutation inference with RMSPE ratios."""

import pandas as pd
import numpy as np
import json

# Load data
proc = pd.read_parquet(
    "Data/processed/gprd_with_carbon.parquet",
    columns=["country", "year", "single_bidder"],
)

# Define treatment/control. Colombia and Iceland are outside the primary EU
# DiD panel; Norway and Switzerland are the never-treated comparators.
eu_countries = [c for c in proc["country"].unique() if c not in {"CO", "IS"}]
proc_eu = proc[proc["country"].isin(eu_countries)]
donors = ["NO", "CH"]
eu_treat = [c for c in eu_countries if c not in donors]

# Compute SB rates by country-year
sb_rates = proc_eu.groupby(["country", "year"])["single_bidder"].mean().reset_index()
sb_rates.columns = ["country", "year", "sb_rate"]
sb_pivot = sb_rates.pivot(index="year", columns="country", values="sb_rate")

pre = [2012, 2013, 2014, 2015]
post = [2017, 2018, 2019, 2020, 2021, 2022, 2023]

print("=== SYNTHETIC CONTROL PERMUTATION INFERENCE ===\n")

# EU aggregate SB rate by year
eu_agg = (
    proc_eu[proc_eu["country"].isin(eu_treat)].groupby("year")["single_bidder"].mean()
)
donor_agg = (
    proc_eu[proc_eu["country"].isin(donors)].groupby("year")["single_bidder"].mean()
)

# EU-level effect
eu_pre = np.mean([eu_agg.get(y, np.nan) for y in pre])
eu_post = np.mean([eu_agg.get(y, np.nan) for y in post])
don_pre = np.mean([donor_agg.get(y, np.nan) for y in pre])
don_post = np.mean([donor_agg.get(y, np.nan) for y in post])

eu_change = eu_post - eu_pre
don_change = don_post - don_pre
true_effect = eu_change - don_change

print(f"EU pre: {eu_pre:.4f}, post: {eu_post:.4f}, change: {eu_change * 100:+.2f} pp")
print(
    f"Donor pre: {don_pre:.4f}, post: {don_post:.4f}, change: {don_change * 100:+.2f} pp"
)
print(f"True SC effect: {true_effect * 100:+.2f} pp\n")

# PERMUTATION: each EU country vs donors
print("=== WITHIN-EU PLACEBO (each country vs donors) ===")
country_effects = {}
for c in eu_treat:
    c_data = sb_pivot.get(c)
    if c_data is None:
        continue
    c_pre_vals = [c_data.get(y, np.nan) for y in pre]
    c_post_vals = [c_data.get(y, np.nan) for y in post]
    c_pre = np.nanmean(c_pre_vals)
    c_post = np.nanmean(c_post_vals)
    if np.isnan(c_pre) or np.isnan(c_post):
        continue
    c_change = c_post - c_pre
    c_effect = c_change - don_change
    country_effects[c] = c_effect * 100

sorted_effects = sorted(country_effects.items(), key=lambda x: x[1])
print("Country effects (pp, relative to donors):")
for c, eff in sorted_effects:
    marker = " ***" if eff <= true_effect * 100 else ""
    print(f"  {c}: {eff:+.2f} pp{marker}")

n_extreme = sum(1 for e in country_effects.values() if e <= true_effect * 100)
p_perm = n_extreme / len(country_effects)
print(
    f"\nPermutation p-value (one-sided, effect <= {true_effect * 100:.2f}): {p_perm:.3f} ({n_extreme}/{len(country_effects)})"
)

# RMSPE-based inference
print("\n=== RMSPE-BASED INFERENCE (Demeaned) ===")
rmspe_ratios = {}

all_units = list(eu_treat) + ["EU_AGG"]
for c in all_units:
    if c == "EU_AGG":
        c_series = eu_agg
    else:
        c_series = sb_pivot.get(c)
        if c_series is None:
            continue

    pre_gaps = []
    post_gaps = []
    for y in pre:
        cv = c_series.get(y, np.nan) if hasattr(c_series, "get") else np.nan
        dv = donor_agg.get(y, np.nan)
        if not np.isnan(cv) and not np.isnan(dv):
            pre_gaps.append(cv - dv)
    for y in post:
        cv = c_series.get(y, np.nan) if hasattr(c_series, "get") else np.nan
        dv = donor_agg.get(y, np.nan)
        if not np.isnan(cv) and not np.isnan(dv):
            post_gaps.append(cv - dv)

    if pre_gaps and post_gaps:
        mean_pre_gap = np.mean(pre_gaps)
        demeaned_pre = [g - mean_pre_gap for g in pre_gaps]
        demeaned_post = [g - mean_pre_gap for g in post_gaps]

        pre_rmspe = np.sqrt(np.mean(np.array(demeaned_pre) ** 2))
        post_rmspe = np.sqrt(np.mean(np.array(demeaned_post) ** 2))

        if pre_rmspe > 0.001:
            ratio = post_rmspe / pre_rmspe
        else:
            ratio = post_rmspe / 0.001
        rmspe_ratios[c] = {
            "pre": float(pre_rmspe),
            "post": float(post_rmspe),
            "ratio": float(ratio),
        }

sorted_rmspe = sorted(rmspe_ratios.items(), key=lambda x: x[1]["ratio"], reverse=True)
print("RMSPE ratios (post/pre, demeaned):")
eu_rank = None
for i, (c, vals) in enumerate(sorted_rmspe):
    marker = " <<<" if c == "EU_AGG" else ""
    r = vals["ratio"]
    pre_v = vals["pre"]
    post_v = vals["post"]
    print(f"  {i + 1}. {c}: ratio={r:.2f} (pre={pre_v:.4f}, post={post_v:.4f}){marker}")
    if c == "EU_AGG":
        eu_rank = i + 1

rmspe_p = eu_rank / len(sorted_rmspe) if eu_rank else None
if eu_rank:
    print(f"\nEU_AGG rank: {eu_rank}/{len(sorted_rmspe)}")
    print(f"RMSPE permutation p-value: {rmspe_p:.3f}")

# Save
results = {
    "true_effect_pp": round(true_effect * 100, 2),
    "country_effects_pp": {c: round(v, 2) for c, v in country_effects.items()},
    "permutation_p_onesided": round(p_perm, 3),
    "n_more_extreme": n_extreme,
    "n_countries": len(country_effects),
    "eu_rmspe_rank": eu_rank,
    "rmspe_p_value": round(rmspe_p, 3) if rmspe_p else None,
    "rmspe_n_total": len(sorted_rmspe),
    "rmspe_ratios": {c: round(v["ratio"], 2) for c, v in sorted_rmspe},
}

with open("results/causal_id/sc_permutation_inference.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nResults saved to results/sc_permutation_inference.json")
