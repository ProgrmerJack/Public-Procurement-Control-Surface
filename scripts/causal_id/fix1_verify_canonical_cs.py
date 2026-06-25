"""
Independent verification of the Fix-1 result with the CANONICAL Callaway & Sant'Anna
estimator (`differences.ATTgt`, doubly-robust, not-yet-treated controls), replacing the
hand-rolled estimator. Same rebuilt raw-TED monthly panel.

If this confirms a non-negative ATT, the paper's -9 to -17 pp reduction cannot stand.
Output: results/causal_id/fix1_canonical_cs.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "causal_id" / "ted_monthly_raw"
OUT = ROOT / "results" / "causal_id" / "fix1_canonical_cs.json"

TRANSP = {
    "DK": (2015, 12), "HU": (2015, 10), "DE": (2016, 2), "FR": (2016, 3),
    "CZ": (2016, 4), "IT": (2016, 4), "HR": (2016, 6), "LV": (2016, 5),
    "BE": (2016, 6), "GR": (2016, 8), "BG": (2016, 10), "EE": (2017, 7),
    "ES": (2017, 11), "LU": (2018, 4), "LT": (2016, 4), "NL": (2016, 4),
    "PL": (2016, 4), "PT": (2016, 4), "SK": (2016, 4), "FI": (2016, 4),
    "SE": (2016, 4), "IE": (2016, 4), "AT": (2017, 6), "SI": (2018, 6),
    "NO": (2017, 1),
}
EXCLUDE = {"GB", "UK", "CH"}


def build():
    frames = [pd.read_csv(f, dtype={"cpv_division": str}) for f in sorted(RAW.glob("*.csv"))]
    raw = pd.concat([d for d in frames if len(d)], ignore_index=True)
    raw["ym_s"] = raw["ym"].astype(str)
    raw["ymabs"] = raw["ym_s"].str[:4].astype(int) * 12 + (raw["ym_s"].str[4:6].astype(int) - 1)
    raw = raw[~raw["country"].isin(EXCLUDE)]
    p = (raw.groupby(["country", "ymabs"]).agg(
        sb=("sb", "sum"), ge3=("ge3", "sum"), n=("n", "sum")).reset_index())
    p["sb_rate"] = p["sb"] / p["n"]
    p["comp3_rate"] = p["ge3"] / p["n"]
    p = p[p["n"] >= 30]
    p["cohort"] = p["country"].map({c: y * 12 + (m - 1) for c, (y, m) in TRANSP.items()})
    p = p.dropna(subset=["cohort"])
    p["cohort"] = p["cohort"].astype(int)
    return p


def main():
    from differences import ATTgt
    p = build()
    # balanced-ish: keep entities x times; differences wants MultiIndex (entity,time)
    d = p.set_index(["country", "ymabs"]).sort_index()
    print(f"panel: {p['country'].nunique()} countries, "
          f"{p['ymabs'].nunique()} months, {len(p)} obs")

    res = {"n_countries": int(p["country"].nunique()), "n_obs": int(len(p)), "outcomes": {}}
    for col in ["sb_rate", "comp3_rate"]:
        att = ATTgt(data=d[[col, "cohort", "n"]], cohort_column="cohort")
        att.fit(formula=f"{col}", control_group="not_yet_treated", est_method="dr",
                weights_column="n", boot_iterations=499, random_state=7, n_jobs=1,
                progress_bar=False)
        simple = att.aggregate("simple", boot_iterations=499, random_state=7)
        event = att.aggregate("event", boot_iterations=499, random_state=7)
        sv = simple.values[0]                      # [ATT, std, lower, upper, marker]
        att_v, std_v, lo_v, hi_v = float(sv[0]), float(sv[1]), float(sv[2]), float(sv[3])
        # post-period event coefs only (relative_period >= 0) for a clean dynamic read
        ev = event.copy(); ev.columns = ["ATT", "std", "lo", "hi", "sig"]
        post = ev[ev.index >= 0]
        print(f"\n=== {col} (canonical C&S, doubly-robust, not-yet-treated) ===")
        print(f"  SIMPLE ATT = {att_v:+.4f}  (std {std_v:.4f})  95% CI [{lo_v:+.4f}, {hi_v:+.4f}]"
              f"  -> in pp: {att_v*100:+.2f} [{lo_v*100:+.2f}, {hi_v*100:+.2f}]")
        print("  post-period event ATT (months 0..12):")
        for e in range(0, 13):
            if e in post.index:
                r = post.loc[e]
                print(f"    e={e:>2}: {r['ATT']*100:+.2f} pp  CI[{r['lo']*100:+.2f},{r['hi']*100:+.2f}]")
        res["outcomes"][col] = {
            "simple_att": att_v, "simple_att_pp": att_v * 100, "std": std_v,
            "ci95_pp": [lo_v * 100, hi_v * 100],
            "post_event_att_pp": {int(e): float(ev.loc[e, "ATT"] * 100)
                                  for e in ev.index if e >= 0},
            "pre_event_att_pp": {int(e): float(ev.loc[e, "ATT"] * 100)
                                 for e in ev.index if -12 <= e < 0},
        }
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
