#!/usr/bin/env python3
"""XOM 舊 CIK 八個歷史季度重播；不以較舊參考掩蓋最新季缺漏。"""
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
from enforce_sec_primary_source import selected_is_sec, assess
from parse_xom_sec import parse_snapshot, parse_sales_page, LABELS

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/comcast-sec-repair-20261104/completion-status.json'
HISTORY = ['2024-09-30', '2024-12-31', '2025-03-31', '2025-06-30', '2025-09-30', '2025-12-31', '2026-03-31', '2026-06-30']
TARGETS = HISTORY[1:] + ['2026-09-30']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def quarter(observations, end):
    year, month, _ = map(int, end.split('-'))
    def period(kind, month):
        candidates = [f for f in observations if (f['kind'], f['year'], f['month']) == (kind, year, month)]
        if not candidates:
            raise ValueError('Missing SEC fiscal period')
        earliest = min(f['source_report_date'] for f in candidates)
        chosen = [f for f in candidates if f['source_report_date'] == earliest]
        result = {f['label']: f for f in chosen}
        if len(result) != 10 or len(chosen) != 10:
            raise ValueError('Missing or duplicate income category')
        return result
    if month != 12:
        return period('Q', month)
    annual, nine = period('FY', 12), period('YTD9', 9)
    result = {}
    for label, a in annual.items():
        n = nine[label]
        if any(a[k] != n[k] for k in ['concept', 'dimensions', 'unit', 'startdate', 'source_cik']):
            raise ValueError('Q4 operands differ in scope, fiscal start or CIK')
        result[label] = {**a, 'kind': 'Q', 'startdate': f'{year}-10-01', 'value': a['value'] - n['value'],
            'error_usd': a['error_usd'] + n['error_usd'], 'derivation': 'annual_minus_nine_months',
            'annual_evidence': a, 'nine_month_evidence': n, 'retrospective_comparative_used': True}
    return result


def selection(fact):
    return {'status': 'observed', 'value': fact['value'], 'error': Decimal(fact['error_usd']),
            'facts': [fact], 'role': 'SEC_segment_income_to_consolidated_sales_reconciliation'}


def repair(rows, observations, gross_facts):
    quarters = {end: quarter(observations, end) for end in HISTORY}
    for end in ['2025-06-30', '2026-06-30']:
        categories = [r['category'] for r in rows if r['source'] == 'futu' and r['kind'] == 'Q' and r.get('date') == end]
        if len(categories) != 5 or set(categories) != set(LABELS) | {'分部間收入'}:
            raise ValueError('Reviewed Q2 five-category reference basis changed')
    for row in rows:
        end = row.get('date')
        if row['kind'] != 'Q' or row['source'] != 'futu' or end not in quarters:
            continue
        old = copy.deepcopy(row)
        label = LABELS.get(row['category'], row['category'])
        # 兩個 Q2 只列五欄，使用 sales + intersegment；其餘歷史季列 all-income 與扣回欄。
        # 期間規則明訂，不依哪個候選金額較接近參考來選數字。
        if end in ('2025-06-30', '2026-06-30'):
            if label in LABELS.values():
                gross = [f for f in gross_facts if (f['kind'], f['year'], f['month'], f['label']) == ('Q', int(end[:4]), 6, label)]
                if len(gross) != 1:
                    raise ValueError('Missing unique SEC gross-sales operand')
                chosen = selection(gross[0])
            else:
                chosen = selection(quarters[end][label])
            if end == '2026-06-30' and (not selected_is_sec(old.get('selected', {})) or old['selected']['value'] != chosen['value']):
                raise ValueError('Independent SEC page-text differs from prior XBRL')
            role = 'SEC_sales_plus_intersegment_scope_for_five_column_reference'
        else:
            chosen = selection(quarters[end][label]); role = chosen['role']
        if not selected_is_sec(chosen):
            raise ValueError('XOM selection lacks SEC source')
        row.update(compare_value(row['raw'], row['scale'], chosen), prior_sec_result=old,
                   sec_period_end=end, alignment='explicit_SEC_table_calendar_quarter', period_reviewed=True,
                   phase='seen_retrospective', role=role, primary_source_check='SEC_operands_verified')
        if row['status'] == 'within_scope_candidate_precision':
            reference, tolerance = amount(row['raw'], row['scale'])
            if abs(reference - Decimal(str(chosen['value']))) <= Decimal(str(chosen['error'])) + tolerance:
                row.update(status='explained_reported_precision', explanation={'kind': 'SEC_reported_operands_precision',
                    'maximum_SEC_error_usd': str(chosen['error']), 'basis': '保留 SEC 原值及顯示差額，容差僅為實際百萬申報運算元的合計精度。'})
    for end in ['2024-12-31', '2025-12-31']:
        group = [r for r in rows if r['source'] == 'futu' and r['kind'] == 'Q' and r.get('date') == end]
        year = int(end[:4]); q4 = end.endswith('12-31'); expected = {}; evidence = {}
        if len(group) != 8 or len({r['category'] for r in group}) != 8:
            continue
        for row in group:
            label = LABELS.get(row['category'], row['category']); correct = quarters[end][label]
            if label in LABELS.values():
                found = [f for f in gross_facts if (f['kind'], f['year'], f['month'], f['label']) == ('FY' if q4 else 'Q', year, 12 if q4 else 6, label)]
                if len(found) != 1:
                    raise ValueError('Missing alternative gross-sales basis evidence')
                alternative = found[0]
                expected[label] = alternative['value'] - (correct['nine_month_evidence']['value'] if q4 else 0)
                evidence[label] = alternative
            else:
                expected[label] = -correct['nine_month_evidence']['value'] if q4 else correct['value']
        if not all(amount(r['raw'], r['scale'])[0] == expected[LABELS.get(r['category'], r['category'])] for r in group):
            continue
        # 全組八欄皆符合具體錯誤公式才裁決，保留正確且可對帳的 SEC 輸出。
        for row in group:
            if row['status'] == 'exact_scope_candidate_match':
                continue
            label = LABELS.get(row['category'], row['category']); correct = quarters[end][label]
            row.update(status='explained_reference_error', explanation={
                'kind': 'reference_mixes_FY_gross_sales_and_YTD_all_income' if q4 else 'reference_gross_sales_with_duplicate_consolidated_income_deductions',
                'all_eight_reference_columns_match_diagnostic_formula': True,
                'correct_SEC_fact': correct, 'alternative_SEC_gross_sales_fact': evidence.get(label),
                'basis': 'Q4 四分部的參考等於全年 gross sales 減九個月 all-income，另四欄等於負九個月；缺少正確 FY 組成，並非同口徑 Q4。' if q4 else
                    '四分部參考採 sales 加 intersegment，另仍扣除合併投資／其他收益，造成重複扣除；輸出保留 all-income 分部與完整對帳。',
                'no_vendor_internal_cause_claimed': True})
    return quarters


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True); args = parser.parse_args()
    manifest = temporal.load(args.manifest); observations = []; gross_facts = []
    for entry in manifest['files']:
        path = ROOT / entry['path']
        if digest(path) != entry['sha256']:
            raise ValueError('SEC capture changed')
        observations.extend(parse_snapshot(temporal.load(path), entry['sha256']))
    for entry in manifest['supplemental_page_text']:
        path = ROOT / entry['path']
        if digest(path) != entry['sha256']:
            raise ValueError('Supplemental SEC page text changed')
        gross_facts.extend(parse_sales_page(path.read_text(), entry['sha256']))
    base = temporal.load(BASE); company = next(c for c in base['companies'] if c['ticker'] == 'XOM')
    prior = ROOT / company['local_detail_path']
    if digest(prior) != company['local_detail_sha256']:
        raise ValueError('Prior reference detail changed')
    rows = temporal.load(prior); quarters = repair(rows, observations, gross_facts)
    args.out.mkdir(parents=True, exist_ok=False)
    local = ROOT / 'data/vendor/local/cohort-adjudication-20261104' / args.out.name; local.mkdir(parents=True, exist_ok=False)
    detail = local / 'XOM-sec-repaired.json'; temporal.save(detail, json.loads(json.dumps(rows, default=str)))
    eligible = copy.deepcopy(rows)
    for row in eligible:
        if row['status'] in ACCEPTED - {'exact_scope_candidate_match'} and row.get('explanation'):
            row['status'] = 'exact_scope_candidate_match'
    verdict = assess(eligible, TARGETS, 'futu')
    historical = assess(eligible, HISTORY, 'futu')
    historical['cell_statuses'] = dict(Counter(r['status'] for r in rows))
    verdict.update(cell_statuses=dict(Counter(r['status'] for r in rows)),
                   primary_source_checks=dict(Counter(r.get('primary_source_check') for r in rows)),
                   historical_eight_quarter_assessment=historical,
                   latest_reference_missing='2026-09-30', latest_test_is_blind=False)
    updated = {'ticker': 'XOM', **verdict, 'local_detail_path': str(detail.relative_to(ROOT)), 'local_detail_sha256': digest(detail)}
    companies = [updated if c['ticker'] == 'XOM' else c for c in base['companies']]
    temporal.save(args.out / 'XOM-parsed-SEC-facts.json', {'observations': observations, 'quarters': quarters, 'gross_sales_evidence': gross_facts,
        'latest_quarter_baseline': 'research/sec-30-baseline-2026-11-04/XOM.json.gz',
        'Q2_note': '2025／2026 Q2 採 SEC sales + intersegment 五項口徑；2026 Q2 另與先前 XBRL 獨立核對；其他歷史季採 all-income 分部再扣合併投資／其他收益。'})
    temporal.save(args.out / 'completion-status.json', {**base, 'companies': companies, 'ok_count': sum(c['status'] == 'OK' for c in companies),
        'XOM_capture_manifest': manifest, 'XOM_capture_manifest_sha256': digest(args.manifest),
        'source_summary_sha256': digest(BASE),
        'XOM_code_sha256': {p: digest(ROOT / p) for p in ['scripts/parse_xom_sec.py', 'scripts/evaluate_xom_sec.py']},
        'XOM_note': '先完成舊 CIK 歷史原表；最新目標季仍缺參考，不以較舊八季提高完成數。'})
    print(json.dumps({'overall_OK': sum(c['status'] == 'OK' for c in companies), 'XOM': verdict}, ensure_ascii=False))


if __name__ == '__main__':
    main()
