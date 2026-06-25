"""
A-2: Quarterly re-aggregation of the not-yet-treated Callaway & Sant'Anna DiD.

The published design aggregates the single-bidding outcome to country-YEAR, which
yields only three group-time cohorts at event times 0 and 1 -- the "three cells"
limitation that recurs throughout the paper. TED award notices are dated to the day
(tender_date), so we re-aggregate the SAME outcome to country-QUARTER. This:
  * roughly quadruples the time resolution (1 -> 4 periods per year),
  * multiplies the number of estimable group-time (g,t) cells,
  * tightens the cohort-timing permutation distribution and the event study.

Identical identification to did_coverage_stable_nyt.py (not-yet-treated, within-EU
timing only, Norway = 2017 cohort, GB/CH/CO excluded, coverage-stable universe of
observed bidder counts). Treatment onset is placed at Q1 of each cohort year (the
transposition year); we only observe cohort YEARS, so within-year onset timing is an
explicit, stated assumption -- the gain is in OUTCOME resolution and the number of
post-treatment periods, not in finer onset dating.

Output: results/causal_id/did_quarterly_nyt.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "causal_id" / "did_quarterly_nyt.json"

TRANSPOSITION = {
    "DK": 2016, "FR": 2016, "DE": 2016, "HU": 2016, "IE": 2016,
    "LT": 2016, "NL": 2016, "PL": 2016, "PT": 2016, "RO": 2016,
    "SK": 2016, "FI": 2016, "SE": 2016, "EE": 2016,
    "AT": 2017, "BE": 2017, "BG": 2017, "CZ": 2017,
    "ES": 2017, "HR": 2017, "IT": 2017, "LV": 2017, "NO": 2017,
    "GR": 2018, "LU": 2018, "SI": 2018,
}
Q_START, Q_END = 2012 * 4, 2023 * 4 + 3   # quarter index range (inclusive)


def qidx(year, quarter):
    return year * 4 + (quarter - 1)


def nyt_aggregate_att(cq, cohort_q):
    """Not-yet-treated C&S aggregate ATT (cohort-size weighted), in pp.

    cq: country x quarter panel with columns country, q (quarter index), sb_rate, n.
    cohort_q: dict country -> treatment-onset quarter index.
    """
    cq = cq.copy()
    cq["cohort_q"] = cq["country"].map(cohort_q)
    cohorts = sorted(set(cohort_q.values()))
    cells = []
    for g in cohorts:
        cd = cq[cq["cohort_q"] == g]
        ccountries = sorted(cd["country"].unique())
        base = g - 1                                   # last pre-treatment quarter
        tb = cd[cd["q"] == base]
        if len(tb) == 0:
            continue
        tb_mean = np.average(tb["sb_rate"], weights=tb["n"])
        for t in range(g, Q_END + 1):                  # every post quarter
            ctrl = cq[cq["cohort_q"] > t]              # not-yet-treated at t
            cb = ctrl[ctrl["q"] == base]
            ct = ctrl[ctrl["q"] == t]
            tt = cd[cd["q"] == t]
            if len(tt) == 0 or len(cb) == 0 or len(ct) == 0:
                continue
            att = ((np.average(tt["sb_rate"], weights=tt["n"]) - tb_mean)
                   - (np.average(ct["sb_rate"], weights=ct["n"])
                      - np.average(cb["sb_rate"], weights=cb["n"])))
            cells.append({"cohort": g, "att": att * 100, "event_q": t - g,
                          "w": len(ccountries)})
    if not cells:
        return np.nan, 0, []
    cdf = pd.DataFrame(cells)
    agg = float(np.average(cdf["att"], weights=cdf["w"]))
    # event-study: average ATT by event-quarter (cohort-weighted)
    es = (cdf.groupby("event_q")
             .apply(lambda d: np.average(d["att"], weights=d["w"]))
             .to_dict())
    return agg, len(cdf), {int(k): float(v) for k, v in es.items()}


def permutation_p(cq, cohort_q, observed_att, n_perm=2000, seed=7):
    rng = np.random.default_rng(seed)
    countries = list(cohort_q.keys())
    labels = np.array(list(cohort_q.values()))
    null = []
    for _ in range(n_perm):
        perm = rng.permutation(labels)
        a, _, _ = nyt_aggregate_att(cq, dict(zip(countries, perm)))
        if not np.isnan(a):
            null.append(a)
    null = np.array(null)
    p = float(np.mean(np.abs(null) >= abs(observed_att)))
    return p, len(null), float(np.mean(null)), float(np.std(null))


def boot_ci(cq, cohort_q, n_boot=500, seed=11):
    """Block bootstrap over countries (resample whole country series)."""
    rng = np.random.default_rng(seed)
    countries = list(cohort_q.keys())
    ests = []
    for _ in range(n_boot):
        pick = rng.choice(countries, size=len(countries), replace=True)
        frames, cmap = [], {}
        for i, c in enumerate(pick):
            sub = cq[cq["country"] == c].copy()
            alias = f"{c}_{i}"
            sub["country"] = alias
            cmap[alias] = cohort_q[c]
            frames.append(sub)
        a, _, _ = nyt_aggregate_att(pd.concat(frames), cmap)
        if not np.isnan(a):
            ests.append(a)
    ests = np.array(ests)
    return float(np.percentile(ests, 2.5)), float(np.percentile(ests, 97.5)), len(ests)


def build_panel(df, observed_only, min_n):
    d = df.copy()
    if observed_only:
        d = d[d["n_bidders"].notna()].copy()
        d["single_bidder"] = (d["n_bidders"] == 1)
    cq = (d.groupby(["country", "q"])
            .agg(sb_rate=("single_bidder", "mean"),
                 n=("single_bidder", "size")).reset_index())
    return cq[cq["n"] >= min_n]


def main():
    df = pq.read_table(PARQUET, columns=[
        "country", "year", "month", "single_bidder", "n_bidders"]).to_pandas()
    df["year"] = df["year"].astype(int)
    df = df[df["year"].between(2012, 2023)]
    df = df[df["country"].isin(TRANSPOSITION.keys())]
    df = df[df["month"].notna()]
    df["quarter"] = ((df["month"].astype(int) - 1) // 3) + 1
    df["q"] = qidx(df["year"], df["quarter"])

    cohort_q = {c: qidx(y, 1) for c, y in TRANSPOSITION.items()}  # onset = Q1 of year

    results = {"cohort_year_map": TRANSPOSITION,
               "onset_rule": "treatment onset placed at Q1 of cohort year",
               "panels": {}}
    # quarterly cells are ~1/4 the size of yearly; lower the min-n floor to 25
    for label, obs_only in [("full_universe", False),
                            ("coverage_stable_observed_bidders", True)]:
        cq = build_panel(df, obs_only, min_n=25)
        att, ncells, es = nyt_aggregate_att(cq, cohort_q)
        p, nperm, nmean, nsd = permutation_p(cq, cohort_q, att)
        lo, hi, nb = boot_ci(cq, cohort_q)
        results["panels"][label] = {
            "resolution": "country-quarter",
            "aggregate_att_pp": att,
            "n_group_time_cells": ncells,
            "boot_ci95_pp": [lo, hi],
            "boot_n": nb,
            "permutation_p": p,
            "permutation_n": nperm,
            "permutation_null_mean": nmean,
            "permutation_null_sd": nsd,
            "n_countries": int(cq["country"].nunique()),
            "n_quarters_observed": int(cq["q"].nunique()),
            "event_study_att_by_event_quarter": es,
        }
        print(f"\n=== {label} (QUARTERLY) ===")
        print(f"  aggregate ATT = {att:+.2f} pp  over {ncells} (g,t) cells, "
              f"{cq['country'].nunique()} countries, {cq['q'].nunique()} quarters")
        print(f"  block-bootstrap 95% CI = [{lo:+.2f}, {hi:+.2f}] pp  (n={nb})")
        print(f"  permutation p = {p:.3f}  [null {nmean:+.2f} +/- {nsd:.2f}, {nperm} perms]")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
