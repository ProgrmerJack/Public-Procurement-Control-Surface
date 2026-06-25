"""
Deep verification of EVERY quantitative claim in descriptor.tex and
supplementary_information.tex, recomputed from the DEPOSITED files and results.
Prints CLAIM | CLAIMED | COMPUTED | PASS/FAIL.
"""
import json, csv
from pathlib import Path
import pyarrow.parquet as pq
import pandas as pd, numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEP = ROOT / "deposit"
R = ROOT / "results"
OK = FAIL = 0
def chk(name, claimed, computed, ok):
    global OK, FAIL
    OK += ok; FAIL += (not ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n        claimed={claimed} | computed={computed}")
def close(a, b, tol=0.01): return abs(a-b) <= tol

print("="*70, "\nLOADING DEPOSITED CONTRACT FILE\n", "="*70)
df = pq.read_table(DEP/"ted_awards_2012_2023.parquet").to_pandas()
ted = df[~df["country"].isin(["CO","GB"])]
print(f"rows={len(df):,}  cols={list(df.columns)}")

# ---- Part A counts ----
chk("M1 21.6M contracts", "21,612,129", len(df), len(df)==21612129)
chk("M4 territories=27, TED=25", "27 / 25", f"{df.country.nunique()} / {ted.country.nunique()}",
    df.country.nunique()==27 and ted.country.nunique()==25)
sc = df.source.value_counts().to_dict()
chk("M5 source TED", "12,820,226", sc.get("TED"), sc.get("TED")==12820226)
chk("M5 source SECOP", "7,973,196", sc.get("SECOP"), sc.get("SECOP")==7973196)
chk("M5 source ContractsFinder", "818,707", sc.get("ContractsFinder"), sc.get("ContractsFinder")==818707)
nb = df.n_bidders
chk("M11a populated bidder-count", "15,538,905", int(nb.notna().sum()), int(nb.notna().sum())==15538905)
chk("M11b >=1 all", "7.4M", int((nb>=1).sum()), close((nb>=1).sum()/1e6, 7.41, 0.05))
chk("M11b >=1 EU/EEA", "7.0M", int((ted.n_bidders>=1).sum()), close((ted.n_bidders>=1).sum()/1e6,6.97,0.05))
chk("zeros (8.1M)", "8.1M", int((nb==0).sum()), close((nb==0).sum()/1e6,8.13,0.05))
euctx = len(df[df.country!="CO"])
chk("EU-context N (ex CO) 13.6M", "13,638,933", euctx, euctx==13638933)

# naive full-field single-bidder by year (TED)
full = ted.groupby("year")["single_bidder"].mean()
claim_full = [0.218,0.172,0.166,0.174,0.170,0.161]
got_full = [round(full.get(y),3) for y in range(2015,2021)]
chk("M7 naive full-field series 2015-20", claim_full, got_full, all(close(a,b,0.002) for a,b in zip(claim_full,got_full)))
chk("M6 naive overall ~18%", "0.178", round(ted.single_bidder.mean(),3), close(ted.single_bidder.mean(),0.178,0.003))
# observed-bid single-bidder by year (TED)
obs = ted[ted.n_bidders>=1]
ser = obs.groupby("year").apply(lambda g:(g.n_bidders==1).mean())
claim_obs=[0.303,0.277,0.305,0.335,0.330,0.325]
got_obs=[round(ser.get(y),3) for y in range(2015,2021)]
chk("M9 observed-bid series 2015-20", claim_obs, got_obs, all(close(a,b,0.002) for a,b in zip(claim_obs,got_obs)))
chk("M8 observed overall ~0.32", "0.32", round((obs.n_bidders==1).mean(),3), close((obs.n_bidders==1).mean(),0.325,0.01))
# 2018 artifact & extract rows ex-CO
exco = df[df.country!="CO"]
rows18 = (exco.year==2018).sum()
chk("M12 2018 extract rows (ex-CO)", "5,793,300", int(rows18), int(rows18)==5793300)
chk("M12 2018 inflation x", "24.9", round(rows18/232989,1), close(rows18/232989,24.9,0.1))
exrows={y:int((exco.year==y).sum()) for y in range(2016,2021)}
chk("M14 extract rows ex-CO 2016-20", "506762/762360/5793300/983068/994896",
    list(exrows.values()), list(exrows.values())==[506762,762360,5793300,983068,994896])
# Colombia
co=df[df.country=="CO"]
chk("M28 Colombia 0-bidder %", "98.4%", round(100*(co.n_bidders==0).mean(),1), close(100*(co.n_bidders==0).mean(),98.4,0.1))
# supplier id placeholder -- column not in deposited file; check source gprd
g2=pq.read_table(ROOT/"Data"/"processed"/"gprd_with_carbon.parquet",columns=["supplier_id"]).to_pandas()
sid=g2.supplier_id.astype(str).str.strip().str.lower()
ph=(sid.isin(["nan","none",""])|g2.supplier_id.isna()).mean()
chk("M29 placeholder supplier-id ~55%", "54.5-54.8%", round(100*ph,1), close(100*ph,54.5,0.5))

# ---- carbon ----
cw=list(csv.DictReader(open(ROOT/"Data"/"reference"/"cpv_exiobase_crosswalk.csv",encoding="utf-8")))
chk("M18 crosswalk entries", "40", len(cw), len(cw)==40)
cvw=df["carbon_kg_per_usd"].dropna()
chk("M19 carbon range min", "0.08", round(cvw.min(),3), close(cvw.min(),0.08,0.001))
chk("M19 carbon range max", "1.20", round(cvw.max(),3), close(cvw.max(),1.20,0.001))
cw_set=set(r["cpv_division"] for r in cw)
unmapped=df[~df.cpv_division.isin(cw_set)]["carbon_kg_per_usd"].dropna().unique()
chk("M19 unmapped default 0.20", "0.20", list(np.round(unmapped,3)), len(unmapped)==1 and close(unmapped[0],0.20,0.001))
v=json.load(open(R/"within_sector"/"exiobase_eurostat_validation_v2.json"))
chk("M20 carbon rho", "0.82", round(v["spearman"]["rho"],3), close(v["spearman"]["rho"],0.82,0.005))
chk("M20 carbon n_sectors", "34", v["n_sectors"], v["n_sectors"]==34)

# ---- panel ----
pan=pq.read_table(DEP/"competition_panel_country_cpv_month.parquet").to_pandas()
chk("M16 panel rows", "44,998", len(pan), len(pan)==44998)
chk("M16 panel countries", "31", pan.country.nunique(), pan.country.nunique()==31)
chk("M16 panel cpv", "45", pan.cpv_division.nunique(), pan.cpv_division.nunique()==45)

# ---- transposition / eutl ----
tr=list(csv.DictReader(open(DEP/"transposition_dates.csv",encoding="utf-8")))
chk("M32 transposition rows", "25", len(tr), len(tr)==25)
eu=pd.read_csv(DEP/"eutl_matched_firms.csv")
chk("S-12 eutl rows", "1,105", len(eu), len(eu)==1105)

# ---- eForms ----
nlines=sum(1 for _ in open(DEP/"eforms_bids_2024_2025.jsonl",encoding="utf-8"))
chk("M21 eForms notices", "302,555", nlines, nlines==302555)
w=json.load(open(R/"eforms_competition"/"within_tender_green_wins.json"))
chk("M23 funnel n_tenders_total", "23,216", w["n_tenders_total"], w["n_tenders_total"]==23216)
chk("M23 identified tenders", "2,601", w["n_tenders_identified"], w["n_tenders_identified"]==2601)
chk("M24 OR", "1.02", round(w["clogit_odds_ratio"],2), close(w["clogit_odds_ratio"],1.02,0.005))
chk("M24 OR CI", "[0.94,1.12]", [round(x,2) for x in w["clogit_OR_ci95"]],
    close(w["clogit_OR_ci95"][0],0.94,0.005) and close(w["clogit_OR_ci95"][1],1.12,0.005))
chk("M24 OR p", "0.62", round(w["clogit_green_p"],2), close(w["clogit_green_p"],0.62,0.005))
bv=json.load(open(R/"eforms_competition"/"BATTERY_VERDICT.json"))
perm=bv["INDEPENDENT_PERMUTATION_CHECK"]["ALL"]
chk("M27 permutation p", "0.165", "0.165 in ALL string", "0.165" in perm)
chk("M25 reweight p=0.75", "0.75", "0.75 in failures", "0.75" in bv["failures"]["1_reweighting"])
chk("M26 placebo 15/50", "15/50", "15/50 in failures", "15/50" in bv["failures"]["3_placebo_invalid_spec"])

# eForms coverage by country (recompute)
import collections
cc=collections.defaultdict(lambda:[0,0,0]); tot=[0,0,0]
for line in open(DEP/"eforms_bids_2024_2025.jsonl",encoding="utf-8"):
    d=json.loads(line); nb2=d.get("n_distinct_bidders") or 0; ge2=1 if nb2>=2 else 0
    for k in (cc[d.get("country","?")],tot): k[0]+=1;k[1]+=ge2;k[2]+=nb2
chk("M22 eForms %>=2 bidders", "7.7%", round(100*tot[1]/tot[0],1), close(100*tot[1]/tot[0],7.7,0.1))
se=cc["SWE"]
chk("S-11 Sweden %>=2", "75.5%", round(100*se[1]/se[0],1), close(100*se[1]/se[0],75.5,0.2))
chk("S-11 mean distinct", "1.24", round(tot[2]/tot[0],2), close(tot[2]/tot[0],1.24,0.01))

print("\n"+"="*70)
print(f"TOTAL: {OK} PASS, {FAIL} FAIL")
print("="*70)
