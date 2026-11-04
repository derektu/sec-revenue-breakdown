#!/usr/bin/env python3
"""只用 SEC 年報附件及季報，重播 PGR 七季參考並保留最新季缺口。"""
import argparse
from collections import Counter
import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from cohort_rule_audit import compare_value
from compare_vendor_cohort import amount
from continue_parser_repairs import ACCEPTED
from continue_remaining_research import PGR_LABELS
from enforce_sec_primary_source import assess, selected_is_sec
from parse_progressive_sec import load_sources

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/sec-only-completion-20261104'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def period_facts(observations, year, month, kind='Q'):
    if month == 12 and kind == 'Q':
        annual = period_facts(observations, year, 12, 'FY'); nine = period_facts(observations, year, 9, 'YTD9')
        result = {}
        for label, fact in annual.items():
            prior = nine.get(label)
            if not prior or any(fact[k] != prior[k] for k in ['concept', 'dimensions', 'unit', 'startdate']):
                raise ValueError('Q4 operands differ in fiscal start, unit or full table scope')
            if (fact['startdate'] != f'{year}-01-01' or fact['enddate'] != f'{year}-12-31'
                    or prior['enddate'] != f'{year}-09-30'):
                raise ValueError('Q4 operands do not cover the full fiscal year and first nine months')
            result[label] = {**fact, 'value': fact['value'] - prior['value'], 'kind': 'Q',
                'startdate': f'{year}-10-01', 'derivation': 'annual_minus_nine_months',
                'annual_evidence': fact, 'nine_month_evidence': prior,
                'retrospective_comparative_used': True}
        return result
    candidates = [f for f in observations if (f['kind'], f['year'], f['month']) == (kind, year, month)]
    if not candidates:
        raise ValueError('Missing SEC period')
    # 以最早可用同分類表選版本；不按參考金額挑申報。
    report_date = min(f['source_report_date'] for f in candidates)
    selected = [f for f in candidates if f['source_report_date'] == report_date]
    result = {}
    for f in selected:
        label = f['label']
        if label in result:
            raise ValueError('Duplicate SEC reported row')
        result[label] = f
    return result


def apply_pgr_sec(rows, observations):
    for row in rows:
        year, month, _ = map(int, row['sec_period_end'].split('-'))
        facts = period_facts(observations, year, month)
        label = PGR_LABELS.get(row['category'], row['category']); fact = facts[label]
        selected = {'status': 'observed', 'value': fact['value'], 'error': Decimal(1_000_000 if month == 12 else 500_000),
                    'facts': [fact], 'role': 'SEC_consolidated_income_or_underwriting_table'}
        if not selected_is_sec(selected):
            raise ValueError('Non-SEC PGR output')
        old = copy.deepcopy(row)
        row.update(compare_value(row['raw'], row['scale'], selected), prior_sec_result=old,
                   role=selected['role'], primary_source_check='SEC_operands_verified')
        if label == 'Total net realized gains (losses) on securities':
            row['not_additive_with_securities_components'] = True
        if month != 12 or row['status'] == 'exact_scope_candidate_match':
            continue
        securities = ['Net realized gains (losses) on securities', 'Net realized gains (losses) on security sales',
                      'Net holding period gains (losses) on securities']
        if row['category'] not in securities:
            continue
        group = [r for r in rows if r['sec_period_end'] == row['sec_period_end'] and r['category'] in securities]
        if len(group) != 3 or sum(amount(r['raw'], r['scale'])[0] for r in group) != facts['Total net realized gains (losses) on securities']['value']:
            continue
        reference, _ = amount(row['raw'], row['scale'])
        annual, nine = fact['annual_evidence'], fact['nine_month_evidence']
        expected = annual['value'] if label == 'Total net realized gains (losses) on securities' else -nine['value']
        if reference == expected:
            row.update(status='explained_reference_error', explanation={
                'kind': 'reference_annual_total_with_negative_ytd_components',
                'SEC_annual_operand': annual, 'SEC_nine_month_operand': nine,
                'reference_securities_group_sum_equals_SEC_single_quarter_total': True,
                'basis': '參考三個證券欄位加總可回到單季總額，但各欄標籤下金額分別等於 FY 總額／負 YTD 組成。輸出保留 SEC 真正單季總額及組成，明標總額不可再與組成重複相加；不推論 vendor 內部程式。'})


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True); args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    local = ROOT / 'data/vendor/local/cohort-adjudication-20261104' / args.out.name
    local.mkdir(parents=True, exist_ok=False)
    manifest = temporal.load(args.manifest); observations = load_sources(manifest, ROOT)
    temporal.save(args.out / 'PGR-parsed-SEC-facts.json', observations)
    base = temporal.load(BASE / 'completion-status.json'); companies = []
    for company in base['companies']:
        if company['ticker'] != 'PGR':
            companies.append(company); continue
        rows = temporal.load(ROOT / company['local_detail_path'])
        if digest(ROOT / company['local_detail_path']) != company['local_detail_sha256']:
            raise ValueError('Prior PGR hash mismatch')
        apply_pgr_sec(rows, observations)
        path = local / 'PGR-sec-repaired.json'; temporal.save(path, json.loads(json.dumps(rows, default=str)))
        eligible = copy.deepcopy(rows)
        for row in eligible:
            if row['status'] in ACCEPTED - {'exact_scope_candidate_match'} and row.get('explanation'):
                row['status'] = 'exact_scope_candidate_match'
        verdict = assess(eligible, company['target_periods'], company['reference'])
        verdict.update(cell_statuses=dict(Counter(r['status'] for r in rows)),
                       primary_source_checks=dict(Counter(r['primary_source_check'] for r in rows)))
        companies.append({'ticker': 'PGR', **verdict, 'local_detail_path': str(path.relative_to(ROOT)), 'local_detail_sha256': digest(path)})
    latest = period_facts(observations, 2026, 9)
    temporal.save(args.out / 'PGR-latest-unreferenced-SEC-quarter.json', {'period_end': '2026-09-30',
        'facts': latest, 'reference_present': False, 'blind_test': False})
    result = {**base, 'companies': companies, 'ok_count': sum(c['status'] == 'OK' for c in companies),
        'source_summary_sha256': digest(BASE / 'completion-status.json'),
        'PGR_source_status': 'SEC Exhibit 13 and four 10-Q tables; artifact formats in capture_manifest; no IR input',
        'PGR_latest_quarter_seen': True, 'PGR_latest_reference_missing': True,
        'capture_manifest': manifest, 'capture_manifest_sha256': digest(args.manifest),
        'repair_code_sha256': {p: digest(ROOT / p) for p in ['scripts/evaluate_progressive_sec.py', 'scripts/parse_progressive_sec.py',
                                                         'scripts/parse_progressive_sec_html.py', 'scripts/collect_progressive_sec_dom.js']}}
    temporal.save(args.out / 'completion-status.json', result)
    print('PGR SEC replay complete; overall ' + str(result['ok_count']) + ' / 30')


if __name__ == '__main__':
    main()
