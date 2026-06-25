"""
Fix 6 (part 2): rebuild the Dead Zone single-bidder spending figure from GENUINE
awarded values (raw TED <VAL_TOTAL CURRENCY="EUR">), instead of the processed
extract's notified-maximum value field (which is ~7x the OECD benchmark).

We stream raw TED 2019 (a richly-covered year), and for each contract-award notice
(TD=7) record country, CPV division, offers-received (single-bidder if ==1), and the
EUR awarded value (sum of EUR VAL_TOTAL in the notice). We then report the genuine
awarded value locked in single-bidder awards in high-carbon (Dead Zone) sectors,
EUR-denominated subset (a transparent lower bound: non-EUR notices and below-threshold
contracts are excluded). This replaces a calibration with a data-grounded estimate.

Output: results/projections/fix6_award_value_rebuild.json
"""
import collections, io, json, re, ssl, tarfile, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "projections" / "fix6_award_value_rebuild.json"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
TMP = ROOT / "_ted_val_tmp.tar.gz"

RE_TD = re.compile(rb'TD_DOCUMENT_TYPE CODE="(\d+)"')
RE_CTRY = re.compile(rb'ISO_COUNTRY VALUE="([A-Z]{2})"')
RE_CPV = re.compile(rb'ORIGINAL_CPV CODE="(\d{2})')
RE_OFF1 = re.compile(rb'OFFERS_RECEIVED_NUMBER[^>]*>(\d+)')
RE_OFF2 = re.compile(rb'NB_TENDERS_RECEIVED>(\d+)')
RE_VALEUR = re.compile(rb'<VAL_TOTAL CURRENCY="EUR">([0-9.]+)<')

# CPV->carbon weight (Dead Zone = carbon >= 0.25)
INTENSITY = {"03":0.85,"09":1.20,"14":1.20,"15":0.65,"18":0.45,"19":0.40,"22":0.55,"24":0.90,
 "30":0.30,"31":0.40,"32":0.15,"33":0.30,"34":0.45,"35":0.60,"38":0.28,"39":0.30,"42":0.35,
 "43":0.30,"44":0.75,"45":0.50,"48":0.10,"50":0.20,"55":0.35,"60":0.85,"63":0.45,"64":0.20,
 "65":0.60,"66":0.08,"70":0.12,"71":0.12,"72":0.10,"73":0.12,"75":0.20,"77":0.85,"79":0.15,
 "80":0.15,"85":0.25,"90":0.55,"92":0.20,"98":0.20}


def iter_xml(tf):
    for mm in tf:
        if not mm.isfile():
            continue
        fo = tf.extractfile(mm)
        if fo is None:
            continue
        with fo:
            blob = fo.read()
        if mm.name.endswith((".tar.gz", ".tgz")):
            try:
                with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as inner:
                    yield from iter_xml(inner)
            except Exception:
                continue
        else:
            yield blob


def parse(x):
    m = RE_TD.search(x)
    if not m or m.group(1) != b"7":
        return None
    c = RE_CTRY.search(x); cpv = RE_CPV.search(x)
    if not c:
        return None
    offers = RE_OFF1.findall(x) or RE_OFF2.findall(x)
    offers = [int(o) for o in offers if o.isdigit() and int(o) > 0]
    vals = [float(v) for v in RE_VALEUR.findall(x)]
    if not offers or not vals:
        return None
    eur = sum(vals)
    sb = 1 if min(offers) == 1 else 0          # notice single-bidder if its smallest award had 1 offer
    return (c.group(1).decode(), cpv.group(1).decode() if cpv else "na", sb, eur)


def main():
    agg = collections.defaultdict(lambda: [0.0, 0.0, 0])   # cpv -> (eur_total, eur_sb, n)
    for m in range(1, 13):
        url = f"https://ted.europa.eu/packages/monthly/2019-{m}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                        timeout=600, context=CTX) as r, open(TMP, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            with tarfile.open(TMP, "r:gz") as tf:
                for x in iter_xml(tf):
                    p = parse(x)
                    if not p:
                        continue
                    ctry, cpv, sb, eur = p
                    a = agg[cpv]
                    a[0] += eur; a[1] += eur if sb else 0.0; a[2] += 1
            print(f"2019-{m} done", flush=True)
        except Exception as e:
            print(f"2019-{m} FAIL {str(e)[:40]}", flush=True)
        finally:
            for _ in range(5):
                try:
                    if TMP.exists():
                        TMP.unlink()
                    break
                except PermissionError:
                    import time; time.sleep(0.5)

    rows = [{"cpv": k, "carbon": INTENSITY.get(k), "eur_total": v[0], "eur_sb": v[1], "n": v[2]}
            for k, v in agg.items() if INTENSITY.get(k) is not None]
    total_eur = sum(r["eur_total"] for r in rows)
    dz = [r for r in rows if r["carbon"] >= 0.25]
    dz_eur = sum(r["eur_total"] for r in dz)
    dz_sb_eur = sum(r["eur_sb"] for r in dz)
    res = {
        "year": 2019, "source": "raw TED VAL_TOTAL CURRENCY=EUR (genuine awarded value)",
        "scope_caveat": "EUR-denominated above-threshold TED award notices only; lower bound",
        "total_awarded_eur_bn": round(total_eur / 1e9, 2),
        "dead_zone_awarded_eur_bn": round(dz_eur / 1e9, 2),
        "dead_zone_sb_locked_eur_bn": round(dz_sb_eur / 1e9, 2),
        "n_award_notices": int(sum(r["n"] for r in rows)),
        "vs_calibration": "manuscript's calibrated figure is EUR190-250B/yr across all DZ SB (OECD-deflated)",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
