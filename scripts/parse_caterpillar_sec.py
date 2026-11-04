#!/usr/bin/env python3
"""解析 CAT SEC 8-K 的當季分部收入；分開兩組公司抵銷並與地區表對帳。"""
from decimal import Decimal
import re

URL = 'https://www.sec.gov/Archives/edgar/data/18230/000001823026000052/ex991toformcat3q2026earnin.htm'
LABELS = ['Power & Energy', 'Construction Industries', 'Resource Industries', 'All Other Segment',
          'Corporate Items and Eliminations', 'Machinery, Power & Energy', 'Financial Products Segment',
          'Corporate Items and Eliminations', 'Financial Products Revenues', 'Consolidated Sales and Revenues']


def money(text):
    if not re.fullmatch(r'\(?\d[\d,]*\)?', text):
        raise ValueError('Unreviewed CAT revenue value; missing is not zero')
    return int(text.replace(',', '').replace('(', '-').replace(')', '')) * 1_000_000


def parse_snapshot(snapshot, artifact_sha256):
    if snapshot.get('source_url') != URL or snapshot.get('format') != 'SEC_DOM_nonempty_cell_text':
        raise ValueError('Not the reviewed CAT SEC exhibit')
    def one(title):
        tables = [t for t in snapshot['tables'] if t['rows'] and t['rows'][0] == [title]]
        if len(tables) != 1:
            raise ValueError('Missing or duplicate CAT source table')
        return tables[0]
    bridge = one('Sales and Revenues by Segment'); geographic = one('Sales and Revenues by Geographic Region')
    expected_header = ['(Millions of dollars)', 'Third Quarter 2025', 'Sales Volume', 'Price Realization', 'Currency',
                       'Inter-Segment / Other', 'Third Quarter 2026', '$ Change', '% Change']
    if bridge['rows'][1] != expected_header:
        raise ValueError('Unreviewed CAT period, unit or bridge column order')
    data = bridge['rows'][2:]
    if [r[0] for r in data] != LABELS or any(len(r) < 7 for r in data):
        raise ValueError('Segment rows or separate corporate scopes changed')
    current = [money(row[6]) for row in data]
    if sum(current[:5]) != current[5] or current[6] + current[7] != current[8] or current[5] + current[8] != current[9]:
        raise ValueError('CAT segment-to-consolidated reconciliation failed')
    headers = geographic['rows'][:4]
    if headers[1] != ['North America', 'Latin America', 'EAME', 'Asia/Pacific', 'External Sales and Revenues',
                      'Inter-Segment', 'Total Sales and Revenues'] or headers[2][0] != '(Millions of dollars)' or headers[3] != ['Third Quarter 2026']:
        raise ValueError('Wrong geographic revenue scope or period')
    geo_rows = geographic['rows'][4:]
    if [r[0] for r in geo_rows] != LABELS:
        raise ValueError('Geographic segment scopes changed')
    for index, row in enumerate(geo_rows):
        total_index = 7 if index in (4, 7) else 13
        if len(row) <= total_index or money(row[total_index]) != current[index]:
            raise ValueError('Gross revenue differs between independent company tables')
        if index < 4 and money(row[9]) + money(row[11]) != current[index]:
            raise ValueError('External plus intersegment does not equal gross revenue')
    groups = ['Machinery, Power & Energy'] * 6 + ['Financial Products'] * 3 + ['Consolidated']
    facts = []
    for index, (label, value, group) in enumerate(zip(LABELS, current, groups)):
        facts.append({'concept': 'sec-table:SalesAndRevenues', 'dimensions': {'reported_group': group, 'reported_row': label},
            'unit': 'iso4217:USD', 'value': value, 'raw': data[index][6], 'decimals': '-6',
            'startdate': '2026-07-01', 'enddate': '2026-09-30', 'source_url': URL,
            'accession': '0000018230-26-000052', 'source_artifact_sha256': artifact_sha256,
            'source_format': snapshot['format'], 'source_table_index': bridge['index'],
            'source_row_index': index + 2, 'source_column': 'Third Quarter 2026',
            'geographical_table_index': geographic['index'], 'geographical_total_verified': True})
    selected = {}
    for label, index in [('Power & Energy', 0), ('Construction', 1), ('Resource', 2), ('Other', 3), ('Financial Products', 6)]:
        selected[label] = {'status': 'observed', 'value': current[index], 'error': Decimal(500_000), 'facts': [facts[index]]}
    selected['Eliminations'] = {'status': 'observed', 'value': current[4] + current[7], 'error': Decimal(1_000_000),
        'facts': [facts[4], facts[7]], 'role': 'sum_of_separately_scoped_corporate_eliminations'}
    return {'period_end': '2026-09-30', 'selected': selected, 'consolidated_total': current[9], 'facts': facts,
            'gross_and_external_scopes_kept_separate': True}
