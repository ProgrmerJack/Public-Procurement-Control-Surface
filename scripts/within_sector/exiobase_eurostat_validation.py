"""
Validate the EXIOBASE-derived carbon classification weights (kg CO2e/USD per CPV
division, used throughout the paper) against INDEPENDENT measured emission
intensities from Eurostat air-emission accounts (GHG / GVA, kg CO2e/EUR by NACE).

Bridge CPV->NACE empirically from the matched EUTL firms (which carry both a CPV
division, from procurement, and a NACE code, from the ETS registry). If the paper's
weights rank-agree with Eurostat measured intensities, the carbon dimension is
validated as a proxy for real sector emissions (addresses measurement-error concern).

Output: results/within_sector/exiobase_eurostat_validation.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
EUROSTAT = ROOT / "Data" / "processed" / "eurostat_carbon_intensities.csv"
MATCHED = ROOT / "results" / "within_sector" / "eutl_matched_firms.csv"
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "within_sector" / "exiobase_eurostat_validation.json"


def main():
    import re
    # 1. Eurostat measured intensity, EU 2015-2021 median per Eurostat NACE code,
    #    then resolved to 2-digit divisions (codes like C20, D, C10-C12, E37-E39).
    es = pd.read_csv(EUROSTAT)
    es = es[es["year"].between(2015, 2021)]
    es = es[es["intensity_kg_eur"].between(0, 50)]
    code_int = es.groupby("nace")["intensity_kg_eur"].median()

    def divs_of(code):
        """(list of 2-digit division strings, specificity[1=best])."""
        nums = re.findall(r"\d{2}", code)
        if ("-" in code or "_" in code) and len(nums) >= 2:
            return [f"{i:02d}" for i in range(int(nums[0]), int(nums[-1]) + 1)], 2
        if nums:
            return [nums[0]], 1
        return [], 9       # section-only letter: too coarse, skip
    div_int, div_spec = {}, {}
    for code, val in code_int.items():
        ds, spec = divs_of(str(code))
        for d in ds:
            if d not in div_spec or spec < div_spec[d]:
                div_int[d], div_spec[d] = val, spec
    eur_int = pd.Series(div_int, name="intensity_kg_eur")
    eur_int.index.name = "nace2"

    # 2. EXIOBASE weight per CPV division (from the paper's parquet)
    pp = pq.read_table(PARQUET, columns=["cpv_division", "carbon_intensity_kg_usd"]).to_pandas()
    cpv_w = pp.groupby("cpv_division")["carbon_intensity_kg_usd"].first()

    # 3. empirical CPV->NACE2 bridge from matched ETS firms
    m = pd.read_csv(MATCHED)
    m["nace2"] = m["nace"].astype(str).str.extract(r"^([0-9]{2})")[0]
    m["cpv"] = pd.to_numeric(m["cpv"], errors="coerce")
    m = m[m["cpv"].notna() & m["nace2"].notna()]
    m["cpv"] = m["cpv"].astype(int).astype(str).str.zfill(2)
    bridge = (m.groupby("cpv")["nace2"]
                .agg(lambda s: s.value_counts().index[0]).rename("nace2").reset_index())

    bridge["exio_weight"] = bridge["cpv"].map(cpv_w)
    bridge["eurostat_measured"] = bridge["nace2"].map(eur_int)
    v = bridge.dropna(subset=["exio_weight", "eurostat_measured"])

    rho, p = stats.spearmanr(v["exio_weight"], v["eurostat_measured"])
    pear, pp_ = stats.pearsonr(np.log(v["exio_weight"].clip(lower=.01)),
                               np.log(v["eurostat_measured"].clip(lower=.01)))
    res = {
        "n_sectors_bridged": int(len(v)),
        "spearman_exio_vs_eurostat": {"rho": float(rho), "p": float(p)},
        "pearson_log": {"r": float(pear), "p": float(pp_)},
        "bridge": v.sort_values("eurostat_measured", ascending=False).round(3).to_dict("records"),
    }
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"sectors bridged (CPV->NACE): {len(v)}")
    print(f"EXIOBASE weight vs Eurostat MEASURED intensity: Spearman rho={rho:+.3f} (p={p:.4f})")
    print(f"  log-log Pearson r={pear:+.3f} (p={pp_:.4f})")
    print("\n  CPV  NACE2   EXIO_wt  Eurostat_measured(kg/EUR)")
    for r in res["bridge"][:18]:
        print(f"  {r['cpv']:>3}  {r['nace2']:>4}   {r['exio_weight']:>6.2f}   {r['eurostat_measured']:>8.3f}")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
