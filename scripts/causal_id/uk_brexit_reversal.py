"""
UK Brexit Withdrawal-of-Treatment Test
========================================
UK transposed Directive 2014/24/EU in 2015 (early adopter, 2015 cohort in our C&S design).
EU procurement rules ceased to apply to UK contracts from 1 January 2021 (end of Brexit transition).
If EU governance rules caused the competition gains, we expect UK to show REVERSAL (rising SB rates)
post-2020 relative to EU member states that remained treated.

This is a withdrawal-of-treatment placebo test — one of the strongest causal diagnostics available.
"""

import json
import pathlib
import numpy as np
import pandas as pd
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT_PATH = ROOT / "results" / "causal_id" / "uk_brexit_reversal.json"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

print("Loading data...")
df = pd.read_parquet(
    DATA_PATH,
    columns=["country", "year", "single_bidder", "carbon_intensity_kg_usd"],
)
df = df.rename(
    columns={
        "country": "iso_code",
        "carbon_intensity_kg_usd": "carbon_intensity_kgco2_per_usd",
    }
)
df["year"] = pd.to_numeric(df["year"], errors="coerce")
df = df[df["year"].between(2012, 2023)].copy()
df["year"] = df["year"].astype(int)

# EU member states that remained in EU (treated, never-exited)
CORE_EU = [
    "AT",
    "BE",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "NL",
    "PL",
    "PT",
    "SE",
    "SI",
    "SK",
]
# UK: early adopter 2015, EU rules ceased Jan 2021
# Norway, Switzerland: never-treated EFTA controls

print("Computing year-by-year single-bidder rates...")


def sb_rate_by_year(country_list, label):
    mask = df["iso_code"].isin(country_list)
    grp = df[mask].groupby("year")["single_bidder"].agg(["mean", "count"]).reset_index()
    grp.columns = ["year", f"{label}_sb_rate", f"{label}_n"]
    return grp


uk_yr = sb_rate_by_year(["GB"], "uk")
eu_yr = sb_rate_by_year(CORE_EU, "eu")
no_yr = sb_rate_by_year(["NO"], "no")
ch_yr = sb_rate_by_year(["CH"], "ch")

panel = uk_yr.merge(eu_yr, on="year").merge(no_yr, on="year").merge(ch_yr, on="year")
panel["eu_control_sb_rate"] = (
    panel["no_sb_rate"] + panel["ch_sb_rate"]
) / 2  # simple average

if panel.empty:
    raise RuntimeError(
        "UK/EU/NO/CH yearly panel is empty after aggregation; check parquet year coverage and country codes."
    )

print("\nYear-by-Year Single-Bidder Rates:")
print(
    panel[["year", "uk_sb_rate", "eu_sb_rate", "eu_control_sb_rate"]].to_string(
        index=False
    )
)

# DiD: UK relative to EU member states
# Pre-Brexit (2016-2020): UK and EU both under EU rules
# Post-Brexit (2021-2023): UK exits EU procurement framework
panel["period"] = panel["year"].apply(
    lambda y: "pre_brexit" if y <= 2020 else "post_brexit"
)
panel["uk_vs_eu_diff"] = panel["uk_sb_rate"] - panel["eu_sb_rate"]
panel["uk_vs_control_diff"] = panel["uk_sb_rate"] - panel["eu_control_sb_rate"]

pre_uk_vs_eu = panel[panel["period"] == "pre_brexit"]["uk_vs_eu_diff"].mean()
post_uk_vs_eu = panel[panel["period"] == "post_brexit"]["uk_vs_eu_diff"].mean()
did_uk_vs_eu = post_uk_vs_eu - pre_uk_vs_eu  # positive = UK worsened relative to EU

print(f"\nUK vs EU (core member states):")
print(f"  Pre-Brexit avg diff (UK-EU): {pre_uk_vs_eu:.3f} pp")
print(f"  Post-Brexit avg diff (UK-EU): {post_uk_vs_eu:.3f} pp")
print(
    f"  DiD (reversal): +{did_uk_vs_eu:.3f} pp (positive = UK SB rose relative to EU)"
)

# Year-on-year UK SB rate change: pre vs post Brexit
uk_pre = panel[panel["year"].between(2017, 2020)]["uk_sb_rate"].values
uk_post = panel[panel["year"].between(2021, 2023)]["uk_sb_rate"].values
eu_pre = panel[panel["year"].between(2017, 2020)]["eu_sb_rate"].values
eu_post = panel[panel["year"].between(2021, 2023)]["eu_sb_rate"].values

uk_change = uk_post.mean() - uk_pre.mean()
eu_change = eu_post.mean() - eu_pre.mean()
relative_divergence = uk_change - eu_change

print(f"\nUK SB rate change (2017-2020 avg → 2021-2023 avg): {uk_change:+.3f} pp")
print(f"EU SB rate change (2017-2020 avg → 2021-2023 avg): {eu_change:+.3f} pp")
print(f"UK relative divergence (withdrawal effect): {relative_divergence:+.3f} pp")
print(
    f"  {'↑ UK DIVERGES FROM EU = withdrawal-of-treatment reversal' if relative_divergence > 0 else '↓ No divergence'}"
)

# UK 2020→2021 single-year inflection test
if 2020 in panel["year"].values and 2021 in panel["year"].values:
    uk_2020 = panel[panel["year"] == 2020]["uk_sb_rate"].values[0]
    uk_2021 = panel[panel["year"] == 2021]["uk_sb_rate"].values[0]
    eu_2020 = panel[panel["year"] == 2020]["eu_sb_rate"].values[0]
    eu_2021 = panel[panel["year"] == 2021]["eu_sb_rate"].values[0]
    print(f"\nInflection at Brexit boundary:")
    print(
        f"  UK:  2020={uk_2020 * 100:.2f}% → 2021={uk_2021 * 100:.2f}% ({(uk_2021 - uk_2020) * 100:+.2f} pp)"
    )
    print(
        f"  EU:  2020={eu_2020 * 100:.2f}% → 2021={eu_2021 * 100:.2f}% ({(eu_2021 - eu_2020) * 100:+.2f} pp)"
    )
    uk_inflect = (uk_2021 - uk_2020) * 100
    eu_inflect = (eu_2021 - eu_2020) * 100
    dd_inflect = uk_inflect - eu_inflect
    print(
        f"  DiD at inflection: {dd_inflect:+.2f} pp (UK relative to EU at Brexit boundary)"
    )

# UK trend: pre-reform (2012-2015), post-reform (2016-2020), post-Brexit (2021-2023)
for label, years in [
    ("pre_reform_2012_2015", range(2012, 2016)),
    ("post_reform_2016_2020", range(2016, 2021)),
    ("post_brexit_2021_2023", range(2021, 2024)),
]:
    yr_data = panel[panel["year"].isin(years)]
    if len(yr_data):
        uk_mean = yr_data["uk_sb_rate"].mean() * 100
        eu_mean = yr_data["eu_sb_rate"].mean() * 100
        print(
            f"\n{label}: UK={uk_mean:.2f}%, EU={eu_mean:.2f}%, UK-EU={uk_mean - eu_mean:+.2f} pp"
        )

# Statistical test: is UK's post-Brexit increase significantly different from EU's trajectory?
# Interrupted time series: regression of UK_SB ~ year + post_brexit + year*post_brexit
panel["post_brexit_flag"] = (panel["year"] >= 2021).astype(int)
panel["year_centered"] = panel["year"] - 2021
uk_panel = panel[["year", "year_centered", "post_brexit_flag", "uk_sb_rate"]].copy()
# Fit ITS model
from numpy.linalg import lstsq

X = np.column_stack(
    [
        np.ones(len(uk_panel)),
        uk_panel["year_centered"].values,
        uk_panel["post_brexit_flag"].values,
        uk_panel["year_centered"].values * uk_panel["post_brexit_flag"].values,
    ]
)
y = uk_panel["uk_sb_rate"].values * 100
coefs, residuals, rank, sv = lstsq(X, y, rcond=None)
yhat = X @ coefs
resid = y - yhat
n, k = len(y), 4
sigma2 = np.sum(resid**2) / (n - k)
cov = sigma2 * np.linalg.inv(X.T @ X)
ses = np.sqrt(np.diag(cov))
t_level_shift = coefs[2] / ses[2]
t_slope_change = coefs[3] / ses[3]
from scipy.stats import t as t_dist

df_resid = n - k
p_level_shift = 2 * t_dist.sf(abs(t_level_shift), df_resid)
p_slope_change = 2 * t_dist.sf(abs(t_slope_change), df_resid)
print(f"\nUK Interrupted Time Series (ITS) at Brexit boundary (2021):")
print(
    f"  Level shift at 2021: {coefs[2]:+.3f} pp (t={t_level_shift:.2f}, p={p_level_shift:.3f})"
)
print(
    f"  Slope change at 2021: {coefs[3]:+.3f} pp/yr (t={t_slope_change:.2f}, p={p_slope_change:.3f})"
)

# UK vs EU divergence as a withdrawal-of-treatment test
# Fit same model to EU
eu_panel = panel[["year", "year_centered", "post_brexit_flag", "eu_sb_rate"]].copy()
X_eu = X.copy()
y_eu = eu_panel["eu_sb_rate"].values * 100
coefs_eu, _, _, _ = lstsq(X_eu, y_eu, rcond=None)
print(f"\nEU ITS at 2021 (comparison):")
print(f"  Level shift: {coefs_eu[2]:+.3f} pp")
print(f"  Slope change: {coefs_eu[3]:+.3f} pp/yr")

uk_minus_eu_level = coefs[2] - coefs_eu[2]
uk_minus_eu_slope = coefs[3] - coefs_eu[3]
print(f"\nUK−EU differential at Brexit boundary:")
print(f"  Level: {uk_minus_eu_level:+.3f} pp")
print(f"  Slope: {uk_minus_eu_slope:+.3f} pp/yr")

# Save results
results = {
    "analysis": "UK Brexit Withdrawal-of-Treatment Test",
    "panel": panel[
        ["year", "uk_sb_rate", "eu_sb_rate", "eu_control_sb_rate", "uk_vs_eu_diff"]
    ]
    .round(6)
    .to_dict(orient="records"),
    "did_uk_vs_eu_pp": float(did_uk_vs_eu * 100),
    "uk_change_pp": float(uk_change * 100),
    "eu_change_pp": float(eu_change * 100),
    "relative_divergence_pp": float(relative_divergence * 100),
    "inflection": {
        "uk_2020": float(uk_2020 * 100),
        "uk_2021": float(uk_2021 * 100),
        "eu_2020": float(eu_2020 * 100),
        "eu_2021": float(eu_2021 * 100),
        "dd_at_boundary": float(dd_inflect),
    }
    if 2020 in panel["year"].values and 2021 in panel["year"].values
    else {},
    "its": {
        "uk_level_shift_pp": float(coefs[2]),
        "uk_level_shift_t": float(t_level_shift),
        "uk_level_shift_p": float(p_level_shift),
        "uk_slope_change_pp_yr": float(coefs[3]),
        "uk_slope_change_t": float(t_slope_change),
        "uk_slope_change_p": float(p_slope_change),
        "eu_level_shift_pp": float(coefs_eu[2]),
        "eu_slope_change_pp_yr": float(coefs_eu[3]),
        "differential_level_pp": float(uk_minus_eu_level),
        "differential_slope_pp_yr": float(uk_minus_eu_slope),
    },
    "interpretation": {
        "positive_divergence": bool(relative_divergence > 0),
        "reversal_direction": "UK SB rates rose relative to EU after Brexit withdrawal = consistent with governance-reform-caused competition gains"
        if relative_divergence > 0
        else "No reversal detected",
    },
}

with open(OUT_PATH, "w") as f:
    json.dump(results, f, indent=2, default=str)

print(f"\nResults saved to {OUT_PATH}")
print("\n=== BREAKTHROUGH DIAGNOSTIC ===")
print(
    "If UK (withdrawal from EU rules) shows RISING SB rates relative to EU (still treated),"
)
print(
    "this is a withdrawal-of-treatment causal validation — the governance mechanism is confirmed."
)
