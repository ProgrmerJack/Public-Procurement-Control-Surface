"""
Gate G2: of the eForms single-award notices that name >=2 bidders, how many have >=2 bidders
matchable to a firm-level "greenness" signal? Greenness signals (broadest first):
  SBTi   - validated science-based climate target (26k firms; clean, not size-confounded)
  EUTL   - EU ETS operator (verified emissions; ~20k named companies)
  E-PRTR - industrial facility with CO2 (~3.4k facilities)
Match bidders by normalised legal name. Report bidder-level match rates and, decisively, the
number of notices with >=2 matched bidders (where the within-tender 'does the greener/cleaner
bidder win' test is identified).

Usage: python g2_match_greenness.py results/eforms_competition/2025-6_bids.jsonl
"""
import json, re, sys, zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "Data"
LEGAL = re.compile(r"\b(GMBH|AG|SE|SA|SPA|SRL|LTD|LIMITED|PLC|BV|NV|OY|OYJ|AB|AS|APS|"
                   r"SP ?Z ?OO|SARL|SAS|GROUP|GROUPE|HOLDING|KFT|ZRT|DOO|EOOD|AD|INC|CORP|"
                   r"CO|COMPANY|KG|MBH|SCA|SNC|KORLATOLT|FELELOSSEGU|TARSASAG|NYRT|BT)\b")
PUNCT = re.compile(r"[^A-Z0-9 ]")
WS = re.compile(r"\s+")


def norm(s):
    s = str(s).upper()
    s = PUNCT.sub(" ", s)
    s = LEGAL.sub(" ", s)
    return WS.sub(" ", s).strip()


def load_greenness():
    keys = {}                                          # nkey -> set of signals
    def add(name, sig):
        k = norm(name)
        if len(k) >= 4:
            keys.setdefault(k, set()).add(sig)
    # SBTi
    try:
        sb = pd.read_csv(DATA / "external" / "sbti_companies.csv", usecols=lambda c: True)
        col = next((c for c in sb.columns if "name" in c.lower()), sb.columns[0])
        for v in sb[col].dropna().unique():
            add(v, "SBTi")
    except Exception as e:
        print("SBTi load warn:", str(e)[:60])
    # EUTL account holders + installation parent companies
    try:
        with zipfile.ZipFile(DATA / "eutl_data.zip") as z:
            ah = pd.read_csv(z.open("account_holder.csv"), usecols=["name"], low_memory=False)
            for v in ah["name"].dropna().unique():
                add(v, "EUTL")
            inst = pd.read_csv(z.open("installation.csv"), usecols=["parentCompany"], low_memory=False)
            for v in inst["parentCompany"].dropna().unique():
                add(v, "EUTL")
    except Exception as e:
        print("EUTL load warn:", str(e)[:60])
    # E-PRTR facility names
    try:
        f = (DATA / "raw" / "eea_t_ied-eprtr_p_2007-2023_v15_r00" / "User-friendly-CSV"
             / "F1_4_Air_Releases_Facilities.csv")
        ep = pd.read_csv(f, usecols=["facilityName", "Pollutant"], low_memory=False)
        ep = ep[ep["Pollutant"].astype(str).str.contains("Carbon dioxide", case=False, na=False)]
        for v in ep["facilityName"].dropna().unique():
            add(v, "EPRTR")
    except Exception as e:
        print("E-PRTR load warn:", str(e)[:60])
    return keys


def main():
    keys = load_greenness()
    print(f"greenness registry: {len(keys):,} distinct normalised firm names "
          f"(SBTi+EUTL+E-PRTR)")
    recs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
    elig = [r for r in recs if r["n_distinct_bidders"] >= 2]
    n_bidders = n_matched = 0
    n_ge2_matched = 0
    sig_counts = {"SBTi": 0, "EUTL": 0, "EPRTR": 0}
    sector_eligible = {}
    for r in elig:
        seen = {}
        for b in r["bidders"]:
            if not b["name"]:
                continue
            seen.setdefault(norm(b["name"]), b)
        matched = []
        for k in seen:
            if k in keys:
                matched.append(k)
                for s in keys[k]:
                    sig_counts[s] += 1
        n_bidders += len(seen)
        n_matched += len(matched)
        if len(matched) >= 2:
            n_ge2_matched += 1
            sector_eligible[r["cpv"]] = sector_eligible.get(r["cpv"], 0) + 1
    print(f"test-eligible notices (>=2 named bidders): {len(elig):,}")
    print(f"distinct bidders in them: {n_bidders:,}; matched to a greenness signal: "
          f"{n_matched:,} ({n_matched/max(n_bidders,1):.1%})")
    print(f"signal hits: {sig_counts}")
    print(f"NOTICES WITH >=2 MATCHED BIDDERS (test-identified): {n_ge2_matched}")
    print(f"  -> per-month rate; eForms era ~32 months => ~{n_ge2_matched*32:,} projected")
    if sector_eligible:
        print("  top CPV divisions among them:",
              dict(sorted(sector_eligible.items(), key=lambda kv: -kv[1])[:8]))


if __name__ == "__main__":
    main()
