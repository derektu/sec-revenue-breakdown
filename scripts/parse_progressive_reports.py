#!/usr/bin/env python3
"""解析 Progressive 原始年季報的收入與分部表；分開記錄證券總額及組成。"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess

INCOME = ['Net premiums earned', 'Investment income', 'Net realized gains (losses) on security sales',
          'Net holding period gains (losses) on securities', 'Total net realized gains (losses) on securities',
          'Fees and other revenues', 'Service revenues', 'Total revenues']
NUM = r'\(?-?\d[\d,]*(?:\.\d+)?\)?'


def row_values(text, label, count):
    hits = [line.strip()[len(label):] for line in text.splitlines()
            if re.match(re.escape(label) + r'\s+', line.strip())]
    if len(hits) != 1:
        raise ValueError('Missing or duplicate row: ' + label)
    tokens = re.findall(NUM, hits[0])
    if len(tokens) != count:
        raise ValueError('Unexpected columns: ' + label)
    return [int(Decimal(n.replace(',', '').replace('(', '-').replace(')', '')) * 1_000_000) for n in tokens]


def parse_income(text, report_year, month=None):
    pages = [p for p in text.split('\f') if 'Consolidated Statements of Comprehensive Income' in p
             and 'Investment income' in p and 'Net premiums earned' in p]
    if len(pages) != 1 or 'millions' not in pages[0]:
        raise ValueError('Missing unique income statement in millions')
    page = pages[0]
    header = page[:page.index('Revenues')]
    annual = month is None
    if annual:
        if 'For the years ended December 31,' not in header:
            raise ValueError('Wrong annual period header')
        years = [report_year, report_year - 1, report_year - 2]
        if [int(y) for y in re.findall(r'\b20\d\d\b', header)] != years:
            raise ValueError('Wrong annual year columns')
        periods = [('FY', y) for y in years]
    else:
        date_label = {3: 'March 31', 6: 'June 30', 9: 'September 30'}[month]
        if date_label not in header or 'Three Months' not in header:
            raise ValueError('Wrong quarterly period header')
        years = [report_year, report_year - 1] * (1 if month == 3 else 2)
        if [int(y) for y in re.findall(r'\b20\d\d\b', header)] != years:
            raise ValueError('Wrong quarterly year columns')
        periods = [('Q', report_year), ('Q', report_year - 1)]
        if month != 3:
            periods += [('YTD' + str(month), report_year), ('YTD' + str(month), report_year - 1)]
    columns = {label: row_values(page, label, len(periods)) for label in INCOME}
    impairment = next((line.strip().split('  ')[0] for line in page.splitlines()
                       if line.strip().startswith('Net impairment losses')), None)
    loss = row_values(page, impairment, len(periods)) if impairment else [0] * len(periods)
    result = []
    for index, (kind, year) in enumerate(periods):
        values = {label: nums[index] for label, nums in columns.items()}
        if sum(values[k] for k in ['Net premiums earned', 'Investment income',
            'Total net realized gains (losses) on securities', 'Fees and other revenues', 'Service revenues']) != values['Total revenues']:
            raise ValueError('Income components do not reconcile')
        if (values['Net realized gains (losses) on security sales']
                + values['Net holding period gains (losses) on securities'] + loss[index]
                != values['Total net realized gains (losses) on securities']):
            raise ValueError('Securities components do not reconcile')
        result.append({'kind': kind, 'year': year, 'month': 12 if annual else month, 'values_usd': values,
                       'impairment_usd': loss[index]})
    return result


def parse_segments(text, report_year, month=None):
    # 2025 以後公司將 Property 納入 Personal Lines，並重編比較欄。
    # 拒絕 2024 舊版分部／稅前利益交錯表，不跨口徑相減。
    if report_year < 2025:
        raise ValueError('Old segment format requires separate reviewed mapping')
    results = []
    for page in text.split('\f'):
        if 'Personal Lines' not in page or 'Commercial Lines' not in page or 'Total underwriting revenue' not in page:
            continue
        if '(millions)' not in page:
            continue
        pattern = (r'December 31, (20\d\d)' if month is None else
            r'(Three|Six|Nine) Months Ended ' + {3: 'March 31', 6: 'June 30', 9: 'September 30'}[month] + r', (20\d\d)')
        headers = list(re.finditer(r'^\s*' + pattern + r'\s*$', page, re.M))
        for i, match in enumerate(headers):
            column_lines = [line for line in page[:match.start()].splitlines()
                            if 'Personal Lines' in line and 'Commercial Lines' in line]
            if not column_lines or not re.search(r'Personal Lines\s+Commercial Lines\s+Other1?\s+Companywide', column_lines[-1]):
                raise ValueError('Unreviewed segment column order')
            block = page[match.end():headers[i + 1].start() if i + 1 < len(headers) else len(page)]
            block = re.split(r'(?m)^\s*Losses and loss adjustment expenses', block, maxsplit=1)[0]
            year = int(match[1] if month is None else match[2])
            if year not in (report_year, report_year - 1, report_year - 2):
                raise ValueError('Unexpected segment year')
            premium = row_values(block, 'Net premiums earned', 4)
            fees = row_values(block, 'Fees and other revenues', 4)
            total = row_values(block, 'Total underwriting revenue', 4)
            if sum(total[:3]) != total[3] or any(p + f != v for p, f, v in zip(premium, fees, total)):
                raise ValueError('Segment revenue components do not reconcile')
            kind = 'FY' if month is None else 'Q' if match[1] == 'Three' else 'YTD' + str(month)
            results.append({'kind': kind, 'year': year, 'month': 12 if month is None else month,
                'values_usd': dict(zip(['個人保險', '商業保險', '其他', 'Total underwriting revenue'], total)),
                'net_premiums_usd': premium, 'fees_usd': fees})
    if not results:
        raise ValueError('No reviewed segment table')
    keys = [(r['kind'], r['year'], r['month']) for r in results]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate segment periods')
    expected = ({('FY', y, 12) for y in range(report_year - 2, report_year + 1)} if month is None else
                {('Q', y, month) for y in (report_year, report_year - 1)})
    if month not in (None, 3):
        expected |= {('YTD' + str(month), y, month) for y in (report_year, report_year - 1)}
    if set(keys) != expected:
        raise ValueError('Incomplete reviewed segment periods')
    return results


def parse_pdf(path, year, month=None):
    text = subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True, text=True, capture_output=True).stdout
    return {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'income': parse_income(text, year, month), 'segments': parse_segments(text, year, month)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    reports = {}
    for name, year, month in [('pgr-2025-10k.pdf', 2025, None), ('pgr-2025-q3.pdf', 2025, 9),
                             ('pgr-2026-q1.pdf', 2026, 3), ('pgr-2026-q2.pdf', 2026, 6), ('pgr-2026-q3.pdf', 2026, 9)]:
        reports[name] = parse_pdf(args.sources / name, year, month)
    with args.out.open('x') as f:
        json.dump(reports, f, ensure_ascii=False, indent=2); f.write('\n')
    print('Parsed five original annual/quarterly reports with income and segment reconciliations')


if __name__ == '__main__':
    main()
