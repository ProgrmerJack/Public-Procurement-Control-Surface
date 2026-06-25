"""
Scale the eForms full-bid-set extraction across the eForms era (disk-safe: stream one monthly
package, parse, write per-month JSONL, delete the raw package before the next month).
"""
import importlib.util, ssl, sys, tarfile, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "ext", ROOT / "scripts" / "eforms_competition" / "extract_eforms_bids.py")
ext = importlib.util.module_from_spec(spec); spec.loader.exec_module(ext)
import json
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
TMP = ROOT / "_eforms_scale_tmp.tar.gz"
OUTDIR = ROOT / "results" / "eforms_competition"

# eForms mandatory Oct 2023; bidder disclosure populated through 2024-2025
MONTHS = [f"{y}-{m}" for y in (2024, 2025) for m in range(1, 13)]


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for ym in MONTHS:
        out = OUTDIR / f"{ym}_bids.jsonl"
        if out.exists():
            print(f"{ym} exists, skip", flush=True); continue
        url = f"https://ted.europa.eu/packages/monthly/{ym}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                        timeout=900, context=CTX) as r, open(TMP, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            n_single = n_ge2 = 0
            with tarfile.open(TMP, "r:gz") as tf, out.open("w", encoding="utf-8") as fo:
                for name, x in ext.iter_xml(tf):
                    if b"efac:NoticeResult" not in x:
                        continue
                    rec = ext.parse_notice(x)
                    if rec is None:
                        continue
                    n_single += 1
                    if rec["n_distinct_bidders"] >= 2:
                        n_ge2 += 1
                    fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"{ym}: {n_single:,} single-award parsed, {n_ge2:,} with >=2 named bidders", flush=True)
        except Exception as e:
            print(f"{ym} FAIL {str(e)[:60]}", flush=True)
        finally:
            for _ in range(5):
                try:
                    if TMP.exists():
                        TMP.unlink()
                    break
                except PermissionError:
                    time.sleep(0.5)
    print("DONE scaling extraction", flush=True)


if __name__ == "__main__":
    main()
