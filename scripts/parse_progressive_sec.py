#!/usr/bin/env python3
"""解析正常 SEC DOM 表格快照；包含 10-K 引用的 Exhibit 13，不讀取公司 IR。"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from enforce_sec_primary_source import sec_url
from parse_progressive_reports import INCOME

MONTHS = {'March 31': 3, 'June 30': 6, 'September 30': 9, 'December 31': 12}
NUMBER = re.compile(r'\(?-?\d[\d,]*\)?')


def numeric_row(table, label, count):
    hits = [row for row in table['rows'] if row and row[0] == label]
    if len(hits) != 1 or len(hits[0]) != count + 1:
        raise ValueError('Missing, duplicate or wrong-width row: ' + label)
    if not all(NUMBER.fullmatch(c) for c in hits[0][1:]):
        raise ValueError('Unreviewed monetary value')
    return [int(Decimal(c.replace(',', '').replace('(', '-').replace(')', '')) * 1_000_000) for c in hits[0][1:]]


def parse_snapshot(data, artifact_sha256):
    url = data['source_url']
    if not sec_url(url) or '/data/80661/' not in url or data.get('format') != 'SEC_DOM_nonempty_cell_text':
        raise ValueError('Not a reviewed PGR SEC table snapshot')
    date = re.search(r'/pgr-(20\d\d)(\d\d)(\d\d)(_d2)?\.htm$', url)
    if not date:
        raise ValueError('Unreviewed PGR source document name')
    report_year, month, day = map(int, date.group(1, 2, 3))
    if month not in (3, 6, 9, 12) or day != (31 if month in (3, 12) else 30):
        raise ValueError('Unreviewed report period')
    annual = month == 12
    if annual and not date[4]:
        raise ValueError('Annual consolidated financials must come from Exhibit 13, not parent-only 10-K tables')
    report_date = f'{report_year:04d}-{month:02d}-{day:02d}'
    accession_digits = url.split('/')[-2]
    accession = accession_digits[:10] + '-' + accession_digits[10:12] + '-' + accession_digits[12:]
    income_tables = [t for t in data['tables'] if all(any(r[0] == label for r in t['rows'] if r) for label in INCOME)]
    if len(income_tables) != 1:
        raise ValueError('Missing unique consolidated income table')
    table = income_tables[0]
    stop = next(i for i, row in enumerate(table['rows']) if row[0] == 'Revenues')
    header = table['rows'][:stop]
    if not any('millions' in cell for row in header for cell in row):
        raise ValueError('Missing income units')
    years = [int(cell) for row in header for cell in row if re.fullmatch(r'20\d\d', cell)]
    expected_years = [report_year, report_year - 1, report_year - 2] if annual else [report_year, report_year - 1] * (1 if month == 3 else 2)
    if years != expected_years:
        raise ValueError('Unexpected income year column order')
    if not annual:
        expected_label = next(label for label, value in MONTHS.items() if value == month)
        if not any(expected_label in ' '.join(row) for row in header) or not any('Three Months' in cell for row in header for cell in row):
            raise ValueError('Wrong income quarter header')
        if month != 3 and not any(('Six Months' if month == 6 else 'Nine Months') in cell for row in header for cell in row):
            raise ValueError('Missing YTD header')
    columns = {label: numeric_row(table, label, len(years)) for label in INCOME}
    impairment_labels = [r[0] for r in table['rows'] if r and r[0].startswith('Net impairment losses')]
    if len(impairment_labels) > 1:
        raise ValueError('Conflicting impairment labels')
    losses = numeric_row(table, impairment_labels[0], len(years)) if impairment_labels else [0] * len(years)
    observations = []
    consolidated_by_period = {}
    def add(kind, year, label, value, table, scope, operands=None):
        end_month = 12 if kind == 'FY' else month
        end = f'{year}-{end_month:02d}-{31 if end_month in (3, 12) else 30}'
        start_month = 1 if kind.startswith(('FY', 'YTD')) else month - 2
        observations.append({'kind': kind, 'year': year, 'month': end_month, 'label': label,
            'value': value, 'concept': 'sec-table:' + scope, 'dimensions': {'reported_row': label, 'table_scope': scope},
            'unit': 'iso4217:USD', 'decimals': '-6', 'startdate': f'{year}-{start_month:02d}-01', 'enddate': end,
            'source_url': url, 'source_report_date': report_date, 'source_table_index': table['index'],
            'accession': accession,
            'source_artifact_sha256': artifact_sha256, 'source_format': data['format'],
            **({'aggregation_evidence': operands} if operands else {})})
    for index, year in enumerate(years):
        kind = 'FY' if annual else 'Q' if index < 2 else 'YTD' + str(month)
        values = {label: nums[index] for label, nums in columns.items()}
        consolidated_by_period[kind, year] = values
        securities = 'Total net realized gains (losses) on securities'
        if (values['Net realized gains (losses) on security sales']
                + values['Net holding period gains (losses) on securities'] + losses[index] != values[securities]):
            raise ValueError('Securities components do not reconcile')
        if sum(values[label] for label in ['Net premiums earned', 'Investment income', securities,
                'Fees and other revenues', 'Service revenues']) != values['Total revenues']:
            raise ValueError('Consolidated revenues do not reconcile')
        for label, value in values.items():
            add(kind, year, label, value, table, 'consolidated_income')
    segment_tables = [t for t in data['tables'] if any(r and r[0] == 'Total underwriting revenue' for r in t['rows'])]
    segment_periods = []
    for segment in segment_tables:
        if segment['rows'][0] != ['(millions)', 'Personal Lines', 'Commercial Lines', 'Other1', 'Companywide']:
            raise ValueError('Wrong segment columns or units')
        period_rows = [r[0] for r in segment['rows'] if r and re.fullmatch(
            r'(December 31, 20\d\d|(Three|Six|Nine) Months Ended (March 31|June 30|September 30), 20\d\d)', r[0])]
        if len(period_rows) != 1:
            raise ValueError('Missing segment period')
        period = period_rows[0]; year = int(period[-4:])
        kind = 'FY' if period.startswith('December') else 'Q' if period.startswith('Three') else 'YTD' + str(month)
        if kind == 'FY' and not annual or annual and kind != 'FY':
            raise ValueError('Annual/quarter segment formats mixed')
        if not annual and not any(label in period and m == month for label, m in MONTHS.items()):
            raise ValueError('Wrong segment date')
        if not annual and not period.startswith(('Three' if kind == 'Q' else 'Six' if month == 6 else 'Nine') + ' Months'):
            raise ValueError('Wrong segment duration')
        segment_periods.append((kind, year))
        premium = numeric_row(segment, 'Net premiums earned', 4)
        fees = numeric_row(segment, 'Fees and other revenues', 4)
        total = numeric_row(segment, 'Total underwriting revenue', 4)
        if sum(total[:3]) != total[3] or any(a + b != c for a, b, c in zip(premium, fees, total)):
            raise ValueError('Segment revenues do not reconcile')
        income = consolidated_by_period.get((kind, year))
        if not income or premium[3] != income['Net premiums earned'] or fees[3] != income['Fees and other revenues']:
            raise ValueError('Segment premium and fees differ from consolidated statement for this period')
        for label, value in zip(['個人保險', '商業保險', '其他', 'Total underwriting revenue'], total):
            add(kind, year, label, value, segment, 'underwriting_revenue_including_fees')
    expected_periods = [('FY', y) for y in expected_years] if annual else [('Q', y) for y in expected_years[:2]]
    if not annual and month != 3:
        expected_periods += [('YTD' + str(month), y) for y in expected_years[:2]]
    if sorted(segment_periods) != sorted(expected_periods):
        raise ValueError('Incomplete or duplicate segment periods')
    return observations


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True); args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text()); results = []
    for source in manifest['files']:
        path = Path(source['path']); raw = path.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
        if digest != source['sha256']:
            raise ValueError('Capture hash mismatch')
        results.extend(parse_snapshot(json.loads(raw), digest))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as f:
        json.dump({'observations': results, 'captures': manifest, 'parser_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, f, ensure_ascii=False, indent=2); f.write('\n')
    print(f'Parsed {len(manifest["files"])} SEC snapshots; {len(results)} facts')


if __name__ == '__main__':
    main()
