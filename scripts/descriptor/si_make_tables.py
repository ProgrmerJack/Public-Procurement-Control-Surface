"""
Generate the Supplementary Information LaTeX table fragments for the Data
Descriptor, computed directly from the deposited/source files (self-contained:
the per-territory and eForms-coverage statistics are computed here, not read
from a pre-existing JSON).

Paths (script lives in scripts/descriptor/):
  ROOT  = repository root
  PAPER = Scientific_Data_Descriptor/        (LaTeX \\input{si_tables/...} targets here)
  RESD  = results/descriptor/                (si_data.json reference output)
"""
import json, csv, collections
from pathlib import Path
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "Scientific_Data_Descriptor"
RESD = ROOT / "results" / "descriptor"; RESD.mkdir(parents=True, exist_ok=True)
OUT = PAPER / "si_tables"; OUT.mkdir(exist_ok=True)
CONTRACTS = ROOT / "Data" / "processed" / "gprd_with_carbon.parquet"
CROSSWALK = ROOT / "Data" / "reference" / "cpv_exiobase_crosswalk.csv"
VALIDATION = ROOT / "results" / "within_sector" / "exiobase_eurostat_validation_v2.json"
EFORMS = ROOT / "deposit" / "eforms_bids_2024_2025.jsonl"


def compute_si_data():
    """Per-territory competition stats and eForms disclosure coverage."""
    src = lambda c: "SECOP" if c == "CO" else ("ContractsFinder" if c == "GB" else "TED")
    df = pq.read_table(CONTRACTS, columns=["country", "n_bidders", "single_bidder"]).to_pandas()
    per_country = []
    for c, g in df.groupby("country"):
        obs = g[g["n_bidders"] >= 1]
        per_country.append(dict(country=c, source=src(c), n=len(g), n_obs=len(obs),
            sb=round((obs["n_bidders"] == 1).mean(), 3) if len(obs) else None,
            comp3=round((obs["n_bidders"] >= 3).mean(), 3) if len(obs) else None))
    per_country.sort(key=lambda r: -r["n"])

    cc = collections.defaultdict(lambda: [0, 0, 0]); tot = [0, 0, 0]
    with open(EFORMS, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line); co = d.get("country", "?"); nb = d.get("n_distinct_bidders") or 0
            ge2 = 1 if nb >= 2 else 0
            for k in (cc[co], tot): k[0] += 1; k[1] += ge2; k[2] += nb
    eforms_total = dict(n=tot[0], pct_ge2=round(100 * tot[1] / tot[0], 1), mean_distinct=round(tot[2] / tot[0], 2))
    eforms_by_country = [dict(country=co, n=n, pct_ge2=round(100 * g2 / n, 1), mean_distinct=round(sd / n, 2))
                         for co, (n, g2, sd) in sorted(cc.items(), key=lambda x: -x[1][0]) if n >= 200]
    return dict(per_country=per_country, eforms_total=eforms_total, eforms_by_country=eforms_by_country)


def main():
    si = compute_si_data()
    (RESD / "si_data.json").write_text(json.dumps(si, indent=1), encoding="utf-8")

    # S1 per-territory
    with open(OUT / "si_tab_country.tex", "w", encoding="utf-8") as f:
        for r in si["per_country"]:
            sb = f"{r['sb']:.3f}" if r["sb"] is not None else "--"
            c3 = f"{r['comp3']:.3f}" if r["comp3"] is not None else "--"
            f.write(f"{r['country']} & {r['source']} & {r['n']:,} & {r['n_obs']:,} & {sb} & {c3} \\\\\n".replace(",", "{,}"))
        f.write("\\bottomrule\n")

    # S2 CPV->EXIOBASE crosswalk (40)
    rd = list(csv.DictReader(open(CROSSWALK, encoding="utf-8")))
    with open(OUT / "si_tab_crosswalk.tex", "w", encoding="utf-8") as f:
        for r in rd:
            f.write(f"{r['cpv_division']} & {r['cpv_description'].replace('&', '\\&')} & "
                    f"{r['exiobase_sector'].replace('&', '\\&')} \\\\\n")
        f.write("\\bottomrule\n")

    # S3 eForms coverage by country
    with open(OUT / "si_tab_eforms.tex", "w", encoding="utf-8") as f:
        for r in si["eforms_by_country"]:
            f.write(f"{r['country']} & {r['n']:,} & {r['pct_ge2']:.1f} & {r['mean_distinct']:.2f} \\\\\n".replace(",", "{,}"))
        f.write("\\bottomrule\n")

    # S4 EXIOBASE-Eurostat validation (34)
    tab = sorted(json.load(open(VALIDATION))["table"], key=lambda t: -t["paper_weight"])
    with open(OUT / "si_tab_validation.tex", "w", encoding="utf-8") as f:
        for t in tab:
            f.write(f"{t['cpv']} & {t['nace']} & {t['paper_weight']:.2f} & {t['eurostat_measured']:.3f} \\\\\n")
        f.write("\\bottomrule\n")

    # S5 per-CPV-division statistics
    cw = {r["cpv_division"]: r["cpv_description"] for r in csv.DictReader(open(CROSSWALK, encoding="utf-8"))}
    g = pq.read_table(CONTRACTS, columns=["cpv_division", "n_bidders", "carbon_intensity_kg_usd", "country"]).to_pandas()
    g = g[~g["country"].isin(["CO", "GB"])]
    cpv_rows = []
    for cpv, grp in g.groupby("cpv_division"):
        if len(grp) < 500:
            continue
        obs = grp[grp["n_bidders"] >= 1]
        sb = round((obs["n_bidders"] == 1).mean(), 3) if len(obs) else None
        carb = grp["carbon_intensity_kg_usd"].dropna()
        cpv_rows.append((str(cpv), cw.get(str(cpv), ""), len(grp), sb,
                         round(carb.median(), 3) if len(carb) else None))
    cpv_rows.sort(key=lambda r: -r[2])
    with open(OUT / "si_tab_cpv.tex", "w", encoding="utf-8") as f:
        for cpv, desc, n, sb, cb in cpv_rows:
            sbs = f"{sb:.3f}" if sb is not None else "--"
            cbs = f"{cb:.3f}" if cb is not None else "--"
            f.write(f"{cpv} & {desc.replace('&', '\\&')[:42]} & {n:,} & {sbs} & {cbs} \\\\\n".replace(",", "{,}"))
        f.write("\\bottomrule\n")

    print(f"wrote {len(si['per_country'])} country, {len(rd)} crosswalk, "
          f"{len(si['eforms_by_country'])} eforms, {len(tab)} validation, {len(cpv_rows)} cpv rows")
    print(f"eForms total: {si['eforms_total']}")


if __name__ == "__main__":
    main()
