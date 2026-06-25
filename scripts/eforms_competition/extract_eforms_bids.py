"""
eForms full-bid-set extractor (for the "does competition select greener winners?" test).

eForms contract-award notices (TED, mandatory since Oct 2023) disclose EVERY tenderer, not
just the winner, with legal names, national/VAT IDs, per-tender rank and bid value. We parse,
per single-award notice, the full ranked bid set: winner + all losing bidders.

Linkage (verified on real 2025 notices):
  Organization (ORG-id -> name, national CompanyID)
  TenderingParty (TPA-id -> Tenderer ORG-id)
  LotTender definition (TEN-id -> TenderingParty TPA-id, RankCode, PayableAmount)
  LotResult (-> winning LotTender TEN-id)
We restrict v1 to notices with exactly one LotResult (one award), so winner and bidder set
are unambiguous without lot-level tender grouping.

Usage: python extract_eforms_bids.py <cached_month.tar.gz>  ->  results/eforms_competition/<month>_bids.jsonl
       prints gate G1 coverage stats.
"""
import io, json, re, sys, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "results" / "eforms_competition"

RE_ORG = re.compile(rb"<efac:Organization>.*?</efac:Organization>", re.S)
RE_ORGID = re.compile(rb'<cac:PartyIdentification>\s*<cbc:ID schemeName="organization">([^<]+)<', re.S)
RE_NAME = re.compile(rb"<cac:PartyName>\s*<cbc:Name[^>]*>([^<]+)<", re.S)
RE_NATID = re.compile(rb"<cac:PartyLegalEntity>\s*<cbc:CompanyID[^>]*>([^<]+)<", re.S)
RE_TPA = re.compile(rb"<efac:TenderingParty>(?:(?!</efac:TenderingParty>).)*?</efac:TenderingParty>", re.S)
RE_TPAID = re.compile(rb'<cbc:ID schemeName="tendering-party">([^<]+)<')
RE_TENDERER_ORG = re.compile(rb'<efac:Tenderer>\s*<cbc:ID schemeName="organization">([^<]+)<')
RE_LOTTENDER = re.compile(rb"<efac:LotTender>(?:(?!</efac:LotTender>).)*?</efac:LotTender>", re.S)
RE_TENID = re.compile(rb'<cbc:ID schemeName="tender">([^<]+)<')
RE_RANK = re.compile(rb"<cbc:RankCode[^>]*>([^<]+)<")
RE_PAYABLE = re.compile(rb'<cbc:PayableAmount currencyID="([A-Z]{3})">([0-9.]+)<')
RE_TPAREF = re.compile(rb'<efac:TenderingParty>\s*<cbc:ID schemeName="tendering-party">([^<]+)<')
RE_LOTRESULT = re.compile(rb"<efac:LotResult>(?:(?!</efac:LotResult>).)*?</efac:LotResult>", re.S)
RE_RES_WINTEN = re.compile(rb'<efac:LotTender>\s*<cbc:ID schemeName="tender">([^<]+)<')
RE_CPV = re.compile(rb'<cbc:ItemClassificationCode[^>]*>(\d{2})\d*<')
RE_COUNTRY = re.compile(rb"<cbc:IdentificationCode[^>]*>([A-Z]{3})<")


def iter_xml(tf):
    for m in tf:
        if not m.isfile():
            continue
        b = tf.extractfile(m).read()
        if m.name.endswith((".tar.gz", ".tgz")):
            try:
                with tarfile.open(fileobj=io.BytesIO(b), mode="r:gz") as inner:
                    yield from iter_xml(inner)
            except Exception:
                continue
        else:
            yield m.name, b


def parse_notice(x):
    if b"efac:NoticeResult" not in x:
        return None
    results = RE_LOTRESULT.findall(x)
    if len(results) != 1:
        return None                                  # v1: single-award notices only
    # org map
    orgs = {}
    for blk in RE_ORG.findall(x):
        oid = RE_ORGID.search(blk)
        if not oid:
            continue
        nm = RE_NAME.search(blk)
        nat = RE_NATID.search(blk)
        orgs[oid.group(1)] = (nm.group(1).decode("utf-8", "replace").strip() if nm else "",
                              nat.group(1).decode("utf-8", "replace").strip() if nat else "")
    # tendering party -> org
    tpa2org = {}
    for blk in RE_TPA.findall(x):
        tid = RE_TPAID.search(blk)
        org = RE_TENDERER_ORG.search(blk)
        if tid and org:
            tpa2org[tid.group(1)] = org.group(1)
    # full lot-tender definitions
    tenders = {}
    for blk in RE_LOTTENDER.findall(x):
        if b"efac:TenderingParty" not in blk:
            continue                                  # skip reference stubs
        ten = RE_TENID.search(blk)
        tpa = RE_TPAREF.search(blk)
        if not (ten and tpa):
            continue
        rank = RE_RANK.search(blk)
        pay = RE_PAYABLE.search(blk)
        tenders[ten.group(1)] = {
            "tpa": tpa.group(1),
            "rank": int(rank.group(1)) if rank and rank.group(1).isdigit() else None,
            "value": float(pay.group(2)) if pay else None,
            "currency": pay.group(1).decode() if pay else None,
        }
    if len(tenders) < 1:
        return None
    win_ten = RE_RES_WINTEN.search(results[0])
    win_ten = win_ten.group(1) if win_ten else None
    cpv = RE_CPV.search(x)
    ctry = RE_COUNTRY.search(x)

    def org_of(ten):
        tpa = tenders[ten]["tpa"]
        oid = tpa2org.get(tpa)
        return orgs.get(oid, ("", "")) if oid else ("", "")

    bidders = []
    for ten, info in tenders.items():
        nm, nat = org_of(ten)
        bidders.append({"name": nm, "nat_id": nat, "rank": info["rank"],
                        "value": info["value"], "won": ten == win_ten})
    # de-dup bidders by (name) for distinct-bidder count
    distinct = {b["name"] for b in bidders if b["name"]}
    winner = next((b for b in bidders if b["won"]), None)
    return {
        "cpv": cpv.group(1).decode() if cpv else None,
        "country": ctry.group(1).decode() if ctry else None,
        "n_tenders": len(tenders),
        "n_distinct_bidders": len(distinct),
        "winner_name": winner["name"] if winner else None,
        "winner_nat_id": winner["nat_id"] if winner else None,
        "bidders": bidders,
    }


def main():
    pkg = Path(sys.argv[1])
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / (pkg.stem.replace(".tar", "") + "_bids.jsonl")
    n_notices = n_single = n_ge2 = n_named = 0
    dist = {}
    with tarfile.open(pkg, "r:gz") as tf, out.open("w", encoding="utf-8") as fo:
        for name, x in iter_xml(tf):
            if b"efac:NoticeResult" not in x:
                continue
            n_notices += 1
            rec = parse_notice(x)
            if rec is None:
                continue
            n_single += 1
            nb = rec["n_distinct_bidders"]
            dist[nb] = dist.get(nb, 0) + 1
            if nb >= 2:
                n_ge2 += 1
            if rec["winner_name"]:
                n_named += 1
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"award notices scanned: {n_notices:,}")
    print(f"single-award notices parsed: {n_single:,}")
    print(f"  with winner named: {n_named:,} ({n_named/max(n_single,1):.1%})")
    print(f"  with >=2 distinct named bidders (test-eligible): {n_ge2:,} ({n_ge2/max(n_single,1):.1%})")
    print("  bidder-count distribution:", dict(sorted({k: v for k, v in dist.items() if k <= 8}.items())))
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
