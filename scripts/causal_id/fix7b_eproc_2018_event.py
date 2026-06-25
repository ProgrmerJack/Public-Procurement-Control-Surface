"""
Fix 7b: test the 18 October 2018 mandatory e-submission deadline (Directive 2014/24
Art. 22 full e-communication) as a second, independent shock on single-bidding, using
the CLEAN raw-rebuilt monthly panel (2015-2020; the corrupted-vintage objection no
longer applies). The mandate date is near-common across EU states (not staggered), so
this is an interrupted time series (panel break) with country FE + seasonality + trend,
not a staggered DiD. We report the break coefficient and state the identification limit.

Output: results/causal_id/fix7b_eproc_2018.json
"""
import glob, json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "causal_id" / "ted_monthly_raw"
OUT = ROOT / "results" / "causal_id" / "fix7b_eproc_2018.json"
EXCLUDE = {"GB", "UK", "CH"}
BREAK = 2018 * 12 + (10 - 1)        # Oct 2018


def main():
    frames = [pd.read_csv(f, dtype={"cpv_division": str}) for f in glob.glob(str(RAW / "*.csv"))]
    raw = pd.concat([d for d in frames if len(d)], ignore_index=True)
    raw["ym"] = raw["ym"].astype(str).str[:4].astype(int) * 12 + (raw["ym"].astype(str).str[4:6].astype(int) - 1)
    raw = raw[~raw["country"].isin(EXCLUDE)]
    p = raw.groupby(["country", "ym"]).agg(sb=("sb", "sum"), n=("n", "sum")).reset_index()
    p["sb_rate"] = p["sb"] / p["n"]
    p = p[p["n"] >= 30].copy()
    p["post"] = (p["ym"] >= BREAK).astype(int)
    p["t"] = p["ym"] - p["ym"].min()
    p["moy"] = (p["ym"] % 12).astype(str)        # seasonality

    # ITS: sb_rate ~ post + trend + seasonality + country FE, clustered by country
    m = smf.wls("sb_rate ~ post + t + C(moy) + C(country)", data=p, weights=p["n"]).fit(
        cov_type="cluster", cov_kwds={"groups": p["country"]})
    coef, se, pval = float(m.params["post"]), float(m.bse["post"]), float(m.pvalues["post"])
    ci = [coef - 1.96 * se, coef + 1.96 * se]

    # event-time means around the break (descriptive)
    p["rel"] = p["ym"] - BREAK
    win = p[p["rel"].between(-12, 12)]
    by = win.groupby("rel").apply(lambda d: np.average(d["sb_rate"], weights=d["n"]),
                                  include_groups=False)

    res = {
        "design": "interrupted time series (near-common Oct-2018 e-submission deadline)",
        "break_ym": "2018-10", "n_country_months": int(len(p)),
        "post_coef_pp": coef * 100, "se_pp": se * 100, "p": pval,
        "ci95_pp": [ci[0] * 100, ci[1] * 100],
        "identification_caveat": ("the e-submission deadline is near-simultaneous across EU states "
                                  "(not staggered), so this is a common-shock ITS with no clean control "
                                  "group; any coefficient is confounded with other 2018-19 trends and "
                                  "is not a causal estimate."),
        "sb_rate_by_relmonth": {int(k): round(float(v), 3) for k, v in by.items()},
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"ITS break at Oct-2018: post coef = {coef*100:+.2f} pp (SE {se*100:.2f}, p={pval:.3f}), "
          f"95% CI [{ci[0]*100:+.2f}, {ci[1]*100:+.2f}]")
    print("Caveat: near-common date -> ITS, not staggered DiD; confounded, not causal.")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
