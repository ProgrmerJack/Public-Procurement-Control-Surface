"""
Firm-level emissions test via EUTL (EU Transaction Log) <-> procurement supplier
name matching. Investigates whether the within-sector carbon channel -- reported
NULL in the manuscript using E-PRTR facility size-matching -- can be revisited with
direct operator-level VERIFIED emissions matched to procurement winners by name.

Data (all already in repo):
  Data/eutl_data.zip :: installation.csv (NACE, operator), account.csv (link),
                        account_holder.csv (company name, LEI), compliance.csv
                        (verified emissions per installation-year)
  Data/processed/gprd_master.parquet :: supplier_name, single_bidder, cpv_division

Output: results/within_sector/eutl_supplier_firm_match.json
"""
import json, re, zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
EUTL = ROOT / "Data" / "eutl_data.zip"
MASTER = ROOT / "Data" / "processed" / "gprd_master.parquet"
OUT = ROOT / "results" / "within_sector" / "eutl_supplier_firm_match.json"

LEGAL = re.compile(r"\b(GMBH|AG|SE|S\.?A\.?|S\.?P\.?A\.?|S\.?R\.?L\.?|LTD|LIMITED|PLC|"
                   r"B\.?V\.?|N\.?V\.?|OY|OYJ|AB|A/?S|APS|SP\.?\s?Z\.?\s?O\.?\s?O\.?|"
                   r"SARL|SAS|GROUP|GROUPE|HOLDING|KFT|ZRT|D\.?O\.?O\.?|EOOD|AD|"
                   r"INC|CORP|CO|COMPANY|KG|MBH|SCA|SNC)\b")
PUNCT = re.compile(r"[^A-Z0-9 ]")
WS = re.compile(r"\s+")


def norm(s):
    s = str(s).upper()
    s = PUNCT.sub(" ", s)
    s = LEGAL.sub(" ", s)
    s = WS.sub(" ", s).strip()
    return s


def load_eutl():
    with zipfile.ZipFile(EUTL) as z:
        inst = pd.read_csv(z.open("installation.csv"),
                           usecols=["id", "nace_id", "country_id", "parentCompany"],
                           low_memory=False)
        acc = pd.read_csv(z.open("account.csv"),
                          usecols=["installation_id", "accountHolder_id"], low_memory=False)
        ah = pd.read_csv(z.open("account_holder.csv"),
                         usecols=["id", "name"], low_memory=False)
        comp = pd.read_csv(z.open("compliance.csv"),
                           usecols=["installation_id", "year", "verified"], low_memory=False)
    comp["verified"] = pd.to_numeric(comp["verified"], errors="coerce")
    emis = (comp[comp["year"].between(2012, 2021) & (comp["verified"] > 0)]
            .groupby("installation_id")["verified"].mean().rename("emis_t"))
    # link installation -> account holder name
    acc = acc.dropna(subset=["installation_id"])
    acc = acc.merge(ah, left_on="accountHolder_id", right_on="id", how="left")
    holder = acc.groupby("installation_id")["name"].first().rename("holder")
    f = inst.merge(emis, left_on="id", right_index=True, how="inner")
    f = f.merge(holder, left_on="id", right_index=True, how="left")
    # firm display name: prefer account holder, else installation parentCompany
    f["firm"] = f["holder"].fillna(f["parentCompany"])
    f = f[f["firm"].notna()].copy()
    f["nkey"] = f["firm"].map(norm)
    f = f[f["nkey"].str.len() >= 4]
    # aggregate to firm level (sum emissions across a firm's installations; keep modal NACE)
    g = (f.groupby("nkey")
           .agg(emis_t=("emis_t", "sum"),
                n_install=("id", "size"),
                nace=("nace_id", lambda s: s.dropna().astype(str).str[:2].mode().iloc[0]
                      if s.dropna().size else None),
                example=("firm", "first")).reset_index())
    return g


SUP_CACHE = ROOT / "results" / "within_sector" / "_supplier_norm_cache.parquet"


def load_suppliers():
    if SUP_CACHE.exists():
        return pd.read_parquet(SUP_CACHE)
    df = pq.read_table(MASTER, columns=[
        "country", "supplier_name", "single_bidder", "cpv_division"]).to_pandas()
    sn = df["supplier_name"].astype(str)
    ok = sn.notna() & (sn.str.lower() != "nan") & (sn.str.strip() != "")
    df = df[ok & (df["country"] != "CO")].copy()
    df["nkey"] = df["supplier_name"].map(norm)
    df = df[df["nkey"].str.len() >= 4]
    g = (df.groupby("nkey")
           .agg(n_contracts=("single_bidder", "size"),
                sb_rate=("single_bidder", "mean"),
                cpv=("cpv_division", lambda s: s.dropna().astype(str).mode().iloc[0]
                     if s.dropna().size else None),
                example=("supplier_name", "first")).reset_index())
    SUP_CACHE.parent.mkdir(parents=True, exist_ok=True)
    g.to_parquet(SUP_CACHE)
    return g


def partial_corr(x, y, z):
    """Pearson partial correlation of x,y controlling for z."""
    x, y, z = np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)
    rxy = np.corrcoef(x, y)[0, 1]
    rxz = np.corrcoef(x, z)[0, 1]
    ryz = np.corrcoef(y, z)[0, 1]
    denom = np.sqrt((1 - rxz**2) * (1 - ryz**2))
    if denom == 0:
        return np.nan
    return (rxy - rxz * ryz) / denom


def main():
    print("loading EUTL firms..."); firms = load_eutl()
    print(f"  EUTL firms (named, with 2012-2021 verified emissions): {len(firms):,}")
    print("loading procurement suppliers..."); sup = load_suppliers()
    print(f"  EU procurement suppliers (distinct normalised names): {len(sup):,}")

    m = firms.merge(sup, on="nkey", how="inner", suffixes=("_eutl", "_proc"))
    m = m[m["n_contracts"] >= 3]            # require a small contract history
    print(f"\nMATCHED firms (>=3 contracts): {len(m):,}")
    print(f"  matched procurement contracts covered: {int(m['n_contracts'].sum()):,}")

    # firm-level within-sector test: does a firm's single-bidder win propensity
    # relate to its verified emissions, controlling for sector (NACE2) and size?
    m["log_emis"] = np.log(m["emis_t"].clip(lower=1))
    res = {
        "n_eutl_firms": int(len(firms)),
        "n_proc_suppliers": int(len(sup)),
        "n_matched_firms": int(len(m)),
        "matched_contracts": int(m["n_contracts"].sum()),
        "match_examples": m.sort_values("emis_t", ascending=False)
                            [["example_proc", "example_eutl", "emis_t", "sb_rate",
                              "n_contracts", "cpv", "nace"]].head(25)
                            .round(3).to_dict("records"),
    }

    if len(m) >= 30:
        # overall correlation: firm SB-rate vs log emissions
        rho, p = stats.spearmanr(m["sb_rate"], m["log_emis"])
        res["spearman_sbrate_vs_logemis"] = {"rho": float(rho), "p": float(p)}
        # split firms into high vs low SB propensity, compare emissions
        hi = m[m["sb_rate"] >= m["sb_rate"].median()]
        lo = m[m["sb_rate"] < m["sb_rate"].median()]
        t, pt = stats.ttest_ind(hi["log_emis"], lo["log_emis"], equal_var=False)
        res["emis_by_sb_propensity"] = {
            "high_sb_median_emis_t": float(hi["emis_t"].median()),
            "low_sb_median_emis_t": float(lo["emis_t"].median()),
            "logemis_ttest_t": float(t), "p": float(pt)}
        # within-NACE-sector: demean log emissions and SB-rate by NACE2, then correlate
        big = m[m["nace"].notna()].copy()
        big["nace_n"] = big.groupby("nace")["nace"].transform("size")
        big = big[big["nace_n"] >= 5]
        if len(big) >= 30:
            big["e_dm"] = big["log_emis"] - big.groupby("nace")["log_emis"].transform("mean")
            big["s_dm"] = big["sb_rate"] - big.groupby("nace")["sb_rate"].transform("mean")
            rho_w, p_w = stats.spearmanr(big["s_dm"], big["e_dm"])
            res["within_nace_spearman_sb_vs_emis"] = {
                "rho": float(rho_w), "p": float(p_w), "n_firms": int(len(big)),
                "n_sectors": int(big["nace"].nunique())}

            # --- SIZE CONTROL (the test that killed the E-PRTR result) ---
            # (a) partial correlation within-NACE, controlling firm size = log #installations
            big["logN"] = np.log(big["n_install"].clip(lower=1))
            big["n_dm"] = big["logN"] - big.groupby("nace")["logN"].transform("mean")
            pc = partial_corr(big["s_dm"], big["e_dm"], big["n_dm"])
            # significance of partial corr (t with n-3 df)
            n = len(big)
            tval = pc * np.sqrt((n - 3) / (1 - pc**2)) if abs(pc) < 1 else np.nan
            pc_p = float(2 * stats.t.sf(abs(tval), n - 3)) if np.isfinite(tval) else np.nan
            res["within_nace_partial_corr_size_controlled"] = {
                "partial_rho": float(pc), "p": pc_p, "control": "log(n_installations)",
                "n_firms": int(n)}
            # (b) emissions-per-installation (size-normalised) within NACE
            big["epi"] = np.log((big["emis_t"] / big["n_install"]).clip(lower=1))
            big["epi_dm"] = big["epi"] - big.groupby("nace")["epi"].transform("mean")
            rho_epi, p_epi = stats.spearmanr(big["s_dm"], big["epi_dm"])
            res["within_nace_sb_vs_emis_per_installation"] = {
                "rho": float(rho_epi), "p": float(p_epi)}
            # (c) stratify by firm-size tercile (n_install), within-NACE corr in each
            big["size_terc"] = pd.qcut(big["n_install"].rank(method="first"), 3,
                                       labels=["small", "mid", "large"])
            strat = {}
            for s, gg in big.groupby("size_terc", observed=True):
                if len(gg) >= 20:
                    r, pv = stats.spearmanr(gg["s_dm"], gg["e_dm"])
                    strat[str(s)] = {"rho": float(r), "p": float(pv), "n": int(len(gg))}
            res["within_nace_by_size_tercile"] = strat
        print(f"\nFirm SB-rate vs log(verified emissions): Spearman rho={rho:+.3f} (p={p:.3f})")
        print(f"  median emissions: high-SB firms {hi['emis_t'].median():,.0f} t vs "
              f"low-SB {lo['emis_t'].median():,.0f} t (log t-test p={pt:.3f})")
        if "within_nace_spearman_sb_vs_emis" in res:
            w = res["within_nace_spearman_sb_vs_emis"]
            print(f"  WITHIN-NACE (uncontrolled): rho={w['rho']:+.3f} (p={w['p']:.3f}), "
                  f"{w['n_firms']} firms / {w['n_sectors']} sectors")
        if "within_nace_partial_corr_size_controlled" in res:
            pc = res["within_nace_partial_corr_size_controlled"]
            print(f"  WITHIN-NACE + SIZE-CONTROLLED (partial corr | log #installations): "
                  f"rho={pc['partial_rho']:+.3f} (p={pc['p']:.3f})")
            epi = res["within_nace_sb_vs_emis_per_installation"]
            print(f"  WITHIN-NACE, emissions-per-installation: rho={epi['rho']:+.3f} (p={epi['p']:.3f})")
            print("  within-NACE by firm-size tercile:")
            for s, d in res["within_nace_by_size_tercile"].items():
                print(f"    {s:6s}: rho={d['rho']:+.3f} (p={d['p']:.3f}, n={d['n']})")
    # also save matched firm table for inspection
    m.to_csv(ROOT / "results" / "within_sector" / "eutl_matched_firms.csv", index=False)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved -> {OUT}")
    print("\nTop matched high-emitter suppliers:")
    for r in res["match_examples"][:12]:
        print(f"  {r['example_proc'][:38]:38s} ~ {str(r['example_eutl'])[:30]:30s} "
              f"{r['emis_t']:>12,.0f} t  SB={r['sb_rate']:.2f}  n={int(r['n_contracts'])}")


if __name__ == "__main__":
    main()
