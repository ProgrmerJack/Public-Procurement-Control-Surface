"""Deep catalog of the entire Data/ folder: every file, size, and a structural
profile (columns/sheets/zip-members/keys) for tabular and archive files."""
import json, os, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "Data"
OUT = Path(__file__).resolve().parents[2] / "results" / "audit" / "data_folder_catalog.json"


def profile(p: Path):
    suf = p.suffix.lower()
    info = {}
    try:
        if suf == ".csv":
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                header = f.readline().strip()
                nrows = sum(1 for _ in f)
            info = {"kind": "csv", "rows_approx": nrows,
                    "columns": header.split(",")[:40], "n_cols": len(header.split(","))}
        elif suf in (".tsv",):
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                header = f.readline().strip()
            info = {"kind": "tsv", "columns": header.split("\t")[:30]}
        elif suf == ".parquet":
            import pyarrow.parquet as pq
            md = pq.read_metadata(p)
            info = {"kind": "parquet", "rows": md.num_rows,
                    "columns": [md.schema.column(i).name for i in range(md.num_columns)][:60]}
        elif suf == ".json":
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                d = json.load(f)
            if isinstance(d, list):
                info = {"kind": "json-list", "len": len(d),
                        "item_keys": list(d[0].keys())[:30] if d and isinstance(d[0], dict) else None}
            elif isinstance(d, dict):
                info = {"kind": "json-dict", "keys": list(d.keys())[:40]}
        elif suf == ".zip":
            with zipfile.ZipFile(p) as z:
                members = [(i.filename, i.file_size) for i in z.infolist()]
            info = {"kind": "zip", "members": members[:40]}
        elif suf in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(p, read_only=True)
                info = {"kind": "excel", "sheets": wb.sheetnames[:30]}
                wb.close()
            except Exception as e:
                info = {"kind": "excel", "sheets_err": str(e)[:60]}
        else:
            info = {"kind": suf or "other"}
    except Exception as e:
        info = {"kind": suf, "error": str(e)[:80]}
    return info


def main():
    files = []
    for dp, dns, fns in os.walk(ROOT):
        for f in fns:
            p = Path(dp) / f
            try:
                sz = p.stat().st_size
            except Exception:
                sz = 0
            files.append((sz, p))
    files.sort(key=lambda x: -x[0])

    catalog = {"total_files": len(files),
               "total_gb": round(sum(s for s, _ in files) / 1e9, 2),
               "files": []}
    # profile everything except the huge (>50MB) opaque bodies (still listed, light profile)
    for sz, p in files:
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        entry = {"path": rel, "size": sz}
        if sz <= 120_000_000 or p.suffix.lower() in (".parquet", ".zip", ".csv"):
            entry.update(profile(p))
        else:
            entry["kind"] = "large-" + (p.suffix.lower() or "blob")
        catalog["files"].append(entry)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(catalog, indent=1, default=str), encoding="utf-8")
    print(f"{catalog['total_files']} files, {catalog['total_gb']} GB -> {OUT}\n")
    for e in catalog["files"]:
        k = e.get("kind", "?")
        extra = ""
        if "rows" in e: extra = f"rows={e['rows']:,}"
        elif "rows_approx" in e: extra = f"~rows={e['rows_approx']:,}"
        elif "len" in e: extra = f"len={e['len']}"
        elif "members" in e: extra = f"zip[{len(e['members'])}members]"
        elif "sheets" in e: extra = f"sheets={e.get('sheets')}"
        print(f"{e['size']:>13,}  {e['path']:<58} {k:14} {extra}")


if __name__ == "__main__":
    main()
