"""
INDEPENDENT corroboration of the EUTL firm-level result using E-PRTR facility CO2.

The manuscript reports a NULL within-sector E-PRTR test, but that test stratified
facilities by EMISSION SIZE -- i.e. it conditioned on the outcome, which mechanically
removes the emission signal. Here we redo it cleanly: aggregate E-PRTR facility CO2
to the firm (by name), match firms to procurement suppliers, and test whether single-
bidder win propensity predicts firm CO2 WITHIN sector, controlling firm size by an
INDEPENDENT measure (number of facilities), not by the outcome.

Inputs: Data/raw/eea_.../F1_4_Air_Releases_Facilities.csv ; cached supplier table.
Output: results/within_sector/eprtr_supplier_firm_match.json
"""
import json, re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
EPRTR = (ROOT / "Data" / "raw" / "eea_t_ied-eprtr_p_2007-2023_v15_r00" /
         "User-friendly-CSV" / "F1_4_Air_Releases_Facilities.csv")
SUP_CACHE = ROOT / "results" / "within_sector" / "_supplier_norm_cache.parquet"
OUT = ROOT / "results" / "within_sector" / "eprtr_supplier_firm_match.json"

LEGAL = re.compile(r"\b(GMBH|AG|SE|S\.?A\.?|S\.?P\.?A\.?|S\.?R\.?L\.?|LTD|LIMITED|PLC|"
                   r"B\.?V\.?|N\.?V\.?|OY|OYJ|AB|A/?S|APS|SP\.?\s?Z\.?\s?O\.?\s?O\.?|"
                   r"SARL|SAS|GROUP|GROUPE|HOLDING|KFT|ZRT|D\.?O\.?O\.?|EOOD|AD|"
                   r"INC|CORP|CO|COMPANY|KG|MBH|SCA|SNC)\b")
PUNCT = re.compile(r"[^A-Z0-9 ]")
WS = re.compile(r"\s+")


def norm(s):
    s = PUNCT.sub(" ", str(s).upper())
    s = LEGAL.sub(" ", s)
    return WS.sub(" ", s).strip()


def partial_corr(x, y, z):
    x, y, z = map(lambda a: np.asarray(a, float), (x, y, z))
    rxy, rxz, ryz = (np.corrcoef(x, y)[0, 1], np.corrcoef(x, z)[0, 1],
                     np.corrcoef(y, z)[0, 1])
    d = np.sqrt((1 - rxz**2) * (1 - ryz**2))
    return np.nan if d == 0 else (rxy - rxz * ryz) / d


def main():
    cols = ["countryName", "reportingYear", "EPRTR_SectorName", "facilityName", "Pollutant", "Releases"]
    df = pd.read_csv(EPRTR, usecols=cols, low_memory=False)
    co2 = df[df["Pollutant"].astype(str).str.startswith("Carbon dioxide (CO2)")].copy()
    co2["Releases"] = pd.to_numeric(co2["Releases"], errors="coerce")
    co2 = co2[(co2["reportingYear"].between(2012, 2021)) & (co2["Releases"] > 0)]
    co2["nkey"] = co2["facilityName"].map(norm)
    co2 = co2[co2["nkey"].str.len() >= 4]
    co2["EPRTR_SectorName"] = co2["EPRTR_SectorName"].astype(str)
    # firm = normalised name; mean annual total CO2 (sum within year, mean across years)
    by_fy = co2.groupby(["nkey", "reportingYear"])["Releases"].sum().reset_index()
    firm = by_fy.groupby("nkey")["Releases"].mean().rename("co2_t").reset_index()
    firm = firm.merge(co2.groupby("nkey").agg(
        n_fac=("facilityName", "nunique"),
        sector=("EPRTR_SectorName", lambda s: s.value_counts().index[0]),
        example=("facilityName", "first")).reset_index(), on="nkey")
    print(f"E-PRTR CO2 firms (named): {len(firm):,}")

    sup = pd.read_parquet(SUP_CACHE)
    print(f"procurement suppliers (cached): {len(sup):,}")
    m = firm.merge(sup, on="nkey", how="inner", suffixes=("_eprtr", "_proc"))
    m = m[m["n_contracts"] >= 3]
    print(f"MATCHED firms (>=3 contracts): {len(m):,}  (contracts {int(m['n_contracts'].sum()):,})")

    m["log_co2"] = np.log(m["co2_t"].clip(lower=1))
    res = {"n_eprtr_firms": int(len(firm)), "n_matched": int(len(m)),
           "matched_contracts": int(m["n_contracts"].sum())}
    if len(m) >= 30:
        rho, p = stats.spearmanr(m["sb_rate"], m["log_co2"])
        res["overall_spearman_sb_vs_logco2"] = {"rho": float(rho), "p": float(p)}
        # within E-PRTR sector + size control (n facilities)
        big = m[m["sector"].notna()].copy()
        big = big[big.groupby("sector")["sector"].transform("size") >= 5]
        if len(big) >= 30:
            for c in ["log_co2", "sb_rate"]:
                big[c + "_dm"] = big[c] - big.groupby("sector")[c].transform("mean")
            big["logF"] = np.log(big["n_fac"].clip(lower=1))
            big["logF_dm"] = big["logF"] - big.groupby("sector")["logF"].transform("mean")
            rho_w, p_w = stats.spearmanr(big["sb_rate_dm"], big["log_co2_dm"])
            pc = partial_corr(big["sb_rate_dm"], big["log_co2_dm"], big["logF_dm"])
            n = len(big); t = pc * np.sqrt((n - 3) / (1 - pc**2))
            pcp = float(2 * stats.t.sf(abs(t), n - 3))
            res["within_sector_uncontrolled"] = {"rho": float(rho_w), "p": float(p_w), "n": n}
            res["within_sector_size_controlled"] = {"partial_rho": float(pc), "p": pcp,
                                                     "control": "log(n_facilities)", "n": n}
            print(f"  overall SB vs logCO2: rho={rho:+.3f} (p={p:.2e})")
            print(f"  within-sector uncontrolled: rho={rho_w:+.3f} (p={p_w:.3f}), n={n}")
            print(f"  within-sector + SIZE-CONTROLLED: partial rho={pc:+.3f} (p={pcp:.2e})")
        res["top_matches"] = (m.sort_values("co2_t", ascending=False)
                              [["example_proc", "example_eprtr", "co2_t", "sb_rate", "n_contracts", "sector"]]
                              .head(15).round(2).to_dict("records"))
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
