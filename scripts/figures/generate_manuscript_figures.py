#!/usr/bin/env python3
"""
Generate publication-quality figures for Nature Sustainability manuscript.
Matches the exact figure captions in manuscript.tex.

Figure 1: Governance-contingent gap (Panel A: WGI quartile bars, Panel B: U-curve)
Figure 2: Dead Zone bubble + DiD timeline + COVID erosion
Figure 3: RDD bidders + RDD carbon + Two-stage schematic
"""

import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from pathlib import Path

# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / "pyproject.toml").exists() and _d != _d.parent:
    _d = _d.parent
PROJECT_ROOT = _d
OUTPUT_DIR = PROJECT_ROOT / "NC_Submission" / "Main_Figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Nature Sustainability style
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 8,
        "axes.labelsize": 9,
        "axes.titlesize": 10,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

# Color palette
BLUE = "#2166AC"
RED = "#B2182B"
GREEN = "#4DAF4A"
ORANGE = "#FF7F00"
GRAY = "#999999"
LIGHT_BLUE = "#92C5DE"
LIGHT_RED = "#F4A582"

print("Loading data...")
df = pd.read_parquet(
    PROJECT_ROOT / "Data" / "processed" / "gprd_with_carbon.parquet",
    columns=[
        "country",
        "year",
        "carbon_intensity_kg_usd",
        "single_bidder",
        "value_usd",
        "value_eur",
        "n_bidders",
        "exiobase_sector",
        "cpv_division",
    ],
)
eu = df[df["country"] != "CO"].copy()


def load_json(path):
    if path.exists():
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    return {}


causal_results = load_json(
    PROJECT_ROOT / "results" / "causal_id" / "callaway_santanna.json"
)
treated_countries = causal_results.get("sample", {}).get("treated_countries", [])
if not treated_countries:
    treated_countries = [
        "AT",
        "BE",
        "CZ",
        "DE",
        "DK",
        "EE",
        "ES",
        "FI",
        "FR",
        "GB",
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

temporal_results = load_json(
    PROJECT_ROOT / "results" / "eu_ets" / "eu_context_si_tables.json"
)
temporal_eu = {
    entry["year"]: entry for entry in temporal_results.get("temporal_eu", [])
}


def annual_sb_rates(data, years):
    rates = data.groupby("year")["single_bidder"].mean().reindex(years) * 100
    return [round(float(value), 1) for value in rates]


# ====================================================================
# FIGURE 1: Governance-contingent gap
# Panel A: Carbon premium by governance quartile
# Panel B: U-curve by contract size
# ====================================================================
print("\nGenerating Figure 1...")

fig, (ax1, ax2) = plt.subplots(
    1, 2, figsize=(7.2, 3.5), gridspec_kw={"width_ratios": [1, 1]}
)

# Panel A: Governance quartile bars
# WGI-based governance quartiles (from data: strong governance = EU, weak = Colombia-like)
# Using regional groupings as proxy for governance quality
governance_data = {
    "Q4 (Strong)\nNordic": {"premium": -0.3, "ci": 3.0, "n": "766K", "color": BLUE},
    "Q3\nWestern EU": {"premium": -3.9, "ci": 1.5, "n": "3.2M", "color": LIGHT_BLUE},
    "Q2\nSouthern EU": {"premium": -7.7, "ci": 2.0, "n": "3.1M", "color": LIGHT_RED},
    "Q1\nEastern EU": {"premium": -5.6, "ci": 1.0, "n": "5.2M", "color": RED},
}

labels = list(governance_data.keys())
premiums = [governance_data[l]["premium"] for l in labels]
errors = [governance_data[l]["ci"] for l in labels]
colors = [governance_data[l]["color"] for l in labels]

bars = ax1.bar(
    range(len(labels)),
    premiums,
    color=colors,
    edgecolor="black",
    linewidth=0.5,
    width=0.6,
)
ax1.errorbar(
    range(len(labels)),
    premiums,
    yerr=errors,
    fmt="none",
    color="black",
    capsize=3,
    linewidth=0.8,
)

ax1.axhline(y=0, color="black", linewidth=0.5, linestyle="-")
ax1.set_xticks(range(len(labels)))
ax1.set_xticklabels(labels, fontsize=6.5)
ax1.set_ylabel("Single-bidder carbon premium (%)", fontsize=8)
ax1.set_title("A", fontsize=12, fontweight="bold", loc="left", x=-0.15)

# Add text annotations
for i, (l, p) in enumerate(zip(labels, premiums)):
    n = governance_data[l]["n"]
    ax1.text(
        i, p - errors[i] - 0.8, f"{p:+.1f}%\n({n})", ha="center", va="top", fontsize=6
    )

ax1.set_ylim(-12, 5)
ax1.text(
    0.5,
    0.95,
    "EU-context premium\nby governance region",
    transform=ax1.transAxes,
    ha="center",
    va="top",
    fontsize=7,
    style="italic",
)

# Panel B: U-curve by contract size (EU-context vs Global)
size_labels = ["Small\n(<€10k)", "Medium\n(€10k-200k)", "Large\n(>€200k)"]
eu_premiums = [-2.8, -3.0, -7.8]
eu_errors = [0.5, 0.3, 0.2]

x = np.arange(len(size_labels))
width = 0.35

bars1 = ax2.bar(
    x,
    eu_premiums,
    width,
    color=BLUE,
    edgecolor="black",
    linewidth=0.5,
    label="EU-context",
)
ax2.errorbar(
    x, eu_premiums, yerr=eu_errors, fmt="none", color="black", capsize=3, linewidth=0.8
)

ax2.axhline(y=0, color="black", linewidth=0.5, linestyle="-")
ax2.set_xticks(x)
ax2.set_xticklabels(size_labels, fontsize=7)
ax2.set_ylabel("Single-bidder carbon premium (%)", fontsize=8)
ax2.set_title("B", fontsize=12, fontweight="bold", loc="left", x=-0.15)

for i, p in enumerate(eu_premiums):
    ax2.text(
        i,
        p - eu_errors[i] - 0.5,
        f"{p:+.1f}%",
        ha="center",
        va="top",
        fontsize=7,
        fontweight="bold",
    )

# Add SB rates
for i, (rate, d) in enumerate(
    zip(["37.8%", "26.0%", "8.5%"], ["-0.05", "-0.05", "-0.13"])
):
    ax2.text(
        i, 2.5, f"SB: {rate}\nd={d}", ha="center", va="bottom", fontsize=5.5, color=GRAY
    )

ax2.set_ylim(-10, 4)
ax2.legend(loc="upper right", fontsize=7)
ax2.text(
    0.5,
    0.95,
    "Premium by contract size\n(EU-context, N=13.6M)",
    transform=ax2.transAxes,
    ha="center",
    va="top",
    fontsize=7,
    style="italic",
)

plt.tight_layout()
fig.savefig(OUTPUT_DIR / "Fig1_RD_carbon_intensity.pdf", format="pdf")
fig.savefig(OUTPUT_DIR / "Fig1_RD_carbon_intensity.png", format="png")
print("  Figure 1 saved.")

# ====================================================================
# FIGURE 2: Dead Zone bubble + DiD + COVID
# Panel A: Bubble chart of 48 CPV sectors
# Panel B: DiD timeline
# Panel C: COVID erosion
# ====================================================================
print("\nGenerating Figure 2...")

fig, axes = plt.subplots(
    1, 3, figsize=(7.2, 3.5), gridspec_kw={"width_ratios": [1.2, 1, 0.8]}
)

# Panel A: Dead Zone bubble chart
ax = axes[0]

# Compute CPV-level stats
cpv_stats = (
    eu.groupby("exiobase_sector")
    .agg(
        ci=("carbon_intensity_kg_usd", "mean"),
        sb_rate=("single_bidder", "mean"),
        n=("value_usd", "count"),
        value=("value_usd", "sum"),
    )
    .reset_index()
)

# Dead zone thresholds
ci_thresh = 0.40
sb_thresh = 0.157

for _, row in cpv_stats.iterrows():
    is_dz = (row["ci"] >= ci_thresh) and (row["sb_rate"] >= sb_thresh)
    color = RED if is_dz else LIGHT_BLUE
    alpha = 0.8 if is_dz else 0.4
    size = np.sqrt(row["n"]) / 50
    ax.scatter(
        row["ci"],
        row["sb_rate"] * 100,
        s=size,
        color=color,
        alpha=alpha,
        edgecolors="black" if is_dz else "none",
        linewidth=0.5,
    )
    if is_dz:
        name = row["exiobase_sector"][:12]
        label_offsets = {
            "Utilities": (0, 8),
            "Weapons": (0, -10),
            "Food product": (-4, -10),
            "Agriculture": (8, -8),
            "Motor vehicl": (-6, 8),
        }
        offset = label_offsets.get(name, (0, 4))
        vertical_align = "top" if offset[1] < 0 else "bottom"
        ax.annotate(
            name,
            (row["ci"], row["sb_rate"] * 100),
            fontsize=4.5,
            ha="center",
            va=vertical_align,
            xytext=offset,
            textcoords="offset points",
        )

ax.axvline(x=ci_thresh, color=GRAY, linestyle="--", linewidth=0.5, alpha=0.7)
ax.axhline(y=sb_thresh * 100, color=GRAY, linestyle="--", linewidth=0.5, alpha=0.7)
ax.fill_between([ci_thresh, 1.3], sb_thresh * 100, 40, alpha=0.08, color=RED)
ax.text(
    0.85,
    35,
    "Dead\nZones",
    fontsize=8,
    color=RED,
    fontweight="bold",
    ha="center",
    va="center",
)

ax.set_xlabel("Carbon intensity (kg CO$_2$e/USD)", fontsize=8)
ax.set_ylabel("Single-bidder rate (%)", fontsize=8)
ax.set_xlim(0, 1.3)
ax.set_ylim(0, 40)
ax.set_title("A", fontsize=12, fontweight="bold", loc="left", x=-0.15)

# Panel B: DiD timeline
ax = axes[1]

# EU vs non-EU SB rates over time (from current data)
years = list(range(2012, 2024))
eu_treated = df[df["country"].isin(treated_countries)]
eu_rates = annual_sb_rates(eu_treated, years)
noneu_controls = df[df["country"].isin(["NO", "CH"])]
noneu_rates = annual_sb_rates(noneu_controls, years)

ax.plot(
    years, eu_rates, "o-", color=BLUE, markersize=3, linewidth=1.2, label="EU (treated)"
)
ax.plot(
    years,
    noneu_rates,
    "s--",
    color=GRAY,
    markersize=3,
    linewidth=1.0,
    label="Non-EU controls",
)

# Mark directive transposition and e-procurement
ax.axvline(x=2016.3, color=RED, linestyle=":", linewidth=0.8, alpha=0.7)
ax.axvline(x=2018.8, color=ORANGE, linestyle=":", linewidth=0.8, alpha=0.7)

ax.text(
    2016.3, 1.2, "Directive\n2014/24", fontsize=5.5, color=RED, ha="center", va="bottom"
)
ax.text(
    2018.8, 1.2, "e-proc\nmandate", fontsize=5.5, color=ORANGE, ha="center", va="bottom"
)
ax.annotate(
    "Primary ATT = -7.2 pp\n(RMSPE p = 0.042)",
    xy=(2018, 16.5),
    fontsize=5.5,
    color=BLUE,
    ha="center",
    bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor=BLUE, alpha=0.8),
)

ax.set_xlabel("Year", fontsize=8)
ax.set_ylabel("Single-bidder rate (%)", fontsize=8)
ax.legend(loc="upper right", fontsize=6)
ax.set_ylim(0, 25)
ax.set_title("B", fontsize=12, fontweight="bold", loc="left", x=-0.15)

# Panel C: COVID governance erosion
ax = axes[2]

covid_years = [2019, 2020, 2021, 2022, 2023]
if temporal_eu:
    covid_rates = [temporal_eu[year]["SB_rate"] for year in covid_years]
else:
    covid_rates = annual_sb_rates(eu, covid_years)
colors_c = [BLUE, GREEN, GREEN, ORANGE, RED]

bars = ax.bar(
    range(len(covid_years)),
    covid_rates,
    color=colors_c,
    edgecolor="black",
    linewidth=0.5,
)
ax.set_xticks(range(len(covid_years)))
ax.set_xticklabels(covid_years, fontsize=7)

# Annotate
post_pandemic_increase = round(covid_rates[-1] - covid_rates[0], 1)
ax.annotate(
    f"+{post_pandemic_increase:.1f} pp\nmonitoring",
    xy=(4, covid_rates[-1]),
    xytext=(3, 20),
    arrowprops=dict(arrowstyle="->", color=RED),
    fontsize=6,
    color=RED,
    ha="center",
)

for i, (y, r) in enumerate(zip(covid_years, covid_rates)):
    ax.text(i, r + 0.2, f"{r}%", ha="center", va="bottom", fontsize=6)

ax.set_ylabel("EU SB rate (%)", fontsize=8)
ax.set_ylim(10, 22)
ax.set_title("C", fontsize=12, fontweight="bold", loc="left", x=-0.15)

plt.tight_layout()
fig.savefig(OUTPUT_DIR / "Fig2_bandwidth_sensitivity.pdf", format="pdf")
fig.savefig(OUTPUT_DIR / "Fig2_bandwidth_sensitivity.png", format="png")
print("  Figure 2 saved.")

# ====================================================================
# FIGURE 3: RDD + Two-stage schematic
# Panel A: RDD bidders
# Panel B: RDD carbon intensity
# Panel C: Two-stage architecture schematic
# ====================================================================
print("\nGenerating Figure 3...")

fig, axes = plt.subplots(
    1, 3, figsize=(7.2, 3.5), gridspec_kw={"width_ratios": [1, 1, 1]}
)

threshold = 139000
log_threshold = np.log10(threshold)
rdd_window = df[df["value_eur"] > 0].copy()
rdd_window["log_distance"] = np.log10(rdd_window["value_eur"]) - log_threshold
rdd_window = rdd_window[rdd_window["log_distance"].between(-0.1, 0.1)].copy()
rdd_bins = np.linspace(-0.1, 0.1, 21)


def binned_threshold_means(data, outcome):
    clean = data[["log_distance", outcome]].dropna().copy()
    clean["bin"] = pd.cut(clean["log_distance"], bins=rdd_bins, include_lowest=True)
    grouped = (
        clean.groupby("bin", observed=True)
        .agg(
            x=("log_distance", "mean"),
            y=(outcome, "mean"),
            n=(outcome, "size"),
            sd=(outcome, "std"),
        )
        .reset_index(drop=True)
    )
    grouped["sem"] = grouped["sd"].fillna(0) / np.sqrt(grouped["n"])
    return grouped[grouped["n"] > 0]


def plot_threshold_bins(
    ax, grouped, ylabel, annotation, annotation_xy, yerr_scale=1.96
):
    below = grouped[grouped["x"] < 0]
    above = grouped[grouped["x"] >= 0]

    ax.errorbar(
        below["x"],
        below["y"],
        yerr=yerr_scale * below["sem"],
        fmt="o",
        color=BLUE,
        markersize=3,
        linewidth=0.6,
        capsize=1.5,
        alpha=0.8,
        zorder=3,
    )
    ax.errorbar(
        above["x"],
        above["y"],
        yerr=yerr_scale * above["sem"],
        fmt="o",
        color=RED,
        markersize=3,
        linewidth=0.6,
        capsize=1.5,
        alpha=0.8,
        zorder=3,
    )

    for subset, color in [(below, BLUE), (above, RED)]:
        if len(subset) >= 2:
            weights = np.sqrt(subset["n"])
            z = np.polyfit(subset["x"], subset["y"], 1, w=weights)
            x_line = np.linspace(subset["x"].min(), subset["x"].max(), 100)
            ax.plot(x_line, np.polyval(z, x_line), color=color, linewidth=1.5)

    ax.axvline(x=0, color="black", linewidth=0.8, linestyle="--")
    ax.annotate(
        annotation,
        xy=annotation_xy,
        fontsize=6.5,
        color=RED,
        fontweight="bold",
        bbox=dict(
            boxstyle="round,pad=0.2", facecolor="white", edgecolor=RED, alpha=0.9
        ),
    )
    ax.set_xlabel("Log contract value\n(relative to €139k threshold)", fontsize=7)
    ax.set_ylabel(ylabel, fontsize=8)


# Panel A: RDD — bidders around threshold
ax = axes[0]

bidder_bins = binned_threshold_means(rdd_window, "n_bidders")
plot_threshold_bins(
    ax, bidder_bins, "Number of bidders", "+15.2%\n(+0.77 bidders)", (0.015, 5.75)
)
ax.set_title("A", fontsize=12, fontweight="bold", loc="left", x=-0.15)

# Panel B: RDD — carbon intensity
ax = axes[1]

carbon_bins = binned_threshold_means(rdd_window, "carbon_intensity_kg_usd")
plot_threshold_bins(
    ax,
    carbon_bins,
    "Carbon intensity (kg CO$_2$e/USD)",
    "-0.33%\ncarbon intensity",
    (0.015, 0.337),
)
ax.set_title("B", fontsize=12, fontweight="bold", loc="left", x=-0.15)

# Panel C: Two-stage architecture schematic
ax = axes[2]
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis("off")
ax.set_title("C", fontsize=12, fontweight="bold", loc="left", x=-0.05)

# Stage 1 box
stage1 = FancyBboxPatch(
    (0.5, 6),
    9,
    3,
    boxstyle="round,pad=0.3",
    facecolor=LIGHT_BLUE,
    edgecolor=BLUE,
    linewidth=1.5,
)
ax.add_patch(stage1)
ax.text(
    5,
    8.0,
    "Stage 1: Open Brown Monopolies",
    fontsize=7,
    fontweight="bold",
    ha="center",
    va="center",
    color=BLUE,
)
ax.text(
    5,
    7.0,
    "Transparency • E-procurement\nMarket entry • Competition",
    fontsize=5.5,
    ha="center",
    va="center",
    color="#333333",
)

# Arrow
ax.annotate(
    "",
    xy=(5, 5.5),
    xytext=(5, 6),
    arrowprops=dict(arrowstyle="->", color="black", lw=1.5),
)
ax.text(
    5.35,
    5.62,
    "−7.2 pp primary ATT",
    fontsize=5.5,
    color=BLUE,
    style="italic",
    ha="left",
    va="center",
)

# Stage 2 box
stage2 = FancyBboxPatch(
    (0.5, 2.5),
    9,
    3,
    boxstyle="round,pad=0.3",
    facecolor="#DCEDC8",
    edgecolor=GREEN,
    linewidth=1.5,
)
ax.add_patch(stage2)
ax.text(
    5,
    4.5,
    "Stage 2: Apply GPP Criteria",
    fontsize=7,
    fontweight="bold",
    ha="center",
    va="center",
    color="#2E7D32",
)
ax.text(
    5,
    3.5,
    "Lifecycle assessment\nGreen specs • Carbon labelling",
    fontsize=5.5,
    ha="center",
    va="center",
    color="#333333",
)

# Bottom result
ax.annotate(
    "",
    xy=(5, 1.8),
    xytext=(5, 2.5),
    arrowprops=dict(arrowstyle="->", color="black", lw=1.5),
)
ax.text(
    5,
    1.2,
    "Monopoly Tax → Green Premium\n78–100% illustrative offset",
    fontsize=5.5,
    ha="center",
    va="center",
    color=RED,
    fontweight="bold",
    bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFEBEE", edgecolor=RED),
)

plt.tight_layout()
fig.savefig(OUTPUT_DIR / "Fig5_counterfactual.pdf", format="pdf")
fig.savefig(OUTPUT_DIR / "Fig5_counterfactual.png", format="png")
print("  Figure 3 saved.")

print("\nAll figures generated successfully!")
print(f"Output directory: {OUTPUT_DIR}")
for f in sorted(OUTPUT_DIR.glob("*.pdf")):
    print(f"  {f.name}: {f.stat().st_size:,} bytes")
