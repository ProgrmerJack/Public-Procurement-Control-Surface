"""
A3: break (or honestly bound) the large-emitter coverage ceiling on the firm-level result.

No mid-cap/service emissions source (Orbis/Trucost/CDP) is available in the repo, so we
cannot extend beyond large industrial emitters. What we CAN do honestly:
 (1) maximise registry coverage: relax the >=3-contract filter to >=1 and pool EUTL.
 (2) QUANTIFY the ceiling: what share of EU procurement contracts and of high-carbon
     (Dead Zone) contract VALUE is won by any registry-matched emitter? (turns the
     "bounded to ~1,100 firms" caveat into a measured coverage statement.)
 (3) re-test the within-sector size-controlled partial correlation on the wider set.

Output: results/within_sector/a3_coverage_expansion.json
"""
import importlib.util, json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "within_sector" / "a3_coverage_expansion.json"
MASTER = ROOT / "Data" / "processed" / "gprd_master.parquet"
CARBON = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"

spec = importlib.util.spec_from_file_location(
    "eutlmod", ROOT / "scripts" / "within_sector" / "eutl_supplier_firm_match.py")
eutlmod = importlib.util.module_from_spec(spec); spec.loader.exec_module(eutlmod)


def partial_corr(x, y, z):
    x, y, z = np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)
    rxy, rxz, ryz = np.corrcoef(x, y)[0, 1], np.corrcoef(x, z)[0, 1], np.corrcoef(y, z)[0, 1]
    d = np.sqrt((1 - rxz**2) * (1 - ryz**2))
    return np.nan if d == 0 else (rxy - rxz * ryz) / d


def main():
    firms = eutlmod.load_eutl()
    sup = eutlmod.load_suppliers()
    res = {"n_eutl_firms": int(len(firms)), "n_proc_suppliers_distinct": int(len(sup))}

    # (1) coverage-max match: every matched firm with >=1 contract
    m = firms.merge(sup, on="nkey", how="inner", suffixes=("_eutl", "_proc"))
    res["n_matched_firms_ge1"] = int(len(m))
    res["n_matched_firms_ge3"] = int((m["n_contracts"] >= 3).sum())

    # (2) quantify the ceiling against the FULL contract universe (value from master, carbon by sector map)
    cb = pq.read_table(CARBON, columns=["cpv_division", "carbon_intensity_kg_usd"]).to_pandas()
    cmap = cb.dropna().groupby("cpv_division")["carbon_intensity_kg_usd"].median()
    df = pq.read_table(MASTER, columns=[
        "country", "supplier_name", "value_eur", "cpv_division"]).to_pandas()
    df = df[df["country"] != "CO"].copy()
    sn = df["supplier_name"].astype(str)
    df = df[sn.notna() & (sn.str.lower() != "nan") & (sn.str.strip() != "")]
    df["carbon_intensity_kg_usd"] = df["cpv_division"].map(cmap)
    df = df.dropna(subset=["carbon_intensity_kg_usd"])
    df["nkey"] = df["supplier_name"].map(eutlmod.norm)
    df["value_eur"] = pd.to_numeric(df["value_eur"], errors="coerce").fillna(0)
    matched_keys = set(m["nkey"])
    df["matched"] = df["nkey"].isin(matched_keys)
    hi = df[df["carbon_intensity_kg_usd"] >= 0.25]            # high-carbon (Dead Zone-relevant)
    res["coverage"] = {
        "matched_share_of_all_contracts": float(df["matched"].mean()),
        "matched_share_of_all_value": float(df.loc[df["matched"], "value_eur"].sum() / df["value_eur"].sum()),
        "matched_share_of_highcarbon_contracts": float(hi["matched"].mean()),
        "matched_share_of_highcarbon_value": float(
            hi.loc[hi["matched"], "value_eur"].sum() / max(hi["value_eur"].sum(), 1)),
        "n_highcarbon_contracts": int(len(hi)),
    }

    # (3) re-test within-sector size-controlled partial corr on the wider (>=1) set
    big = m[m["nace"].notna()].copy()
    big["log_emis"] = np.log(big["emis_t"].clip(lower=1))
    big["nace_n"] = big.groupby("nace")["nace"].transform("size")
    big = big[big["nace_n"] >= 5]
    big["e_dm"] = big["log_emis"] - big.groupby("nace")["log_emis"].transform("mean")
    big["s_dm"] = big["sb_rate"] - big.groupby("nace")["sb_rate"].transform("mean")
    big["logN"] = np.log(big["n_install"].clip(lower=1))
    big["n_dm"] = big["logN"] - big.groupby("nace")["logN"].transform("mean")
    pc = partial_corr(big["s_dm"], big["e_dm"], big["n_dm"])
    n = len(big)
    tval = pc * np.sqrt((n - 3) / (1 - pc**2)) if abs(pc) < 1 else np.nan
    res["wider_set_within_nace_partial_corr"] = {
        "partial_rho": float(pc), "p": float(2 * stats.t.sf(abs(tval), n - 3)),
        "n_firms": int(n), "vs_baseline_1105": "baseline partial rho was +0.15 on >=3-contract set"}

    res["ceiling_statement"] = (
        "Registry coverage is structurally capped: EUTL/E-PRTR list only installations above "
        "ETS/IED capacity thresholds, so most procurement winners (services, SMEs) are absent. "
        "No mid-cap/service emissions source (Orbis/Trucost/CDP) is available, so the firm-level "
        "result cannot be extended beyond large industrial emitters. The coverage figures above "
        "quantify this: matched emitters are few in COUNT but the high-carbon-value share they "
        "cover is the policy-relevant quantity.")

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    c = res["coverage"]
    print(f"matched firms: >=1 contract {res['n_matched_firms_ge1']:,}; >=3 {res['n_matched_firms_ge3']:,}")
    print(f"coverage: {c['matched_share_of_all_contracts']:.2%} of all contracts, "
          f"{c['matched_share_of_all_value']:.2%} of all value")
    print(f"high-carbon coverage: {c['matched_share_of_highcarbon_contracts']:.2%} of contracts, "
          f"{c['matched_share_of_highcarbon_value']:.2%} of value")
    w = res["wider_set_within_nace_partial_corr"]
    print(f"wider-set within-NACE size-controlled partial rho = {w['partial_rho']:+.3f} "
          f"(p={w['p']:.3f}, n={w['n_firms']})")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
