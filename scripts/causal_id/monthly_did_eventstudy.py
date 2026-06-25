"""
Fix 1 + inference upgrade: not-yet-treated Callaway & Sant'Anna at MONTHLY resolution
on the rebuilt TED country x month panel. Converts the 3-cell annual design into a
dynamic event study with many ATT(g,t) cells and a block-bootstrap simultaneous CI
(replacing the "-9 to -17 pp range").

Treatment timing = national entry-into-force MONTH of Directive 2014/24/EU. Dates from
EUR-Lex NIM (CELEX 32014L0024) entry-into-force where available; remaining countries
placed at the 18 April 2016 deadline (2016 cohort) / mid-year of their validated cohort
year. `exact` flag records sourcing. Norway = EEA 2017. GB/CH excluded.

Outputs: results/causal_id/monthly_did_eventstudy.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "Data" / "processed" / "ted_country_month_panel.parquet"
OUT = ROOT / "results" / "causal_id" / "monthly_did_eventstudy.json"

def ym(y, m):
    return y * 12 + (m - 1)          # absolute month index (matches panel builder)

# (country): (year, month, exact?)  -- entry-into-force month
TRANSP = {
    "DK": (2015, 12, True), "HU": (2015, 10, True), "DE": (2016, 2, True),
    "FR": (2016, 3, True), "CZ": (2016, 4, True), "IT": (2016, 4, True),
    "HR": (2016, 6, False), "LV": (2016, 5, True), "BE": (2016, 6, True),
    "GR": (2016, 8, True), "BG": (2016, 10, True), "EE": (2017, 7, True),
    "ES": (2017, 11, True), "LU": (2018, 4, True), "LT": (2016, 4, False),
    # filled from validated cohort years (deadline / mid-year), month approximate:
    "NL": (2016, 4, False), "PL": (2016, 4, False), "PT": (2016, 4, False),
    "SK": (2016, 4, False), "FI": (2016, 4, False), "SE": (2016, 4, False),
    "IE": (2016, 4, False), "AT": (2017, 6, False), "SI": (2018, 6, False),
    "NO": (2017, 1, True),
}
COHORT = {c: ym(y, m) for c, (y, m, _) in TRANSP.items()}


def nyt_dynamic(panel, cohort, col="sb_rate", emax=24, pre=6):
    """Not-yet-treated ATT(g,e); returns dynamic ES dict and overall ATT (pp)."""
    p = panel.copy()
    p["g"] = p["country"].map(cohort)
    cohorts = sorted(set(cohort.values()))
    cells = []  # (g, e, att, weight)
    for g in cohorts:
        treated = p[p["g"] == g]
        ncoh = treated["country"].nunique()
        base = treated[(treated["ym"] >= g - pre) & (treated["ym"] < g)]
        if len(base) == 0:
            continue
        tb = np.average(base[col], weights=base["n"])
        for e in range(0, emax + 1):
            t = g + e
            ctrl = p[p["g"] > t]                       # not-yet-treated at t
            cb = ctrl[(ctrl["ym"] >= g - pre) & (ctrl["ym"] < g)]
            ct = ctrl[ctrl["ym"] == t]
            tt = treated[treated["ym"] == t]
            if len(tt) == 0 or len(cb) == 0 or len(ct) == 0:
                continue
            att = ((np.average(tt[col], weights=tt["n"]) - tb)
                   - (np.average(ct[col], weights=ct["n"])
                      - np.average(cb[col], weights=cb["n"])))
            cells.append((g, e, att * 100, ncoh))
    if not cells:
        return {}, np.nan, 0
    cdf = pd.DataFrame(cells, columns=["g", "e", "att", "w"])
    es = (cdf.groupby("e").apply(lambda d: np.average(d["att"], weights=d["w"]))
            .to_dict())
    overall = float(np.average(cdf["att"], weights=cdf["w"]))
    return {int(k): float(v) for k, v in es.items()}, overall, len(cdf)


def block_bootstrap(panel, cohort, col="sb_rate", n_boot=600, seed=13, emax=24):
    rng = np.random.default_rng(seed)
    countries = list(cohort.keys())
    overalls, es_draws = [], []
    for _ in range(n_boot):
        pick = rng.choice(countries, len(countries), replace=True)
        frames, cmap = [], {}
        for i, c in enumerate(pick):
            sub = panel[panel["country"] == c].copy()
            a = f"{c}_{i}"; sub["country"] = a; cmap[a] = cohort[c]
            frames.append(sub)
        es, ov, _ = nyt_dynamic(pd.concat(frames), cmap, col, emax)
        if not np.isnan(ov):
            overalls.append(ov); es_draws.append(es)
    overalls = np.array(overalls)
    ci = [float(np.percentile(overalls, 2.5)), float(np.percentile(overalls, 97.5))]
    return ci, float(np.mean(overalls)), float(np.std(overalls)), len(overalls)


def main():
    panel = pd.read_parquet(PANEL)
    panel = panel[panel["country"].isin(COHORT) & (panel["n"] >= 30)].copy()

    # cohort-month histogram (binding diagnostic)
    hist = pd.Series([ym(*TRANSP[c][:2]) for c in panel["country"].unique()]).value_counts()
    by_month = {}
    for c in sorted(set(panel["country"])):
        y, m, ex = TRANSP[c]
        by_month.setdefault(f"{y}-{m:02d}", []).append(c + ("" if ex else "*"))
    distinct_months = len(by_month)

    res = {"n_countries": int(panel["country"].nunique()),
           "distinct_cohort_months": distinct_months,
           "cohort_month_histogram": {k: by_month[k] for k in sorted(by_month)},
           "panels": {}}
    for col, label in [("sb_rate", "single-bidder rate"),
                       ("comp3_rate", ">=3-bidder share")]:
        es, overall, ncells = nyt_dynamic(panel, COHORT, col)
        ci, bmean, bsd, nb = block_bootstrap(panel, COHORT, col)
        res["panels"][col] = {
            "outcome": label, "overall_att_pp": overall, "n_gt_cells": ncells,
            "boot_ci95": ci, "boot_mean": bmean, "boot_sd": bsd, "boot_n": nb,
            "z": overall / bsd if bsd else None,
            "event_study_att_pp": es,
        }
        print(f"\n=== {label} (monthly not-yet-treated) ===")
        print(f"  overall ATT = {overall:+.2f} pp over {ncells} ATT(g,t) cells")
        print(f"  block-bootstrap 95% CI = [{ci[0]:+.2f}, {ci[1]:+.2f}] pp (z={overall/bsd:+.2f}, n={nb})")
        evs = {k: round(v, 1) for k, v in sorted(es.items()) if k in (0, 3, 6, 12, 18, 24)}
        print(f"  event-study ATT at e=0,3,6,12,18,24 months: {evs}")
    print(f"\ndistinct cohort months: {distinct_months}  (was 3 annual cohorts)")
    print("cohort-month histogram:")
    for k in sorted(by_month):
        print(f"   {k}: {by_month[k]}")
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
