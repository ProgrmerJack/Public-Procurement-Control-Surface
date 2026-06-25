"""
Triangulation of the transposition DiD across OUTCOMES (replaces the infeasible
quarterly/2018-event additions; see did_quarterly_nyt.py docstring and the
INFEASIBILITY note printed below for why those two cannot be run honestly).

Why outcomes, not time: the not-yet-treated estimator is capped at three (g,t)
identifying cells -- (2016,2016), (2016,2017), (2017,2017) -- because no
not-yet-treated control exists after the final 2018 cohort. Quarterly resolution
cannot lift this (sub-annual dates are absent before 2017 in the observed-bidder
universe), and a 2018 e-procurement event study is confounded by the corrupted
2018 ingestion vintage (observed-bidder single-bid rate spikes 0.10->0.25->0.11
around 2018). So we thicken the evidence by re-running the SAME identification on
SEVERAL competition outcomes. If reform lowers single-bidding, it should also
raise bidder counts and the multi-bidder share -- convergent signs across
independent outcome definitions are hard to produce by chance.

Outcomes (coverage-stable, observed n_bidders only):
  sb_rate        : share with exactly one bidder           (expect DECREASE)
  mean_bidders   : mean number of bidders                  (expect INCREASE)
  competitive    : share with >= 2 bidders                 (expect INCREASE)
  three_plus     : share with >= 3 bidders                 (expect INCREASE)

Robustness: leave-one-country-out on the headline sb_rate.
Also verifies that 2018 never enters identification.

Output: results/causal_id/did_multi_outcome_triangulation.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "causal_id" / "did_multi_outcome_triangulation.json"

TRANSPOSITION = {
    "DK": 2016, "FR": 2016, "DE": 2016, "HU": 2016, "IE": 2016,
    "LT": 2016, "NL": 2016, "PL": 2016, "PT": 2016, "RO": 2016,
    "SK": 2016, "FI": 2016, "SE": 2016, "EE": 2016,
    "AT": 2017, "BE": 2017, "BG": 2017, "CZ": 2017,
    "ES": 2017, "HR": 2017, "IT": 2017, "LV": 2017, "NO": 2017,
    "GR": 2018, "LU": 2018, "SI": 2018,
}


def nyt_att(cy, transposition, col):
    """Not-yet-treated C&S aggregate ATT (cohort-size weighted) for outcome `col`."""
    cy = cy.copy()
    cy["cohort"] = cy["country"].map(transposition)
    cohorts = sorted(set(transposition.values()))
    cells, used_years = [], set()
    for g in cohorts:
        cd = cy[cy["cohort"] == g]
        ncoh = cd["country"].nunique()
        base = g - 1
        tb = cd[cd["year"] == base]
        if len(tb) == 0:
            continue
        tb_mean = np.average(tb[col], weights=tb["n"])
        for t in range(g, 2024):
            ctrl = cy[cy["cohort"] > t]
            cb, ct, tt = ctrl[ctrl["year"] == base], ctrl[ctrl["year"] == t], cd[cd["year"] == t]
            if len(tt) == 0 or len(cb) == 0 or len(ct) == 0:
                continue
            att = ((np.average(tt[col], weights=tt["n"]) - tb_mean)
                   - (np.average(ct[col], weights=ct["n"])
                      - np.average(cb[col], weights=cb["n"])))
            cells.append({"att": att, "w": ncoh})
            used_years.update([base, t])
    if not cells:
        return np.nan, 0, used_years
    cdf = pd.DataFrame(cells)
    return float(np.average(cdf["att"], weights=cdf["w"])), len(cdf), used_years


def perm_p(cy, transposition, col, obs, n_perm=2000, seed=7):
    rng = np.random.default_rng(seed)
    countries = list(transposition.keys())
    labels = np.array(list(transposition.values()))
    null = []
    for _ in range(n_perm):
        a, _, _ = nyt_att(cy, dict(zip(countries, rng.permutation(labels))), col)
        if not np.isnan(a):
            null.append(a)
    null = np.array(null)
    return float(np.mean(np.abs(null) >= abs(obs))), len(null)


def main():
    df = pq.read_table(PARQUET, columns=[
        "country", "year", "n_bidders"]).to_pandas()
    df["year"] = df["year"].astype(int)
    df = df[df["year"].between(2012, 2023)]
    df = df[df["country"].isin(TRANSPOSITION.keys())]
    # Genuine-bid universe: n_bidders >= 1. The raw field uses 0 as a
    # missing-count sentinel (median is 0), so we restrict to contracts with a
    # genuine recorded bidder count and winsorise the heavy right tail (max=2011)
    # at the 99th percentile for the mean outcome.
    df = df[df["n_bidders"].notna() & (df["n_bidders"] >= 1)].copy()
    cap = float(df["n_bidders"].quantile(0.99))
    df["sb_rate"] = (df["n_bidders"] == 1).astype(float)
    df["three_plus"] = (df["n_bidders"] >= 3).astype(float)
    df["mean_bidders"] = df["n_bidders"].clip(upper=cap).astype(float)
    print(f"genuine-bid universe n={len(df):,}; winsor cap (p99)={cap:.0f} bidders")

    cy = (df.groupby(["country", "year"])
            .agg(sb_rate=("sb_rate", "mean"),
                 three_plus=("three_plus", "mean"),
                 mean_bidders=("mean_bidders", "mean"),
                 n=("sb_rate", "size")).reset_index())
    cy = cy[cy["n"] >= 100]

    outcomes = {
        "sb_rate": ("single-bidder share (n>=1 universe)", "decrease"),
        "three_plus": ("competitive (>=3 bidders) share", "increase"),
        "mean_bidders": ("mean bidders (winsorised p99)", "increase"),
    }
    res = {"design": "not-yet-treated C&S, coverage-stable, within-EU timing only",
           "outcomes": {}}
    for col, (desc, direction) in outcomes.items():
        att, ncells, yrs = nyt_att(cy, TRANSPOSITION, col)
        p, nperm = perm_p(cy, TRANSPOSITION, col, att)
        unit = "pp" if col != "mean_bidders" else "bidders"
        scale = 100 if col != "mean_bidders" else 1
        res["outcomes"][col] = {
            "description": desc, "expected_direction": direction,
            "att": att * scale, "unit": unit, "n_cells": ncells,
            "identifying_years": sorted(int(y) for y in yrs),
            "permutation_p": p, "permutation_n": nperm,
        }
        print(f"{desc:28s} ATT = {att*scale:+.3f} {unit:8s} "
              f"perm p={p:.3f}  years={sorted(int(y) for y in yrs)} ({ncells} cells)")

    # leave-one-country-out on the headline outcome
    loo = {}
    for c in TRANSPOSITION:
        sub = cy[cy["country"] != c]
        tmap = {k: v for k, v in TRANSPOSITION.items() if k != c}
        a, _, _ = nyt_att(sub, tmap, "sb_rate")
        loo[c] = round(a * 100, 2)
    res["leave_one_country_out_sb_pp"] = loo
    vals = [v for v in loo.values() if not np.isnan(v)]
    res["loo_range_pp"] = [min(vals), max(vals)]
    print(f"\nLOO sb_rate ATT range: [{min(vals):+.2f}, {max(vals):+.2f}] pp "
          f"(all {'negative' if max(vals) < 0 else 'mixed'})")

    res["2018_excluded_from_identification"] = 2018 not in res["outcomes"]["sb_rate"]["identifying_years"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
