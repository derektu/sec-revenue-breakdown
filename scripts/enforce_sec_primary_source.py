#!/usr/bin/env python3
"""所有數字擷取與計算只接受 SEC；公司 IR 與 vendor 只作參考。"""
import argparse
from collections import Counter
import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse

import temporal_eval as temporal
from cohort_rule_audit import compare_value
from compare_vendor_cohort import amount
from continue_parser_repairs import ACCEPTED, google_hedging
from evaluate_eight_quarter_status import assess
from extend_issuer_repairs import pools_for, selection

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/remaining-company-resolution-20261104'
UPS_URL = 'https://www.sec.gov/Archives/edgar/data/1090727/000162828026067381/exhibit991-earningspressre.htm'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sec_url(url):
    parsed = urlparse(url or '')
    return (parsed.scheme == 'https' and parsed.hostname in ('sec.gov', 'www.sec.gov')
            and not parsed.username and not parsed.password and parsed.port in (None, 443)
            and re.fullmatch(r'/Archives/edgar/data/\d+/\d+/[^/]+', parsed.path) is not None)


def fact_is_sec(fact):
    if not sec_url(fact.get('source_url')):
        return False
    if fact.get('derivation') == 'annual_minus_nine_months':
        if not all(fact.get(key) and fact_is_sec(fact[key]) for key in ['annual_evidence', 'nine_month_evidence']):
            return False
    if fact.get('aggregation_evidence'):
        if not all(fact_is_sec(f) for f in fact['aggregation_evidence']):
            return False
    return True


def selected_is_sec(selected):
    return (selected.get('status') == 'observed' and bool(selected.get('facts'))
            and all(fact_is_sec(f) for f in selected['facts']))


def parse_ups_sec_page(text):
    # 保存的是正常 web 工具已讀取之 SEC 頁面文字，不冒稱原始 HTML bytes。
    if text.splitlines()[0] != 'www.sec.gov (' + UPS_URL + ')':
        raise ValueError('SEC response URL differs')
    lines = []
    for line in text.splitlines():
        match = re.match(r'L(\d+): (.*)', line)
        if match:
            lines.append((int(match[1]), match[2]))
    body = '\n'.join(t for _, t in lines)
    if 'UPS RELEASES 3Q 2026 EARNINGS' not in body or 'Exhibit 99.1' not in body:
        raise ValueError('Wrong SEC exhibit or quarter')
    sections = [('Domestic Package', 'U.S. Domestic Segment'), ('International Package', 'International Segment'),
                ('Supply Chain and Freight', 'Supply Chain Solutions1')]
    result = {}
    for index, (label, heading) in enumerate(sections):
        starts = [i for i, (_, line) in enumerate(lines) if line == heading]
        if len(starts) != 1:
            raise ValueError('Missing or duplicate SEC segment heading')
        start = starts[0]
        end = next((i for i in range(start + 1, len(lines)) if index + 1 < len(sections)
                    and lines[i][1] == sections[index + 1][1]), len(lines))
        block = lines[start:end]
        revenues = [(number, line) for number, line in block if line.startswith('Revenue  |')]
        if len(revenues) != 1:
            raise ValueError('Missing or duplicate SEC revenue row')
        number, line = revenues[0]
        header = '\n'.join(t for n, t in block if n < number)
        if not re.search(r'3Q 2026\s+\| Non-GAAP Adjusted 3Q 2026', header) or '3Q 2025' not in header:
            raise ValueError('Wrong current/prior SEC columns')
        cells = [s.strip() for s in line.split('|')]
        if len(cells) < 5 or cells[2]:
            raise ValueError('Unreviewed revenue table layout')
        current = re.fullmatch(r'\$([\d,]+) M', cells[1])
        prior = re.fullmatch(r'\$([\d,]+) M', cells[3])
        if not current or not prior:
            raise ValueError('Revenue unit or signed value not reviewed')
        result[label] = {'value_usd': int(current[1].replace(',', '')) * 1_000_000, 'line': number}
    return result


def replace_from_sec(row, selected, role):
    if not selected_is_sec(selected):
        raise ValueError('Replacement lacks SEC operands')
    old = copy.deepcopy(row)
    row.update(compare_value(row['raw'], row['scale'], selected), prior_non_sec_result=old, role=role)
    if row['status'] == 'within_scope_candidate_precision' and selected.get('error') is not None:
        ref, tolerance = amount(row['raw'], row['scale'])
        if abs(ref - selected['value']) <= selected['error'] + tolerance:
            row.update(status='explained_reported_precision', explanation={
                'kind': 'sec_reported_fy_ytd_precision', 'maximum_sec_error_usd': str(selected['error']),
                'basis': '數字只由 SEC 原申報全年、九個月及完整 scope 運算；保留差額與每個申報精度，不以公司 IR 的單季數字替換。'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ups-sec-page', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.ups_sec_page = args.ups_sec_page.resolve()
    ups = parse_ups_sec_page(args.ups_sec_page.read_text())
    args.out.mkdir(parents=True, exist_ok=False)
    temporal.save(args.out / 'UPS-SEC-quarter.json', {'source_url': UPS_URL,
        'accession': '0001628280-26-067381', 'period_end': '2026-09-30',
        'source_format': 'SEC_page_text_returned_by_web_tool',
        'source_artifact_sha256': sha(args.ups_sec_page), 'values': ups})
    local = ROOT / 'data/vendor/local/cohort-adjudication-20261104' / args.out.name
    local.mkdir(parents=True, exist_ok=False)
    base = temporal.load(BASE / 'completion-status.json'); companies = []
    for company in base['companies']:
        ticker = company['ticker']; rows = temporal.load(ROOT / company['local_detail_path'])
        if sha(ROOT / company['local_detail_path']) != company['local_detail_sha256']:
            raise ValueError('Prior detail hash mismatch')
        if ticker in ('META', 'GOOGL'):
            receipt = temporal.load(ROOT / 'research/completed-parser-repairs-20261104' / (ticker + '-freeze.json'))
            data = temporal.checked_data(receipt['plan'], ROOT / receipt['plan']['baseline_file'])
            temporal.verify_freeze(receipt, data); _, pools = pools_for(ticker, data)
            facts, conflicts = pools['2025-12-31']
            for row in rows:
                if row['sec_period_end'] == '2025-12-31' and ('direct_company' in row.get('role', '')):
                    selected = selection(ticker, row['category'], facts, conflicts) if ticker == 'META' else google_hedging(facts, conflicts)
                    replace_from_sec(row, selected, 'sec_only_fy_minus_ytd_with_reported_precision')
        elif ticker == 'UNH':
            for row in rows:
                if row.get('role') == 'company_direct_gaap_revenue_parsed':
                    prior = row['prior_result']; selected = prior['selected']
                    if not selected_is_sec(selected) or selected['value'] != row['selected']['value']:
                        raise ValueError('UNH SEC restoration differs')
                    row.update(prior_non_sec_result=copy.deepcopy(row), selected=selected, role=prior['role'])
                    if row.get('explanation'):
                        if 'primary_table' in row['explanation']:
                            row['explanation']['reference_company_table'] = row['explanation'].pop('primary_table')
                        row['explanation']['company_table_is_reference_only'] = True
        elif ticker == 'UPS':
            for row in rows:
                if row.get('role') == 'direct_company_release_pdf_parsed':
                    parsed = ups[row['category']]
                    fact = {'concept': 'sec-table:SegmentRevenue', 'dimensions': {'reported_segment': row['category']},
                        'unit': 'iso4217:USD', 'value': parsed['value_usd'], 'decimals': '-6',
                        'startdate': '2026-07-01', 'enddate': '2026-09-30', 'source_url': UPS_URL,
                        'accession': '0001628280-26-067381', 'source_line': parsed['line'],
                        'source_artifact_sha256': sha(args.ups_sec_page), 'source_format': 'SEC_page_text_returned_by_web_tool'}
                    replace_from_sec(row, {'status': 'observed', 'value': fact['value'], 'error': Decimal(500_000),
                        'facts': [fact]}, 'direct_sec_8k_exhibit_table_parsed')
        elif ticker == 'PGR':
            # 公司網站 PDF 的解析保留作參考研究；主要數字恢復先前 SEC facts，沒有重標其出處。
            old_summary = temporal.load(ROOT / 'research/completed-parser-repairs-20261104/extended-completion-status.json')
            old = next(c for c in old_summary['companies'] if c['ticker'] == 'PGR')
            rows = temporal.load(ROOT / old['local_detail_path'])
        for row in rows:
            if row['status'] == 'reference_not_applicable_evidenced':
                row['primary_source_check'] = 'not_applicable_no_numeric_output'
            elif selected_is_sec(row.get('selected', {})):
                row['primary_source_check'] = 'SEC_operands_verified'
            else:
                row['primary_source_check'] = 'SEC_primary_not_verified'
                # 缺 SEC 原始運算元時，不能以其他來源觀察到的數字冒充主要輸出。
                if row.get('selected', {}).get('status') == 'observed':
                    row.update(status='sec_primary_source_required', unverified_selected=row.pop('selected'))
        path = local / (ticker + '-sec-only.json')
        temporal.save(path, json.loads(json.dumps(rows, default=str)))
        eligible = [copy.deepcopy(r) for r in rows if r['status'] != 'reference_not_applicable_evidenced']
        for r in eligible:
            if r['status'] in ACCEPTED - {'exact_scope_candidate_match'} and r.get('explanation'):
                r['status'] = 'exact_scope_candidate_match'
        verdict = assess(eligible, company['target_periods'], company['reference'])
        chosen = [r for r in rows if r['source'] == company['reference'] and r['kind'] == 'Q']
        if any(r['primary_source_check'] == 'SEC_primary_not_verified' for r in chosen):
            verdict['status'] = 'Fail'; verdict['fail_reasons'].append('SEC_primary_source_not_complete')
        verdict.update(cell_statuses=dict(Counter(r['status'] for r in chosen)),
            primary_source_checks=dict(Counter(r['primary_source_check'] for r in chosen)))
        companies.append({'ticker': ticker, **verdict, 'local_detail_path': str(path.relative_to(ROOT)), 'local_detail_sha256': sha(path)})
    result = {'primary_data_policy': '擷取與數字計算僅 SEC；vendor／公司 IR 只作參考與差異解釋。',
        'ok_count': sum(c['status'] == 'OK' for c in companies), 'total': 30, 'companies': companies, 'blind_tests': 0,
        'source_summary_sha256': sha(BASE / 'completion-status.json'),
        'source_policy_code_sha256': sha(Path(__file__)), 'ups_sec_url': UPS_URL,
        'ups_sec_page_path': str(args.ups_sec_page.relative_to(ROOT)), 'ups_sec_page_sha256': sha(args.ups_sec_page),
        'ups_source_format': '正常 web 工具讀取 SEC 附件後保存的頁面文字；非公司 IR、非原始 HTML bytes；CLI 單次 GET 回 403 後未重試。',
        'PGR_company_pdf_status': 'reference_study_only_not_SEC_parser_output'}
    temporal.save(args.out / 'completion-status.json', result)
    print(str(result['ok_count']) + ' / 30 SEC-only')


if __name__ == '__main__':
    main()
