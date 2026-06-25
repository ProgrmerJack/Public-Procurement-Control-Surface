"""
E-PRTR size-stratified comparison (publication plan Item 3).

The published "+65.3% higher CO2 in single-bidder contracts" compares ABSOLUTE
facility emissions, confounded with facility size (sole-source awards plausibly
go to larger plants). E-PRTR has no output denominator, so true intensity is not
computable; the plan's minimum-viable test is to STRATIFY by facility emission
size and ask whether the SB-vs-MB gap survives within strata.

Test: assign each matched facility to an emission decile (overall and within
sector); within each stratum compute the SB-vs-MB facility-CO2 premium; aggregate
a within-stratum weighted premium. If the gap collapses toward 0 within strata,
the +65.3% was a size-composition artifact (paper stays competition-first). If it
persists, single-bidding selects dirtier facilities of comparable scale (a
measured within-sector carbon link -> NS-grade).

Output: results/within_sector/eprtr_size_stratified_intensity.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eprtr_procurement_matching as M  # noqa

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "within_sector" / "eprtr_size_stratified_intensity.json"


def weighted_within_stratum_premium(d, strat_col):
    """Within-stratum SB-vs-MB premium, contract-weighted across strata."""
    rows = []
    for s, g in d.groupby(strat_col):
        sb = g.loc[g.single_bidder == True, "co2_mean_kg"]
        mb = g.loc[g.single_bidder == False, "co2_mean_kg"]
        if len(sb) < 5 or len(mb) < 5 or mb.mean() <= 0:
            continue
        prem = (sb.mean() - mb.mean()) / mb.mean() * 100
        rows.append({"stratum": str(s), "n": len(g), "premium_pct": prem,
                     "sb_mean": float(sb.mean()), "mb_mean": float(mb.mean()),
                     "n_sb": len(sb), "n_mb": len(mb)})
    if not rows:
        return None, []
    r = pd.DataFrame(rows)
    wprem = float(np.average(r["premium_pct"], weights=r["n"]))
    return wprem, rows


def main():
    eprtr = M.load_eprtr_co2()
    proc = M.load_procurement_suppliers()
    matches = M.match_eprtr_to_procurement(eprtr, proc)

    md = pd.DataFrame(matches)[["procurement_name_norm", "country", "co2_mean_kg",
                                "exio_sector", "eprtr_sector"]]
    md = md.rename(columns={"procurement_name_norm": "name_norm",
                            "country": "match_country"})
    md = md.drop_duplicates(subset=["match_country", "name_norm"])
    pm = proc.merge(md, on=["match_country", "name_norm"], how="inner")
    pm = pm.dropna(subset=["co2_mean_kg", "single_bidder"])
    pm["single_bidder"] = pm["single_bidder"].astype(bool)

    res = {"n_matched_contracts": int(len(pm)),
           "n_sb": int(pm.single_bidder.sum()),
           "n_mb": int((~pm.single_bidder).sum())}

    # 1. Reproduce the published ABSOLUTE (size-confounded) premium
    sb = pm.loc[pm.single_bidder, "co2_mean_kg"]
    mb = pm.loc[~pm.single_bidder, "co2_mean_kg"]
    t, p = stats.ttest_ind(sb, mb, equal_var=False)
    res["absolute_premium"] = {
        "premium_pct": float((sb.mean() - mb.mean()) / mb.mean() * 100),
        "sb_mean_kg": float(sb.mean()), "mb_mean_kg": float(mb.mean()),
        "t": float(t), "p": float(p)}

    # 2. Size-stratified: emission deciles (overall)
    pm["co2_decile"] = pd.qcut(pm["co2_mean_kg"].rank(method="first"), 10,
                               labels=False)
    w_dec, dec_rows = weighted_within_stratum_premium(pm, "co2_decile")
    res["within_emission_decile"] = {
        "weighted_premium_pct": w_dec, "strata": dec_rows}

    # 3. Size-stratified within sector x decile
    pm["sector_decile"] = (pm["exio_sector"].astype(str) + "|"
                           + pm["co2_decile"].astype(str))
    w_sd, sd_rows = weighted_within_stratum_premium(pm, "sector_decile")
    res["within_sector_x_decile"] = {
        "weighted_premium_pct": w_sd, "n_strata": len(sd_rows)}

    # 4. Log-CO2 difference (size-robust): regress log(co2) on SB + decile FE
    pm["log_co2"] = np.log(pm["co2_mean_kg"].clip(lower=1))
    # within-decile demeaning of SB and log_co2
    pm["sb_f"] = pm.single_bidder.astype(float)
    for col in ["log_co2", "sb_f"]:
        pm[col + "_dm"] = pm[col] - pm.groupby("co2_decile")[col].transform("mean")
    denom = float((pm["sb_f_dm"] ** 2).sum())
    beta_log = float((pm["sb_f_dm"] * pm["log_co2_dm"]).sum() / denom) if denom > 0 else None
    res["within_decile_log_co2_coef"] = beta_log  # ~pct gap in log points

    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")

    print("\n" + "=" * 64)
    print("E-PRTR SIZE-STRATIFIED TEST (Item 3)")
    print("=" * 64)
    print(f"  matched contracts: {res['n_matched_contracts']:,} "
          f"(SB {res['n_sb']:,} / MB {res['n_mb']:,})")
    a = res["absolute_premium"]
    print(f"\n  [1] Absolute (published, size-confounded): {a['premium_pct']:+.1f}% "
          f"(t={a['t']:.1f}, p={a['p']:.2g})")
    print(f"  [2] Within emission-decile weighted premium: "
          f"{res['within_emission_decile']['weighted_premium_pct']:+.1f}%")
    print(f"  [3] Within sector x decile weighted premium: "
          f"{res['within_sector_x_decile']['weighted_premium_pct']:+.1f}% "
          f"({res['within_sector_x_decile']['n_strata']} strata)")
    print(f"  [4] Within-decile log-CO2 SB coef: {beta_log:+.3f} log-points "
          f"(~{(np.exp(beta_log)-1)*100:+.1f}%)")
    verdict = ("PERSISTS -> size-robust selection signal (NS-grade)"
               if (w_dec is not None and w_dec > 10) else
               "COLLAPSES -> +65.3% was size composition; stay competition-first")
    print(f"\n  VERDICT: {verdict}")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
