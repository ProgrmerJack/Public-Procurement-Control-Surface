"""
SMART DOWNLOAD for Fix 1: stream the raw TED monthly bulk XML packages, extract only
the fields the monthly DiD needs, aggregate to country x sector x month, and DELETE the
raw package -- never storing the full multi-GB corpus on disk.

Source: https://ted.europa.eu/packages/monthly/{yyyy-m}  (~200 MB gzip/month, no login)
Per Contract-Award-Notice (TD_DOCUMENT_TYPE=7), extract per-award OFFERS_RECEIVED_NUMBER
-> single-bidder (offers==1), >=3-offer share, mean offers, by country x CPV division x
dispatch-month. Resumable: writes one CSV per month to results/causal_id/ted_monthly_raw/.

This recovers the pre-2017 sub-annual resolution the local extract lacks (dates are the
string 'None' there), dissolving the 3-cell ceiling.
"""
import collections, csv, io, os, re, ssl, sys, tarfile, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "results" / "causal_id" / "ted_monthly_raw"
OUTDIR.mkdir(parents=True, exist_ok=True)
TMP = ROOT / "_ted_tmp.tar.gz"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

RE_CTRY = re.compile(rb'ISO_COUNTRY VALUE="([A-Z]{2})"')
RE_DISP = re.compile(rb'(?:DS_DATE_DISPATCH|NOTICE_DISPATCH_DATE)>(\d{8})')
RE_TD = re.compile(rb'TD_DOCUMENT_TYPE CODE="(\d+)"')
RE_CPV = re.compile(rb'ORIGINAL_CPV CODE="(\d{2})')
RE_OFF = re.compile(rb'OFFERS_RECEIVED_NUMBER[^>]*>(\d+)')      # TED_EXPORT R2.0.8 (to ~2018)
RE_OFF2 = re.compile(rb'NB_TENDERS_RECEIVED>(\d+)')             # TED_EXPORT R2.0.9 (2018-2019+)


def parse_notice(x):
    if RE_TD.search(x) is None:
        return None
    td = RE_TD.search(x).group(1)
    if td != b"7":                       # 7 = contract award notice
        return None
    c = RE_CTRY.search(x)
    d = RE_DISP.search(x)
    cpv = RE_CPV.search(x)
    if not (c and d):
        return None
    raw = RE_OFF.findall(x) or RE_OFF2.findall(x)   # whichever schema's offer tag is present
    offers = [int(o) for o in raw if o.isdigit() and int(o) > 0]
    if not offers:
        return None
    ym = d.group(1)[:6].decode()         # YYYYMM
    return (c.group(1).decode(), ym,
            (cpv.group(1).decode() if cpv else "na"), offers)


def process_month(yyyy, m):
    tag = f"{yyyy}-{m}"
    out = OUTDIR / f"{yyyy}_{m:02d}.csv"
    if out.exists():
        return f"{tag} cached"
    url = f"https://ted.europa.eu/packages/monthly/{yyyy}-{m}"
    try:
        with urllib.request.urlopen(urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"}), timeout=600, context=CTX) as r, \
                open(TMP, "wb") as f:
            while True:
                buf = r.read(1 << 20)
                if not buf:
                    break
                f.write(buf)
    except Exception as e:
        return f"{tag} DOWNLOAD-FAIL {str(e)[:50]}"

    agg = collections.defaultdict(lambda: [0, 0, 0, 0])  # key->(n,sb,ge3,sum_off)
    n_notices = 0

    def iter_xml(tf):
        """Yield XML bytes, recursing into nested daily .tar.gz members (2020+ format)."""
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

    try:
        with tarfile.open(TMP, "r:gz") as tf:
            for x in iter_xml(tf):
                r = parse_notice(x)
                if r is None:
                    continue
                n_notices += 1
                ctry, ym, cpv, offers = r
                k = (ctry, ym, cpv)
                for o in offers:
                    a = agg[k]
                    a[0] += 1
                    a[1] += 1 if o == 1 else 0
                    a[2] += 1 if o >= 3 else 0
                    a[3] += min(o, 200)        # winsorise extreme
    except Exception as e:
        return f"{tag} PARSE-FAIL {str(e)[:50]}"
    finally:
        for _ in range(5):                     # Windows file-lock retry
            try:
                if TMP.exists():
                    TMP.unlink()
                break
            except PermissionError:
                time.sleep(0.5)

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["country", "ym", "cpv_division", "n", "sb", "ge3", "sum_offers"])
        for (ctry, ym, cpv), a in agg.items():
            w.writerow([ctry, ym, cpv, a[0], a[1], a[2], a[3]])
    return f"{tag} OK notices={n_notices} cells={len(agg)}"


def main():
    y0, y1 = 2015, 2019                  # 2014 packages use an unsupported layout
    if len(sys.argv) >= 3:
        y0, y1 = int(sys.argv[1]), int(sys.argv[2])
    for yyyy in range(y0, y1 + 1):
        for m in range(1, 13):
            t0 = time.time()
            msg = process_month(yyyy, m)
            print(f"{msg}  ({time.time()-t0:.0f}s)", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
