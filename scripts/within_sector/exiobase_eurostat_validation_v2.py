"""
A4 (redone): Validate the paper's EXIOBASE-derived carbon weights against Eurostat
MEASURED emission intensities, using a transparent hand-built CPV->NACE concordance
(NOT the flawed firm-based bridge, which conflated what a firm wins with what it makes).

For each CPV division we assign the best-matching NACE division by its product/service
description, look up Eurostat measured intensity (kg CO2e/EUR GVA, EU 2015-2021 median),
and correlate with the paper's classification weight (kg CO2e/USD). A positive rank
correlation validates the weights as a proxy for measured sector emission intensity.

Output: results/within_sector/exiobase_eurostat_validation_v2.json
"""
import json, re
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
EUROSTAT = ROOT / "Data" / "processed" / "eurostat_carbon_intensities.csv"
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "within_sector" / "exiobase_eurostat_validation_v2.json"

# Hand concordance: CPV division -> NACE division (2-digit) by product/service meaning.
# Services with no industrial NACE emission analogue are left None (excluded).
CPV_TO_NACE = {
    "03": "01", "09": "19", "14": "07", "15": "10", "18": "14", "19": "15",
    "22": "18", "24": "20", "30": "26", "31": "27", "32": "26", "33": "26",
    "34": "29", "35": "25", "38": "26", "39": "31", "42": "28", "43": "28",
    "44": "25", "45": "41", "48": "62", "50": "33", "55": "55", "60": "49",
    "63": "52", "64": "53", "65": "35", "66": "64", "70": "68", "71": "71",
    "72": "62", "73": "72", "75": "84", "77": "01", "79": "70", "80": "85",
    "85": "86", "90": "38", "92": "90", "98": "96",
}


def build_eurostat_div_intensity():
    es = pd.read_csv(EUROSTAT)
    es = es[es["year"].between(2015, 2021) & es["intensity_kg_eur"].between(0, 50)]
    code_int = es.groupby("nace")["intensity_kg_eur"].median()

    def divs_of(code):
        nums = re.findall(r"\d{2}", code)
        if ("-" in code or "_" in code) and len(nums) >= 2:
            return [f"{i:02d}" for i in range(int(nums[0]), int(nums[-1]) + 1)], 2
        if nums:
            return [nums[0]], 1
        return [], 9
    div_int, spec = {}, {}
    for code, val in code_int.items():
        ds, sp = divs_of(str(code))
        for d in ds:
            if d not in spec or sp < spec[d]:
                div_int[d], spec[d] = val, sp
    return div_int


def main():
    eur_div = build_eurostat_div_intensity()
    pp = pq.read_table(PARQUET, columns=["cpv_division", "carbon_intensity_kg_usd"]).to_pandas()
    cpv_w = pp.groupby("cpv_division")["carbon_intensity_kg_usd"].first()

    rows = []
    for cpv, nace in CPV_TO_NACE.items():
        w = cpv_w.get(cpv)
        em = eur_div.get(nace)
        if w is not None and em is not None:
            rows.append({"cpv": cpv, "nace": nace, "paper_weight": float(w),
                         "eurostat_measured": float(em)})
    v = pd.DataFrame(rows)

    rho, p = stats.spearmanr(v["paper_weight"], v["eurostat_measured"])
    vp = v[v["eurostat_measured"] > 0]
    pear, pp_ = stats.pearsonr(np.log(vp["paper_weight"]), np.log(vp["eurostat_measured"]))
    res = {
        "n_sectors": int(len(v)),
        "concordance": "hand CPV->NACE division by product/service meaning",
        "spearman": {"rho": float(rho), "p": float(p)},
        "pearson_loglog": {"r": float(pear), "p": float(pp_)},
        "table": v.sort_values("eurostat_measured", ascending=False).round(3).to_dict("records"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"sectors validated: {len(v)}")
    print(f"paper weight vs Eurostat MEASURED intensity: Spearman rho={rho:+.3f} (p={p:.4f})")
    print(f"  log-log Pearson r={pear:+.3f} (p={pp_:.4f})")
    print("\n  CPV NACE paper_wt  eurostat_measured")
    for r in res["table"]:
        print(f"  {r['cpv']:>3} {r['nace']:>3}  {r['paper_weight']:>6.2f}   {r['eurostat_measured']:>8.3f}")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
