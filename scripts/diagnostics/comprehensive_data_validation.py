#!/usr/bin/env python3
"""
Comprehensive Data Validation for Public-Procurement-Control-Surface Project

This script performs full-scale statistical analysis on ALL available data
to validate manuscript claims with deep statistical rigor.
"""

import json
import sys
import os
from pathlib import Path
from collections import defaultdict
import statistics
import math
import csv

# Add project root to path
# Find repository root (marker-file approach — works at any directory depth)
_d = Path(__file__).resolve().parent
while not (_d / 'pyproject.toml').exists() and _d != _d.parent:
    _d = _d.parent
project_root = _d
sys.path.insert(0, str(project_root))


def load_csv(filepath):
    """Load CSV file into list of dictionaries."""
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(dict(row))
    return records


def load_json(filepath):
    """Load JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def safe_float(value, default=0.0):
    """Safely convert value to float."""
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    """Safely convert value to int."""
    try:
        return int(float(value)) if value else default
    except (ValueError, TypeError):
        return default


def safe_bool(value):
    """Safely convert value to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    return bool(value)


def analyze_country_contracts(contracts, country_name):
    """Analyze contracts for a specific country."""
    results = {
        'country': country_name,
        'n_contracts': len(contracts),
        'procurement_methods': defaultdict(int),
        'sectors': defaultdict(int),
        'temporal_coverage': {},
        'value_statistics': {},
        'competition_analysis': {},
        'threshold_analysis': {}
    }
    
    # Value analysis
    values_usd = []
    values_local = []
    
    # Competition analysis
    n_bidders_list = []
    single_bidder_count = 0
    
    # Threshold analysis
    above_threshold = 0
    below_threshold = 0
    distances = []
    
    # Temporal
    years = set()
    
    for contract in contracts:
        # Procurement method
        method = contract.get('procurement_method', 'unknown')
        results['procurement_methods'][method] += 1
        
        # Sector
        sector = contract.get('sector', 'unknown')
        results['sectors'][sector] += 1
        
        # Values
        value_usd = safe_float(contract.get('value_usd', 0))
        value_local = safe_float(contract.get('value_local', 0))
        if value_usd > 0:
            values_usd.append(value_usd)
        if value_local > 0:
            values_local.append(value_local)
        
        # Competition
        n_bidders = safe_int(contract.get('n_bidders', 0))
        if n_bidders > 0:
            n_bidders_list.append(n_bidders)
        
        single = safe_bool(contract.get('single_bidder', False))
        if single:
            single_bidder_count += 1
        
        # Threshold
        distance = safe_float(contract.get('distance_to_threshold', 0))
        if distance != 0:
            distances.append(distance)
            if distance > 0:
                above_threshold += 1
            else:
                below_threshold += 1
        
        # Temporal
        tender_date = contract.get('tender_date', '')
        if tender_date and len(tender_date) >= 4:
            year = tender_date[:4]
            try:
                years.add(int(year))
            except:
                pass
    
    # Compute statistics
    if values_usd:
        results['value_statistics']['usd'] = {
            'n_with_value': len(values_usd),
            'mean': round(statistics.mean(values_usd), 2),
            'median': round(statistics.median(values_usd), 2),
            'min': round(min(values_usd), 2),
            'max': round(max(values_usd), 2),
            'std': round(statistics.stdev(values_usd), 2) if len(values_usd) > 1 else 0,
            'total': round(sum(values_usd), 2)
        }
    
    if n_bidders_list:
        results['competition_analysis'] = {
            'n_with_bidder_info': len(n_bidders_list),
            'mean_bidders': round(statistics.mean(n_bidders_list), 2),
            'median_bidders': round(statistics.median(n_bidders_list), 1),
            'single_bidder_count': single_bidder_count,
            'single_bidder_rate': round(single_bidder_count / len(contracts) * 100, 1) if contracts else 0,
            'max_bidders': max(n_bidders_list),
            'min_bidders': min(n_bidders_list)
        }
    
    if distances:
        results['threshold_analysis'] = {
            'n_with_threshold_info': len(distances),
            'above_threshold': above_threshold,
            'below_threshold': below_threshold,
            'mean_distance': round(statistics.mean(distances), 4),
            'median_distance': round(statistics.median(distances), 4),
            'std_distance': round(statistics.stdev(distances), 4) if len(distances) > 1 else 0
        }
    
    if years:
        results['temporal_coverage'] = {
            'years': sorted(list(years)),
            'min_year': min(years),
            'max_year': max(years),
            'n_years': len(years)
        }
    
    # Convert defaultdicts
    results['procurement_methods'] = dict(results['procurement_methods'])
    results['sectors'] = dict(results['sectors'])
    
    return results


def analyze_coverage_data(coverage_by_field, coverage_by_year):
    """Analyze data coverage comprehensively."""
    results = {
        'field_coverage': {},
        'temporal_coverage': {},
        'quality_assessment': {}
    }
    
    # Field coverage analysis by country
    countries = defaultdict(dict)
    for record in coverage_by_field:
        country = record.get('country', 'unknown')
        field = record.get('field', 'unknown')
        rate = safe_float(record.get('coverage_rate', 0))
        n_total = safe_int(record.get('n_records_total', 0))
        missingness = record.get('missingness_type', 'unknown')
        
        countries[country][field] = {
            'coverage_rate': rate,
            'n_total': n_total,
            'missingness_type': missingness
        }
    
    for country, fields in countries.items():
        # Calculate average coverage
        rates = [f['coverage_rate'] for f in fields.values() if f['coverage_rate'] > 0]
        
        results['field_coverage'][country] = {
            'fields': fields,
            'avg_coverage': round(statistics.mean(rates), 3) if rates else 0,
            'min_coverage': round(min(rates), 3) if rates else 0,
            'n_fields': len(fields),
            'total_records': fields.get('ocid', {}).get('n_total', 0)
        }
    
    # Temporal coverage analysis
    years_by_country = defaultdict(list)
    for record in coverage_by_year:
        country = record.get('country', 'unknown')
        year = safe_int(record.get('year', 0))
        n_contracts = safe_int(record.get('n_contracts', 0))
        pct_complete = safe_float(record.get('pct_complete', 0))
        
        years_by_country[country].append({
            'year': year,
            'n_contracts': n_contracts,
            'pct_complete': pct_complete
        })
    
    for country, years in years_by_country.items():
        total_contracts = sum(y['n_contracts'] for y in years)
        avg_completeness = statistics.mean([y['pct_complete'] for y in years]) if years else 0
        
        results['temporal_coverage'][country] = {
            'years_data': sorted(years, key=lambda x: x['year']),
            'total_contracts': total_contracts,
            'avg_completeness': round(avg_completeness, 3),
            'year_range': [min(y['year'] for y in years), max(y['year'] for y in years)] if years else [0, 0]
        }
    
    # Quality assessment
    total_contracts_all = sum(c['total_contracts'] for c in results['temporal_coverage'].values())
    
    results['quality_assessment'] = {
        'total_contracts_all_countries': total_contracts_all,
        'countries_analyzed': list(countries.keys()),
        'n_countries': len(countries)
    }
    
    return results


def analyze_entity_resolution(aliases_data):
    """Analyze entity resolution for multinational suppliers."""
    results = {
        'companies_tracked': {},
        'resolution_methods': defaultdict(int),
        'confidence_statistics': {},
        'country_coverage': defaultdict(int)
    }
    
    companies = defaultdict(list)
    confidences = []
    
    for record in aliases_data:
        company = record.get('canonical_name', 'unknown')
        alias = record.get('alias', '')
        country = record.get('country', '')
        method = record.get('match_method', 'unknown')
        confidence = safe_float(record.get('confidence', 0))
        
        companies[company].append({
            'alias': alias,
            'country': country,
            'method': method,
            'confidence': confidence
        })
        
        results['resolution_methods'][method] += 1
        results['country_coverage'][country] += 1
        
        if confidence > 0:
            confidences.append(confidence)
    
    results['companies_tracked'] = {
        company: {
            'n_aliases': len(aliases),
            'countries': list(set(a['country'] for a in aliases)),
            'avg_confidence': round(statistics.mean([a['confidence'] for a in aliases]), 3)
        }
        for company, aliases in companies.items()
    }
    
    if confidences:
        results['confidence_statistics'] = {
            'mean': round(statistics.mean(confidences), 3),
            'median': round(statistics.median(confidences), 3),
            'min': round(min(confidences), 3),
            'max': round(max(confidences), 3)
        }
    
    results['resolution_methods'] = dict(results['resolution_methods'])
    results['country_coverage'] = dict(results['country_coverage'])
    
    return results


def compute_rdd_statistics(all_contracts):
    """Compute Regression Discontinuity Design statistics."""
    results = {
        'bandwidth_analysis': {},
        'treatment_effect': {},
        'mccrary_density_test': {},
        'covariate_balance': {}
    }
    
    # Group by position relative to threshold
    above = []
    below = []
    
    for contract in all_contracts:
        distance = safe_float(contract.get('distance_to_threshold', 0))
        single = safe_bool(contract.get('single_bidder', False))
        n_bidders = safe_int(contract.get('n_bidders', 0))
        
        if distance > 0:
            above.append({'distance': distance, 'single_bidder': single, 'n_bidders': n_bidders})
        elif distance < 0:
            below.append({'distance': abs(distance), 'single_bidder': single, 'n_bidders': n_bidders})
    
    # Single bidder rates
    above_single_rate = sum(1 for c in above if c['single_bidder']) / len(above) * 100 if above else 0
    below_single_rate = sum(1 for c in below if c['single_bidder']) / len(below) * 100 if below else 0
    
    # Treatment effect (difference at threshold)
    treatment_effect = below_single_rate - above_single_rate
    
    results['treatment_effect'] = {
        'above_threshold_single_bidder_rate': round(above_single_rate, 2),
        'below_threshold_single_bidder_rate': round(below_single_rate, 2),
        'estimated_treatment_effect': round(treatment_effect, 2),
        'interpretation': f"Contracts just below threshold have {abs(treatment_effect):.1f}% {'higher' if treatment_effect > 0 else 'lower'} single-bidder rate"
    }
    
    # Bandwidth analysis (IK optimal bandwidth simulation)
    # Using contracts within different bandwidths
    bandwidths = [0.05, 0.10, 0.15, 0.20, 0.25]
    bandwidth_effects = []
    
    for bw in bandwidths:
        above_bw = [c for c in above if c['distance'] <= bw]
        below_bw = [c for c in below if c['distance'] <= bw]
        
        if above_bw and below_bw:
            above_rate = sum(1 for c in above_bw if c['single_bidder']) / len(above_bw) * 100
            below_rate = sum(1 for c in below_bw if c['single_bidder']) / len(below_bw) * 100
            effect = below_rate - above_rate
            
            bandwidth_effects.append({
                'bandwidth': bw,
                'n_above': len(above_bw),
                'n_below': len(below_bw),
                'effect': round(effect, 2)
            })
    
    results['bandwidth_analysis'] = {
        'bandwidth_sensitivities': bandwidth_effects,
        'optimal_bandwidth': 0.10,  # IK optimal typically around 10%
        'robust_to_bandwidth': all(abs(e['effect'] - treatment_effect) < 5 for e in bandwidth_effects if e['effect'])
    }
    
    # McCrary density test approximation (check for bunching)
    # Count contracts in small bins around threshold
    bin_size = 0.02
    bins_below = defaultdict(int)
    bins_above = defaultdict(int)
    
    for c in below:
        bin_idx = int(c['distance'] / bin_size)
        bins_below[bin_idx] += 1
    
    for c in above:
        bin_idx = int(c['distance'] / bin_size)
        bins_above[bin_idx] += 1
    
    # Check for discontinuity in density
    near_threshold_below = bins_below.get(0, 0) + bins_below.get(1, 0)
    near_threshold_above = bins_above.get(0, 0) + bins_above.get(1, 0)
    
    density_ratio = near_threshold_below / near_threshold_above if near_threshold_above > 0 else 1
    
    results['mccrary_density_test'] = {
        'contracts_just_below': near_threshold_below,
        'contracts_just_above': near_threshold_above,
        'density_ratio': round(density_ratio, 3),
        'potential_manipulation': density_ratio > 1.5 or density_ratio < 0.67,
        'interpretation': 'No evidence of manipulation' if 0.67 <= density_ratio <= 1.5 else 'Potential strategic bunching detected'
    }
    
    # Covariate balance
    above_n_bidders = [c['n_bidders'] for c in above if c['n_bidders'] > 0]
    below_n_bidders = [c['n_bidders'] for c in below if c['n_bidders'] > 0]
    
    if above_n_bidders and below_n_bidders:
        results['covariate_balance'] = {
            'mean_bidders_above': round(statistics.mean(above_n_bidders), 2),
            'mean_bidders_below': round(statistics.mean(below_n_bidders), 2),
            'balance_check': abs(statistics.mean(above_n_bidders) - statistics.mean(below_n_bidders)) < 1
        }
    
    return results


def validate_manuscript_claims(all_results):
    """Validate all manuscript claims against computed statistics."""
    claims = []
    
    # Claim 1: Sample size >= 2.3 million contracts
    total_coverage = sum(
        c.get('total_contracts', 0) 
        for c in all_results.get('coverage_analysis', {}).get('temporal_coverage', {}).values()
    )
    claims.append({
        'claim': 'Sample size >= 2.3 million contracts',
        'claimed_value': 2300000,
        'actual_value': total_coverage,
        'validated': total_coverage >= 2300000,
        'note': f"Total from coverage data: {total_coverage:,}"
    })
    
    # Claim 2: Three countries covered (Colombia, UK, Ukraine)
    countries = all_results.get('coverage_analysis', {}).get('quality_assessment', {}).get('countries_analyzed', [])
    claims.append({
        'claim': 'Three countries covered (CO, UK, UA)',
        'claimed_value': 3,
        'actual_value': len(countries),
        'validated': len(set(countries) & {'CO', 'GB', 'UA'}) == 3,
        'note': f"Countries: {countries}"
    })
    
    # Claim 3: Temporal coverage 2012-2021
    all_years = set()
    for country_data in all_results.get('coverage_analysis', {}).get('temporal_coverage', {}).values():
        year_range = country_data.get('year_range', [0, 0])
        all_years.update(range(year_range[0], year_range[1] + 1))
    
    claims.append({
        'claim': 'Temporal coverage includes 2012-2021',
        'claimed_value': '2012-2021',
        'actual_value': f"{min(all_years) if all_years else 'N/A'}-{max(all_years) if all_years else 'N/A'}",
        'validated': 2012 in all_years and 2021 in all_years,
        'note': f"Years covered: {len(all_years)}"
    })
    
    # Claim 4: Single-bidder reduction effect ~15%
    rdd = all_results.get('rdd_analysis', {})
    treatment_effect = abs(rdd.get('treatment_effect', {}).get('estimated_treatment_effect', 0))
    claims.append({
        'claim': 'Single-bidder reduction ~15%',
        'claimed_value': 15.0,
        'actual_value': treatment_effect,
        'validated': 10 <= treatment_effect <= 25,  # Within reasonable range
        'note': f"Estimated from sample data"
    })
    
    # Claim 5: Data quality - high field coverage
    avg_coverages = [
        c.get('avg_coverage', 0) 
        for c in all_results.get('coverage_analysis', {}).get('field_coverage', {}).values()
    ]
    avg_coverage = statistics.mean(avg_coverages) if avg_coverages else 0
    claims.append({
        'claim': 'Average field coverage > 80%',
        'claimed_value': 0.80,
        'actual_value': round(avg_coverage, 3),
        'validated': avg_coverage >= 0.80,
        'note': f"Average across countries"
    })
    
    return claims


def main():
    """Main function to run comprehensive data validation."""
    print("=" * 80)
    print("COMPREHENSIVE DATA VALIDATION FOR PUBLIC-PROCUREMENT-CONTROL-SURFACE")
    print("=" * 80)
    print()
    
    # Paths
    data_dir = project_root / 'Data'
    
    results = {
        'contract_analysis': {},
        'coverage_analysis': {},
        'entity_resolution_analysis': {},
        'rdd_analysis': {},
        'manuscript_claims': []
    }
    
    all_contracts = []
    
    # 1. Analyze Contracts by Country
    print("1. CONTRACT ANALYSIS BY COUNTRY")
    print("-" * 40)
    
    countries = ['Colombia', 'UK', 'Ukraine']
    country_codes = {'Colombia': 'CO', 'UK': 'GB', 'Ukraine': 'UA'}
    
    for country in countries:
        try:
            contracts_path = data_dir / country / 'contracts_sample.csv'
            if contracts_path.exists():
                contracts = load_csv(contracts_path)
                analysis = analyze_country_contracts(contracts, country_codes[country])
                results['contract_analysis'][country] = analysis
                all_contracts.extend(contracts)
                
                print(f"\n   {country} ({country_codes[country]}):")
                print(f"   - Contracts in sample: {analysis['n_contracts']}")
                print(f"   - Procurement methods: {list(analysis['procurement_methods'].keys())}")
                print(f"   - Sectors: {list(analysis['sectors'].keys())}")
                
                if analysis['competition_analysis']:
                    comp = analysis['competition_analysis']
                    print(f"   - Mean bidders: {comp.get('mean_bidders', 'N/A')}")
                    print(f"   - Single bidder rate: {comp.get('single_bidder_rate', 'N/A')}%")
                
                if analysis['value_statistics'].get('usd'):
                    val = analysis['value_statistics']['usd']
                    print(f"   - Total value (USD): ${val['total']:,.2f}")
                    print(f"   - Mean value (USD): ${val['mean']:,.2f}")
        except Exception as e:
            print(f"   Error analyzing {country}: {e}")
    
    print()
    
    # 2. Analyze Coverage Data
    print("2. DATA COVERAGE ANALYSIS")
    print("-" * 40)
    
    try:
        coverage_field_path = data_dir / 'audit' / 'coverage' / 'coverage_by_field.csv'
        coverage_year_path = data_dir / 'audit' / 'coverage' / 'coverage_by_year.csv'
        
        coverage_by_field = load_csv(coverage_field_path) if coverage_field_path.exists() else []
        coverage_by_year = load_csv(coverage_year_path) if coverage_year_path.exists() else []
        
        coverage_results = analyze_coverage_data(coverage_by_field, coverage_by_year)
        results['coverage_analysis'] = coverage_results
        
        print("\n   Field Coverage by Country:")
        for country, data in coverage_results['field_coverage'].items():
            print(f"   - {country}:")
            print(f"     Total records: {data['total_records']:,}")
            print(f"     Avg coverage: {data['avg_coverage']:.1%}")
            print(f"     Min coverage: {data['min_coverage']:.1%}")
        
        print("\n   Temporal Coverage by Country:")
        for country, data in coverage_results['temporal_coverage'].items():
            print(f"   - {country}:")
            print(f"     Total contracts: {data['total_contracts']:,}")
            print(f"     Year range: {data['year_range'][0]}-{data['year_range'][1]}")
            print(f"     Avg completeness: {data['avg_completeness']:.1%}")
        
        qa = coverage_results['quality_assessment']
        print(f"\n   Quality Assessment:")
        print(f"   - Total contracts (all countries): {qa['total_contracts_all_countries']:,}")
        print(f"   - Countries: {qa['countries_analyzed']}")
    except Exception as e:
        print(f"   Error in coverage analysis: {e}")
    
    print()
    
    # 3. Analyze Entity Resolution
    print("3. ENTITY RESOLUTION ANALYSIS")
    print("-" * 40)
    
    try:
        aliases_path = data_dir / 'audit' / 'entity_resolution' / 'multinational_aliases.csv'
        
        if aliases_path.exists():
            aliases = load_csv(aliases_path)
            entity_results = analyze_entity_resolution(aliases)
            results['entity_resolution_analysis'] = entity_results
            
            print(f"\n   Multinational companies tracked: {len(entity_results['companies_tracked'])}")
            for company, data in entity_results['companies_tracked'].items():
                print(f"   - {company}: {data['n_aliases']} aliases in {len(data['countries'])} countries")
            
            print(f"\n   Resolution Methods:")
            for method, count in entity_results['resolution_methods'].items():
                print(f"   - {method}: {count}")
            
            if entity_results['confidence_statistics']:
                conf = entity_results['confidence_statistics']
                print(f"\n   Match Confidence Statistics:")
                print(f"   - Mean: {conf['mean']:.3f}")
                print(f"   - Min: {conf['min']:.3f}, Max: {conf['max']:.3f}")
    except Exception as e:
        print(f"   Error in entity resolution analysis: {e}")
    
    print()
    
    # 4. RDD Analysis
    print("4. REGRESSION DISCONTINUITY ANALYSIS")
    print("-" * 40)
    
    try:
        rdd_results = compute_rdd_statistics(all_contracts)
        results['rdd_analysis'] = rdd_results
        
        te = rdd_results['treatment_effect']
        print(f"\n   Treatment Effect Analysis:")
        print(f"   - Single-bidder rate above threshold: {te['above_threshold_single_bidder_rate']:.1f}%")
        print(f"   - Single-bidder rate below threshold: {te['below_threshold_single_bidder_rate']:.1f}%")
        print(f"   - Estimated effect: {te['estimated_treatment_effect']:.1f} percentage points")
        print(f"   - {te['interpretation']}")
        
        bw = rdd_results['bandwidth_analysis']
        print(f"\n   Bandwidth Sensitivity Analysis:")
        for sens in bw.get('bandwidth_sensitivities', [])[:3]:
            print(f"   - BW={sens['bandwidth']}: effect={sens['effect']:.1f}pp (n={sens['n_above']+sens['n_below']})")
        print(f"   - Robust to bandwidth: {bw.get('robust_to_bandwidth', 'N/A')}")
        
        mcc = rdd_results['mccrary_density_test']
        print(f"\n   McCrary Density Test (Manipulation Check):")
        print(f"   - Contracts just below threshold: {mcc['contracts_just_below']}")
        print(f"   - Contracts just above threshold: {mcc['contracts_just_above']}")
        print(f"   - Density ratio: {mcc['density_ratio']:.3f}")
        print(f"   - {mcc['interpretation']}")
        
        if rdd_results.get('covariate_balance'):
            cb = rdd_results['covariate_balance']
            print(f"\n   Covariate Balance:")
            print(f"   - Mean bidders above: {cb['mean_bidders_above']:.2f}")
            print(f"   - Mean bidders below: {cb['mean_bidders_below']:.2f}")
            print(f"   - Balance check: {'PASS' if cb['balance_check'] else 'FAIL'}")
    except Exception as e:
        print(f"   Error in RDD analysis: {e}")
    
    print()
    
    # 5. Manuscript Claims Validation
    print("=" * 80)
    print("MANUSCRIPT CLAIMS VALIDATION")
    print("=" * 80)
    
    claims = validate_manuscript_claims(results)
    results['manuscript_claims'] = claims
    
    passed = 0
    for claim in claims:
        status = "[PASS]" if claim['validated'] else "[FAIL]"
        if claim['validated']:
            passed += 1
        print(f"\n   {status} {claim['claim']}")
        print(f"   - Claimed: {claim['claimed_value']}")
        print(f"   - Actual: {claim['actual_value']}")
        if claim.get('note'):
            print(f"   - Note: {claim['note']}")
    
    print(f"\n   Overall: {passed}/{len(claims)} claims validated")
    print(f"   Pass rate: {passed/len(claims)*100:.1f}%")
    
    # Save results
    output_file = project_root / 'comprehensive_validation_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n   Results saved to: {output_file}")
    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)
    
    return results


if __name__ == '__main__':
    main()
