#!/usr/bin/env python3
"""重播剩餘六家八季 SEC 輸出；不讀取第三方原值，不改完成判定。"""
import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from cohort_rule_audit import resolve
from cohort_rule_catalog import catalog, rule, leaf, S, C, G, P
from enforce_sec_primary_source import selected_is_sec
from extend_issuer_repairs import pools_for, selection
from repair_chevron_q4 import normalize_old_scope
from evaluate_progressive_sec import period_facts
from parse_progressive_sec_html import parse_html
from evaluate_xom_sec import quarter, selection as table_selection
from evaluate_eight_quarter_status import period_coverage

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / 'research/reference-gap-completion-20261104/completion-status.json'
REVENUE = 'us-gaap:Revenues'
XOM_MEMBERS = dict(zip(['上游', '能源產品', '化工產品', '特種產品'], ['Upstream', 'EnergyProducts', 'ChemicalProducts', 'SpecialtyProducts']))
XOM_ENGLISH = dict(zip(XOM_MEMBERS, ['Upstream', 'Energy Products', 'Chemical Products', 'Specialty Products']))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def xom_latest(facts, conflicts):
    """保留 all-income 與 gross-sales 兩組定義，不以未知參考挑口徑。"""
    all_income = {label: resolve(rule([leaf(REVENUE, {S: 'xom:' + member + 'Member', G: geo})
                  for geo in ['country:US', 'us-gaap:NonUsMember']]), facts, conflicts) for label, member in XOM_MEMBERS.items()}
    all_income.update({
        'Other revenues': resolve(rule(leaf(REVENUE, {C: 'us-gaap:CorporateNonSegmentMember'})), facts, conflicts),
        '分部間收入': selection('XOM', '分部間收入', facts, conflicts),
        '其他收入': resolve(rule(leaf(REVENUE, {P: 'xom:OtherRevenueMember'}, -1)), facts, conflicts),
        'Income from equity affiliates': resolve(rule(leaf(REVENUE, {P: 'xom:IncomeFromEquityAffiliatesMember'}, -1)), facts, conflicts),
        'Total revenues and other income': resolve(rule(leaf(REVENUE, {})), facts, conflicts),
        'Sales and other operating revenue': resolve(rule(leaf(REVENUE, {P: 'xom:SalesAndOtherOperatingRevenueMember'})), facts, conflicts)})
    gross = {label: selection('XOM', label, facts, conflicts) for label in [*XOM_MEMBERS, '分部間收入']}
    checks = {}
    components = list(all_income)[:8]
    if all(selected_is_sec(s) for s in all_income.values()):
        value = sum(all_income[label]['value'] for label in components)
        target = all_income['Sales and other operating revenue']
        error = sum(Decimal(str(all_income[label]['error'])) for label in components) + Decimal(str(target['error']))
        checks = {'all_income_components_to_consolidated_sales_difference_usd': value - target['value'],
            'reported_operand_error_budget_usd': str(error), 'reconciles': abs(value - target['value']) <= error}
        if not checks['reconciles']:
            raise ValueError('XOM all-income definition does not reconcile to consolidated sales')
    if all(selected_is_sec(s) for s in gross.values()) and selected_is_sec(all_income['Sales and other operating revenue']):
        checks['gross_sales_five_fields_unallocated_difference_usd'] = all_income['Sales and other operating revenue']['value'] - sum(s['value'] for s in gross.values())
    return {'all_income_with_consolidated_deductions': all_income, 'gross_sales_and_intersegment': gross}, checks


def pgr_facts():
    manifest = temporal.load(ROOT / 'research/progressive-sec-html-20261104/manifest.json'); observations = []
    for source in manifest['files']:
        path = ROOT / source['path']
        if digest(path) != source['sha256']:
            raise ValueError('PGR gzip source changed')
        raw = gzip.decompress(path.read_bytes())
        if hashlib.sha256(raw).hexdigest() != source['raw_sha256']:
            raise ValueError('PGR raw HTML source changed')
        observations.extend(parse_html(raw, source['source_url']))
    return observations


def inspect():
    summary = temporal.load(SUMMARY); results = []; pgr = pgr_facts()
    xom_file = ROOT / 'research/xom-sec-verified-20261104/XOM-parsed-SEC-facts.json'
    xom = temporal.load(xom_file)['observations']
    rules = catalog()
    for company in summary['companies']:
        if company['status'] == 'OK':
            continue
        ticker = company['ticker']; receipt_path = ROOT / f'research/cohort-rule-replay-20261104/{ticker}-freeze.json'
        receipt = temporal.load(receipt_path); baseline_path = ROOT / receipt['plan']['baseline_file']
        data = temporal.checked_data(receipt['plan'], baseline_path); temporal.verify_freeze(receipt, data)
        records, pools = pools_for(ticker, data)
        if ticker == 'CVX':
            records = sorted([normalize_old_scope(r) for r in data['raw_filings']], key=lambda r: r['filing']['filingDate'])
            pools = {r['filing']['reportDate']: temporal.runner().quarter(r['facts'], r['filing']['reportDate'], r['filing']['form'],
                [f for prior in records[:index] for f in prior['facts']]) for index, r in enumerate(records)}
        quarters = []
        for end in company['target_periods']:
            checks = {}; alternatives = {}
            if ticker == 'PGR':
                year, month, _ = map(int, end.split('-'))
                primary = {label: {'status': 'observed', 'value': fact['value'], 'facts': [fact],
                    'error': Decimal(1_000_000 if fact.get('derivation') == 'annual_minus_nine_months' else 500_000),
                    'role': 'SEC_PGR_consolidated_or_underwriting_table'} for label, fact in period_facts(pgr, year, month).items()}
            elif ticker == 'XOM' and end != '2026-09-30':
                primary = {next((zh for zh, en in XOM_ENGLISH.items() if en == label), label): table_selection(fact)
                           for label, fact in quarter(xom, end).items()}
            else:
                facts, conflicts = pools[end]
                if ticker == 'XOM':
                    alternatives, checks = xom_latest(facts, conflicts)
                    primary = alternatives['all_income_with_consolidated_deductions']
                else:
                    primary = {label: selection(ticker, label, facts, conflicts) if ticker == 'LLY' else resolve(spec, facts, conflicts)
                               for label, spec in rules[ticker][company['reference']].items()}
            count = sum(selected_is_sec(s) for s in primary.values())
            quarters.append({'period_end': end, 'SEC_defined_fields': len(primary), 'fields_with_SEC_operands': count,
                'status': 'SEC_output_available' if count == len(primary) and count else 'SEC_scope_gap',
                'reference_period_present_in_saved_fixed_source': end in company['reference_periods'],
                'outputs': primary, 'alternative_definitions': alternatives, 'reconciliation': checks})
        results.append({'ticker': ticker, 'completion_status_unchanged': company['status'], 'fixed_reference': company['reference'],
            **period_coverage(company['target_periods'], company['reference_periods']), 'quarters': quarters,
            'quarter_status_counts': dict(Counter(q['status'] for q in quarters)),
            'SEC_output_fields': sum(q['fields_with_SEC_operands'] for q in quarters),
            'baseline_path': str(baseline_path.relative_to(ROOT)), 'baseline_sha256': digest(baseline_path),
            'freeze_receipt_sha256': digest(receipt_path), 'not_a_reference_accuracy_score': True})
    return {'source_completion_status_sha256': digest(SUMMARY), 'completion_OK_count_unchanged': summary['ok_count'],
        'scope': '只重播六家公司現有 SEC 原表／facts 與預定義 scope；不讀取第三方原值、不改參考或完成家數。',
        'blind_tests': 0, 'all_periods_seen_retrospective': True, 'companies': results,
        'source_artifacts': {'XOM_parsed_source_sha256': digest(xom_file),
            'PGR_raw_HTML_manifest_sha256': digest(ROOT / 'research/progressive-sec-html-20261104/manifest.json')},
        'code_sha256': {p: digest(ROOT / p) for p in ['scripts/audit_remaining_sec_coverage.py', 'scripts/evaluate_xom_sec.py',
            'scripts/evaluate_progressive_sec.py', 'scripts/extend_issuer_repairs.py', 'scripts/repair_chevron_q4.py']}}


def main():
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--out', type=Path, required=True);args = parser.parse_args()
    result = inspect(); temporal.save(args.out, json.loads(json.dumps(result, default=str)))
    print(json.dumps([{'ticker': c['ticker'], 'quarter_status_counts': c['quarter_status_counts'], 'SEC_fields': c['SEC_output_fields']} for c in result['companies']], ensure_ascii=False))


if __name__ == '__main__':
    main()
