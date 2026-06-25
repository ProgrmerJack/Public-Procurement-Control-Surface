"""
A-3: Corrected CPV->EXIOBASE crosswalk + Dead Zone screen robustness.

Two crosswalk mappings flagged by industrial-ecology logic are corrected:
  CPV 09 (Petroleum and fuel products): was 'Mining' (extraction).
     -> 'Coke and refined petroleum products'. Refining is a MANUFACTURED-product
        industry and is among the most GHG-intensive EXIOBASE industries per unit
        output -- at least as intensive as extraction. We place it at the top of
        the existing classification-weight scale (1.20 kg CO2e/USD, = current max),
        a conservative choice that keeps CPV 09 firmly high-carbon.
  CPV 90 (Sewage, refuse, refuse-treatment): was 'Water supply' (0.25, low).
     -> 'Waste management / sewerage'. Waste services (incineration, landfill
        methane, sewage treatment) are a distinct, materially higher-intensity
        EXIOBASE activity than water distribution. We assign 0.55 kg CO2e/USD
        (between Construction 0.50 and Utilities 0.60), clearly above the 0.25
        low-carbon water-supply value.

These are the only two intensity changes. We then recompute the EU-context Dead
Zone screen (carbon >= 67th percentile across sectors AND single-bidder rate >=
median) under the ORIGINAL vs CORRECTED weights and report any membership change.
Goal: demonstrate the screen's robustness (or report honestly if it shifts).

Output: results/dead_zones/crosswalk_correction_robustness.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

_d = Path(__file__).resolve().parent
while not (_d / "pyproject.toml").exists() and _d != _d.parent:
    _d = _d.parent
ROOT = _d
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "dead_zones" / "crosswalk_correction_robustness.json"

CORRECTIONS = {            # cpv_division -> (new EXIOBASE industry, new intensity)
    "09": ("Coke and refined petroleum products", 1.20),
    "90": ("Waste management and sewerage", 0.55),
}


def dead_zone_set(sdf, ci_col):
    ci_thr = sdf[ci_col].quantile(0.67)
    sb_thr = sdf["sb_rate"].median()
    dz = sdf[(sdf[ci_col] >= ci_thr) & (sdf["sb_rate"] >= sb_thr)]
    return set(dz["cpv"]), float(ci_thr), float(sb_thr), dz


def main():
    df = pq.read_table(PARQUET, columns=[
        "country", "cpv_division", "single_bidder", "carbon_intensity_kg_usd",
        "value_eur", "carbon_footprint_kg", "exiobase_sector"]).to_pandas()
    eu = df[df["country"] != "CO"].copy()

    rows = []
    for cpv, g in eu.groupby("cpv_division"):
        if str(cpv) == "na" or pd.isna(cpv):
            continue
        ci_orig = g["carbon_intensity_kg_usd"].mean()
        ci_corr = CORRECTIONS[str(cpv)][1] if str(cpv) in CORRECTIONS else ci_orig
        rows.append({
            "cpv": str(cpv),
            "exio_orig": g["exiobase_sector"].iloc[0],
            "exio_corr": CORRECTIONS[str(cpv)][0] if str(cpv) in CORRECTIONS
                         else g["exiobase_sector"].iloc[0],
            "n": len(g),
            "sb_rate": g["single_bidder"].mean(),
            "ci_orig": ci_orig,
            "ci_corr": ci_corr,
            "sb_val": g[g["single_bidder"] == True]["value_eur"].sum(),
            "carbon_kg": g["carbon_footprint_kg"].sum(),
        })
    sdf = pd.DataFrame(rows)

    dz_o, ci_o, sb_o, dzo = dead_zone_set(sdf, "ci_orig")
    dz_c, ci_c, sb_c, dzc = dead_zone_set(sdf, "ci_corr")

    added = sorted(dz_c - dz_o)
    removed = sorted(dz_o - dz_c)

    print(f"Sectors: {len(sdf)}")
    print(f"ORIGINAL : 67th-pct CI threshold = {ci_o:.3f}, SB-median = {sb_o*100:.2f}%, "
          f"Dead Zones = {len(dz_o)}")
    print(f"CORRECTED: 67th-pct CI threshold = {ci_c:.3f}, SB-median = {sb_c*100:.2f}%, "
          f"Dead Zones = {len(dz_c)}")
    print(f"Membership added by correction:   {added}")
    print(f"Membership removed by correction: {removed}")
    print(f"Jaccard stability = {len(dz_o & dz_c)/len(dz_o | dz_c):.3f}")
    for cpv in ("09", "90"):
        r = sdf[sdf.cpv == cpv].iloc[0]
        print(f"  CPV {cpv}: SB={r.sb_rate*100:.1f}%  CI {r.ci_orig:.2f}->{r.ci_corr:.2f}  "
              f"in_DZ_orig={cpv in dz_o} in_DZ_corr={cpv in dz_c}")

    res = {
        "corrections": {k: {"exiobase": v[0], "intensity_kg_usd": v[1]}
                        for k, v in CORRECTIONS.items()},
        "n_sectors": int(len(sdf)),
        "original": {"ci_67th": ci_o, "sb_median": sb_o,
                     "n_dead_zones": len(dz_o), "members": sorted(dz_o)},
        "corrected": {"ci_67th": ci_c, "sb_median": sb_c,
                      "n_dead_zones": len(dz_c), "members": sorted(dz_c)},
        "membership_added": added,
        "membership_removed": removed,
        "jaccard_stability": len(dz_o & dz_c) / len(dz_o | dz_c),
        "cpv09_in_dz": {"orig": "09" in dz_o, "corr": "09" in dz_c},
        "cpv90_in_dz": {"orig": "90" in dz_o, "corr": "90" in dz_c},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
