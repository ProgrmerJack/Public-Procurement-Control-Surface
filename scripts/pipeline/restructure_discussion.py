"""
Restructure the Discussion section of manuscript.tex.

New order: findings → mechanism → scale → policy → scope → conclusion
  1. "Competition and governance" (was Para 2 - Governance)
  2. "The bidder count paradox" (was Para 5 - moved up)
  3. "Quantifying the within-sector channel" (was Para 4 - moved up)
  4. "Scale and structural lock-in" (was Para 1 - Brown Monopoly, restructured opening)
  5. "Policy architecture" + Table (was Para 6)
  6. "The Monopoly Tax" (was Para 3 - moved after Policy)
  7. "Scope and interpretation" (was Para 7)
  8. "Conclusion" (was Para 8)
"""

import re

with open("NC_Submission/manuscript.tex", "r", encoding="utf-8") as f:
    content = f.read()

# Markers for Discussion boundaries
disc_start_marker = "\n\\section{Discussion}\n"
disc_end_marker = "\n\\section{Methods}\n"

disc_start = content.index(disc_start_marker)
disc_end = content.index(disc_end_marker)

# Extract Discussion section (including the \section{Discussion} line)
disc_section = content[disc_start:disc_end]

# Split Discussion into individual bold-paragraph blocks
# Each paragraph starts with \textbf{
parts = re.split(r"\n\n(?=\\textbf\{)", disc_section)

print(f"Found {len(parts)} parts:")
for i, p in enumerate(parts):
    header = p[:80].replace("\n", "|")
    print(f"  [{i}]: {header}")

# Identify each paragraph by its heading text
# parts[0] = \section{Discussion} header
# Then alternating \n\n + paragraph content
paragraphs = {}
for i, p in enumerate(parts):
    if "\\textbf{The Brown Monopoly Problem" in p:
        paragraphs["brown_monopoly"] = (i, p)
    elif "\\textbf{Governance as prerequisite" in p:
        paragraphs["governance"] = (i, p)
    elif "\\textbf{The Monopoly Tax" in p:
        paragraphs["monopoly_tax"] = (i, p)
    elif "\\textbf{Quantifying the within-sector" in p:
        paragraphs["within_sector"] = (i, p)
    elif "\\textbf{The bidder count paradox" in p:
        paragraphs["bidder_paradox"] = (i, p)
    elif "\\textbf{Policy architecture" in p:
        paragraphs["policy_arch"] = (i, p)
    elif "\\textbf{Scope and interpretation" in p:
        paragraphs["scope"] = (i, p)
    elif "\\textbf{Conclusion" in p:
        paragraphs["conclusion"] = (i, p)

print(f"\nIdentified paragraphs: {list(paragraphs.keys())}")

# === Modify Para 2 (Governance → "Competition and governance: the central findings") ===
idx, gov_text = paragraphs["governance"]
gov_modified = gov_text.replace(
    "\\textbf{Governance as prerequisite, not supplement.} The $-4.3\\%$ EU-context negative premium is the central insight, but its direction requires careful interpretation.",
    "\\textbf{Competition and governance: the central findings.} "
    "The staggered Callaway \\& Sant'Anna estimator yields ATT $= -7.2$ pp "
    "(RMSPE permutation $p = 0.042$, rank 1 of 24; Sun-Abraham interaction-weighted "
    "estimator confirms: $-7.2$ pp, SE $= 0.57$ pp; SI Section~7), establishing "
    "governance-mandated transparency as the operative causal mechanism for reducing "
    "single-bidder rates. The $-4.3\\%$ EU-context negative premium is the central "
    "descriptive insight, but its direction requires careful interpretation.",
)
assert gov_modified != gov_text, "Governance paragraph modification failed"
print("\n[OK] Governance paragraph renamed and -7.2pp sentence added")

# === Modify Para 1 (Brown Monopoly → "Scale and structural lock-in: the Brown Monopoly Problem") ===
idx, bm_text = paragraphs["brown_monopoly"]
bm_modified = bm_text.replace(
    "\\textbf{The Brown Monopoly Problem.} Our findings reveal a structural market failure we term the Brown Monopoly Problem: de facto monopoly provision --- not necessarily monopoly power, but single-source procurement arising from market thinness, narrow specifications, or poor publicity --- in high-carbon sectors places an estimated \\texteuro190--250 billion in annual public spending beyond the reach of GPP policy (OECD-calibrated; see Methods). Unlike conventional market failures correctable by price signals, Dead Zone lock-in is self-reinforcing --- entrenched suppliers face no competitive pressure to adopt cleaner technology, contracting authorities lack alternatives for environmental conditionality, and long-term dependent relationships ($11+$ repeat transactions with same supplier, showing $+54.5\\%$ carbon intensity vs.~first-time awards; SI Table~S23) deepen the enclosure over time. Three political economy dynamics sustain this lock-in: incumbent suppliers invest in relationship-specific assets that raise switching costs; procurement officers face asymmetric incentives where sole-source awards minimise protest risk and administrative burden while carbon costs remain invisible\\cite{decarolis2020rules}; and the absence of carbon-linked procurement data---the measurement gap this study addresses---means the environmental cost of Dead Zones has been structurally unobservable to policymakers. To contextualise the scale: Dead Zone carbon represents an estimated 3--6\\% of national Paris Agreement reduction targets in major European economies (Dead Zone-specific; the full single-bidder portfolio accounts for 7--12\\% of aggregate EU NDC commitments under Monte Carlo uncertainty---mean 9.3\\%, 90\\% CI: 7.2--11.8\\%; methodology in SI Section~29) --- Germany's Dead Zones alone lock approximately 18\\,Mt\\,CO\\textsubscript{2}e annually (5.8\\% of its NDC reduction commitment), while Poland's reach 6.5\\,Mt\\,CO\\textsubscript{2}e (4.4\\% of its reduction target)\\cite{gcb2023,unfccc2021ndc}. These are portfolio-level estimates based on EXIOBASE sector averages; actual emissions locked in Dead Zones may be substantially larger given 5--10$\\times$ within-sector firm-level variation\\cite{marin2017productivity}. National Net Zero strategies that do not address procurement monopolisation are therefore structurally incomplete.",
    "\\textbf{Scale and structural lock-in: the Brown Monopoly Problem.} "
    "The structural consequence of procurement monopolisation is quantifiable at "
    "NDC scale: the full single-bidder portfolio accounts for an estimated 7--12\\% "
    "of aggregate EU NDC commitments (mean 9.3\\%, 90\\% CI: 7.2--11.8\\%; "
    "methodology in SI Section~29), placing \\texteuro190--250 billion in annual "
    "public spending beyond the reach of GPP policy (OECD-calibrated; see "
    "Methods)---Germany's Dead Zones alone lock approximately 18\\,Mt\\,CO"
    "\\textsubscript{2}e annually (5.8\\% of its NDC reduction commitment), while "
    "Poland's reach 6.5\\,Mt\\,CO\\textsubscript{2}e (4.4\\% of its reduction "
    "target)\\cite{gcb2023,unfccc2021ndc}; Dead Zone carbon represents 3--6\\% of "
    "national Paris Agreement reduction targets in major European economies "
    "(Dead Zone-specific). This structural pathology defines what we term the "
    "Brown Monopoly Problem: de facto monopoly provision---not necessarily monopoly "
    "power, but single-source procurement arising from market thinness, narrow "
    "specifications, or poor publicity---in high-carbon sectors. Unlike conventional "
    "market failures correctable by price signals, Dead Zone lock-in is "
    "self-reinforcing---entrenched suppliers face no competitive pressure to adopt "
    "cleaner technology, contracting authorities lack alternatives for environmental "
    "conditionality, and long-term dependent relationships ($11+$ repeat transactions "
    "with same supplier, showing $+54.5\\%$ carbon intensity vs.~first-time awards; "
    "SI Table~S23) deepen the enclosure over time. Three political economy dynamics "
    "sustain this lock-in: incumbent suppliers invest in relationship-specific assets "
    "that raise switching costs; procurement officers face asymmetric incentives where "
    "sole-source awards minimise protest risk and administrative burden while carbon "
    "costs remain invisible\\cite{decarolis2020rules}; and the absence of "
    "carbon-linked procurement data---the measurement gap this study addresses---means "
    "the environmental cost of Dead Zones has been structurally unobservable to "
    "policymakers. These are portfolio-level estimates based on EXIOBASE sector "
    "averages; actual emissions locked in Dead Zones may be substantially larger given "
    "5--10$\\times$ within-sector firm-level variation\\cite{marin2017productivity}. "
    "National Net Zero strategies that do not address procurement monopolisation are "
    "therefore structurally incomplete.",
)
if bm_modified == bm_text:
    print("[WARN] Brown Monopoly modification may have failed - checking substring...")
    # Print first 200 chars of existing text to debug
    print("  Existing start:", repr(bm_text[:200]))
else:
    print("[OK] Brown Monopoly paragraph restructured to open with NDC quantification")

# === Rebuild Discussion in new order ===
# New order: [header, gov*, bidder_paradox, within_sector, bm*, policy_arch, monopoly_tax, scope, conclusion]
section_header = parts[0]  # '\n\section{Discussion}'

new_disc = (
    section_header
    + "\n\n"
    + gov_modified
    + "\n\n"
    + paragraphs["bidder_paradox"][1]
    + "\n\n"
    + paragraphs["within_sector"][1]
    + "\n\n"
    + bm_modified
    + "\n\n"
    + paragraphs["policy_arch"][1]
    + "\n\n"
    + paragraphs["monopoly_tax"][1]
    + "\n\n"
    + paragraphs["scope"][1]
    + "\n\n"
    + paragraphs["conclusion"][1]
)

# Reconstruct full file
new_content = content[:disc_start] + new_disc + content[disc_end:]

with open("NC_Submission/manuscript.tex", "w", encoding="utf-8") as f:
    f.write(new_content)

print("\n[OK] Discussion restructured and file written")
print(f"  Old Discussion length: {len(disc_section)} chars")
print(f"  New Discussion length: {len(new_disc)} chars")

# Verify new order by checking the sequence of bold headings
new_headings = re.findall(r"\\textbf\{([^}]+)\}", new_disc)
print("\nNew Discussion paragraph order:")
for h in new_headings[:12]:
    if (
        "Competition" in h
        or "bidder" in h
        or "within-sector" in h
        or "within_sector" in h
        or "Brown" in h
        or "Scale" in h
        or "Policy" in h
        or "Monopoly Tax" in h
        or "Scope" in h
        or "Conclusion" in h
    ):
        print(f"  → {h}")
