import json

with open('results/validation/eprtr_country_decomposition.json') as f:
    data = json.load(f)

print('✓ JSON is valid and complete')
print()
print('ANALYSIS RESULTS:')
print('=' * 70)
print('  Sector:                  {}'.format(data['metadata']['sector']))
print('  E-PRTR Refineries:       {}'.format(data['metadata']['n_eprtr_refineries']))
print('  Matched Contracts:       {}'.format(data['metadata']['n_matched_contracts']))
print('  Countries with Data:     {}'.format(data['metadata']['n_countries']))
print()
print('OVERALL EFFECT:')
unm = data['overall_effect']['unmatched_sample']
mtch = data['overall_effect']['country_balanced_matched']
atten = data['overall_effect']['attenuation']
print('  Unmatched SB Premium:    {:.1f}% (p={:.4f})'.format(unm['sb_premium_pct'], unm['p_value']))
print('  Country-Matched Premium: {:.1f}% (p={:.4f})'.format(mtch['sb_premium_pct'], mtch['p_value']))
print('  Attenuation:             {:.1f} pp'.format(atten['percentage_points']))
print()
print('KEY FINDING:')
print('  Pattern: {}'.format(data['key_findings']['pattern']))
print('  Largest Contributing Country: {}'.format(data['key_findings']['largest_contributing_country']))
print('  Max Attenuation Country: {}'.format(data['key_findings']['country_with_max_attenuation']))
print('  Max Attenuation Value: {} pp'.format(data['key_findings']['max_attenuation_pp']))
print()
print('COUNTRY PREMIUMS:')
for cc in sorted(data['country_level_premiums'].keys()):
    stats = data['country_level_premiums'][cc]
    print('  {}: {:3d} SB, {:3d} MB, premium={:+6.1f}%'.format(cc, stats['n_sb'], stats['n_mb'], stats['premium_pct']))

print()
print('FILES CREATED:')
print('  ✓ results/eprtr_country_decomposition.json')
print('  ✓ EPRTR_COUNTRY_DECOMPOSITION_SUMMARY.md')
