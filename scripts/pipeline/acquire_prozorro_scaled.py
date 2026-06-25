"""
Scaled ProZorro (Ukraine) acquisition — beyond the 2,161-contract pilot.

Same disk-safe streaming/aggregation as the pilot, but uses a thread pool for the
per-tender detail fetches (the throughput bottleneck) and a larger budget, so we
obtain a system-scale sample (tens of thousands of contracts) rather than a pilot.
Only sector-level aggregates are written.

Output: results/cross_continental/acquired_global_systems.json  (UA entry updated)
"""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "Data" / "reference" / "cpv_sectors.csv"
OUT = ROOT / "results" / "cross_continental" / "acquired_global_systems.json"
UA = {"User-Agent": "Mozilla/5.0 (academic procurement research)"}
BASE = "https://public-api.prozorro.gov.ua/api/2.5/tenders"
FX_UAH = 0.027
PZ_NONCOMP = {"negotiation", "negotiation.quick", "reporting", "priceQuotation"}

BUDGET_S = 2400          # 40 min
MAX_RECORDS = 60000
N_WORKERS = 12


def load_cpv_carbon():
    import csv
    m = {}
    with open(REF, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                m[str(row["cpv_division"]).zfill(2)] = float(
                    row["emission_intensity_kg_co2_per_usd"])
            except (ValueError, KeyError):
                pass
    return m


CPV_CARBON = load_cpv_carbon()


def carbon_for(c):
    return CPV_CARBON.get(str(c).zfill(2), 0.35)


def cpv2(items):
    if not items:
        return None
    cid = str((items[0].get("classification") or {}).get("id", ""))
    d = cid.split("-")[0]
    return d[:2] if len(d) >= 2 and d[:2].isdigit() else None


agg = {}            # cpv2 -> [n, noncomp, value_usd]
lock = threading.Lock()
counter = {"n": 0}
tlocal = threading.local()


def sess():
    s = getattr(tlocal, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update(UA)
        tlocal.s = s
    return s


def fetch_one(tid):
    try:
        d = sess().get(f"{BASE}/{tid}", timeout=15).json().get("data", {})
    except Exception:
        return
    cpv = cpv2(d.get("items") or [])
    if not cpv:
        return
    val = d.get("value") or {}
    usd = float(val.get("amount") or 0) * (FX_UAH if (val.get("currency") or "UAH") == "UAH" else 0.027)
    noncomp = 1 if d.get("procurementMethodType") in PZ_NONCOMP else 0
    with lock:
        a = agg.setdefault(cpv, [0, 0, 0.0])
        a[0] += 1; a[1] += noncomp; a[2] += usd
        counter["n"] += 1


def main():
    t0 = time.time()
    s = sess()
    url = BASE + "?descending=1&limit=100"
    with ThreadPoolExecutor(max_workers=N_WORKERS) as pool:
        while time.time() - t0 < BUDGET_S and counter["n"] < MAX_RECORDS:
            try:
                lst = s.get(url, timeout=20).json()
            except Exception:
                time.sleep(1); continue
            ids = [x["id"] for x in lst.get("data", [])]
            if not ids:
                break
            list(pool.map(fetch_one, ids))
            if counter["n"] % 2000 < len(ids):
                print(f"  ... {counter['n']} records, {int(time.time()-t0)}s", flush=True)
            nxt = (lst.get("next_page") or {}).get("uri")
            if not nxt:
                break
            url = nxt

    n = counter["n"]
    num = den = noncomp_total = 0.0
    sectors = {}
    for c, (cnt, ncomp, vusd) in agg.items():
        carbon = carbon_for(c)
        w = max(vusd, 1.0) * carbon
        num += w * (ncomp / cnt); den += w; noncomp_total += ncomp
        sectors[c] = {"n": cnt, "noncomp_rate": round(ncomp / cnt, 3)}
    rec = {
        "country": "Ukraine", "iso": "UA", "n_records": n,
        "seconds": round(time.time() - t0, 1),
        "competition_definition": "procurement-method proxy (reporting/negotiation = non-competitive)",
        "overall_noncompetitive_rate": round(noncomp_total / n, 4) if n else None,
        "carbon_weighted_noncompetitive_exposure": round(num / den, 4) if den else None,
        "n_cpv_divisions": len(agg), "scaled": True,
    }
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    data["UA"] = rec
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("DONE", json.dumps(rec))


if __name__ == "__main__":
    main()
