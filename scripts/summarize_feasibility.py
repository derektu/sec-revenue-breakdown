#!/usr/bin/env python3
"""盤點三十家既有證據、期間與分類規則，不改完成判定。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from cohort_rule_catalog import catalog
from enforce_sec_primary_source import selected_is_sec

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / 'research/cross-source-final-20261104/completion-status.json'
COVERAGE = ROOT / 'research/remaining-sec-coverage-20261104/coverage.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def operands(fact):
    yield fact
    for key in ['annual_evidence', 'nine_month_evidence']:
        if fact.get(key):
            yield from operands(fact[key])
    for item in fact.get('aggregation_evidence', []):
        yield from operands(item)


def inventory():
    summary = temporal.load(SUMMARY)
    coverage = {c['ticker']: c for c in temporal.load(COVERAGE)['companies']}
    rules = catalog()
    companies = []
    ref_totals = Counter()
    comparison_totals = Counter()
    for company in summary['companies']:
        ticker = company['ticker']
        path = ROOT / company['local_detail_path']
        if sha(path) != company['local_detail_sha256']:
            raise ValueError('Company detail hash changed: ' + ticker)
        rows = temporal.load(path)
        reference_rows = [r for r in rows if r['status'] != 'reference_not_applicable_evidenced'
            and (company.get('cross_source_changed') or r.get('source') == company['reference'])]
        primary = reference_rows if company['status'] == 'OK' else [
            {'period_end': q['period_end'], 'category': label, 'selected': selected}
            for q in coverage[ticker]['quarters'] for label, selected in q['outputs'].items()]
        identities = [(r.get('period_end', r.get('sec_period_end')), r['category']) for r in primary]
        if len(set(identities)) != len(identities):
            raise ValueError('Duplicate primary period and category: ' + ticker)
        if company['status'] == 'OK' and len(primary) != company['quarterly_cells']:
            raise ValueError('Primary count differs from completion receipt: ' + ticker)
        periods = set()
        categories = set()
        source_urls = set()
        forms = set()
        quarter_reference_sources = {}
        comparisons = Counter()
        for row in reference_rows:
            end = row.get('period_end', row.get('sec_period_end'))
            if end not in company['target_periods']:
                raise ValueError('Reference outside target window: ' + ticker)
            sources = row.get('reference_sources', [row.get('source')])
            quarter_reference_sources.setdefault(end, set()).update(sources)
            comparisons[row['status']] += 1
        for sources in quarter_reference_sources.values():
            ref_totals.update(sources)
        for row in primary:
            end = row.get('period_end', row.get('sec_period_end'))
            selected = row['selected']
            if not selected_is_sec(selected):
                raise ValueError('Non-SEC primary: ' + ticker)
            if any(f['enddate'] != end for f in selected['facts']):
                raise ValueError('Primary period mismatch: ' + ticker)
            periods.add(end)
            categories.add(row['category'])
            for fact in selected['facts']:
                for item in operands(fact):
                    source_urls.add(item['source_url'])
                    forms.add(item.get('form') or 'not_recorded_on_selected_operand')
        if periods != set(company['target_periods']) or len(periods) != 8:
            raise ValueError('Eight SEC periods incomplete: ' + ticker)
        definitions = [spec for group in rules[ticker].values() for spec in group.values()]
        comparison_totals.update(comparisons)
        alternatives = [terms for spec in definitions for terms in spec['alternatives']]
        companies.append({'ticker': ticker, 'comparison_status': company['status'],
            'target_periods': company['target_periods'], 'SEC_periods_verified': sorted(periods),
            'SEC_numeric_output_cells': len(primary), 'primary_output_category_count': len(categories),
            'primary_output_categories': sorted(categories), 'reference_periods': sorted(quarter_reference_sources),
            'reference_sources_by_period': {k: sorted(v) for k, v in sorted(quarter_reference_sources.items())},
            'reference_comparison_counts': dict(comparisons), 'SEC_document_urls': sorted(source_urls),
            'SEC_form_labels_on_operands': sorted(forms),
            'catalog_mapping_entries_by_source': {s: len(v) for s, v in rules[ticker].items()},
            'catalog_mapping_entries': len(definitions), 'catalog_alternative_scope_sets': len(alternatives),
            'catalog_operand_terms': sum(len(terms) for terms in alternatives),
            'catalog_rules_exclude_procedural_repairs_and_non_catalog_parsers': True,
            'detail_sha256_verified': sha(path), 'latest_period_seen_during_development': True,
            'independent_human_second_review_recorded': False, 'human_minutes_measured': None})
    return {'company_count': len(companies), 'SEC_eight_quarter_companies': len(companies),
        'SEC_company_quarter_slots': sum(len(c['SEC_periods_verified']) for c in companies),
        'SEC_numeric_output_cells': sum(c['SEC_numeric_output_cells'] for c in companies),
        'cross_source_OK': summary['ok_count'], 'historical_fixed_vendor_OK': summary['historical_fixed_vendor_ok_count'],
        'comparison_company_quarter_slots_present': sum(len(c['reference_periods']) for c in companies),
        'reference_source_quarter_slots_not_independent': dict(ref_totals),
        'reference_numeric_comparison_cells': sum(comparison_totals.values()),
        'reference_comparison_counts': dict(comparison_totals),
        'company_specific_active_output_definitions': sum(c['primary_output_category_count'] for c in companies),
        'catalog_mapping_entries': sum(c['catalog_mapping_entries'] for c in companies),
        'catalog_alternative_scope_sets': sum(c['catalog_alternative_scope_sets'] for c in companies),
        'catalog_operand_terms': sum(c['catalog_operand_terms'] for c in companies),
        'independent_vendor_eight_quarter_score': None, 'full_disclosure_recall': None,
        'unseen_quarter_tests': 0, 'all_periods_seen_during_development': True,
        'human_time_minutes': None, 'end_to_end_batch_throughput': None,
        'SEC_raw_HTML_all_reparsed_in_this_inventory': False,
        'source_summary_sha256': sha(SUMMARY), 'source_coverage_sha256': sha(COVERAGE),
        'catalog_code_sha256': sha(ROOT / 'scripts/cohort_rule_catalog.py'),
        'inventory_code_sha256': sha(__file__), 'companies': companies}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    result = inventory()
    temporal.save(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ['companies']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
