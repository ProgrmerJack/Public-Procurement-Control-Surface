"""
A2: Do less-contested procurement markets select fewer climate-committed firms?

Match procurement winners by normalised name to the Science Based Targets initiative
(SBTi) company list (firms with validated/committed emission-reduction targets). For
matched suppliers, test whether a firm's single-bidder win propensity relates to
whether it holds a science-based target -- i.e. whether competition selects greener
(target-setting) firms. Complements the EUTL/E-PRTR emissions result with a
forward-looking firm-climate-ambition measure.

Inputs: Data/external/sbti_companies.csv ; cached supplier table (_supplier_norm_cache.parquet)
Output: results/within_sector/sbti_supplier_match.json
"""
import json, re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
SBTI = ROOT / "Data" / "external" / "sbti_companies.csv"
SUP_CACHE = ROOT / "results" / "within_sector" / "_supplier_norm_cache.parquet"
OUT = ROOT / "results" / "within_sector" / "sbti_supplier_match.json"

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


def main():
    sb = pd.read_csv(SBTI, low_memory=False)
    sb["nkey"] = sb["company_name"].map(norm)
    sb = sb[sb["nkey"].str.len() >= 4].drop_duplicates("nkey")
    sbti_keys = set(sb["nkey"])
    print(f"SBTi companies (normalised): {len(sbti_keys):,}")

    sup = pd.read_parquet(SUP_CACHE)        # nkey, n_contracts, sb_rate, cpv, example
    print(f"procurement suppliers (cached): {len(sup):,}")
    sup = sup[sup["n_contracts"] >= 3].copy()
    sup["has_sbti"] = sup["nkey"].isin(sbti_keys).astype(int)
    n_match = int(sup["has_sbti"].sum())
    print(f"suppliers (>=3 contracts) matched to SBTi: {n_match:,} / {len(sup):,}")

    res = {"n_sbti": len(sbti_keys), "n_suppliers": int(len(sup)),
           "n_matched_sbti": n_match}
    if n_match >= 30:
        # do SBTi (target-setting) suppliers win less via single-bidding?
        sb_yes = sup[sup["has_sbti"] == 1]["sb_rate"]
        sb_no = sup[sup["has_sbti"] == 0]["sb_rate"]
        t, p = stats.ttest_ind(sb_yes, sb_no, equal_var=False)
        # within-sector logistic-style: correlation of has_sbti with sb_rate, sector-demeaned
        s = sup[sup["cpv"].notna()].copy()
        s["cpv"] = s["cpv"].astype(str)
        s = s[s.groupby("cpv")["cpv"].transform("size") >= 20]
        s["sb_dm"] = s["sb_rate"] - s.groupby("cpv")["sb_rate"].transform("mean")
        s["sbti_dm"] = s["has_sbti"] - s.groupby("cpv")["has_sbti"].transform("mean")
        rho_w, p_w = stats.spearmanr(s["sb_dm"], s["sbti_dm"])
        res.update({
            "sbti_supplier_mean_sb_rate": float(sb_yes.mean()),
            "non_sbti_supplier_mean_sb_rate": float(sb_no.mean()),
            "welch_t": float(t), "welch_p": float(p),
            "within_sector_spearman_sbti_vs_sb": {"rho": float(rho_w), "p": float(p_w),
                                                  "n": int(len(s))},
        })
        print(f"  mean single-bidder rate: SBTi firms {sb_yes.mean():.3f} vs "
              f"non-SBTi {sb_no.mean():.3f} (Welch p={p:.2e})")
        print(f"  within-sector SBTi vs single-bidder: rho={rho_w:+.3f} (p={p_w:.3f})")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
