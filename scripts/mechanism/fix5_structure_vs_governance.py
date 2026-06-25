"""
Fix 5: turn "market structure, not governance, determines where competition is thin"
from an assertion into a tested decomposition.

Build country x CPV-division market-structure variables from the procurement microdata,
attach country-level governance (WGI Rule of Law), and run a horse-race:
  single-bidder rate ~ structure block | governance, with sector fixed effects.
Report (i) each block's joint significance, (ii) whether governance loses explanatory
power once structure enters, and (iii) a Shapley/sequential-R2 variance decomposition.

Output: results/mechanism/fix5_structure_vs_governance.json
"""
import json
from pathlib import Path
from itertools import permutations

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "Data" / "processed" / "gprd_master.parquet"
GOV = ROOT / "results" / "audit" / "falsifiable_governance_test.json"
OUT = ROOT / "results" / "mechanism" / "fix5_structure_vs_governance.json"


def main():
    df = pq.read_table(MASTER, columns=[
        "country", "cpv_division", "single_bidder", "value_eur", "supplier_name", "year"]).to_pandas()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df[(df["country"] != "CO") & df["year"].between(2012, 2023)]
    sn = df["supplier_name"].astype(str)
    df = df[sn.notna() & (sn.str.lower() != "nan") & (sn.str.strip() != "")]
    df = df[df["value_eur"].notna() & (df["value_eur"] > 0)].copy()
    df["cell"] = df["country"] + "|" + df["cpv_division"].astype(str)

    # per supplier within cell
    sup = (df.groupby(["cell", "supplier_name"])
             .agg(val=("value_eur", "sum"), nawards=("value_eur", "size")).reset_index())
    cells = []
    for cell, g in sup.groupby("cell"):
        tot = g["val"].sum()
        if tot <= 0:
            continue
        shares = (g["val"] / tot).values
        hhi = float(np.sum(shares ** 2))
        cr1 = float(shares.max())
        n_sup = int(len(g))
        repeat_val = float(g.loc[g["nawards"] >= 2, "val"].sum() / tot)  # incumbency proxy
        cells.append({"cell": cell, "hhi": hhi, "cr1": cr1, "n_suppliers": n_sup,
                      "incumbency": repeat_val})
    cd = pd.DataFrame(cells)

    base = (df.groupby(["cell", "country", "cpv_division"])
              .agg(sb_rate=("single_bidder", "mean"), n=("single_bidder", "size")).reset_index())
    m = base.merge(cd, on="cell")
    m = m[m["n"] >= 100].copy()       # adequately-sized cells

    gov = pd.DataFrame(json.loads(GOV.read_text())["country_table"])[["country", "rol"]]
    m = m.merge(gov, on="country", how="inner")
    m["log_nsup"] = np.log(m["n_suppliers"])
    # standardise predictors for comparable coefficients
    for c in ["hhi", "cr1", "log_nsup", "incumbency", "rol"]:
        m[c + "_z"] = (m[c] - m[c].mean()) / m[c].std()

    struct = ["hhi_z", "cr1_z", "log_nsup_z", "incumbency_z"]
    res = {"n_cells": int(len(m)), "n_countries": int(m["country"].nunique())}

    def fit(rhs):
        f = "sb_rate ~ " + " + ".join(rhs) + " + C(cpv_division)"
        return smf.wls(f, data=m, weights=m["n"]).fit(cov_type="cluster",
                                                       cov_kwds={"groups": m["country"]})
    mA = fit(["rol_z"])                         # governance only
    mB = fit(struct)                            # structure only
    mC = fit(struct + ["rol_z"])               # horse race

    res["governance_only"] = {"rol_coef": float(mA.params["rol_z"]),
                              "rol_p": float(mA.pvalues["rol_z"]), "r2": float(mA.rsquared)}
    res["structure_only"] = {"r2": float(mB.rsquared),
                             "coefs": {c: float(mB.params[c]) for c in struct},
                             "p": {c: float(mB.pvalues[c]) for c in struct}}
    # joint F-test on the structure block in the horse race
    ftest = mC.f_test(" , ".join(f"{c} = 0" for c in struct))
    res["horse_race"] = {
        "r2": float(mC.rsquared),
        "rol_coef": float(mC.params["rol_z"]), "rol_p": float(mC.pvalues["rol_z"]),
        "structure_joint_F": float(np.ravel(ftest.fvalue)[0]), "structure_joint_p": float(ftest.pvalue),
        "structure_coefs": {c: float(mC.params[c]) for c in struct},
        "structure_p": {c: float(mC.pvalues[c]) for c in struct},
    }

    # Shapley variance decomposition (structure block vs governance), over sector-FE-residualised R2
    def r2(rhs):
        if not rhs:
            return float(smf.wls("sb_rate ~ C(cpv_division)", data=m, weights=m["n"]).fit().rsquared)
        return float(smf.wls("sb_rate ~ " + " + ".join(rhs) + " + C(cpv_division)",
                             data=m, weights=m["n"]).fit().rsquared)
    base_r2 = r2([])
    blocks = {"structure": struct, "governance": ["rol_z"]}
    shap = {b: 0.0 for b in blocks}
    names = list(blocks)
    for perm in permutations(names):
        prev = []
        prev_r2 = base_r2
        for b in perm:
            cur = prev + blocks[b]
            cur_r2 = r2(cur)
            shap[b] += (cur_r2 - prev_r2)
            prev, prev_r2 = cur, cur_r2
    nperm = len(list(permutations(names)))
    shap = {b: shap[b] / nperm for b in blocks}
    tot = sum(shap.values()) or 1
    res["shapley_r2"] = {b: float(v) for b, v in shap.items()}
    res["shapley_share"] = {b: float(v / tot) for b, v in shap.items()}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"cells={res['n_cells']}, countries={res['n_countries']}")
    print(f"Governance-only: RoL coef={res['governance_only']['rol_coef']:+.3f} "
          f"(p={res['governance_only']['rol_p']:.3f}), R2={res['governance_only']['r2']:.3f}")
    print(f"Structure-only R2={res['structure_only']['r2']:.3f}")
    hr = res["horse_race"]
    print(f"Horse race: structure joint F={hr['structure_joint_F']:.1f} (p={hr['structure_joint_p']:.2e}); "
          f"RoL coef={hr['rol_coef']:+.3f} (p={hr['rol_p']:.3f})  [governance loses significance if p>0.05]")
    print(f"Shapley shares: structure={res['shapley_share']['structure']:.1%}, "
          f"governance={res['shapley_share']['governance']:.1%}")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
