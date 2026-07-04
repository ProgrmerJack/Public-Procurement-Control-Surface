"""
Deep verification of the quantitative claims in descriptor.tex and
supplementary_information.tex, recomputed from the DEPOSITED files and the
deterministic result JSONs. Prints CLAIM | CLAIMED | COMPUTED | PASS/FAIL.

This recomputes the numbers from the data; it does not re-run the original
pipeline (see verify_original.py for that).
"""
import json, csv, collections
from pathlib import Path
import pyarrow.parquet as pq
import pandas as pd, numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEP = ROOT / "deposit"
R = ROOT / "results"
RESD = R / "descriptor"
OK = FAIL = 0
def chk(name, claimed, computed, ok):
    global OK, FAIL
    OK += ok; FAIL += (not ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n        claimed={claimed} | computed={computed}")
def close(a, b, tol=0.01): return abs(a-b) <= tol

print("="*70, "\nLOADING DEPOSITED CONTRACT FILE\n", "="*70)
df = pq.read_table(DEP/"procurement_awards_2012_2023.parquet").to_pandas()
ted = df[df.source == "TED"]
print(f"rows={len(df):,}  cols={list(df.columns)}")

# ---- Part A counts ----
chk("M1 total de-duplicated contracts", "16,968,922", len(df), len(df) == 16968922)
chk("M4 territories total / TED", "33 / 31", f"{df.country.nunique()} / {ted.country.nunique()}",
    df.country.nunique() == 33 and ted.country.nunique() == 31)
sc = df.source.value_counts().to_dict()
chk("M5 source TED", "8,177,019", sc.get("TED"), sc.get("TED") == 8177019)
chk("M5 source SECOP", "7,973,196", sc.get("SECOP"), sc.get("SECOP") == 7973196)
chk("M5 source ContractsFinder", "818,707", sc.get("ContractsFinder"), sc.get("ContractsFinder") == 818707)
nb = ted.n_bidders
chk("M11a TED bidder-count populated", "6,474,567", int(nb.notna().sum()), int(nb.notna().sum()) == 6474567)
chk("M11b TED n_bidders>=1", "6,467,956", int((nb >= 1).sum()), int((nb >= 1).sum()) == 6467956)
chk("TED zero-bidder rows", "6,611", int((nb == 0).sum()), int((nb == 0).sum()) == 6611)
euctx = len(df[df.source != "SECOP"])
chk("EU-context N (ex Colombia) ~9.0M", "8,995,726", euctx, euctx == 8995726)
sb_rate = (ted[ted.n_bidders >= 1].n_bidders == 1).mean()
chk("TED single-bidder rate (obs) ~30.8%", "0.308", round(sb_rate, 3), close(sb_rate, 0.308, 0.003))
wn = ted.winner_name.notna().mean()
chk("M29 winner_name coverage (TED) 84.6%", "0.846", round(wn, 3), close(wn, 0.846, 0.003))
fw = ted.is_framework.mean()
chk("M29b is_framework share (TED) 20.0%", "0.200", round(fw, 3), close(fw, 0.200, 0.003))

# released-file per-year TED award volumes (reconciliation; artifact eliminated)
per_year = ted.groupby("year").size()
claim_py = {2016: 489181, 2017: 612761, 2018: 673762, 2019: 770746, 2020: 847156}
got_py = {y: int(per_year.get(y, 0)) for y in claim_py}
chk("M13 released-file awards 2016-20", claim_py, got_py, got_py == claim_py)
chk("M13 2018 not an artifact (2.9x official)", "2.9", round(673762/232989, 1), close(673762/232989, 2.9, 0.1))

# ---- naive vs observed single-bidder series (from the deterministic panel rebuild) ----
val = json.loads((RESD/"partA_validation.json").read_text())
naive = [round(val["extract_full_field_single_bidder_by_year"][str(y)], 3) for y in range(2015, 2021)]
chk("M7 naive full-field series 2015-20", [0.218,0.172,0.166,0.174,0.170,0.161], naive,
    all(close(a, b, 0.002) for a, b in zip([0.218,0.172,0.166,0.174,0.170,0.161], naive)))
chk("M6 naive overall ~18%", "0.178", round(val["extract_overall_full_field_single_bidder"], 3),
    close(val["extract_overall_full_field_single_bidder"], 0.178, 0.004))
obs = [round(val["extract_observed_single_bidder_by_year"][str(y)], 3) for y in range(2015, 2021)]
chk("M9 observed-bid series 2015-20", [0.303,0.277,0.305,0.335,0.330,0.325], obs,
    all(close(a, b, 0.002) for a, b in zip([0.303,0.277,0.305,0.335,0.330,0.325], obs)))
chk("M8 rebuild overall 2017-20 ~0.32", "0.32", val["rebuild_overall_single_bidder_rate_2017_2020"],
    close(val["rebuild_overall_single_bidder_rate_2017_2020"], 0.325, 0.01))

# ---- Colombia (SECOP) 0/null-bidder share ----
co = df[df.source == "SECOP"]
zshare = (co.n_bidders.isna() | (co.n_bidders == 0)).mean()
chk("M28 SECOP 0/null-bidder %", "98.4%", round(100*zshare, 1), close(100*zshare, 98.4, 0.2))

# ---- carbon ----
cw = list(csv.DictReader(open(DEP/"cpv_exiobase_crosswalk.csv", encoding="utf-8")))
chk("M18 crosswalk entries", "40", len(cw), len(cw) == 40)
cvw = df["carbon_kg_per_usd"].dropna()
chk("M19 carbon range min", "0.08", round(cvw.min(), 3), close(cvw.min(), 0.08, 0.001))
chk("M19 carbon range max", "1.20", round(cvw.max(), 3), close(cvw.max(), 1.20, 0.001))
cw_set = set(int(r["cpv_division"]) for r in cw)
unmapped = df[~df.cpv_division.isin(cw_set)]["carbon_kg_per_usd"].dropna().unique()
chk("M19 unmapped default 0.20", "0.20", list(np.round(unmapped, 3)),
    len(unmapped) == 1 and close(unmapped[0], 0.20, 0.001))
v = json.load(open(R/"within_sector"/"exiobase_eurostat_validation_v2.json"))
chk("M20 carbon rho", "0.82", round(v["spearman"]["rho"], 3), close(v["spearman"]["rho"], 0.82, 0.005))
chk("M20 carbon n_sectors", "34", v["n_sectors"], v["n_sectors"] == 34)

# ---- panel ----
pan = pq.read_table(DEP/"competition_panel_country_cpv_month.parquet").to_pandas()
chk("M16 panel rows", "44,998", len(pan), len(pan) == 44998)
chk("M16 panel countries", "31", pan.country.nunique(), pan.country.nunique() == 31)
chk("M16 panel cpv", "45", pan.cpv_division.nunique(), pan.cpv_division.nunique() == 45)

# ---- transposition / eutl ----
tr = list(csv.DictReader(open(DEP/"transposition_dates.csv", encoding="utf-8")))
chk("M32 transposition rows", "25", len(tr), len(tr) == 25)
eu = pd.read_csv(DEP/"eutl_matched_firms.csv")
chk("S12 eutl rows", "1,105", len(eu), len(eu) == 1105)

# ---- eForms ----
nlines = sum(1 for _ in open(DEP/"eforms_bids_2024_2025.jsonl", encoding="utf-8"))
chk("M21 eForms notices", "302,555", nlines, nlines == 302555)
w = json.load(open(R/"eforms_competition"/"within_tender_green_wins.json"))
chk("M23 funnel n_tenders_total", "23,216", w["n_tenders_total"], w["n_tenders_total"] == 23216)
chk("M23 identified tenders", "2,601", w["n_tenders_identified"], w["n_tenders_identified"] == 2601)
chk("M24 OR", "1.02", round(w["clogit_odds_ratio"], 2), close(w["clogit_odds_ratio"], 1.02, 0.005))
chk("M24 OR CI", "[0.94,1.12]", [round(x, 2) for x in w["clogit_OR_ci95"]],
    close(w["clogit_OR_ci95"][0], 0.94, 0.005) and close(w["clogit_OR_ci95"][1], 1.12, 0.005))
chk("M24 OR p", "0.62", round(w["clogit_green_p"], 2), close(w["clogit_green_p"], 0.62, 0.005))
bv = json.load(open(R/"eforms_competition"/"BATTERY_VERDICT.json"))
chk("M27 permutation p", "0.165", "0.165 in ALL", "0.165" in bv["INDEPENDENT_PERMUTATION_CHECK"]["ALL"])
chk("M25 reweight p=0.75", "0.75", "0.75 in failures", "0.75" in bv["failures"]["1_reweighting"])
chk("M26 placebo 15/50", "15/50", "15/50 in failures", "15/50" in bv["failures"]["3_placebo_invalid_spec"])

cc = collections.defaultdict(lambda: [0, 0, 0]); tot = [0, 0, 0]
for line in open(DEP/"eforms_bids_2024_2025.jsonl", encoding="utf-8"):
    d = json.loads(line); nb2 = d.get("n_distinct_bidders") or 0; ge2 = 1 if nb2 >= 2 else 0
    for k in (cc[d.get("country", "?")], tot): k[0] += 1; k[1] += ge2; k[2] += nb2
chk("M22 eForms %>=2 bidders", "7.7%", round(100*tot[1]/tot[0], 1), close(100*tot[1]/tot[0], 7.7, 0.1))
chk("mean distinct bidders", "1.24", round(tot[2]/tot[0], 2), close(tot[2]/tot[0], 1.24, 0.01))

print("\n" + "="*70)
print(f"TOTAL: {OK} PASS, {FAIL} FAIL")
print("="*70)
