"""
Fix 3: does the (rebuilt) reform effect differ by sector carbon intensity? Tests the
paper's former title claim ("...in High-Carbon Procurement") as treatment-effect
heterogeneity. Builds country x carbon-tercile x month single-bidding panels from the
raw-TED monthly aggregates and runs the not-yet-treated estimator per tercile, with a
high-minus-low contrast (country block bootstrap).

Output: results/causal_id/fix3_carbon_heterogeneity.json
"""
import glob, json, os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "causal_id" / "ted_monthly_raw"
OUT = ROOT / "results" / "causal_id" / "fix3_carbon_heterogeneity.json"

INTENSITY = {"03":0.85,"09":1.20,"14":1.20,"15":0.65,"18":0.45,"19":0.40,"22":0.55,"24":0.90,
 "30":0.30,"31":0.40,"32":0.15,"33":0.30,"34":0.45,"35":0.60,"38":0.28,"39":0.30,"42":0.35,
 "43":0.30,"44":0.75,"45":0.50,"48":0.10,"50":0.20,"55":0.35,"60":0.85,"63":0.45,"64":0.20,
 "65":0.60,"66":0.08,"70":0.12,"71":0.12,"72":0.10,"73":0.12,"75":0.20,"77":0.85,"79":0.15,
 "80":0.15,"85":0.25,"90":0.55,"92":0.20,"98":0.20}
TRANSP = {"DK":(2015,12),"HU":(2015,10),"DE":(2016,2),"FR":(2016,3),"CZ":(2016,4),"IT":(2016,4),
 "HR":(2016,6),"LV":(2016,5),"BE":(2016,6),"GR":(2016,8),"BG":(2016,10),"EE":(2017,7),"ES":(2017,11),
 "LU":(2018,4),"LT":(2016,4),"NL":(2016,4),"PL":(2016,4),"PT":(2016,4),"SK":(2016,4),"FI":(2016,4),
 "SE":(2016,4),"IE":(2016,4),"AT":(2017,6),"SI":(2018,6),"NO":(2017,1)}
COHORT = {c: y*12+(m-1) for c,(y,m) in TRANSP.items()}
EXCLUDE = {"GB","UK","CH"}


def nyt(panel, cohort, emax=24, pre=6):
    p = panel.copy(); p["g"] = p["country"].map(cohort)
    cells = []
    for g in sorted(set(cohort.values())):
        tr = p[p["g"] == g]; ncoh = tr["country"].nunique()
        base = tr[(tr["ym"] >= g-pre) & (tr["ym"] < g)]
        if not len(base): continue
        tb = np.average(base["sb_rate"], weights=base["n"])
        for e in range(emax+1):
            t = g+e; ctrl = p[p["g"] > t]
            cb, ct, tt = ctrl[ctrl["ym"]==g-1+0+(g-pre-(g-pre))], None, None
            cb = ctrl[(ctrl["ym"]>=g-pre)&(ctrl["ym"]<g)]; ct = ctrl[ctrl["ym"]==t]; tt = tr[tr["ym"]==t]
            if not(len(tt) and len(cb) and len(ct)): continue
            att = ((np.average(tt["sb_rate"],weights=tt["n"])-tb)
                   -(np.average(ct["sb_rate"],weights=ct["n"])-np.average(cb["sb_rate"],weights=cb["n"])))
            cells.append((att*100, ncoh))
    if not cells: return np.nan
    c = pd.DataFrame(cells, columns=["att","w"]); return float(np.average(c["att"],weights=c["w"]))


def main():
    frames = [pd.read_csv(f, dtype={"cpv_division":str}) for f in glob.glob(str(RAW/"*.csv"))]
    raw = pd.concat([d for d in frames if len(d)], ignore_index=True)
    raw["ym"] = raw["ym"].astype(str).str[:4].astype(int)*12 + (raw["ym"].astype(str).str[4:6].astype(int)-1)
    raw = raw[~raw["country"].isin(EXCLUDE) & raw["country"].isin(COHORT)]
    raw["carbon"] = raw["cpv_division"].map(INTENSITY)
    raw = raw.dropna(subset=["carbon"])
    # carbon terciles across CPV divisions (value-neutral: by sector carbon)
    qs = raw.drop_duplicates("cpv_division")["carbon"].quantile([1/3, 2/3]).values
    def terc(c): return "low" if c <= qs[0] else ("mid" if c <= qs[1] else "high")
    raw["terc"] = raw["carbon"].map(terc)

    res = {"tercile_cutoffs": [float(qs[0]), float(qs[1])], "att_by_tercile": {}}
    panels = {}
    for t in ["low","mid","high"]:
        sub = raw[raw["terc"]==t]
        panel = (sub.groupby(["country","ym"]).agg(sb=("sb","sum"),n=("n","sum")).reset_index())
        panel["sb_rate"] = panel["sb"]/panel["n"]; panel = panel[panel["n"]>=20]
        panels[t] = panel
        res["att_by_tercile"][t] = nyt(panel, COHORT)
    # high-low contrast with country block bootstrap
    rng = np.random.default_rng(5); cs = list(COHORT); diffs=[]
    for _ in range(400):
        pick = rng.choice(cs, len(cs), replace=True)
        def rebuild(panel):
            fr={}; cmap={}; out=[]
            for i,c in enumerate(pick):
                s=panel[panel["country"]==c].copy(); a=f"{c}_{i}"; s["country"]=a; cmap[a]=COHORT[c]; out.append(s)
            return pd.concat(out) if out else panel, cmap
        ph,cmaph=rebuild(panels["high"]); pl,cmapl=rebuild(panels["low"])
        ah=nyt(ph,cmaph); al=nyt(pl,cmapl)
        if not(np.isnan(ah) or np.isnan(al)): diffs.append(ah-al)
    diffs=np.array(diffs)
    res["high_minus_low_contrast"]={"diff_pp":float(res["att_by_tercile"]["high"]-res["att_by_tercile"]["low"]),
        "boot_ci95":[float(np.percentile(diffs,2.5)),float(np.percentile(diffs,97.5))],
        "boot_n":len(diffs)}
    OUT.write_text(json.dumps(res,indent=2,default=str),encoding="utf-8")
    print("carbon tercile cutoffs:",[round(q,2) for q in qs])
    for t in ["low","mid","high"]:
        print(f"  {t}-carbon ATT = {res['att_by_tercile'][t]:+.2f} pp")
    hl=res["high_minus_low_contrast"]
    print(f"high-low contrast = {hl['diff_pp']:+.2f} pp, 95% CI [{hl['boot_ci95'][0]:+.2f},{hl['boot_ci95'][1]:+.2f}]")
    print(f"Saved -> {OUT}")


if __name__ == "__main__":
    main()
