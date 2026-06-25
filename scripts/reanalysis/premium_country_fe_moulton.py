"""
Country-FE carbon premium with cell-level (Moulton) inference (desk review M1).

Two claims in M1:
  (i)  The pooled EU -4.3% premium is never estimated with country fixed effects;
       cross-country composition can generate/flip it.
  (ii) Contract-level t-statistics (t=-110) are invalid: carbon intensity is
       constant within ~1,000 country-sector cells, so the effective number of
       independent observations is ~the number of cells, not 13.6M (Moulton).

Verified separately: within-cell SD of carbon is exactly 0 across all 1,183
country x CPV cells, so we collapse to (country, cpv, year, single_bidder) cells
with contract counts as weights. WLS on these cells reproduces the contract-level
OLS point estimate exactly, and lets us compute both:
  - the naive contract-level iid SE (reproducing t=-110), and
  - a cluster-robust SE at the country x CPV (Moulton) level,
across a ladder of fixed-effects specifications.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "audit" / "premium_country_fe_moulton.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def wls_cluster(y, w, X, cluster_ids, n_contracts):
    """WLS beta with naive-iid (contract-level) and cluster-robust SEs.

    y: (G,) cell outcome; w: (G,) cell weights (contract counts);
    X: (G,k) design; cluster_ids: (G,) cluster label per cell;
    n_contracts: total contract count (sum w) for iid dof.
    Returns dict of beta, se_naive, se_cluster for column 0 (SB coef assumed col 1).
    """
    W = w
    XtWX = (X * W[:, None]).T @ X
    XtWX_inv = np.linalg.pinv(XtWX)
    beta = XtWX_inv @ ((X * W[:, None]).T @ y)
    resid = y - X @ beta

    k = X.shape[1]
    N = n_contracts
    # naive contract-level iid SE: SSR = sum w*e^2 (e constant within cell)
    ssr = float(np.sum(W * resid**2))
    sigma2 = ssr / (N - k)
    V_naive = sigma2 * XtWX_inv

    # cluster-robust (CR1) at cluster level
    scores = (X * (W * resid)[:, None])  # (G,k) cell score contributions
    df_s = pd.DataFrame(scores)
    df_s["c"] = cluster_ids
    cluster_scores = df_s.groupby("c").sum().values  # (G_clusters,k)
    meat = cluster_scores.T @ cluster_scores
    G = cluster_scores.shape[0]
    adj = (G / (G - 1)) * ((N - 1) / (N - k)) if G > 1 else 1.0
    V_cl = adj * (XtWX_inv @ meat @ XtWX_inv)

    return {
        "beta_sb": float(beta[1]),
        "se_naive": float(np.sqrt(max(V_naive[1, 1], 0))),
        "se_cluster": float(np.sqrt(max(V_cl[1, 1], 0))),
        "n_clusters": int(G),
    }


def build_design(cells, fe_cols):
    """Intercept + single_bidder + dummy FE for fe_cols (drop-first)."""
    G = len(cells)
    parts = [np.ones((G, 1)), cells["single_bidder"].values.astype(float)[:, None]]
    for col in fe_cols:
        d = pd.get_dummies(cells[col].astype(str), drop_first=True, dtype=float)
        parts.append(d.values)
    return np.hstack(parts)


def main():
    df = pq.read_table(PARQUET, columns=[
        "country", "cpv_division", "year", "single_bidder",
        "carbon_intensity_kg_usd"]).to_pandas()
    df = df[df["country"] != "CO"].dropna(subset=["carbon_intensity_kg_usd"])
    df["year"] = df["year"].astype(int)

    # Collapse to cells (carbon constant within country x cpv => exact)
    cells = (df.groupby(["country", "cpv_division", "year", "single_bidder"])
               .agg(carbon=("carbon_intensity_kg_usd", "mean"),
                    n=("carbon_intensity_kg_usd", "size"))
               .reset_index())
    N = int(cells["n"].sum())
    mb_mean = float(np.average(
        df.loc[~df["single_bidder"], "carbon_intensity_kg_usd"]))
    print(f"Contracts: {N:,}   cells: {len(cells):,}   MB mean carbon: {mb_mean:.4f}")

    cells["cluster_ccpv"] = cells["country"].astype(str) + "|" + cells["cpv_division"].astype(str)
    y = cells["carbon"].values
    w = cells["n"].values.astype(float)
    clu = cells["cluster_ccpv"].values

    specs = {
        "M0_pooled_no_FE": [],
        "M1_country_FE": ["country"],
        "M2_country_year_FE": ["country", "year"],
        "M3_country_cpv_FE_within_sector": ["country", "cpv_division"],
    }
    results = {"n_contracts": N, "n_cells": len(cells),
               "mb_mean_carbon": mb_mean, "models": {}}

    for name, fe in specs.items():
        X = build_design(cells, fe)
        r = wls_cluster(y, w, X, clu, N)
        premium_pct = 100 * r["beta_sb"] / mb_mean
        t_naive = r["beta_sb"] / r["se_naive"] if r["se_naive"] > 0 else np.nan
        t_cl = r["beta_sb"] / r["se_cluster"] if r["se_cluster"] > 0 else np.nan
        results["models"][name] = {
            "fe": fe,
            "beta_sb": r["beta_sb"],
            "premium_pct": premium_pct,
            "se_naive_contract": r["se_naive"],
            "t_naive_contract": float(t_naive),
            "se_cluster_country_cpv": r["se_cluster"],
            "t_cluster": float(t_cl),
            "n_clusters": r["n_clusters"],
        }
        print(f"\n{name}: premium = {premium_pct:+.2f}%  (beta={r['beta_sb']:+.5f})")
        print(f"   naive contract-level t = {t_naive:+.1f}")
        print(f"   country x CPV clustered t = {t_cl:+.2f}  ({r['n_clusters']} clusters)")

    # ---- Within-country premium spread (M1 first paragraph) ----
    per_country = []
    for c, g in df.groupby("country"):
        sb = g.loc[g["single_bidder"], "carbon_intensity_kg_usd"].mean()
        mb = g.loc[~g["single_bidder"], "carbon_intensity_kg_usd"].mean()
        if pd.notna(sb) and pd.notna(mb) and mb > 0:
            per_country.append((c, 100 * (sb - mb) / mb, len(g)))
    pc = pd.DataFrame(per_country, columns=["country", "premium_pct", "n"])
    results["within_country_premium_spread"] = {
        "min": float(pc["premium_pct"].min()),
        "max": float(pc["premium_pct"].max()),
        "n_negative": int((pc["premium_pct"] < 0).sum()),
        "n_positive": int((pc["premium_pct"] > 0).sum()),
        "n_meta_weighted_mean": float(np.average(pc["premium_pct"], weights=pc["n"])),
    }
    print("\nWithin-country premium spread: "
          f"[{pc['premium_pct'].min():+.1f}%, {pc['premium_pct'].max():+.1f}%]; "
          f"{int((pc['premium_pct']<0).sum())} neg / {int((pc['premium_pct']>0).sum())} pos")

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
