"""
The core NC test: within a tender, does the GREENER bidder win?

From eForms full bid sets, for every tender that names >=2 bidders, flag each bidder as
"green" (matched to a validated science-based climate target [SBTi] or, secondarily, an EU
ETS/E-PRTR emitter record). A conditional (fixed-effects) logit of winning on greenness, with
tender fixed effects, asks whether---holding the tender constant---the bidder with a climate
commitment is more or less likely to win, and whether that rises with the number of bidders
(the 'contestability selects greening' mechanism).

Positive coefficient = competition selects greener winners (confirms the thesis dynamically).
Null/negative = it does not (GPP cannot ride on contestability alone). Either is publishable.

Usage: python within_tender_green_wins.py results/eforms_competition/*.jsonl
"""
import glob, json, re, sys, zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.discrete.conditional_models import ConditionalLogit

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "Data"
LEGAL = re.compile(r"\b(GMBH|AG|SE|SA|SPA|SRL|LTD|LIMITED|PLC|BV|NV|OY|OYJ|AB|AS|APS|SP ?Z ?OO|"
                   r"SARL|SAS|GROUP|GROUPE|HOLDING|KFT|ZRT|DOO|EOOD|AD|INC|CORP|CO|COMPANY|KG|"
                   r"MBH|SCA|SNC|KORLATOLT|FELELOSSEGU|TARSASAG|NYRT|BT)\b")
PUNCT = re.compile(r"[^A-Z0-9 ]"); WS = re.compile(r"\s+")
def norm(s):
    s = PUNCT.sub(" ", str(s).upper()); s = LEGAL.sub(" ", s); return WS.sub(" ", s).strip()


def load_green():
    keys = set()
    def add(n):
        k = norm(n)
        if len(k) >= 4: keys.add(k)
    try:
        sb = pd.read_csv(DATA / "external" / "sbti_companies.csv")
        col = next((c for c in sb.columns if "name" in c.lower()), sb.columns[0])
        for v in sb[col].dropna().unique(): add(v)
    except Exception as e: print("SBTi warn", str(e)[:50])
    try:
        with zipfile.ZipFile(DATA / "eutl_data.zip") as z:
            for t, c in [("account_holder.csv", "name"), ("installation.csv", "parentCompany")]:
                d = pd.read_csv(z.open(t), usecols=[c], low_memory=False)
                for v in d[c].dropna().unique(): add(v)
    except Exception as e: print("EUTL warn", str(e)[:50])
    return keys


def main():
    files = []
    for a in sys.argv[1:]:
        files += glob.glob(a)
    green = load_green()
    rows = []
    for f in files:
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            if r["n_distinct_bidders"] < 2:
                continue
            seen = {}
            for b in r["bidders"]:
                if b["name"]:
                    seen.setdefault(norm(b["name"]), b)
            if len(seen) < 2:
                continue
            tid = f"{f}:{id(r)}:{r['winner_name']}"
            nb = len(seen)
            for k, b in seen.items():
                rows.append({"tender": tid, "won": int(bool(b["won"])),
                             "green": int(k in green), "nbid": nb,
                             "cpv": r["cpv"], "value": b["value"]})
    df = pd.DataFrame(rows)
    # keep tenders that have a recorded winner and within-group variation in green
    g = df.groupby("tender")
    keep = g["won"].transform("sum").eq(1) & g["green"].transform("nunique").ge(2)
    d = df[keep].copy()
    res = {"n_tenders_total": int(df["tender"].nunique()),
           "n_tenders_identified": int(d["tender"].nunique()),
           "n_bidder_rows": int(len(d)),
           "green_share_of_bidders": float(df["green"].mean()),
           "green_share_of_winners": float(df.loc[df.won == 1, "green"].mean())}
    # descriptive: among identified tenders, how often does a green bidder win
    if res["n_tenders_identified"] >= 5:
        won_green = d.loc[d.won == 1, "green"].mean()
        base = d.groupby("tender")["green"].mean().mean()   # avg green share within identified tenders
        res["P_winner_green_identified"] = float(won_green)
        res["baseline_green_share_identified"] = float(base)
    # conditional logit: won ~ green | tender FE
    try:
        m = ConditionalLogit(d["won"], d[["green"]], groups=d["tender"]).fit(disp=False)
        b, se = float(m.params["green"]), float(m.bse["green"])
        res["clogit_green_coef"] = b; res["clogit_green_se"] = se
        res["clogit_green_p"] = float(m.pvalues["green"])
        res["clogit_odds_ratio"] = float(np.exp(b))
        res["clogit_OR_ci95"] = [float(np.exp(b - 1.96*se)), float(np.exp(b + 1.96*se))]
    except Exception as e:
        res["clogit_error"] = str(e)[:120]
    # MECHANISM: does the green edge rise with competition? green x log(pool size) | tender FE
    try:
        d2 = d.copy(); d2["green_x_logn"] = d2["green"] * np.log(d2["nbid"])
        mm = ConditionalLogit(d2["won"], d2[["green", "green_x_logn"]], groups=d2["tender"]).fit(disp=False)
        res["mechanism_green_x_logpool"] = {
            "interaction_coef": float(mm.params["green_x_logn"]),
            "interaction_se": float(mm.bse["green_x_logn"]),
            "interaction_p": float(mm.pvalues["green_x_logn"])}
    except Exception as e:
        res["mechanism_error"] = str(e)[:120]
    # KEY (continuous, non-arbitrary): does the green-wins effect scale with sector carbon intensity?
    INT = {"03":0.85,"09":1.20,"14":1.20,"15":0.65,"18":0.45,"19":0.40,"22":0.55,"24":0.90,"30":0.30,
     "31":0.40,"32":0.15,"33":0.30,"34":0.45,"35":0.60,"38":0.28,"39":0.30,"42":0.35,"43":0.30,"44":0.75,
     "45":0.50,"48":0.10,"50":0.20,"55":0.35,"60":0.85,"63":0.45,"64":0.20,"65":0.60,"66":0.08,"70":0.12,
     "71":0.12,"72":0.10,"73":0.12,"75":0.20,"77":0.85,"79":0.15,"80":0.15,"85":0.25,"90":0.55,"92":0.20,"98":0.20}
    dc = d.copy(); dc["carbon"] = dc["cpv"].map(INT); dc = dc.dropna(subset=["carbon"])
    dc["green_x_carbon"] = dc["green"] * dc["carbon"]
    try:
        mc = ConditionalLogit(dc["won"], dc[["green", "green_x_carbon"]], groups=dc["tender"]).fit(disp=False)
        bi, sei = float(mc.params["green_x_carbon"]), float(mc.bse["green_x_carbon"])
        res["green_x_carbon_intensity"] = {"interaction_coef": bi, "se": sei,
            "p": float(mc.pvalues["green_x_carbon"]),
            "reading": "positive = greener bidder wins MORE in higher-carbon tenders (the thesis mechanism)"}
    except Exception as e:
        res["carbon_interaction_error"] = str(e)[:100]
    # high-carbon subset with CI + robustness by signal source
    HIC = {"09","14","24","44","45","60","65","77","90","42","43","34","35","03","24"}
    for label, sub in [("highcarbon", d[d["cpv"].isin(HIC)]), ("lowcarbon", d[~d["cpv"].isin(HIC)])]:
        if sub["tender"].nunique() >= 30:
            try:
                ms = ConditionalLogit(sub["won"], sub[["green"]], groups=sub["tender"]).fit(disp=False)
                bb, ss = float(ms.params["green"]), float(ms.bse["green"])
                res[f"{label}_subset"] = {"n_tenders": int(sub["tender"].nunique()),
                    "green_OR": float(np.exp(bb)), "OR_ci95": [float(np.exp(bb-1.96*ss)), float(np.exp(bb+1.96*ss))],
                    "p": float(ms.pvalues["green"])}
            except Exception as e:
                res[f"{label}_error"] = str(e)[:80]
    OUT = ROOT / "results" / "eforms_competition" / "within_tender_green_wins.json"
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))
    if "clogit_green_coef" in res:
        d_ = "MORE" if res["clogit_green_coef"] > 0 else "LESS"
        print(f"\n=> within a tender, the climate-committed/emitter bidder is {d_} likely to win "
              f"(OR={res['clogit_odds_ratio']:.2f}, p={res['clogit_green_p']:.3f}); "
              f"{res['n_tenders_identified']} identified tenders. "
              f"{'PROOF-OF-CONCEPT (one month) - scale before concluding.' }")


if __name__ == "__main__":
    main()
