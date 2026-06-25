"""
Fix 1 (real): build a country x month single-bidding panel from the streamed raw-TED
monthly aggregates (results/causal_id/ted_monthly_raw/*.csv), then run the not-yet-
treated Callaway & Sant'Anna dynamic event study at MONTHLY resolution with a country
block-bootstrap simultaneous CI. Converts the 3-cell "-9 to -17 pp range" into a
dynamic ATT path with a CI (or an honest imprecise null).

Cohort = national entry-into-force MONTH of Directive 2014/24/EU (EUR-Lex NIM).
GB/CH excluded. Pre-window base = 6 months. Outcomes: single-bidder rate, >=3-offer
share, mean offers.

Output: results/causal_id/fix1_monthly_did.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "causal_id" / "ted_monthly_raw"
OUT = ROOT / "results" / "causal_id" / "fix1_monthly_did.json"

def ym_abs(y, m):
    return y * 12 + (m - 1)

TRANSP = {  # (year, month, exact?)
    "DK": (2015, 12, True), "HU": (2015, 10, True), "DE": (2016, 2, True),
    "FR": (2016, 3, True), "CZ": (2016, 4, True), "IT": (2016, 4, True),
    "HR": (2016, 6, False), "LV": (2016, 5, True), "BE": (2016, 6, True),
    "GR": (2016, 8, True), "BG": (2016, 10, True), "EE": (2017, 7, True),
    "ES": (2017, 11, True), "LU": (2018, 4, True), "LT": (2016, 4, False),
    "NL": (2016, 4, False), "PL": (2016, 4, False), "PT": (2016, 4, False),
    "SK": (2016, 4, False), "FI": (2016, 4, False), "SE": (2016, 4, False),
    "IE": (2016, 4, False), "AT": (2017, 6, False), "SI": (2018, 6, False),
    "NO": (2017, 1, True),
}
COHORT = {c: ym_abs(y, m) for c, (y, m, _) in TRANSP.items()}
EXCLUDE = {"GB", "UK", "CH"}


def build_panel():
    frames = []
    for f in sorted(RAW.glob("*.csv")):
        d = pd.read_csv(f, dtype={"cpv_division": str})
        if len(d):
            frames.append(d)
    raw = pd.concat(frames, ignore_index=True)
    raw["ym_s"] = raw["ym"].astype(str)
    raw["year"] = raw["ym_s"].str[:4].astype(int)
    raw["mon"] = raw["ym_s"].str[4:6].astype(int)
    raw["ymabs"] = raw["year"] * 12 + (raw["mon"] - 1)
    raw = raw[~raw["country"].isin(EXCLUDE)]
    panel = (raw.groupby(["country", "ymabs"])
                .agg(sb=("sb", "sum"), ge3=("ge3", "sum"),
                     sum_off=("sum_offers", "sum"), n=("n", "sum")).reset_index())
    panel["sb_rate"] = panel["sb"] / panel["n"]
    panel["comp3_rate"] = panel["ge3"] / panel["n"]
    panel["mean_off"] = panel["sum_off"] / panel["n"]
    panel = panel.rename(columns={"ymabs": "ym"})
    return panel, raw


def nyt_dynamic(panel, cohort, col, emax=24, pre=6):
    p = panel.copy(); p["g"] = p["country"].map(cohort)
    cells = []
    for g in sorted(set(cohort.values())):
        tr = p[p["g"] == g]; ncoh = tr["country"].nunique()
        base = tr[(tr["ym"] >= g - pre) & (tr["ym"] < g)]
        if not len(base):
            continue
        tb = np.average(base[col], weights=base["n"])
        for e in range(0, emax + 1):
            t = g + e
            ctrl = p[p["g"] > t]
            cb = ctrl[(ctrl["ym"] >= g - pre) & (ctrl["ym"] < g)]
            ct = ctrl[ctrl["ym"] == t]; tt = tr[tr["ym"] == t]
            if not (len(tt) and len(cb) and len(ct)):
                continue
            att = ((np.average(tt[col], weights=tt["n"]) - tb)
                   - (np.average(ct[col], weights=ct["n"])
                      - np.average(cb[col], weights=cb["n"])))
            cells.append((e, att * 100, ncoh))
    if not cells:
        return {}, np.nan, 0
    cdf = pd.DataFrame(cells, columns=["e", "att", "w"])
    es = cdf.groupby("e").apply(lambda d: np.average(d["att"], weights=d["w"]),
                                include_groups=False).to_dict()
    return {int(k): float(v) for k, v in es.items()}, \
        float(np.average(cdf["att"], weights=cdf["w"])), len(cdf)


def boot(panel, cohort, col, nb=600, seed=17, emax=24):
    rng = np.random.default_rng(seed); cs = list(cohort)
    ov = []
    for _ in range(nb):
        pick = rng.choice(cs, len(cs), replace=True)
        fr, cmap = [], {}
        for i, c in enumerate(pick):
            s = panel[panel["country"] == c].copy(); a = f"{c}_{i}"
            s["country"] = a; cmap[a] = cohort[c]; fr.append(s)
        _, o, _ = nyt_dynamic(pd.concat(fr), cmap, col, emax)
        if not np.isnan(o):
            ov.append(o)
    ov = np.array(ov)
    return [float(np.percentile(ov, 2.5)), float(np.percentile(ov, 97.5))], float(ov.std()), len(ov)


def main():
    panel, raw = build_panel()
    panel = panel[panel["country"].isin(COHORT) & (panel["n"] >= 30)].copy()
    yr0, yr1 = raw["year"].min(), raw["year"].max()
    print(f"panel: {panel['country'].nunique()} countries, ym {panel['ym'].min()}..{panel['ym'].max()}, "
          f"{len(panel)} cells, data years {yr0}-{yr1}")

    res = {"data_years": [int(yr0), int(yr1)],
           "n_countries": int(panel["country"].nunique()),
           "n_country_month_cells": int(len(panel)), "panels": {}}
    for col, lab in [("sb_rate", "single-bidder rate"),
                     ("comp3_rate", ">=3-offer share"), ("mean_off", "mean offers")]:
        es, ov, ncell = nyt_dynamic(panel, COHORT, col)
        if np.isnan(ov):
            continue
        ci, sd, nbn = boot(panel, COHORT, col)
        res["panels"][col] = {"outcome": lab, "overall_att": ov, "unit": "pp" if col != "mean_off" else "offers",
                              "n_gt_cells": ncell, "boot_ci95": ci, "z": ov / sd if sd else None,
                              "event_study": es}
        print(f"\n{lab}: ATT={ov:+.2f} over {ncell} cells | 95%CI [{ci[0]:+.2f},{ci[1]:+.2f}] | z={ov/sd:+.2f}")
        print("  ES:", {k: round(v, 1) for k, v in sorted(es.items()) if k in (0, 3, 6, 12, 18, 24)})
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
