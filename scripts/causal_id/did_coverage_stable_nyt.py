"""
Coverage-stable, not-yet-treated DiD with Norway reclassified (desk review M3).

Addresses three M3 defects at once:
  (a) Norway is NOT never-treated (Anskaffelsesloven in force Jan 2017, EEA) ->
      reclassified as a 2017 treated cohort; the primary design uses NO external
      never-treated controls at all (not-yet-treated within-EU identification).
  (b) The outcome (single-bidder rate) is measured on a reporting universe that
      changes with treatment (2018 surge; inferred-SB millions; GB from a
      different source). We therefore re-estimate on a COVERAGE-STABLE universe:
      only contracts with OBSERVED bidder counts (single_bidder := n_bidders==1),
      GB excluded, and compare to the published full-universe panel.
  (d) Finite-sample inference via a cohort-timing permutation (randomization)
      test reported as primary, not the asymptotic p-value.

Output: results/causal_id/did_coverage_stable_nyt.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "causal_id" / "did_coverage_stable_nyt.json"

# Transposition cohorts; Norway reclassified to 2017 (was a never-treated control).
TRANSPOSITION = {
    "DK": 2016, "FR": 2016, "DE": 2016, "HU": 2016, "IE": 2016,
    "LT": 2016, "NL": 2016, "PL": 2016, "PT": 2016, "RO": 2016,
    "SK": 2016, "FI": 2016, "SE": 2016, "EE": 2016,
    "AT": 2017, "BE": 2017, "BG": 2017, "CZ": 2017,
    "ES": 2017, "HR": 2017, "IT": 2017, "LV": 2017,
    "NO": 2017,  # <-- reclassified (Anskaffelsesloven, Jan 2017, EEA)
    "GR": 2018, "LU": 2018, "SI": 2018,
}
# GB (2015, Contracts Finder — different source) and CH (non-EU, contaminated 2021)
# are excluded from the coverage-stable not-yet-treated panel.


def nyt_aggregate_att(cy, transposition):
    """Not-yet-treated C&S aggregate ATT (cohort-size weighted), in pp."""
    cy = cy.copy()
    cy["cohort"] = cy["country"].map(transposition)
    cohorts = sorted(set(transposition.values()))
    cells = []
    for g in cohorts:
        cd = cy[cy["cohort"] == g]
        ccountries = sorted(cd["country"].unique())
        base = g - 1
        tb = cd[cd["year"] == base]
        if len(tb) == 0:
            continue
        tb_mean = np.average(tb["sb_rate"], weights=tb["n"])
        for t in range(g, 2024):
            ctrl = cy[cy["cohort"] > t]
            cb = ctrl[ctrl["year"] == base]
            ct = ctrl[ctrl["year"] == t]
            tt = cd[cd["year"] == t]
            if len(tt) == 0 or len(cb) == 0 or len(ct) == 0:
                continue
            att = ((np.average(tt["sb_rate"], weights=tt["n"]) - tb_mean)
                   - (np.average(ct["sb_rate"], weights=ct["n"])
                      - np.average(cb["sb_rate"], weights=cb["n"])))
            cells.append({"cohort": g, "att": att * 100,
                          "w": len(ccountries)})
    if not cells:
        return np.nan, 0
    cdf = pd.DataFrame(cells)
    return float(np.average(cdf["att"], weights=cdf["w"])), len(cdf)


def permutation_p(cy, transposition, observed_att, n_perm=2000, seed=7):
    """Randomization test: shuffle cohort labels across countries."""
    rng = np.random.default_rng(seed)
    countries = list(transposition.keys())
    labels = np.array(list(transposition.values()))
    null = []
    for _ in range(n_perm):
        perm = rng.permutation(labels)
        tmap = dict(zip(countries, perm))
        a, _ = nyt_aggregate_att(cy, tmap)
        if not np.isnan(a):
            null.append(a)
    null = np.array(null)
    p = float(np.mean(np.abs(null) >= abs(observed_att)))
    return p, len(null), float(np.mean(null)), float(np.std(null))


def build_panel(df, observed_only):
    d = df.copy()
    if observed_only:
        d = d[d["n_bidders"].notna()].copy()
        d["single_bidder"] = (d["n_bidders"] == 1)
    cy = (d.groupby(["country", "year"])
            .agg(sb_rate=("single_bidder", "mean"),
                 n=("single_bidder", "size")).reset_index())
    return cy[cy["n"] >= 100]  # drop ultra-thin cells


def main():
    df = pq.read_table(PARQUET, columns=[
        "country", "year", "single_bidder", "n_bidders"]).to_pandas()
    df["year"] = df["year"].astype(int)
    df = df[df["year"].between(2012, 2023)]
    df = df[df["country"].isin(TRANSPOSITION.keys())]  # EU + NO, drops GB/CH/CO

    results = {"cohort_map": TRANSPOSITION, "panels": {}}
    for label, obs_only in [("full_universe", False),
                            ("coverage_stable_observed_bidders", True)]:
        cy = build_panel(df, obs_only)
        att, ncells = nyt_aggregate_att(cy, TRANSPOSITION)
        p, nperm, null_mean, null_sd = permutation_p(cy, TRANSPOSITION, att)
        results["panels"][label] = {
            "observed_bidders_only": obs_only,
            "gb_excluded": True,
            "norway_as_2017_treated": True,
            "external_never_treated_controls": 0,
            "aggregate_att_pp": att,
            "n_group_time_cells": ncells,
            "permutation_p": p,
            "permutation_n": nperm,
            "permutation_null_mean": null_mean,
            "permutation_null_sd": null_sd,
            "n_countries": int(cy["country"].nunique()),
        }
        print(f"\n=== {label} ===")
        print(f"  not-yet-treated aggregate ATT = {att:+.2f} pp "
              f"({ncells} cells, {cy['country'].nunique()} countries)")
        print(f"  permutation p (cohort-timing randomization) = {p:.3f} "
              f"[null mean {null_mean:+.2f}, sd {null_sd:.2f}, {nperm} perms]")

    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
