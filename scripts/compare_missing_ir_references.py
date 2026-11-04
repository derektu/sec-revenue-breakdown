#!/usr/bin/env python3
"""以非 SEC 報表副本作獨立欄位參考；所有輸出數字仍只由 SEC facts 產生。"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re

from cohort_rule_audit import resolve
from cohort_rule_catalog import catalog
from enforce_sec_primary_source import selected_is_sec
from remaining_issuer_rules import normalize_record
import temporal_eval as temporal

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / 'data/vendor/local/cloud-ir-reference-20261104'
SOURCES = {
    'BRK-B-2024Q3.txt': 'https://www.berkshirehathaway.com/qtrly/3rdqtr24.pdf',
    'BRK-B-2025Q3.txt': 'https://www.berkshirehathaway.com/qtrly/3rdqtr25.pdf',
    'MCD-2025Q3-comparative.txt': 'https://d18rn0p25nwr6d.cloudfront.net/CIK-0000063908/8564664b-2af9-4960-b5d2-e8f8b30dc99f.pdf'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pdf_lines(text):
    """合併同一 PDF 的多次文字摘錄；重複行不一致時拒絕。"""
    lines = {}
    for line in text.splitlines():
        match = re.fullmatch(r'L(\d+)@P\d+(?:-\d+)?: (.*)', line)
        if match:
            number, body = int(match[1]), match[2]
            if number in lines and lines[number] != body:
                raise ValueError('Conflicting PDF text captures')
            lines[number] = body
    return '\n'.join(lines[n] for n in sorted(lines))


def one(text, pattern):
    hits = re.findall(pattern, text, re.M)
    if len(hits) != 1:
        raise ValueError('Missing or ambiguous reference table: ' + pattern)
    return hits[0]


def numbers(row, count):
    cells = row.replace('$', '').split()
    if len(cells) != count or not all(re.fullmatch(r'\(?-?\d[\d,]*\)?', c) for c in cells):
        raise ValueError('Reference numeric column count or monetary value differs')
    return [int(c.replace(',', '').replace('(', '-').replace(')', '')) * 1_000_000 for c in cells]


def mcd_reference(text):
    body = one(pdf_lines(text), r'Quarters Ended Nine Months Ended\nSeptember 30, September 30,\n'
        r'In millions 2025 2024 2025 2024\n(U\.S\. .*?\nInternational Operated Markets .*?\n'
        r'International Developmental Licensed Markets & Corporate .*?\nTotal Revenues .*?)\n')
    labels = {'United States (US)': 'U.S.', '國際運營的市場': 'International Operated Markets',
        '國際開發許可市場和公司': 'International Developmental Licensed Markets & Corporate'}
    values = {label: numbers(one(body, re.escape(row) + r' (.+)$'), 4)[1] for label, row in labels.items()}
    total = numbers(one(body, r'Total Revenues (.+)$'), 4)[1]
    if sum(values.values()) != total:
        raise ValueError('MCD reference segments do not reconcile')
    return values


def brk_reference(text, year):
    body = pdf_lines(text)
    if year == 2024:
        if 'Third Quarter First Nine Months\n2024 2023 2024 2023' not in body or 'were as follows (in millions).' not in body:
            raise ValueError('BRK 2024 reference period or unit differs')
        table = one(body, r'Revenues of Operating Businesses\n([\s\S]*?)\nEarnings Before Income Taxes')
        labels = {'保險': 'Total insurance', '製造業': 'Manufacturing', 'Pilot': 'Pilot', 'McLane': 'McLane',
            '服務和零售': 'Service and retailing', 'Berkshire Hathaway Energy (BHE)': 'BHE',
            'Burlington Northern Santa Fe, LLC (BNSF)': 'BNSF', '公司、抵銷和其他': 'Corporate, eliminations and other'}
        values = {label: numbers(one(table, '^' + re.escape(row) + r' (.+)$'), 4)[0] for label, row in labels.items()}
        components = ['GEICO', 'Berkshire Hathaway Primary Group', 'Berkshire Hathaway Reinsurance Group', 'Investment income']
        if sum(numbers(one(table, '^' + re.escape(row) + r' (.+)$'), 4)[0] for row in components) != values['保險']:
            raise ValueError('BRK insurance reference components differ')
        total = numbers(one(table, r'^\$ (.+)$'), 4)[0]
    elif year == 2025:
        if 'Third Quarter 2025' not in body or '(in millions).' not in body:
            raise ValueError('BRK 2025 reference period or unit differs')
        insurance = one(body, r'Third Quarter 2025\n[\s\S]*?\nRevenues (.+)$')
        insurance = numbers(insurance, 6)
        if sum(insurance[:3]) != insurance[3] or insurance[3] + insurance[4] != insurance[5]:
            raise ValueError('BRK insurance reference components differ')
        values = {'保險': insurance[5]}
        for label, heading in [('Burlington Northern Santa Fe, LLC (BNSF)', 'BNSF'), ('Berkshire Hathaway Energy (BHE)', 'BHE')]:
            row = one(body, '^' + heading + r'\nThird Quarter First Nine Months\n2025 2024 2025 2024\nRevenues (.+)$')
            values[label] = numbers(row, 4)[0]
        for left, right, heading in [('製造業', '服務和零售', 'Manufacturing Service and retailing'), ('Pilot', 'McLane', 'Pilot McLane')]:
            row = one(body, '^' + heading + r'\nThird Quarter First Nine Months Third Quarter First Nine Months\n'
                r'2025 2024 2025 2024 2025 2024 2025 2024\nRevenues (.+)$')
            cells = numbers(row, 8); values[left], values[right] = cells[0], cells[4]
        reconciliation = one(body, r'Revenues Earnings before income taxes\nThird Quarter First Nine Months Third Quarter First Nine Months\n'
            r'2025 2024 2025 2024 2025 2024 2025 2024\n([\s\S]*?)\nAdditional segment data')
        values['公司、抵銷和其他'] = numbers(one(reconciliation, r'Corporate, eliminations and\nother (.+)$'), 8)[0]
        total = numbers(one(reconciliation, r'^\$ (.+)$'), 8)[0]
    else:
        raise ValueError('Unreviewed BRK year')
    if sum(values.values()) != total:
        raise ValueError('BRK reference segments do not reconcile')
    return values


def sec_selections(ticker, period):
    receipt = temporal.load(ROOT / f'research/cohort-rule-replay-20261104/{ticker}-freeze.json')
    data = temporal.checked_data(receipt['plan'], ROOT / receipt['plan']['baseline_file'])
    record = copy.deepcopy(next(r for r in data['raw_filings'] if r['filing']['reportDate'] == period))
    evidence = next(f for f in receipt['plan']['training'] + receipt['plan']['holdout']
        if f['accession'] == record['filing']['accessionNumber'])
    for fact in record['facts']:
        fact.update(source_url=evidence['url'], source_artifact_sha256=evidence['sha256'],
            source_format='saved_SEC_iXBRL_candidates', accession=evidence['accession'])
    facts, conflicts = temporal.runner().quarter(normalize_record(ticker, record)['facts'], period, '10-Q', [])
    result = {label: resolve(spec, facts, conflicts) for label, spec in catalog()[ticker]['futu'].items()}
    if not all(selected_is_sec(selected) for selected in result.values()):
        raise ValueError('Missing or non-SEC output')
    return result, receipt['plan']['baseline_sha256']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--references', type=Path, default=PRIVATE)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    for name in SOURCES:
        if not (args.references / name).is_file():
            raise FileNotFoundError('Missing private reference capture: ' + name)
    local = args.references / args.out.name
    local.mkdir(exist_ok=False)
    comparisons, public = [], []
    jobs = [('MCD', '2024-09-30', 'MCD-2025Q3-comparative.txt'),
        ('BRK-B', '2024-09-30', 'BRK-B-2024Q3.txt'), ('BRK-B', '2025-09-30', 'BRK-B-2025Q3.txt')]
    for ticker, period, name in jobs:
        path = args.references / name; text = path.read_text()
        if SOURCES[name] not in text:
            raise ValueError('Reference URL not present in capture')
        values = mcd_reference(text) if ticker == 'MCD' else brk_reference(text, int(period[:4]))
        selected, baseline_sha = sec_selections(ticker, period)
        if set(values) != set(selected):
            raise ValueError('Reference and SEC category sets differ')
        for label, value in values.items():
            comparisons.append({'ticker': ticker, 'period_end': period, 'category': label,
                'reference_usd': value, 'reference_source_url': SOURCES[name], 'reference_sha256': digest(path),
                'reference_format': 'web_tool_PDF_text_excerpt', 'reference_artifact': str(path.relative_to(ROOT)),
                'status': 'exact_match' if selected[label]['value'] == value else 'differs',
                'selected': selected[label], 'baseline_sha256': baseline_sha,
                'blind_test': False, 'reference_independent_of_issuer_filing': False,
                'later_comparative_reference': ticker == 'MCD'})
    detail = local / 'comparisons.json'
    temporal.save(detail, json.loads(json.dumps(comparisons, default=str)))
    for row in comparisons:
        public.append({k: v for k, v in row.items() if k not in ('reference_usd',)})
    prior_summary = ROOT / 'research/reference-gap-completion-20261104/completion-status.json'
    result = {'status': 'supplementary_reference_study_only',
        'fixed_vendor_completion_count': temporal.load(prior_summary)['ok_count'],
        'source_summary_path': str(prior_summary.relative_to(ROOT)), 'source_summary_sha256': digest(prior_summary),
        'completion_status_changed': False, 'blind_test': False,
        'reference_format': 'web_tool_PDF_text_excerpt_not_original_PDF_bytes',
        'comparison_count': len(comparisons), 'comparison_statuses': dict(Counter(r['status'] for r in comparisons)),
        'private_detail_path': str(detail.relative_to(ROOT)), 'private_detail_sha256': digest(detail),
        'code_sha256': {p: digest(ROOT / p) for p in ['scripts/compare_missing_ir_references.py',
            'scripts/cohort_rule_catalog.py', 'scripts/cohort_rule_audit.py', 'scripts/remaining_issuer_rules.py',
            'research/recovered-sec/eight_quarter_eval/run.py']}, 'comparisons': public}
    args.out.mkdir(parents=True, exist_ok=False)
    temporal.save(args.out / 'summary.json', json.loads(json.dumps(result, default=str)))
    print(json.dumps(result['comparison_statuses']))


if __name__ == '__main__':
    main()
