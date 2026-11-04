#!/usr/bin/env python3
"""延續八季修復：明確歷史接合、已停用分類與有證據的來源差異。"""
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

import temporal_eval as temporal
from cohort_rule_audit import resolve, compare_value
from cohort_rule_catalog import R, S, C, P, OP, leaf, rule
from compare_vendor_cohort import ROOT, PRIVATE, amount
from evaluate_eight_quarter_status import assess, CHOSEN

GOOGLE_RELEASE = 'https://s206.q4cdn.com/479360582/files/doc_financials/2025/q4/2025q4-alphabet-earnings-release.pdf'
SOURCES = {
    'ORCL': 'https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm',
    'GOOGL': 'https://www.sec.gov/Archives/edgar/data/1652044/000165204425000014/goog-20241231.htm',
    'MSFT': 'https://www.sec.gov/Archives/edgar/data/789019/000119312526191507/msft-20260331.htm',
    'PG': 'https://www.sec.gov/Archives/edgar/data/80424/000008042426000256/pg-20260930.htm',
    'JPM': 'https://www.sec.gov/Archives/edgar/data/19617/000001961725000270/jpm-20241231.htm',
}
ACCEPTED = {'exact_scope_candidate_match', 'explained_reported_precision', 'explained_reference_error'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_google_release(pdf):
    text = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], check=True, capture_output=True, text=True).stdout
    start = text.index('Q4 2025 Supplemental Information (in millions,')
    block = text[start:text.index('Segment Operating Results', start)]
    if not re.search(r'Quarter Ended December 31,\s+2024\s+2025', block):
        raise ValueError('Unreviewed Google quarterly header')
    labels = ['Google Search & other', 'YouTube ads', 'Google Network', 'Google advertising',
        'Google subscriptions, platforms, and devices', 'Google Services total', 'Google Cloud',
        'Other Bets', 'Hedging gains (losses)', 'Total revenues']
    values = {}
    for label in labels:
        pattern = r'^\s*' + re.escape(label) + r'\s+\$?\s*([\d,()]+)\s+\$?\s*([\d,()]+)\s*$'
        found = re.findall(pattern, block, re.M)
        if len(found) != 1:
            raise ValueError('Missing or ambiguous direct-quarter row: ' + label)
        raw = found[0][1]
        values[label] = int(raw.replace(',', '').replace('(', '-').replace(')', '')) * 1_000_000
    if (sum(values[k] for k in ['Google Search & other', 'YouTube ads', 'Google Network']) != values['Google advertising']
        or values['Google advertising'] + values['Google subscriptions, platforms, and devices'] != values['Google Services total']
        or sum(values[k] for k in ['Google Services total', 'Google Cloud', 'Other Bets', 'Hedging gains (losses)']) != values['Total revenues']):
        raise ValueError('Inconsistent direct-quarter revenue partition')
    return values


def quarter_pools(ticker, data):
    records = copy.deepcopy(sorted(data['raw_filings'], key=lambda r: r['filing']['filingDate']))
    if ticker == 'JPM':
        for record in records:
            if record['filing']['reportDate'] != '2024-09-30':
                continue
            for fact in record['facts']:
                if (fact['concept'] == 'us-gaap:RevenuesNetOfInterestExpense'
                    and fact['dimensions'] == {S: 'jpm:CorporateAndInvestmentBankMember', C: OP}):
                    fact.update(original_dimensions=fact['dimensions'], dimensions={S: 'jpm:CommercialAndInvestmentBankMember', C: OP},
                        normalization_rule_id='jpm-2024q3-cib-reorganization-member', normalization_source=SOURCES['JPM'])
    engine = temporal.runner()
    return {record['filing']['reportDate']: engine.quarter(record['facts'], record['filing']['reportDate'], record['filing']['form'],
        [f for old in records[:index] for f in old['facts']]) for index, record in enumerate(records)}


def google_hedging(facts, conflicts):
    # SEC Note 2 明列的對帳關係，不用參考金額決定任何 selector。
    selected = resolve(rule([leaf('us-gaap:Revenues', {}), *[
        leaf(R, {S: member}, -1) for member in ['goog:GoogleServicesMember', 'goog:GoogleCloudMember', 'us-gaap:AllOtherSegmentsMember']]],
        [leaf(R, {}), *[leaf(R, {S: member}, -1) for member in
            ['goog:GoogleServicesMember', 'goog:GoogleCloudMember', 'us-gaap:AllOtherSegmentsMember']]]), facts, conflicts)
    selected['role'] = 'sec_reported_segment_reconciliation_hedging'
    return selected


def oracle_period(display, actual):
    if not actual or not '2024-11-30' <= actual <= '2026-08-31':
        return False
    date = dt.date.fromisoformat(actual)
    if date.month not in (2, 5, 8, 11) or date.day != calendar.monthrange(date.year, date.month)[1]:
        return False
    label = dt.date(date.year, date.month + 1, calendar.monthrange(date.year, date.month + 1)[1])
    return dt.datetime.strptime(display, '%b %d, %Y').date() == label


def mark_inactive(rows, active_labels, source_url, reason, require_total=None):
    active = [r for r in rows if r['category'] in active_labels]
    if (len(active) != len(active_labels) or {r['category'] for r in active} != set(active_labels)
        or any(r['raw'] is None or r['status'] not in ACCEPTED or not r['period_reviewed'] for r in active)):
        return
    if require_total is not None:
        if require_total['status'] != 'observed' or sum(r['selected']['value'] for r in active) != require_total['value']:
            return
    for row in rows:
        if row['category'] not in active_labels and row['raw'] is None and row['period_reviewed']:
            row.update(status='reference_not_applicable_evidenced', role='retired_category_not_zero',
                nonapplicability_evidence={'source_url': source_url, 'reason': reason, 'active_labels': active_labels})


def adjudicate(row, primary, fresh_ui):
    if row['source'] != 'stockanalysis' or row.get('raw') is None:
        return
    ticker, end, label = row['ticker'], row['sec_period_end'], row['category']
    if ticker == 'PG' and row['status'] == 'within_scope_candidate_precision':
        value, tolerance = amount(row['raw'], row['scale'])
        selected = row['selected']
        if isinstance(row['raw'], str) and abs(value - Decimal(selected['value'])) <= tolerance + Decimal(selected['error']):
            row.update(status='explained_reported_precision', explanation={'kind': 'reported_precision_intersection',
                'basis': '網站 B／M 顯示步階與 SEC 原始小數精度相交；Q4 累加年度及九個月兩側誤差，不擴大百分比容差。'})
    exception = None
    if ticker == 'MSFT' and end == '2026-03-31' and label == 'More Personal Computing':
        exception = primary['MSFT']
    if ticker == 'PG' and end == '2026-09-30' and label == 'Fabric and Homecare':
        exception = primary['PG']
    if exception and row['status'] == 'scope_candidate_differs':
        selected = row['selected']; facts = selected.get('facts', [])
        if (selected['value'] == exception['reported_revenue_usd'] and facts
            and all(f['source_url'] == exception['source_url'] and f['enddate'] == end for f in facts)):
            ui = fresh_ui[ticker]; index = ui['columns'].index(label)
            observed = [r for r in ui['rows'] if dt.datetime.strptime(r[0], '%b %d, %Y').date().isoformat() == end]
            value, tolerance = amount(row['raw'], row['scale'])
            if len(observed) != 1:
                return
            fresh, fresh_tol = amount(observed[0][index], 1)
            if abs(fresh - value) > fresh_tol + tolerance:
                return
            if ticker == 'MSFT' and value != exception['other_segment_operating_income_usd']:
                return
            row.update(status='explained_reference_error', explanation=exception)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT / 'scripts/resolve_parser_failures.py'), '--out', str(args.out),
        '--meta-release', str(PRIVATE / 'parser-fixes-20261104/meta-q4-2025-release.html')], check=True)
    local = PRIVATE / 'cohort-adjudication-20261104' / args.out.name
    base = temporal.load(args.out / 'eight-quarter-status.json')
    folder = PRIVATE / 'remaining-repairs-20261104'
    fresh = temporal.load(folder / 'fresh-ui-checks.json')
    primary = temporal.load(ROOT / 'research/issuer-repair-evidence/primary-adjudications.json')
    direct = parse_google_release(folder / 'googl-q4-2025.pdf')
    temporal.save(args.out / 'google-direct-quarter.json', {'source_url': GOOGLE_RELEASE,
        'local_pdf_path': str((folder / 'googl-q4-2025.pdf').relative_to(ROOT)), 'sha256': digest(folder / 'googl-q4-2025.pdf'),
        'period_end': '2025-12-31', 'values_usd': direct})
    companies = []
    for company in base['companies']:
        ticker = company['ticker']; original = local / (ticker + '-resolved.json'); rows = temporal.load(original)
        receipt = temporal.load(args.out / (ticker + '-freeze.json'))
        data = temporal.checked_data(receipt['plan'], ROOT / receipt['plan']['baseline_file'])
        pools = quarter_pools(ticker, data) if ticker in SOURCES else {}
        if ticker in SOURCES:
            for row in rows:
                end = row['sec_period_end']; facts, conflicts = pools.get(end, ([], []))
                if ticker == 'ORCL' and row['source'] == 'stockanalysis' and oracle_period(row['display_date'], end):
                    row.update(period_reviewed=True, alignment='reviewed_oracle_fiscal_quarter_label')
                selected = None
                if ticker == 'JPM' and row['category'] == 'Commercial and Investment Bank':
                    selected = resolve(rule(leaf('us-gaap:RevenuesNetOfInterestExpense', {S: 'jpm:CommercialAndInvestmentBankMember', C: OP})), facts, conflicts)
                    selected['role'] = 'managed_segment_revenue_bounded_member_bridge'
                if ticker == 'GOOGL' and row['category'] == 'Hedging Gains':
                    selected = google_hedging(facts, conflicts)
                    if end == '2025-12-31':
                        selected = {'status': 'observed', 'value': direct['Hedging gains (losses)'], 'error': Decimal(500_000),
                            'role': 'direct_company_quarter_pdf_parsed', 'source_url': GOOGLE_RELEASE, 'period_end': end}
                if selected is not None:
                    old = copy.deepcopy(row)
                    row.update(compare_value(row['raw'], row['scale'], selected))
                    row.update(role=selected['role'], prior_result=old)
                adjudicate(row, primary, fresh)
            for end in sorted({r['sec_period_end'] for r in rows if r['sec_period_end']}):
                group = [r for r in rows if r['sec_period_end'] == end and r['source'] == 'stockanalysis' and r['kind'] == 'Q']
                facts, conflicts = pools.get(end, ([], []))
                total = resolve(rule(leaf(R, {}), leaf('us-gaap:Revenues', {})), facts, conflicts)
                if ticker == 'ORCL':
                    active = ['Services', 'Hardware'] + (['Cloud License and On-Premise License', 'Cloud Services and License Support'] if end <= '2025-05-31' else ['Cloud', 'Software'])
                    mark_inactive(group, active, SOURCES[ticker], '分期的四個收入類別已全部相同且合計等於 SEC 總收入；保留新舊欄，不補零。', total)
                elif ticker == 'MSFT':
                    active = ['Agents and Infra', 'Devices and Consumer'] if end >= '2026-09-30' else ['Intelligent Cloud', 'More Personal Computing', 'Productivity and Business Processes']
                    mark_inactive(group, active, SOURCES[ticker], '按當期分部集合，選中 SEC 原值的分部合計與總收入完全相同；公司層級及另一版本欄位不適用。', total)
                elif ticker == 'JPM':
                    mark_inactive(group, ['Commercial and Investment Bank', 'Consumer and Community Banking', 'Wealth Management', 'Corporate'],
                        SOURCES[ticker], '2024 Q2 商業銀行與投資銀行整合後，以三分部及 Corporate 的 managed basis 呈現。')
                elif ticker == 'GOOGL':
                    mark_inactive(group, ['Google Search & Other', 'Google Subscriptions, Platforms & Devices', 'YouTube Ads', 'Google Network', 'Google Cloud', 'Other Bets', 'Hedging Gains'],
                        SOURCES[ticker], '當期 Note 2 的現行分類齊備；Google Other 是舊版欄位，非本期漏項。')
        output = local / (ticker + '-repaired.json')
        temporal.save(output, json.loads(json.dumps(rows, default=str)))
        eligible = [copy.deepcopy(r) for r in rows if r['status'] != 'reference_not_applicable_evidenced']
        explained = Counter(r['status'] for r in eligible if r['status'] in ACCEPTED - {'exact_scope_candidate_match'})
        for r in eligible:
            if r['status'] in ACCEPTED - {'exact_scope_candidate_match'} and r.get('explanation'):
                r['status'] = 'exact_scope_candidate_match'  # 僅共用完成條件；原狀態另列，不宣稱原數字相同。
        result = assess(eligible, [q['report_date'] for q in data['quarter_results']], CHOSEN.get(ticker, 'stockanalysis'))
        result['cell_statuses'] = dict(Counter(r['status'] for r in rows if r['source'] == result['reference'] and r['kind'] == 'Q'))
        companies.append({'ticker': ticker, **result, 'accepted_explanations': dict(explained),
            'local_detail_path': str(output.relative_to(ROOT)), 'local_detail_sha256': digest(output)})
    report = {'ok_count': sum(c['status'] == 'OK' for c in companies), 'total': len(companies), 'companies': companies,
        'strict_blind_tests': 0, 'evaluation': '已接觸期間回溯；每家公司固定一家參考；差異須有明列理由。',
        'code_sha256': {p: digest(ROOT / p) for p in ['scripts/continue_parser_repairs.py', 'scripts/resolve_parser_failures.py',
            'scripts/cohort_rule_audit.py', 'scripts/cohort_rule_catalog.py', 'scripts/evaluate_eight_quarter_status.py']},
        'evidence_sha256': {str(p.relative_to(ROOT)): digest(p) for p in [folder / 'fresh-ui-checks.json', folder / 'googl-q4-2025.pdf',
            ROOT / 'research/issuer-repair-evidence/primary-adjudications.json']},
        'base_receipts_note': '三十份 freeze 是原始候選規則收據；後續修復與裁決另由本檔 code／evidence 雜湊固定，不將原 freeze 冒稱含新規則。'}
    temporal.save(args.out / 'completion-status.json', report)
    print(f"Repaired: {report['ok_count']} / {report['total']}")


if __name__ == '__main__':
    main()
