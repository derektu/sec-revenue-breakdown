#!/usr/bin/env python3
"""固定一家參考來源，逐公司判定八季 parser 是否完成；不公開參考原值。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from compare_vendor_cohort import ROOT, PRIVATE

INPUT = ROOT / 'research/cohort-rule-replay-20261104'
DETAILS = PRIVATE / 'cohort-adjudication-20261104/cohort-rule-replay-20261104'
VENDORS = {'stockanalysis', 'futu', 'tradingview'}
CHOSEN = {t: 'futu' for t in ['MCD', 'WMT', 'BRK-B', 'PGR', 'XOM', 'CVX', 'NEE']}
CHOSEN['PLD'] = 'issuer_ir'


def period_coverage(expected_periods, reference_periods):
    """分開列出目標窗口內覆蓋與窗口外參考，避免以舊八季冒充目標八季。"""
    target, reference = set(expected_periods), set(reference_periods)
    return {'target_quarters_present': len(target & reference),
        'missing_target_periods': sorted(target - reference),
        'reference_periods_outside_target': sorted(reference - target)}


def assess(rows, expected_periods, source):
    selected = [r for r in rows if r['source'] == source and r['kind'] == 'Q']
    dates = {r['sec_period_end'] for r in selected if r.get('sec_period_end')}
    failures = []
    if source not in VENDORS:
        failures.append('original_three_vendor_reference_missing')
    if len(set(expected_periods)) != 8 or dates != set(expected_periods):
        failures.append('eight_target_quarters_not_complete')
    if not selected or any(r.get('raw') is None for r in selected):
        failures.append('reference_cells_missing')
    if any(not r['period_reviewed'] for r in selected):
        failures.append('period_mapping_not_confirmed')
    if any(r['role'].startswith(('primary_text_reviewed', 'inferred_')) for r in selected):
        failures.append('manual_table_or_unverified_residual_not_completed_parser')
    if any(r['status'] != 'exact_scope_candidate_match' for r in selected):
        failures.append('unequal_or_unresolved_cells')
    return {'status': 'Fail' if failures else 'OK', 'reference': source,
        'reference_quarters_present': len(dates), 'target_periods': sorted(expected_periods),
        **period_coverage(expected_periods, dates),
        'reference_periods': sorted(dates), 'quarterly_cells': len(selected),
        'cell_statuses': dict(Counter(r['status'] for r in selected)), 'fail_reasons': failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    summary = temporal.load(INPUT / 'summary.json')
    companies = []
    for company in summary['companies']:
        ticker = company['ticker']
        path = DETAILS / (ticker + '-detailed.json')
        receipt = temporal.load(INPUT / (ticker + '-freeze.json'))
        data = temporal.checked_data(receipt['plan'], ROOT / receipt['plan']['baseline_file'])
        temporal.verify_freeze(receipt, data)
        rows = temporal.load(path)
        result = assess(rows, [q['report_date'] for q in data['quarter_results']], CHOSEN.get(ticker, 'stockanalysis'))
        companies.append({'ticker': ticker, **result,
            'local_detail_path': str(path.relative_to(ROOT)), 'local_detail_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    result = {'criterion': '固定原三家網站之一、八個目標季度、期間已確認、所有參考分類精確相等；人工補表及未裁決差異不算完成。',
        'ok_count': sum(c['status'] == 'OK' for c in companies), 'total': len(companies),
        'documented_exceptions_accepted': [],
        'note': '目前沒有將來源錯誤或精度相容納入例外；日後可憑完整證據加入裁決，不要求所有來源一致。',
        'evaluation_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'input_summary_sha256': hashlib.sha256((INPUT / 'summary.json').read_bytes()).hexdigest(),
        'companies': companies}
    with args.out.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(f"{result['ok_count']} / {result['total']}")


if __name__ == '__main__':
    main()
