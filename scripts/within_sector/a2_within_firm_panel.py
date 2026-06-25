"""
A2: within-firm fixed-effects test. The surviving firm-level result ("single-bidder-
leaning suppliers are higher-emitting") is cross-firm and could reflect dirty firms
SORTING into thin markets. Here we hold the firm constant: within a given supplier's
own portfolio, are its single-bidder wins in higher-carbon sectors than its
competitively-won contracts? A positive within-firm coefficient means "even the same
firm wins dirtier when uncontested," which sorting alone cannot produce.

Model: carbon_intensity ~ single_bidder + firm FE (+ country-year FE), clustered by firm.
Estimated by alternating within-transformation (firm; country-year), cluster-robust SE.

Output: results/within_sector/a2_within_firm_panel.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "Data" / "processed" / "gprd_master.parquet"
CARBON = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "within_sector" / "a2_within_firm_panel.json"


def demean(df, col, by):
    return df[col] - df.groupby(by)[col].transform("mean")


def twoway_within(df, y, x, fe1, fe2, iters=6):
    """Alternating-projection within-transformation for two-way FE."""
    yy = df[y].astype(float).copy()
    xx = df[x].astype(float).copy()
    g1 = df[fe1].values
    g2 = df[fe2].values
    t = pd.DataFrame({"y": yy.values, "x": xx.values, "g1": g1, "g2": g2})
    for _ in range(iters):
        for g in ("g1", "g2"):
            t["y"] -= t.groupby(g)["y"].transform("mean")
            t["x"] -= t.groupby(g)["x"].transform("mean")
    return t["y"].values, t["x"].values


def main():
    # carbon intensity is sector-level; build a cpv_division -> carbon map from the carbon parquet
    cb = pq.read_table(CARBON, columns=["cpv_division", "carbon_intensity_kg_usd"]).to_pandas()
    cmap = cb.dropna().groupby("cpv_division")["carbon_intensity_kg_usd"].median()

    df = pq.read_table(MASTER, columns=[
        "country", "supplier_name", "single_bidder", "year", "cpv_division"]).to_pandas()
    df = df[(df["country"] != "CO")]
    sn = df["supplier_name"].astype(str)
    df = df[sn.notna() & (sn.str.lower() != "nan") & (sn.str.strip() != "")]
    df["carbon_intensity_kg_usd"] = df["cpv_division"].map(cmap)
    df = df.dropna(subset=["carbon_intensity_kg_usd", "single_bidder", "year"])
    df["single_bidder"] = df["single_bidder"].astype(float)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"])
    df["cy"] = df["country"] + "_" + df["year"].astype(int).astype(str)

    # firm FE is only identified for firms with within-firm variation in single_bidder
    fstat = df.groupby("supplier_name")["single_bidder"].agg(["mean", "size"])
    keep = fstat[(fstat["mean"] > 0) & (fstat["mean"] < 1) & (fstat["size"] >= 2)].index
    d = df[df["supplier_name"].isin(keep)].copy()
    res = {"n_contracts": int(len(d)), "n_firms": int(d["supplier_name"].nunique())}

    # (1) one-way firm FE
    yfd = demean(d, "carbon_intensity_kg_usd", "supplier_name").values
    xfd = demean(d, "single_bidder", "supplier_name").values
    beta1 = float(np.sum(xfd * yfd) / np.sum(xfd ** 2))
    # cluster-robust SE by firm
    resid = yfd - beta1 * xfd
    sxx = np.sum(xfd ** 2)
    fcodes = d["supplier_name"].values
    score = xfd * resid
    sc = pd.Series(score).groupby(fcodes).sum().values
    meat = np.sum(sc ** 2)
    se1 = float(np.sqrt(meat) / sxx)
    res["firm_FE"] = {"beta_carbon_per_single_bidder": beta1, "se": se1,
                      "t": beta1 / se1, "ci95": [beta1 - 1.96 * se1, beta1 + 1.96 * se1]}

    # (2) two-way: firm + country-year FE
    yy, xx = twoway_within(d, "carbon_intensity_kg_usd", "single_bidder", "supplier_name", "cy")
    beta2 = float(np.sum(xx * yy) / np.sum(xx ** 2))
    resid2 = yy - beta2 * xx
    sc2 = pd.Series(xx * resid2).groupby(fcodes).sum().values
    se2 = float(np.sqrt(np.sum(sc2 ** 2)) / np.sum(xx ** 2))
    res["firm_and_countryyear_FE"] = {"beta_carbon_per_single_bidder": beta2, "se": se2,
                                      "t": beta2 / se2, "ci95": [beta2 - 1.96 * se2, beta2 + 1.96 * se2]}

    # (3) descriptive: within firm, mean carbon of SB vs non-SB wins; share of firms where SB dirtier
    sb_mean = d[d["single_bidder"] == 1].groupby("supplier_name")["carbon_intensity_kg_usd"].mean()
    comp_mean = d[d["single_bidder"] == 0].groupby("supplier_name")["carbon_intensity_kg_usd"].mean()
    gp = pd.DataFrame({"sb": sb_mean, "comp": comp_mean}).dropna()
    res["within_firm_descriptive"] = {
        "n_firms_both": int(len(gp)),
        "mean_carbon_SB_wins": float(gp["sb"].mean()),
        "mean_carbon_competitive_wins": float(gp["comp"].mean()),
        "share_firms_SB_dirtier": float((gp["sb"] > gp["comp"]).mean()),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"firms={res['n_firms']:,}, contracts={res['n_contracts']:,}")
    f = res["firm_FE"]; print(f"Firm FE: carbon per single-bidder = {f['beta_carbon_per_single_bidder']:+.4f} "
                              f"kg/USD (SE {f['se']:.4f}, t={f['t']:.1f}), CI [{f['ci95'][0]:+.4f},{f['ci95'][1]:+.4f}]")
    g = res["firm_and_countryyear_FE"]; print(f"Firm + country-year FE: {g['beta_carbon_per_single_bidder']:+.4f} "
                                              f"(SE {g['se']:.4f}, t={g['t']:.1f})")
    dd = res["within_firm_descriptive"]; print(f"Within-firm: SB wins {dd['mean_carbon_SB_wins']:.3f} vs "
                                               f"competitive {dd['mean_carbon_competitive_wins']:.3f} kg/USD; "
                                               f"{dd['share_firms_SB_dirtier']:.1%} of firms dirtier when single-bidder")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
