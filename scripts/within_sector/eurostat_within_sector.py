import pyarrow.parquet as pq
import csv, json, collections
from pathlib import Path
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]

cpv_to_nace = {
    "03": "A",
    "09": "B",
    "14": "C13-C15",
    "15": "C10-C12",
    "16": "A02",
    "18": "C13-C15",
    "19": "C13-C15",
    "22": "C17",
    "24": "C20",
    "30": "C29_C30",
    "31": "C26",
    "32": "C26",
    "33": "C21",
    "34": "C29_C30",
    "35": "C25",
    "37": "C28",
    "38": "C31_C32",
    "39": "C31_C32",
    "42": "C28",
    "43": "C28",
    "44": "C24",
    "45": "F",
    "48": "J62_J63",
    "50": "H50",
    "51": "H51",
    "55": "I",
    "60": "H49",
    "63": "H52",
    "64": "J58",
    "66": "K",
    "70": "J62_J63",
    "71": "M71",
    "72": "J62_J63",
    "73": "M72",
    "74": "M69_M70",
    "75": "O",
    "76": "M69_M70",
    "77": "M69_M70",
    "79": "N79",
    "80": "P",
    "85": "Q",
    "90": "E",
    "92": "R",
    "98": "M69_M70",
}
exio_to_nace = {
    "Agriculture": "A",
    "Chemicals": "C20",
    "Computer equipment": "C26",
    "Computer services": "J62_J63",
    "Construction": "F",
    "Education": "P",
    "Electrical equipment": "C27",
    "Financial services": "K",
    "Food products": "C10-C12",
    "Furniture": "C31_C32",
    "Health services": "Q",
    "Hotels": "I",
    "Land transport": "H49",
    "Leather": "C13-C15",
    "Machinery": "C28",
    "Metal products": "C24",
    "Mining": "B",
    "Motor vehicles": "C29_C30",
    "Office machinery": "C26",
    "Other business services": "M69_M70",
    "Other manufacturing": "C31_C32",
    "Other services": "M69_M70",
    "Paper": "C17",
    "Petroleum": "C19",
    "Pharmaceuticals": "C21",
    "Post and telecommunications": "J61",
    "Public administration": "O",
    "Publishing": "J58",
    "Rubber and plastics": "C22",
    "Security services": "N80",
    "Textiles": "C13-C15",
    "Transport equipment": "C29_C30",
    "Water transport": "H50",
    "Wood products": "C16",
    "Non-metallic minerals": "C23",
    "Architectural services": "M71",
}

intensities = {}
with open(ROOT / "Data" / "processed" / "eurostat_carbon_intensities.csv", "r") as f:
    for row in csv.DictReader(f):
        intensities[(row["country"], row["nace"], row["year"])] = float(
            row["intensity_kg_eur"]
        )

table = pq.read_table(
    ROOT / "Data" / "processed" / "gprd_with_carbon.parquet",
    columns=[
        "country",
        "year",
        "cpv_division",
        "exiobase_sector",
        "single_bidder",
        "value_eur",
        "n_bidders",
    ],
)
countries = table.column("country").to_pylist()
years_raw = table.column("year").to_pylist()
cpvs = table.column("cpv_division").to_pylist()
exios = table.column("exiobase_sector").to_pylist()
sb_col = table.column("single_bidder").to_pylist()
N = len(countries)

years_int = []
for y in years_raw:
    try:
        years_int.append(int(float(y)))
    except:
        years_int.append(None)

cmap = {"GR": "EL"}
eu_set = {
    "AT",
    "BE",
    "BG",
    "HR",
    "CY",
    "CZ",
    "DK",
    "EE",
    "FI",
    "FR",
    "DE",
    "GR",
    "HU",
    "IE",
    "IT",
    "LV",
    "LT",
    "LU",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "SK",
    "SI",
    "ES",
    "SE",
    "GB",
    "NO",
    "CH",
}

eurostat_ci = [None] * N
nace_assigned = [None] * N
for i in range(N):
    c = countries[i]
    y = years_int[i]
    cpv = cpvs[i]
    exio = exios[i]
    if not c or y is None:
        continue
    eu_c = cmap.get(c, c)
    nace = cpv_to_nace.get(cpv) if cpv else None
    if not nace and exio:
        nace = exio_to_nace.get(exio)
    if not nace:
        continue
    nace_assigned[i] = nace
    ys = str(y)
    key = (eu_c, nace, ys)
    if key in intensities:
        eurostat_ci[i] = intensities[key]
        continue
    parent = nace[0] if len(nace) > 1 else nace
    key2 = (eu_c, parent, ys)
    if key2 in intensities:
        eurostat_ci[i] = intensities[key2]
        continue
    found = False
    for dy in range(1, 4):
        for offset in [str(y - dy), str(y + dy)]:
            for n_try in [nace, parent]:
                if (eu_c, n_try, offset) in intensities:
                    eurostat_ci[i] = intensities[(eu_c, n_try, offset)]
                    found = True
                    break
            if found:
                break
        if found:
            break

# WITHIN-COUNTRY-WITHIN-SECTOR PREMIUM
print("=== WITHIN-COUNTRY-WITHIN-SECTOR ANALYSIS ===")
groups = collections.defaultdict(lambda: {"sb": [], "mb": []})
for i in range(N):
    if eurostat_ci[i] is None or countries[i] not in eu_set:
        continue
    nace = nace_assigned[i]
    if not nace:
        continue
    key = (countries[i], nace)
    grp = "sb" if sb_col[i] else "mb"
    groups[key][grp].append(eurostat_ci[i])

group_premiums = []
sig_count = 0
total_tested = 0
neg_sig = 0
pos_sig = 0

for key, d in groups.items():
    if len(d["sb"]) >= 30 and len(d["mb"]) >= 30:
        total_tested += 1
        sb_m = np.mean(d["sb"])
        mb_m = np.mean(d["mb"])
        if mb_m > 0:
            prem = (sb_m - mb_m) / mb_m * 100
            t, p = stats.ttest_ind(d["sb"], d["mb"], equal_var=False)
            group_premiums.append(
                {"key": key, "premium": prem, "p": p, "n": len(d["sb"]) + len(d["mb"])}
            )
            if p < 0.05:
                sig_count += 1
                if prem < 0:
                    neg_sig += 1
                else:
                    pos_sig += 1

print(f"Groups with 30+ per side: {total_tested}")
print(f"Significant at p<0.05: {sig_count} ({100 * sig_count / total_tested:.1f}%)")
print(f"  Negative (SB < MB): {neg_sig}")
print(f"  Positive (SB > MB): {pos_sig}")

wt_prems = [(g["premium"], g["n"]) for g in group_premiums]
avg_p = sum(p * n for p, n in wt_prems) / sum(n for _, n in wt_prems)
print(f"Weighted avg within-group premium: {avg_p:.1f}%")

# Top 10 largest groups
top10 = sorted(group_premiums, key=lambda x: x["n"], reverse=True)[:10]
print("\nTop 10 largest country-sector groups:")
for g in top10:
    c, nace = g["key"]
    sig = "*" if g["p"] < 0.05 else ""
    print(f"  {c}-{nace}: {g['premium']:+.1f}% (n={g['n']:,}, p={g['p']:.3f}){sig}")

# TEMPORAL
print("\n=== TEMPORAL CARBON TRENDS (Eurostat) ===")
yearly = collections.defaultdict(lambda: {"sb": [], "mb": []})
for i in range(N):
    if eurostat_ci[i] is None or countries[i] not in eu_set:
        continue
    y = years_int[i]
    if y and 2012 <= y <= 2023:
        grp = "sb" if sb_col[i] else "mb"
        yearly[y][grp].append(eurostat_ci[i])

print("Year    SB_mean   MB_mean   Prem%   N_SB       N_MB")
for y in sorted(yearly.keys()):
    d = yearly[y]
    if len(d["sb"]) > 100 and len(d["mb"]) > 100:
        sm = np.mean(d["sb"])
        mm = np.mean(d["mb"])
        p = (sm - mm) / mm * 100 if mm else 0
        print(
            f"{y}    {sm:.4f}   {mm:.4f}  {p:+.1f}%  {len(d['sb']):>9,}  {len(d['mb']):>9,}"
        )

# CARBON DID
print("\n=== CARBON DID (Eurostat) ===")
pre_sb, pre_mb, post_sb, post_mb = [], [], [], []
for i in range(N):
    if eurostat_ci[i] is None or countries[i] not in eu_set:
        continue
    y = years_int[i]
    if y and 2012 <= y <= 2015:
        if sb_col[i]:
            pre_sb.append(eurostat_ci[i])
        else:
            pre_mb.append(eurostat_ci[i])
    elif y and 2017 <= y <= 2023:
        if sb_col[i]:
            post_sb.append(eurostat_ci[i])
        else:
            post_mb.append(eurostat_ci[i])

pre_prem = np.mean(pre_sb) - np.mean(pre_mb)
post_prem = np.mean(post_sb) - np.mean(post_mb)
did_eff = post_prem - pre_prem
print(f"Pre-reform SB-MB gap: {pre_prem:.4f} kg/EUR")
print(f"Post-reform SB-MB gap: {post_prem:.4f} kg/EUR")
print(f"DiD (narrowing of gap): {did_eff:.4f} kg/EUR")
print(f"Pre: SB={len(pre_sb):,}, MB={len(pre_mb):,}")
print(f"Post: SB={len(post_sb):,}, MB={len(post_mb):,}")

# Test significance of DiD
# Combine into one big array with dummies
n_all = len(pre_sb) + len(pre_mb) + len(post_sb) + len(post_mb)
print(f"Total obs for DiD: {n_all:,}")

# Simple 2x2 test: is post premium significantly different from pre premium?
pre_all_sb = np.array(pre_sb)
pre_all_mb = np.array(pre_mb)
post_all_sb = np.array(post_sb)
post_all_mb = np.array(post_mb)

# Bootstrap DiD confidence interval
np.random.seed(42)
n_boot = 1000
boot_dids = []
for _ in range(n_boot):
    ps = np.random.choice(pre_all_sb, size=min(10000, len(pre_all_sb)))
    pm = np.random.choice(pre_all_mb, size=min(10000, len(pre_all_mb)))
    qs = np.random.choice(post_all_sb, size=min(10000, len(post_all_sb)))
    qm = np.random.choice(post_all_mb, size=min(10000, len(post_all_mb)))
    boot_did = (np.mean(qs) - np.mean(qm)) - (np.mean(ps) - np.mean(pm))
    boot_dids.append(boot_did)

ci_lo = np.percentile(boot_dids, 2.5)
ci_hi = np.percentile(boot_dids, 97.5)
boot_p = 2 * min(np.mean(np.array(boot_dids) > 0), np.mean(np.array(boot_dids) < 0))
print(f"Bootstrap DiD: {np.mean(boot_dids):.4f} [{ci_lo:.4f}, {ci_hi:.4f}]")
print(f"Bootstrap p-value: {boot_p:.4f}")

# Save
results = {
    "within_sector": {
        "groups_tested": total_tested,
        "significant_p05": sig_count,
        "pct_significant": round(100 * sig_count / total_tested, 1),
        "negative_significant": neg_sig,
        "positive_significant": pos_sig,
        "weighted_avg_premium_pct": round(avg_p, 1),
    },
    "carbon_did_eurostat": {
        "pre_premium_kg_eur": round(float(pre_prem), 4),
        "post_premium_kg_eur": round(float(post_prem), 4),
        "did_effect_kg_eur": round(float(did_eff), 4),
        "bootstrap_ci_lo": round(float(ci_lo), 4),
        "bootstrap_ci_hi": round(float(ci_hi), 4),
        "bootstrap_p": round(float(boot_p), 4),
        "n_total": n_all,
    },
}
output_path = (
    ROOT / "results" / "within_sector" / "eurostat_within_sector_analysis.json"
)
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nSaved to {output_path.relative_to(ROOT)}")
