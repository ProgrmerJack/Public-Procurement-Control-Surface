"""
Smart streaming acquisition of non-EU procurement systems (disk-safe).

Disk is ~93% full, so we NEVER store bulk: we stream records from public OCDS
APIs, extract only {year, cpv_division, value, competition flag}, aggregate to
sector level on the fly, and write a few-KB summary. Each source is time-boxed.

Carbon factor by CPV division from Data/reference/cpv_sectors.csv
(emission_intensity_kg_co2_per_usd). Competition proxy where bidder counts are
unavailable: procurement-method type (direct/negotiation/reporting = non-competitive).

Output: results/cross_continental/acquired_global_systems.json
"""
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "Data" / "reference" / "cpv_sectors.csv"
OUT = ROOT / "results" / "cross_continental" / "acquired_global_systems.json"
UA = {"User-Agent": "Mozilla/5.0 (academic procurement research)"}

# rough FX to USD (2023 averages) -- only affects value weights, not rates
FX_USD = {"UAH": 0.027, "PYG": 0.00014, "USD": 1.0, "EUR": 1.08, "MDL": 0.056}


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
DEFAULT_CARBON = 0.35  # fallback ~ services/other


def carbon_for(cpv2):
    return CPV_CARBON.get(str(cpv2).zfill(2), DEFAULT_CARBON)


def cpv_division_from_item(items):
    """Extract 2-digit CPV division from a CPV-format classification id,
    regardless of the (possibly localized) scheme name, e.g. 'DK021'/'CPV'."""
    if not items:
        return None
    cl = items[0].get("classification") or {}
    cid = str(cl.get("id", ""))
    # CPV ids look like '45000000-7' (8 digits, optional check digit)
    digits = cid.split("-")[0]
    if len(digits) >= 2 and digits[:2].isdigit():
        return digits[:2]
    return None


def session():
    s = requests.Session()
    s.headers.update(UA)
    return s


# ---------------------------------------------------------------- ProZorro (UA)
PZ_NONCOMP = {"negotiation", "negotiation.quick", "reporting", "priceQuotation"}


def acquire_prozorro(budget_s=420, max_records=6000):
    s = session()
    base = "https://public-api.prozorro.gov.ua/api/2.5/tenders"
    agg = {}  # cpv2 -> [n, noncomp, value_usd]
    t0 = time.time()
    n = 0
    # walk newest-first
    url = base + "?descending=1&limit=100"
    pages = 0
    while time.time() - t0 < budget_s and n < max_records:
        try:
            lst = s.get(url, timeout=20).json()
        except Exception:
            break
        ids = [d["id"] for d in lst.get("data", [])]
        if not ids:
            break
        for tid in ids:
            if time.time() - t0 >= budget_s or n >= max_records:
                break
            try:
                d = s.get(f"{base}/{tid}", timeout=15).json().get("data", {})
            except Exception:
                continue
            cpv = cpv_division_from_item(d.get("items") or [])
            if not cpv:
                continue
            val = (d.get("value") or {})
            amt = val.get("amount") or 0
            cur = val.get("currency") or "UAH"
            usd = float(amt) * FX_USD.get(cur, 0.027)
            noncomp = 1 if d.get("procurementMethodType") in PZ_NONCOMP else 0
            a = agg.setdefault(cpv, [0, 0, 0.0])
            a[0] += 1; a[1] += noncomp; a[2] += usd
            n += 1
        pages += 1
        nxt = (lst.get("next_page") or {}).get("uri")
        if not nxt:
            break
        url = nxt
    return summarize("Ukraine", "UA", agg, n, time.time() - t0, pages,
                     "procurement-method proxy (reporting/negotiation = non-competitive)")


# ---------------------------------------------------------------- Paraguay DNCP
def acquire_paraguay(budget_s=300, max_records=4000):
    s = session()
    # search requires a filter; use year filter, newest processes
    agg = {}
    t0 = time.time()
    n = 0
    page = 1
    base = "https://www.contrataciones.gov.py/datos/api/v3/doc"
    while time.time() - t0 < budget_s and n < max_records:
        try:
            r = s.get(f"{base}/search/processes",
                      params={"fecha_desde": "2023-01-01", "page": page},
                      timeout=20)
            js = r.json()
        except Exception:
            break
        lst = js.get("list") or js.get("data") or []
        if not lst:
            break
        for it in lst:
            if time.time() - t0 >= budget_s or n >= max_records:
                break
            ocid = it.get("idLlamado") or it.get("ocid") or it.get("nro_licitacion")
            if not ocid:
                continue
            try:
                rel = s.get(f"{base}/ocds/release-package/{ocid}", timeout=15).json()
                releases = rel.get("releases") or []
                if not releases:
                    continue
                rr = releases[0]
                tender = rr.get("tender") or {}
                cpv = cpv_division_from_item(tender.get("items") or [])
                if not cpv:
                    continue
                nt = tender.get("numberOfTenderers")
                noncomp = 1 if (nt is not None and nt <= 1) else 0
                amt = (tender.get("value") or {}).get("amount") or 0
                cur = (tender.get("value") or {}).get("currency") or "PYG"
                usd = float(amt) * FX_USD.get(cur, 0.00014)
                a = agg.setdefault(cpv, [0, 0, 0.0])
                a[0] += 1; a[1] += noncomp; a[2] += usd
                n += 1
            except Exception:
                continue
        page += 1
    return summarize("Paraguay", "PY", agg, n, time.time() - t0, page,
                     "numberOfTenderers<=1")


def summarize(country, iso, agg, n, secs, pages, comp_def):
    if n == 0:
        return {"country": country, "iso": iso, "n": 0, "note": "no records",
                "seconds": round(secs, 1)}
    # carbon-weighted non-competitive exposure
    num = den = 0.0
    overall_nc = 0
    sectors = {}
    for cpv2, (cnt, ncomp, vusd) in agg.items():
        c = carbon_for(cpv2)
        w = max(vusd, 1.0) * c
        nc_rate = ncomp / cnt
        num += w * nc_rate
        den += w
        overall_nc += ncomp
        sectors[cpv2] = {"n": cnt, "noncomp_rate": round(nc_rate, 3),
                         "carbon": c}
    return {
        "country": country, "iso": iso, "n_records": n,
        "seconds": round(secs, 1), "pages": pages,
        "competition_definition": comp_def,
        "overall_noncompetitive_rate": round(overall_nc / n, 4),
        "carbon_weighted_noncompetitive_exposure": round(num / den, 4) if den else None,
        "n_cpv_divisions": len(agg),
    }


def main():
    results = {}
    print("Acquiring ProZorro (Ukraine) ...")
    results["UA"] = acquire_prozorro()
    print("  ->", json.dumps(results["UA"]))
    print("Acquiring Paraguay (DNCP) ...")
    try:
        results["PY"] = acquire_paraguay()
    except Exception as e:
        results["PY"] = {"country": "Paraguay", "error": str(e)[:120]}
    print("  ->", json.dumps(results["PY"]))
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("Saved ->", OUT)


if __name__ == "__main__":
    main()
