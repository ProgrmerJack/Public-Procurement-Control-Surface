"""
Path A (feasible winner-side test of the thesis): does competition select greener winners?

The literal full-bid-set design is blocked by a jurisdiction mismatch: ProZorro discloses
all tenderers but its firms (Ukraine) are absent from EU emission registries (EUTL/E-PRTR);
EU eForms firms are emission-matchable but only winners are published. So we test the same
mechanism on the WINNER side, which existing EU data support: as the number of bidders on a
contract rises, is the WINNING firm lower-emitting, within sector and firm-size class?

Contract-level: winner is an EUTL-matched emitter; outcome = winner log verified emissions
(and size-normalised emissions-per-installation); regressor = bidder count (and the
single- vs multi-bidder contrast); NACE sector FE; firm-size control; clustered by firm.

A negative coefficient = competition selects greener winners (confirms the thesis dynamically).
A null = competition does not select greener winners (GPP cannot ride on contestability alone).
Pre-registered direction: negative (more bidders -> lower-emitting winner).

Output: results/within_sector/pathA_winner_emissions_vs_competition.json
"""
import importlib.util, json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "Data" / "processed" / "gprd_master.parquet"
OUT = ROOT / "results" / "within_sector" / "pathA_winner_emissions_vs_competition.json"

spec = importlib.util.spec_from_file_location(
    "eutlmod", ROOT / "scripts" / "within_sector" / "eutl_supplier_firm_match.py")
eutlmod = importlib.util.module_from_spec(spec); spec.loader.exec_module(eutlmod)


def within_ols(d, y, x, fe, cluster, controls=()):
    """OLS of y on x (+controls) absorbing FE `fe`, cluster-robust SE by `cluster`."""
    t = d[[y, x, fe, cluster, *controls]].dropna().copy()
    for c in [y, x, *controls]:
        t[c] = t[c].astype(float) - t.groupby(fe)[c].transform("mean")
    X = np.column_stack([t[x].values] + [t[c].values for c in controls])
    Y = t[y].values
    XtX = X.T @ X
    beta = np.linalg.solve(XtX, X.T @ Y)
    resid = Y - X @ beta
    XtX_inv = np.linalg.inv(XtX)
    # cluster-robust meat
    g = t[cluster].values
    meat = np.zeros((X.shape[1], X.shape[1]))
    df_c = pd.DataFrame(X * resid[:, None])
    for _, idx in df_c.groupby(g).groups.items():
        s = df_c.loc[idx].sum().values
        meat += np.outer(s, s)
    V = XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(V))
    return float(beta[0]), float(se[0]), int(len(t)), int(t[cluster].nunique())


def main():
    firms = eutlmod.load_eutl()[["nkey", "emis_t", "n_install", "nace"]]
    df = pq.read_table(MASTER, columns=[
        "country", "supplier_name", "n_bidders", "single_bidder", "cpv_division"]).to_pandas()
    df = df[df["country"] != "CO"].copy()
    sn = df["supplier_name"].astype(str)
    df = df[sn.notna() & (sn.str.lower() != "nan") & (sn.str.strip() != "")]
    df["nkey"] = df["supplier_name"].map(eutlmod.norm)
    df["n_bidders"] = pd.to_numeric(df["n_bidders"], errors="coerce")
    d = df.merge(firms, on="nkey", how="inner")
    d = d[d["n_bidders"].between(1, 50)].copy()          # plausible bidder counts
    d["log_emis"] = np.log(d["emis_t"].clip(lower=1))
    d["epi"] = np.log((d["emis_t"] / d["n_install"].clip(lower=1)).clip(lower=1))
    d["log_nbid"] = np.log(d["n_bidders"])
    d["logN"] = np.log(d["n_install"].clip(lower=1))
    d["nace"] = d["nace"].astype(str)
    d = d[d.groupby("nace")["nace"].transform("size") >= 50]

    res = {"n_contracts": int(len(d)), "n_winner_firms": int(d["nkey"].nunique()),
           "n_sectors": int(d["nace"].nunique()),
           "pre_registered_direction": "negative (more bidders -> lower-emitting winner)"}

    # (1) winner log-emissions on bidder count, NACE FE + size control, cluster by firm
    b, se, n, nc = within_ols(d, "log_emis", "log_nbid", "nace", "nkey", controls=["logN"])
    res["winner_logemis_on_log_bidders"] = {
        "beta": b, "se": se, "t": b / se, "p": float(2 * stats.norm.sf(abs(b / se))),
        "n": n, "n_clusters": nc, "controls": "NACE FE + log(n_installations)"}

    # (2) size-normalised emissions-per-installation
    b2, se2, n2, nc2 = within_ols(d, "epi", "log_nbid", "nace", "nkey", controls=["logN"])
    res["winner_emis_per_install_on_log_bidders"] = {
        "beta": b2, "se": se2, "t": b2 / se2, "p": float(2 * stats.norm.sf(abs(b2 / se2))), "n": n2}

    # (3) single- vs multi-bidder contrast on winner emissions (descriptive)
    d["single_bidder"] = d["single_bidder"].astype(float)
    b3, se3, n3, nc3 = within_ols(d, "log_emis", "single_bidder", "nace", "nkey", controls=["logN"])
    res["winner_logemis_single_vs_multi"] = {
        "beta": b3, "se": se3, "t": b3 / se3, "p": float(2 * stats.norm.sf(abs(b3 / se3))), "n": n3,
        "note": "positive = single-bidder winners are higher-emitting than multi-bidder winners (within sector+size)"}

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    r = res["winner_logemis_on_log_bidders"]
    print(f"contracts={res['n_contracts']:,}, winner firms={res['n_winner_firms']:,}, sectors={res['n_sectors']}")
    print(f"(1) winner log-emissions ~ log(bidders) | NACE FE + size: beta={r['beta']:+.4f} "
          f"(SE {r['se']:.4f}, p={r['p']:.4f})  [neg = competition selects greener winners]")
    r2 = res["winner_emis_per_install_on_log_bidders"]
    print(f"(2) emissions-per-installation ~ log(bidders): beta={r2['beta']:+.4f} (p={r2['p']:.4f})")
    r3 = res["winner_logemis_single_vs_multi"]
    print(f"(3) single-vs-multi winner emissions: beta={r3['beta']:+.4f} (p={r3['p']:.4f})")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
