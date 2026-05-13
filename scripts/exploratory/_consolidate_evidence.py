import json

files = {
    'within_supplier': 'results/within_sector/within_supplier_analysis.json',
    'within_sector': 'results/within_sector/within_sector_validation.json',
    'ted_eprtr': 'results/validation/ted_eprtr_matching.json',
    'firm_validation': 'results/validation/firm_level_validation.json',
    'sbti_v2': 'results/validation/sbti_winner_matching_v2.json',
}

for name, path in files.items():
    with open(path) as f:
        d = json.load(f)
    print(f'=== {name} ===')
    if name == 'within_supplier':
        ws = d['within_supplier_all']
        wr = d['within_supplier_robust']
        print(f"  N={ws['n_suppliers']:,}, premium={ws['premium_pct']}%, d={ws['cohens_d']}, t={ws['paired_t']}, p={ws['p_value']:.2e}")
        print(f"  Robust: N={wr['n_suppliers']:,}, prem={wr['premium_pct']}%, d={wr['cohens_d']}")
    elif name == 'within_sector':
        kf = d['key_findings']
        for k, v in kf.items():
            print(f'  {v}')
    elif name == 'ted_eprtr':
        o = d['overall']
        print(f"  Overall: N_SB={o['n_sb']}, N_MB={o['n_mb']}, premium={o['premium_pct']}%, d={o['d']}, t={o['t']}")
        wcs = d['within_country_sector']
        print(f"  Within country-sector: {wcs['n_groups']} groups, {wcs['n_positive']} positive")
        print("  Within-sector results:")
        for sector, vals in d['within_sector'].items():
            print(f"    {sector}: premium={vals['premium_pct']}%, t={vals['t']:.2f}, n={vals['n_sb']+vals['n_mb']}")
    elif name == 'firm_validation':
        h = d['headline_findings']
        print(f"  Combined prem: {h['combined_premium_with_technical_pct']}%")
        print(f"  EUETS CV: {h['euets_mean_cv']}")
        print(f"  SBTi DZ EU firms: {h['sbti_dead_zone_firms_eu']}")
    elif name == 'sbti_v2':
        m = d['matching']
        s = d['selection']
        print(f"  Matched: {m['matched_supplier_names']:,} firms, {m['total_sbti_contracts']:,} contracts")
        print(f"  Comp rate: {s['sbti_rate_competitive_pct']:.4f}%, SB rate: {s['sbti_rate_sb_pct']:.4f}%")
        print(f"  Ratio: {s['ratio']:.2f}x")
    print()
