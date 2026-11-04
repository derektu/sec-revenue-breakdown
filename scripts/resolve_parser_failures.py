#!/usr/bin/env python3
"""修復已核對的日期、停用分類與直接 Q4 披露；保留原始比較紀錄。"""
import argparse
import calendar
from collections import Counter
import copy
import datetime as dt
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from lxml import html
import temporal_eval as temporal
from compare_vendor_cohort import ROOT, PRIVATE
from cohort_rule_audit import compare_value
from evaluate_eight_quarter_status import assess, CHOSEN

META_URL = 'https://investor.atmeta.com/investor-news/press-release-details/2026/Meta-Reports-Fourth-Quarter-and-Full-Year-2025-Results/'
POLICIES = {
    'DIS': {'weekday': 5, 'start': '2024-09-28', 'end': '2026-06-27',
        'inactive': 'Media and Entertainment', 'active': ['Entertainment', 'Parks and Experiences', 'Sports'],
        'source_url': 'https://www.sec.gov/Archives/edgar/data/1744489/000174448925000155/dis-20250927.htm',
        'basis': '公司採最接近九月底的週六年度結帳；2023 已將舊媒體分部重組為 Entertainment 與 Sports。只確認本輪八季的曆季標籤。'},
    'JNJ': {'weekday': 6, 'start': '2024-12-29', 'end': '2026-09-27',
        'inactive': 'Consumer Health', 'active': ['Pharmaceutical', 'Medtech'],
        'source_url': 'https://www.sec.gov/Archives/edgar/data/200406/000020040626000016/jnj-20251228.htm',
        'basis': '公司採最接近十二月底的週日年度結帳；Consumer Health 於 2023 分拆，持續營運為 Innovative Medicine／MedTech 兩分部。只確認本輪八季的曆季標籤。'},
}


def reviewed_period(ticker, display_date, actual_date):
    policy = POLICIES.get(ticker)
    if not policy or not actual_date or not policy['start'] <= actual_date <= policy['end']:
        return False
    actual = dt.date.fromisoformat(actual_date)
    displayed = dt.datetime.strptime(display_date, '%b %d, %Y').date()
    return (actual.weekday() == policy['weekday'] and actual.year == displayed.year
        and actual.month == displayed.month and displayed.month in (3, 6, 9, 12)
        and displayed.day == calendar.monthrange(displayed.year, displayed.month)[1]
        and 0 <= (displayed - actual).days <= 7)


def resolve_retired_columns(ticker, rows):
    """只辨認有公司改組依據、同季現行分類齊備的空欄，不把 null 當零。"""
    policy = POLICIES[ticker]
    for row in rows:
        if row['source'] != 'stockanalysis' or row['kind'] != 'Q':
            continue
        if reviewed_period(ticker, row['display_date'], row['sec_period_end']):
            row.update(period_reviewed=True, alignment='reviewed_calendar_quarter_label', period_policy=ticker)
    for row in rows:
        if row['source'] != 'stockanalysis' or row['category'] != policy['inactive'] or row['raw'] is not None or not row['period_reviewed']:
            continue
        active = [r for r in rows if r['source'] == row['source'] and r['kind'] == 'Q'
            and r['sec_period_end'] == row['sec_period_end'] and r['category'] != policy['inactive']]
        if (len(active) == len(policy['active']) and {r['category'] for r in active} == set(policy['active'])
                and all(r['status'] == 'exact_scope_candidate_match' and r['raw'] is not None for r in active)):
            row.update(status='reference_not_applicable_evidenced', role='retired_category_not_zero',
                nonapplicability_evidence=policy)


def parse_meta_direct_quarter(raw_html):
    """以公司表格的單季欄優先，拒絕重複表格、年份或欄位位置不符。"""
    root = html.fromstring(raw_html)
    tables = [t for t in root.xpath('//table') if all(x in t.text_content() for x in ['Segment Information', 'Advertising', 'Other revenue', 'Reality Labs'])]
    if len(tables) != 1:
        raise ValueError('Expected one complete segment table')
    rows = [[' '.join(c.text_content().split()) for c in r.xpath('./td|./th')]
            for r in tables[0].xpath('./tr|./tbody/tr')]
    # 發行稿後續 non-GAAP 區塊可能沿用同一 HTML table；僅限本分部收入區塊。
    boundary = next((i for i, r in enumerate(rows) if r and r[0] == 'Income (loss) from operations:'), None)
    if boundary is None:
        raise ValueError('Missing revenue block boundary')
    rows = rows[:boundary]
    periods = [r for r in rows if 'Three Months Ended December 31,' in r]
    years = [r for r in rows if len(r) == 9 and r[2] == '2025' and r[4] == '2024' and r[6] == '2025' and r[8] == '2024']
    if (len(periods) != 1 or periods[0][2] != 'Three Months Ended December 31,'
            or periods[0][4] != 'Twelve Months Ended December 31,' or len(years) != 1
            or '(In millions)' not in tables[0].text_content()):
        raise ValueError('Unreviewed period, unit or table header')
    values = {}
    for r in rows:
        if r and r[0] == 'Income (loss) from operations:':
            break
        if r and r[0] in ['Advertising', 'Other revenue', 'Family of Apps', 'Reality Labs', 'Total revenue']:
            if len(r) != 9 or r[0] in values:
                raise ValueError('Ambiguous revenue row')
            text = r[2].replace('$', '').replace(',', '').strip()
            if not re.fullmatch(r'\d+', text):
                raise ValueError('Unreviewed numeric format')
            values[r[0]] = int(text) * 1_000_000
    if (set(values) != {'Advertising', 'Other revenue', 'Family of Apps', 'Reality Labs', 'Total revenue'}
            or values['Advertising'] + values['Other revenue'] != values['Family of Apps']
            or values['Family of Apps'] + values['Reality Labs'] != values['Total revenue']):
        raise ValueError('Incomplete or inconsistent segment revenue')
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--meta-release', type=Path, required=True)
    args = parser.parse_args()
    args.meta_release = args.meta_release.resolve()
    # 舊 runner 不改；建立全新三十家公司重播，避免變更舊收據的程式雜湊。
    subprocess.run([sys.executable, str(ROOT / 'scripts/cohort_rule_audit.py'), '--out', str(args.out)],
                   check=True, stdout=subprocess.DEVNULL)
    local = PRIVATE / 'cohort-adjudication-20261104' / args.out.name
    raw = args.meta_release.read_bytes()
    direct = parse_meta_direct_quarter(raw)
    primary = {'source_url': META_URL, 'period_end': '2025-12-31', 'kind': 'direct_three_months',
        'raw_html_local_path': str(args.meta_release.relative_to(ROOT)), 'raw_html_sha256': hashlib.sha256(raw).hexdigest(),
        'values_usd': direct, 'extractor': 'parse_meta_direct_quarter'}
    temporal.save(args.out / 'meta-direct-quarter.json', primary)
    summary = temporal.load(args.out / 'summary.json')
    companies = []
    for company in summary['companies']:
        ticker = company['ticker']; path = local / (ticker + '-detailed.json')
        rows = temporal.load(path)
        if ticker in POLICIES:
            resolve_retired_columns(ticker, rows)
        if ticker == 'META':
            labels = {'Advertising': 'Advertising', 'Payments and Other': 'Other revenue', 'Reality Labs': 'Reality Labs'}
            for row in rows:
                if row['source'] == 'stockanalysis' and row['kind'] == 'Q' and row['sec_period_end'] == '2025-12-31':
                    original = copy.deepcopy(row)
                    selected = {'status': 'observed', 'value': direct[labels[row['category']]], 'error': Decimal(500_000),
                        'role': 'direct_company_quarter_table_parsed', 'primary_evidence': primary}
                    row.update(compare_value(row['raw'], row['scale'], selected))
                    row.update(role=selected['role'], prior_annual_minus_nine_month_result=original)
        path = local / (ticker + '-resolved.json')
        temporal.save(path, json.loads(json.dumps(rows, default=str)))
        # 有證據的「已停用分類」不構成缺資料；原始空欄仍保留在完整紀錄。
        inactive = [r for r in rows if r['status'] == 'reference_not_applicable_evidenced']
        assessment_rows = [r for r in rows if r['status'] != 'reference_not_applicable_evidenced']
        receipt = temporal.load(args.out / (ticker + '-freeze.json'))
        data = temporal.checked_data(receipt['plan'], ROOT / receipt['plan']['baseline_file'])
        temporal.verify_freeze(receipt, data)
        result = assess(assessment_rows, [q['report_date'] for q in data['quarter_results']], CHOSEN.get(ticker, 'stockanalysis'))
        companies.append({'ticker': ticker, **result, 'evidenced_inactive_reference_cells': len(inactive),
            'local_detail_path': str(path.relative_to(ROOT)), 'local_detail_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    verdict = {'ok_count': sum(c['status'] == 'OK' for c in companies), 'total': len(companies),
        'companies': companies, 'period_and_category_policies': POLICIES,
        'original_six_company_result': 'research/cohort-rule-replay-20261104/eight-quarter-status.json',
        'code_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
            ['scripts/resolve_parser_failures.py', 'scripts/evaluate_eight_quarter_status.py']},
        'meta_direct_quarter_source_sha256': primary['raw_html_sha256'],
        'unchanged_replay_summary': 'summary.json',
        'note': 'summary.json 保留原 runner 的未裁決數值計數；本輪完成判定以本檔及新私有逐筆結果為準。新規則無參考金額常數。'}
    temporal.save(args.out / 'eight-quarter-status.json', verdict)
    print(f"{verdict['ok_count']} / {verdict['total']}")


if __name__ == '__main__':
    main()
