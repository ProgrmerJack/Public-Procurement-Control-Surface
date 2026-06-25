"""
A1: Supplier market concentration (HHI) as a second contestability signal.

The paper proxies contestability only by the single-bidder rate. Here we compute a
transparent supplier Herfindahl-Hirschman Index (HHI) from supplier market shares
within each country x CPV-division cell, and ask:
  (i)  does concentration corroborate the single-bidder rate? (construct validity)
  (ii) are high-carbon sectors more concentrated? (does the Dead Zone pattern hold
       under a concentration measure, not just single-bidding?)

HHI per country x CPV cell = sum_s (value share of supplier s)^2, in [0,1].
Also CR4 (top-4 value share) and distinct-supplier count.

Output: results/within_sector/hhi_concentration.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "Data" / "processed" / "gprd_master.parquet"
XWALK = ROOT / "Data" / "reference" / "cpv_exiobase_crosswalk.csv"
OUT = ROOT / "results" / "within_sector" / "hhi_concentration.json"

INTENSITY = {  # EXIOBASE shorthand -> classification weight (paper's scale)
    "Agriculture": 0.85, "Coke and refined petroleum products": 1.20, "Mining": 1.20,
    "Food products": 0.65, "Textiles": 0.45, "Leather": 0.40, "Paper": 0.55,
    "Chemicals": 0.90, "Computer equipment": 0.30, "Electrical equipment": 0.40,
    "Telecommunications": 0.15, "Medical instruments": 0.30, "Motor vehicles": 0.45,
    "Weapons": 0.60, "Precision instruments": 0.28, "Furniture": 0.30,
    "Machinery": 0.35, "Mining machinery": 0.30, "Metal products": 0.75,
    "Construction": 0.50, "Computer services": 0.10, "Repair services": 0.20,
    "Hotels": 0.35, "Land transport": 0.85, "Transport support": 0.45, "Post": 0.20,
    "Utilities": 0.60, "Financial services": 0.08, "Real estate": 0.12,
    "Architectural services": 0.12, "R&D": 0.12, "Public administration": 0.20,
    "Other business services": 0.15, "Education": 0.15, "Health services": 0.25,
    "Waste management and sewerage": 0.55, "Recreation": 0.20, "Other services": 0.20,
}


def main():
    df = pq.read_table(MASTER, columns=[
        "country", "cpv_division", "single_bidder", "value_eur", "supplier_name", "year"]).to_pandas()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df[(df["country"] != "CO") & df["year"].between(2012, 2023)]
    sn = df["supplier_name"].astype(str)
    df = df[sn.notna() & (sn.str.lower() != "nan") & (sn.str.strip() != "")]
    df = df[df["value_eur"].notna() & (df["value_eur"] > 0)]
    df["cell"] = df["country"] + "_" + df["cpv_division"].astype(str)

    # HHI per country x CPV cell from supplier value shares
    cells = []
    for (cell, cc, cpv), g in df.groupby(["cell", "country", "cpv_division"]):
        if len(g) < 50:
            continue
        sup_val = g.groupby("supplier_name")["value_eur"].sum()
        tot = sup_val.sum()
        if tot <= 0:
            continue
        shares = (sup_val / tot).values
        hhi = float(np.sum(shares ** 2))
        cr4 = float(np.sort(shares)[::-1][:4].sum())
        cells.append({"country": cc, "cpv": str(cpv), "n": len(g),
                      "n_suppliers": int(sup_val.size), "hhi": hhi, "cr4": cr4,
                      "sb_rate": float(g["single_bidder"].mean()),
                      "value": float(tot)})
    cd = pd.DataFrame(cells)
    cd["carbon"] = cd["cpv"].map(
        pd.read_csv(XWALK, dtype={"cpv_division": str})
        .assign(intensity=lambda d: d["exiobase_sector"].map(INTENSITY))
        .set_index("cpv_division")["intensity"])
    cd = cd.dropna(subset=["carbon"])

    # (i) construct validity: HHI vs single-bidder rate across cells
    r_sb, p_sb = stats.spearmanr(cd["hhi"], cd["sb_rate"])
    # (ii) carbon vs concentration across cells (value-weighted sector means)
    sec = (cd.groupby("cpv")
             .apply(lambda g: pd.Series({
                 "hhi_w": np.average(g["hhi"], weights=g["value"]),
                 "sb_w": np.average(g["sb_rate"], weights=g["value"]),
                 "carbon": g["carbon"].iloc[0],
                 "n_cells": len(g), "value": g["value"].sum()}))
             .reset_index())
    r_carb, p_carb = stats.spearmanr(sec["carbon"], sec["hhi_w"])

    # Dead Zone under concentration: high carbon (>=0.25) AND high HHI (>= median)
    hhi_med = sec["hhi_w"].median()
    dz_conc = sec[(sec["carbon"] >= 0.25) & (sec["hhi_w"] >= hhi_med)]
    # overlap with single-bidder Dead Zone (carbon>=0.25 & sb>=median)
    sb_med = sec["sb_w"].median()
    dz_sb = sec[(sec["carbon"] >= 0.25) & (sec["sb_w"] >= sb_med)]
    overlap = set(dz_conc["cpv"]) & set(dz_sb["cpv"])

    res = {
        "n_cells": int(len(cd)),
        "n_sectors": int(len(sec)),
        "hhi_mean": float(cd["hhi"].mean()), "hhi_median": float(cd["hhi"].median()),
        "construct_validity_hhi_vs_sb": {"spearman_rho": float(r_sb), "p": float(p_sb)},
        "carbon_vs_concentration": {"spearman_rho": float(r_carb), "p": float(p_carb)},
        "dead_zone_concentration_sectors": sorted(dz_conc["cpv"]),
        "dead_zone_singlebidder_sectors": sorted(dz_sb["cpv"]),
        "dead_zone_overlap": sorted(overlap),
        "jaccard_dz_overlap": len(overlap) / len(set(dz_conc["cpv"]) | set(dz_sb["cpv"])),
        "top_concentrated_highcarbon": sec[sec.carbon >= 0.25].sort_values("hhi_w", ascending=False)
            [["cpv", "carbon", "hhi_w", "sb_w"]].head(10).round(3).to_dict("records"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"cells={len(cd)}, sectors={len(sec)}")
    print(f"HHI mean={cd['hhi'].mean():.3f} median={cd['hhi'].median():.3f}")
    print(f"(i)  HHI vs single-bidder rate: Spearman rho={r_sb:+.3f} (p={p_sb:.2e})  [construct validity]")
    print(f"(ii) carbon vs concentration:   Spearman rho={r_carb:+.3f} (p={p_carb:.3f})")
    print(f"Dead Zone (concentration): {len(dz_conc)} sectors; (single-bidder): {len(dz_sb)}; "
          f"overlap {len(overlap)} (Jaccard {res['jaccard_dz_overlap']:.2f})")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
