"""
Difference-in-discontinuities on the 2019->2020 central threshold move
(publication plan Item 4, cleaner alternative to the dead RDD).

The central-government supplies/services cutoff dropped EUR144,000 (2018-19) ->
EUR139,000 (2020-21). Contracts in the [139k,144k) band therefore switched from
BELOW-threshold (no mandatory EU-wide publication) in 2019 to ABOVE-threshold in
2020-21 -- a legal change in disclosure status, by band, holding contract size
roughly fixed. We compare this treated band to two control bands that did not
switch status, before vs after.

  Treated band     [139k,144k): below-thr 2019 -> above-thr 2020-21  (gains disclosure)
  Control (always) [144k,160k): above-thr in both periods
  Control (never)  [120k,139k): below-thr in both periods

Outcome: single-bidder rate (n_bidders==1) and mean bidder count, central-gov
supplies/services only, observed bidder counts, 2018 dropped.
DiD: (treated post-pre) - (control post-pre).

Output: results/rdd/diff_in_disc_threshold_move.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
TED = ROOT / "Data" / "processed" / "eu_ted" / "eu_ted_harmonized.parquet"
OUT = ROOT / "results" / "rdd" / "diff_in_disc_threshold_move.json"

CENTRAL_BUYERS = {"Central government", "National agency", "EU institution"}
PRE = [2016, 2017, 2019]   # 2018 dropped (corrupted)
POST = [2020, 2021]


def cell(df, lo, hi, years):
    s = df[(df.value_eur >= lo) & (df.value_eur < hi) & (df.year.isin(years))]
    return s


def main():
    df = pq.read_table(TED, columns=[
        "country", "year", "buyer_type", "contract_type",
        "value_eur", "n_bidders"]).to_pandas()
    df["year"] = df["year"].astype("Int64")
    df = df[df.buyer_type.isin(CENTRAL_BUYERS)]
    df = df[df.contract_type.isin(["Supplies", "Services"])]
    df = df[df.value_eur > 0].dropna(subset=["value_eur", "n_bidders"])
    df["sb"] = (df.n_bidders == 1).astype(float)

    bands = {
        "treated_139_144": (139_000, 144_000),
        "control_always_144_160": (144_000, 160_000),
        "control_never_120_139": (120_000, 139_000),
    }
    out = {"pre_years": PRE, "post_years": POST, "bands": {}}
    means = {}
    for name, (lo, hi) in bands.items():
        pre = cell(df, lo, hi, PRE)
        post = cell(df, lo, hi, POST)
        rec = {
            "n_pre": int(len(pre)), "n_post": int(len(post)),
            "sb_pre": float(pre.sb.mean()), "sb_post": float(post.sb.mean()),
            "bidders_pre": float(pre.n_bidders.mean()),
            "bidders_post": float(post.n_bidders.mean()),
            "sb_change": float(post.sb.mean() - pre.sb.mean()),
            "bidders_change": float(post.n_bidders.mean() - pre.n_bidders.mean()),
        }
        out["bands"][name] = rec
        means[name] = rec
        print(f"{name}: SB {rec['sb_pre']*100:.1f}%->{rec['sb_post']*100:.1f}% "
              f"(Δ{rec['sb_change']*100:+.2f}pp); bidders {rec['bidders_pre']:.2f}->"
              f"{rec['bidders_post']:.2f} (Δ{rec['bidders_change']:+.2f})  "
              f"[n_pre={rec['n_pre']:,}, n_post={rec['n_post']:,}]")

    # DiD vs each control (treated should see SB fall / bidders rise if disclosure helps)
    t = means["treated_139_144"]
    for ctrl_name in ["control_always_144_160", "control_never_120_139"]:
        c = means[ctrl_name]
        did_sb = t["sb_change"] - c["sb_change"]
        did_bid = t["bidders_change"] - c["bidders_change"]
        # crude SE for SB DiD via 4-group binomial
        def se_sb(rec):
            return (rec["sb_pre"] * (1 - rec["sb_pre"]) / max(rec["n_pre"], 1)
                    + rec["sb_post"] * (1 - rec["sb_post"]) / max(rec["n_post"], 1))
        se = np.sqrt(se_sb(t) + se_sb(c))
        z = did_sb / se if se > 0 else np.nan
        p = float(2 * stats.norm.sf(abs(z))) if not np.isnan(z) else None
        out[f"did_vs_{ctrl_name}"] = {
            "did_sb_pp": did_sb * 100, "did_sb_se_pp": se * 100,
            "did_sb_z": float(z), "did_sb_p": p,
            "did_bidders": did_bid,
        }
        print(f"\nDiD (treated - {ctrl_name}): "
              f"SB {did_sb*100:+.2f}pp (z={z:+.2f}, p={p:.3g}); "
              f"bidders {did_bid:+.3f}")

    OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
