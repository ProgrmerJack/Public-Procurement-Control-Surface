"""
Falsifiable governance-contingency test (desk review M2).

The manuscript's interpretive rule is currently sign-flexible: a negative premium
is read as governance success, a positive premium as the "Brown Monopoly" awaiting
reform, so any sign confirms the theory. M2 asks for an EX-ANTE, sign-predicting
rule grounded in a measured institutional variable, plus a stated configuration
that would REFUTE it.

Ex-ante rule (pre-registered here):
  H1: Across countries, the single-bidder carbon premium is DECREASING in
      institutional quality. Operationalized: corr(premium_c, RuleOfLaw_c) < 0,
      one-sided, with |rho| materially different from 0 (we pre-set a refutation
      band: the rule is NOT supported if the correlation is >= 0 OR is
      statistically indistinguishable from 0 at alpha=0.05).

  Refuting configuration (stated in advance):
    - rho >= 0  (better-governed countries have MORE positive premiums), OR
    - p > 0.05  (no detectable monotonic governance gradient).
  Either outcome refutes the claim that governance quality predicts the sign.

RuleOfLaw = World Bank WGI Rule of Law 2018 point estimate (~[-2.5, 2.5]).
NOTE: values below are WGI 2018 estimates entered for this test; replace with the
official WGI download (info.worldbank.org/governance/wgi) for the final version.
The test is a rank (Spearman) correlation, robust to small value errors.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
PARQUET = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
OUT = ROOT / "results" / "audit" / "falsifiable_governance_test.json"

# WGI Rule of Law 2018 point estimates (provisional; see note above).
WGI_RULE_OF_LAW_2018 = {
    "FI": 2.05, "SE": 1.95, "NO": 2.00, "DK": 1.95, "NL": 1.85, "LU": 1.85,
    "AT": 1.80, "DE": 1.62, "IE": 1.55, "GB": 1.55, "BE": 1.42, "FR": 1.42,
    "EE": 1.25, "PT": 1.12, "ES": 1.00, "SI": 1.00, "CZ": 1.00, "LT": 0.95,
    "LV": 0.82, "PL": 0.55, "SK": 0.55, "HU": 0.52, "RO": 0.48, "IT": 0.30,
    "HR": 0.30, "GR": 0.28, "BG": 0.05, "CH": 1.95, "IS": 1.70,
}


def main():
    df = pq.read_table(PARQUET, columns=[
        "country", "single_bidder", "carbon_intensity_kg_usd"]).to_pandas()
    df = df[df["country"] != "CO"].dropna(subset=["carbon_intensity_kg_usd"])

    rows = []
    for c, g in df.groupby("country"):
        sb = g.loc[g["single_bidder"], "carbon_intensity_kg_usd"].mean()
        mb = g.loc[~g["single_bidder"], "carbon_intensity_kg_usd"].mean()
        if pd.notna(sb) and pd.notna(mb) and mb > 0 and c in WGI_RULE_OF_LAW_2018:
            rows.append({"country": c, "premium_pct": 100 * (sb - mb) / mb,
                         "n": len(g), "rol": WGI_RULE_OF_LAW_2018[c]})
    d = pd.DataFrame(rows)

    rho_s, p_s = stats.spearmanr(d["rol"], d["premium_pct"])
    r_p, p_p = stats.pearsonr(d["rol"], d["premium_pct"])
    # one-sided p for negative association
    p_s_one = p_s / 2 if rho_s < 0 else 1 - p_s / 2
    p_p_one = p_p / 2 if r_p < 0 else 1 - p_p / 2

    supported = (rho_s < 0) and (p_s_one < 0.05)
    res = {
        "ex_ante_rule": "corr(premium, RuleOfLaw) < 0 (better governance -> more negative premium)",
        "refuting_configuration": "rho >= 0 OR one-sided p > 0.05",
        "n_countries": int(len(d)),
        "spearman_rho": float(rho_s), "spearman_p_two_sided": float(p_s),
        "spearman_p_one_sided_negative": float(p_s_one),
        "pearson_r": float(r_p), "pearson_p_one_sided_negative": float(p_p_one),
        "rule_supported": bool(supported),
        "verdict": ("SUPPORTED: governance quality predicts a more-negative premium"
                    if supported else
                    "REFUTED / NOT SUPPORTED: no significant negative governance gradient"),
        "country_table": d.sort_values("rol").to_dict(orient="records"),
    }
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")

    print("FALSIFIABLE GOVERNANCE-CONTINGENCY TEST (M2)")
    print("=" * 60)
    print(f"  N countries: {len(d)}")
    print(f"  Spearman rho(premium, RuleOfLaw) = {rho_s:+.3f} "
          f"(one-sided p={p_s_one:.3f})")
    print(f"  Pearson  r  (premium, RuleOfLaw) = {r_p:+.3f} "
          f"(one-sided p={p_p_one:.3f})")
    print(f"\n  Ex-ante rule: better governance -> MORE NEGATIVE premium (rho<0)")
    print(f"  VERDICT: {res['verdict']}")
    print(f"\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
