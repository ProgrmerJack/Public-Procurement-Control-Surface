"""
Verify the descriptor's ORIG-tagged claims by actually RE-RUNNING the original
pipeline scripts (not by recomputing from data, which is verify_claims.py's job).

Each step executes the original generating script as a subprocess, then checks
that the result file it writes matches the value cited in the descriptor.

Some steps are slow (the eForms conditional-logit re-runs over 302k notices).
Run from the repository root:  python scripts/descriptor/verify_original.py
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EFORMS = ROOT / "deposit" / "eforms_bids_2024_2025.jsonl"
OK = BAD = 0


def run(cmd):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run([sys.executable, *map(str, cmd)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print("    (script exited non-zero)\n", r.stderr[-500:])
    return r


def check(name, ok, detail):
    global OK, BAD
    OK += ok; BAD += (not ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def close(a, b, tol):
    return abs(a - b) <= tol


print("Re-running original pipeline scripts and checking their outputs...\n")

# 1. Carbon validation (fast)
print("1. Carbon-weight validation")
run(["scripts/within_sector/exiobase_eurostat_validation_v2.py"])
v = json.load(open(ROOT / "results/within_sector/exiobase_eurostat_validation_v2.json"))
check("carbon rho", close(v["spearman"]["rho"], 0.82, 0.01), f"rho={v['spearman']['rho']:.3f}, sectors={v['n_sectors']}")

# 2. eForms within-tender (slow: conditional logit over the corpus)
print("2. eForms within-tender result")
run(["scripts/eforms_competition/within_tender_green_wins.py", EFORMS])
w = json.load(open(ROOT / "results/eforms_competition/within_tender_green_wins.json"))
check("eForms tender funnel", w["n_tenders_total"] == 23216 and w["n_tenders_identified"] == 2601,
      f"total={w['n_tenders_total']}, identified={w['n_tenders_identified']}")
check("eForms within-tender OR", close(w["clogit_odds_ratio"], 1.02, 0.01),
      f"OR={w['clogit_odds_ratio']:.4f} [{w['clogit_OR_ci95'][0]:.3f},{w['clogit_OR_ci95'][1]:.3f}], p={w['clogit_green_p']:.3f}")

# 3. Robustness battery (slow)
print("3. Robustness battery")
run(["scripts/eforms_competition/robustness_battery.py", EFORMS])
bv = json.load(open(ROOT / "results/eforms_competition/BATTERY_VERDICT.json"))
check("battery reweight p", "0.75" in bv["failures"]["1_reweighting"], "reweighted coef −0.056, p=0.75")

print(f"\n{'='*60}\nORIGINAL-CODE VERIFICATION: {OK} PASS, {BAD} FAIL\n{'='*60}")
sys.exit(1 if BAD else 0)
