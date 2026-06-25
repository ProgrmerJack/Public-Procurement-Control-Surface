"""
ProZorro (Ukraine) acquisition for a DESCRIPTIVE non-EU corroboration point.

Why descriptive, not a causal DiD: the public OCDS API (public.api.openprocurement.org)
does not expose bid counts (numberOfBids/bids[]/lots are null even for completed
competitive tenders), and procuringEntity.kind is absent before mid-2016 -- so the
2016 two-step mandate DiD cannot be identified (outcome + cohort fields postdate the
treatment). What IS reliably populated is procurementMethodType, which we use as a
competition proxy exactly as the manuscript already does for Canada: 'reporting' and
'negotiation*' are non-competitive (single-source) methods; e-auction/open procedures
are competitive. We compute, per CPV division, the non-competitive-method rate over a
2018-2021 sample (war-bounded: pre-2022), join the existing CPV->EXIOBASE carbon
weights, and report the carbon vs non-competition association (Spearman).

Bounded sample: ~N_PER_MONTH tenders per month across 2018-01..2021-12 via the dated
feed, threaded detail fetches. Output: Data/processed/prozorro_corroboration_raw.json
"""
import json, ssl, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Data" / "processed" / "prozorro_corroboration_raw.json"
BASE = "https://public.api.openprocurement.org/api/2.5/tenders"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
N_PER_MONTH = 90          # detail fetches per month
MONTHS = [f"{y}-{m:02d}-01" for y in (2018, 2019, 2020, 2021) for m in range(1, 13)]


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "academic-research"})
            return json.loads(urllib.request.urlopen(req, timeout=40, context=CTX).read().decode())
        except Exception:
            time.sleep(0.5 * (i + 1))
    return None


def feed_ids(offset, want):
    ids, cur = [], f"{BASE}?offset={offset}T00:00:00&limit=100"
    while len(ids) < want and cur:
        d = get(cur)
        if not d or not d.get("data"):
            break
        ids += [x["id"] for x in d["data"]]
        cur = d.get("next_page", {}).get("uri")
    return ids[:want]


def parse(tid):
    d = get(f"{BASE}/{tid}")
    if not d or "data" not in d:
        return None
    t = d["data"]
    items = t.get("items") or []
    cpv = None
    for it in items:
        c = (it.get("classification") or {}).get("id")
        if c and len(str(c)) >= 2:
            cpv = str(c)[:2]; break
    val = (t.get("value") or {}).get("amount")
    return {
        "id": tid,
        "date": t.get("dateCreated"),
        "method": t.get("procurementMethodType"),
        "kind": (t.get("procuringEntity") or {}).get("kind"),
        "cpv_division": cpv,
        "value": val,
        "status": t.get("status"),
    }


def main():
    all_ids = []
    for off in MONTHS:
        ids = feed_ids(off, int(N_PER_MONTH * 1.4))   # over-pull, some fail/parse-empty
        all_ids += [(off, i) for i in ids[:N_PER_MONTH]]
        print(f"feed {off}: {len(ids)} ids", flush=True)
    print(f"total ids to fetch: {len(all_ids)}", flush=True)

    rows, done = [], 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(parse, tid): off for off, tid in all_ids}
        for f in as_completed(futs):
            r = f.result()
            done += 1
            if r:
                rows.append(r)
            if done % 250 == 0:
                print(f"  fetched {done}/{len(all_ids)} (kept {len(rows)})", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"SAVED {len(rows)} tenders -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
