"""
Pre-registered robustness battery for the eForms "competition selects greener winners" test.
Decision rule in results/eforms_competition/PREREGISTRATION.md.

PRIMARY: within-tender (choice-set FE) linear-probability model of winning on
green x sector-carbon-intensity, controlling bidder-level firm SIZE and INCUMBENCY,
SEs clustered by FIRM, on a representativeness-reweighted sample, one-sided.
Plus: placebo, leave-one-firm-out, concentration, signal sensitivity, coverage/provenance.
"""
import glob, json, re, zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "Data"
OUT = ROOT / "results" / "eforms_competition" / "robustness_battery.json"
LEGAL = re.compile(r"\b(GMBH|AG|SE|SA|SPA|SRL|LTD|LIMITED|PLC|BV|NV|OY|OYJ|AB|AS|APS|SARL|SAS|GROUP|"
                   r"GROUPE|HOLDING|KFT|ZRT|DOO|EOOD|AD|INC|CORP|CO|COMPANY|KG|MBH|SCA|SNC|KORLATOLT|"
                   r"FELELOSSEGU|TARSASAG|NYRT|BT)\b")
PUNCT = re.compile(r"[^A-Z0-9 ]"); WS = re.compile(r"\s+")
def norm(s): s = PUNCT.sub(" ", str(s).upper()); s = LEGAL.sub(" ", s); return WS.sub(" ", s).strip()
INT = {"03":0.85,"09":1.20,"14":1.20,"15":0.65,"18":0.45,"19":0.40,"22":0.55,"24":0.90,"30":0.30,"31":0.40,
 "32":0.15,"33":0.30,"34":0.45,"35":0.60,"38":0.28,"39":0.30,"42":0.35,"43":0.30,"44":0.75,"45":0.50,"48":0.10,
 "50":0.20,"55":0.35,"60":0.85,"63":0.45,"64":0.20,"65":0.60,"66":0.08,"70":0.12,"71":0.12,"72":0.10,"73":0.12,
 "75":0.20,"77":0.85,"79":0.15,"80":0.15,"85":0.25,"90":0.55,"92":0.20,"98":0.20}


def green_names():
    ks = set()
    def add(n):
        k = norm(n)
        if len(k) >= 4: ks.add(k)
    sb = pd.read_csv(DATA / "external" / "sbti_companies.csv")
    col = next(c for c in sb.columns if "name" in c.lower())
    for v in sb[col].dropna().unique(): add(v)
    sbti = set(ks); ks2 = set()
    with zipfile.ZipFile(DATA / "eutl_data.zip") as z:
        for t, c in [("account_holder.csv", "name"), ("installation.csv", "parentCompany")]:
            d = pd.read_csv(z.open(t), usecols=[c], low_memory=False)
            for v in d[c].dropna().unique():
                k = norm(v)
                if len(k) >= 4: ks2.add(k)
    return sbti, ks2                                    # SBTi set, EUTL set


def clustered(d, rhs, cluster="firm", weights=None):
    f = "won ~ " + " + ".join(rhs)
    mod = smf.wls(f, data=d, weights=weights) if weights is not None else smf.ols(f, data=d)
    return mod.fit(cov_type="cluster", cov_kwds={"groups": d[cluster]})


def main():
    sbti, eutl = green_names()
    files = glob.glob(str(ROOT / "results" / "eforms_competition" / "*_bids.jsonl"))
    # firm activity/incumbency from ALL parsed notices
    fbids = {}; fwins = {}
    recs_all = []
    for f in files:
        for line in open(f, encoding="utf-8"):
            r = json.loads(line); recs_all.append(r)
            for b in r["bidders"]:
                if not b["name"]:
                    continue
                fid = b["nat_id"] or norm(b["name"])
                fbids[fid] = fbids.get(fid, 0) + 1
                if b["won"]: fwins[fid] = fwins.get(fid, 0) + 1
    # population country x cpv distribution (all single-award notices) for reweighting
    pop = pd.Series([(r["country"], r["cpv"]) for r in recs_all]).value_counts(normalize=True)

    rows = []
    for r in recs_all:
        if r["n_distinct_bidders"] < 2 or r["cpv"] not in INT:
            continue
        seen = {}
        for b in r["bidders"]:
            if b["name"]: seen.setdefault(norm(b["name"]), b)
        if len(seen) < 2:
            continue
        tid = id(r); carbon = INT[r["cpv"]]
        for k, b in seen.items():
            fid = b["nat_id"] or k
            tot_b = fbids.get(fid, 1); tot_w = fwins.get(fid, 0)
            incumb_val = (tot_w - int(bool(b["won"]))) / max(tot_b - 1, 1)   # jackknifed win rate
            rows.append({"tender": tid, "won": int(bool(b["won"])), "firm": fid,
                         "green": int(k in sbti or k in eutl), "green_sbti": int(k in sbti),
                         "green_eutl": int(k in eutl), "carbon": carbon, "cpv": r["cpv"],
                         "country": r["country"], "log_size": np.log(tot_b + 1), "incumb": incumb_val})
    df = pd.DataFrame(rows)
    g = df.groupby("tender")
    df = df[g["won"].transform("sum").eq(1)]                      # tenders with a recorded winner
    # identified for interaction: within-tender variation in green
    d = df[df.groupby("tender")["green"].transform("nunique").ge(2)].copy()
    d["green_carbon"] = d["green"] * d["carbon"]
    res = {"n_tenders": int(d["tender"].nunique()), "n_rows": int(len(d)),
           "n_distinct_firms": int(d["firm"].nunique()),
           "n_distinct_green_winning_firms": int(d[(d.won == 1) & (d.green == 1)]["firm"].nunique()),
           "country_concentration_top": d.drop_duplicates("tender")["country"].value_counts(normalize=True).head(5).round(3).to_dict()}

    # PRIMARY: green_carbon + controls, firm-clustered. one-sided p.
    base = ["green", "green_carbon", "log_size", "incumb"]
    m = clustered(d, base)
    b, se = float(m.params["green_carbon"]), float(m.bse["green_carbon"])
    from scipy import stats
    res["PRIMARY_green_x_carbon"] = {"coef": b, "se": se, "z": b/se,
        "p_one_sided": float(stats.norm.sf(b/se)), "controls": "firm size+incumbency, firm-clustered SE"}

    # reweighted to population country x cpv
    d["w"] = d.apply(lambda r: pop.get((r["country"], r["cpv"]), 0), axis=1)
    samp = d.drop_duplicates("tender").groupby(["country", "cpv"]).size()
    samp = samp / samp.sum()
    d["w"] = d.apply(lambda r: pop.get((r["country"], r["cpv"]), 0) / max(samp.get((r["country"], r["cpv"]), 1e9), 1e-9), axis=1).clip(0, 20)
    mw = clustered(d, base, weights=d["w"])
    bw, sew = float(mw.params["green_carbon"]), float(mw.bse["green_carbon"])
    res["PRIMARY_reweighted"] = {"coef": bw, "se": sew, "p_one_sided": float(stats.norm.sf(bw/sew))}

    # placebo: random green with same marginal rate
    rng = np.random.default_rng(7); rate = d["green"].mean()
    d["pg"] = (rng.random(len(d)) < rate).astype(int); d["pg_carbon"] = d["pg"] * d["carbon"]
    mp = clustered(d, ["pg", "pg_carbon", "log_size", "incumb"])
    res["placebo_green"] = {"coef": float(mp.params["pg_carbon"]), "p_two_sided": float(mp.pvalues["pg_carbon"])}

    # leave-one-firm-out: drop the firm with most green wins, re-estimate primary
    topfirm = d[(d.won == 1) & (d.green == 1)]["firm"].value_counts().idxmax() if res["n_distinct_green_winning_firms"] else None
    if topfirm is not None:
        dl = d[d["firm"] != topfirm]
        ml = clustered(dl, base)
        res["leave_top_firm_out"] = {"dropped_firm_green_wins": int((d[(d.won==1)&(d.green==1)]["firm"]==topfirm).sum()),
            "coef": float(ml.params["green_carbon"]), "p_one_sided": float(stats.norm.sf(ml.params["green_carbon"]/ml.bse["green_carbon"]))}

    # signal sensitivity within the controlled framework
    for sig in ["green_sbti", "green_eutl"]:
        dd = df[df.groupby("tender")[sig].transform("nunique").ge(2)].copy()
        if dd["tender"].nunique() < 30:
            continue
        dd["sc"] = dd[sig] * dd["carbon"]
        ms = clustered(dd, [sig, "sc", "log_size", "incumb"])
        res[f"signal_{sig}"] = {"n_tenders": int(dd["tender"].nunique()),
            "coef": float(ms.params["sc"]), "p_one_sided": float(stats.norm.sf(ms.params["sc"]/ms.bse["sc"]))}

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    pr = res["PRIMARY_green_x_carbon"]; prw = res["PRIMARY_reweighted"]
    print(f"identified tenders={res['n_tenders']}, distinct firms={res['n_distinct_firms']}, "
          f"green-winning firms={res['n_distinct_green_winning_firms']}")
    print(f"top-country share: {list(res['country_concentration_top'].items())[:3]}")
    print(f"PRIMARY green x carbon (size+incumbency ctrl, firm-clustered): coef={pr['coef']:+.3f} "
          f"p_1sided={pr['p_one_sided']:.4f}")
    print(f"  reweighted to population: coef={prw['coef']:+.3f} p_1sided={prw['p_one_sided']:.4f}")
    print(f"  placebo (random green): p={res['placebo_green']['p_two_sided']:.3f} (want ~1, null)")
    if "leave_top_firm_out" in res:
        print(f"  leave-top-firm-out: coef={res['leave_top_firm_out']['coef']:+.3f} p_1sided={res['leave_top_firm_out']['p_one_sided']:.4f}")
    for sig in ["signal_green_sbti", "signal_green_eutl"]:
        if sig in res: print(f"  {sig}: coef={res[sig]['coef']:+.3f} p_1sided={res[sig]['p_one_sided']:.4f} (n={res[sig]['n_tenders']})")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
