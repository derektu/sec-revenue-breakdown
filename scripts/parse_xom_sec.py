#!/usr/bin/env python3
"""由 XOM SEC 分部與合併表擷取收入，分開單季、累計及全年。"""
from datetime import date
import re

from enforce_sec_primary_source import sec_url

GROUPS = ['Upstream', 'Energy Products', 'Chemical Products', 'Specialty Products']
LABELS = dict(zip(['上游', '能源產品', '化工產品', '特種產品'], GROUPS))
MONTHS = {'March 31': 3, 'June 30': 6, 'September 30': 9, 'December 31': 12}


def money(value):
    if not re.fullmatch(r'(?:\d[\d,]*|\(\d[\d,]*\))', value):
        raise ValueError('Missing or unreviewed XOM amount; dash is not zero')
    return int(value.replace(',', '').replace('(', '-').replace(')', '')) * 1_000_000


def one(rows, label, length=None):
    matches = [r for r in rows if r and r[0] == label and (length is None or len(r) == length)]
    if len(matches) != 1:
        raise ValueError('Missing or duplicate XOM row: ' + label)
    return matches[0]


def parse_snapshot(snapshot, artifact_sha256):
    url = snapshot['source_url']
    match = re.search(r'/data/(34088|2115436)/(\d{18})/xom-(20\d\d)(03|06|09|12)(31|30)\.htm$', url)
    if not sec_url(url) or not match or snapshot.get('format') != 'SEC_DOM_cell_textContent':
        raise ValueError('Unreviewed XOM SEC source')
    cik, accession, year, month, day = match.groups(); year, month, day = map(int, [year, month, day])
    report_date = date(year, month, day).isoformat()
    if day != (31 if month in (3, 12) else 30):
        raise ValueError('Wrong XOM fiscal end date')
    tables = snapshot['tables']
    incomes = [t for t in tables if any(r and r[0] == 'Total revenues and other income' for r in t['rows'])]
    if len(incomes) != 1:
        raise ValueError('Missing unique consolidated income table')
    income = incomes[0]; header = income['rows'][:4]
    text = ' '.join(' '.join(r) for r in header)
    if 'millions of dollars' not in text:
        raise ValueError('Wrong consolidated units')
    if month == 12:
        columns = [('FY', y) for y in (year, year - 1, year - 2)]
    else:
        if 'Three Months Ended' + next(k for k, v in MONTHS.items() if v == month) not in text:
            raise ValueError('Missing quarter date caption')
        columns = [('Q', year), ('Q', year - 1)]
        if month != 3:
            caption = ('Six' if month == 6 else 'Nine') + ' Months Ended' + next(k for k, v in MONTHS.items() if v == month)
            if caption not in text:
                raise ValueError('Missing cumulative date caption')
            columns += [('YTD' + str(month), year), ('YTD' + str(month), year - 1)]
    years = [s for r in header for s in r if re.fullmatch(r'20\d\d', s)]
    if years != [str(y) for _, y in columns]:
        raise ValueError('Wrong consolidated year-column order')
    consolidated = {}
    for label in ['Sales and other operating revenue', 'Income from equity affiliates', 'Other income', 'Total revenues and other income']:
        row = one(income['rows'], label)
        if len(row) not in (len(columns) + 1, len(columns) + 2):
            raise ValueError('Unexpected income columns')
        if len(row) == len(columns) + 2 and (label not in ['Sales and other operating revenue', 'Income from equity affiliates'] or not re.fullmatch(r'\d+', row[1])):
            raise ValueError('Unreviewed note-reference column')
        for (kind, y), value in zip(columns, row[-len(columns):]):
            consolidated[kind, y, label] = money(value)
    for kind, y in columns:
        parts = sum(consolidated[kind, y, label] for label in ['Sales and other operating revenue', 'Income from equity affiliates', 'Other income'])
        if abs(parts - consolidated[kind, y, 'Total revenues and other income']) > 2_000_000:
            raise ValueError('Consolidated income reconciliation failed')
    facts = []; periods = set()
    for table in tables:
        rows = table['rows']
        if not any(r and r[0] == 'Segment revenues and other income' for r in rows):
            continue
        if rows[1] != ['(millions of dollars)', *GROUPS, 'Segment Total'] or rows[2] != ['U.S.', 'Non-U.S.'] * 4:
            raise ValueError('Wrong business groups, geography order or units')
        captions = [r[0] for r in rows[:6] if len(r) == 1 and re.fullmatch(r'(Three Months Ended|Six Months Ended|Nine Months Ended|Year ended) (March 31|June 30|September 30|December 31), 20\d\d', r[0])]
        if len(captions) != 1:
            raise ValueError('Missing unique segment fiscal caption')
        period, ending, y = re.fullmatch(r'(.+) (March 31|June 30|September 30|December 31), (20\d\d)', captions[0]).groups()
        y = int(y); m = MONTHS[ending]
        kind = {'Three Months Ended': 'Q', 'Six Months Ended': 'YTD6', 'Nine Months Ended': 'YTD9', 'Year ended': 'FY'}[period]
        if m != month or (kind, y) not in columns or (kind, y) in periods:
            raise ValueError('Segment period differs from consolidated headers or repeats')
        periods.add((kind, y))
        group_row = one(rows, 'Segment revenues and other income', 10)
        numbers = list(map(money, group_row[1:]))
        subtotal = money(one(rows, 'Segment revenues and other income', 2)[1])
        other = money(one(rows, 'Other revenues (2)', 2)[1])
        elimination = money(one(rows, 'Elimination of intersegment revenues', 2)[1])
        total = money(one(rows, 'Total consolidated revenues and other income', 2)[1])
        if numbers[-1] != subtotal or abs(sum(numbers[:8]) - subtotal) > 4_500_000 or abs(subtotal + other + elimination - total) > 2_000_000:
            raise ValueError('Segment income or elimination reconciliation failed')
        if total != consolidated[kind, y, 'Total revenues and other income']:
            raise ValueError('Segment reconciliation and consolidated statement disagree')
        start = f'{y}-{m - 2 if kind == "Q" else 1:02d}-01'; end = f'{y}-{m:02d}-{31 if m in (3,12) else 30}'
        base = {'kind': kind, 'year': y, 'month': m, 'startdate': start, 'enddate': end, 'unit': 'iso4217:USD', 'decimals': '-6',
            'source_url': url, 'source_cik': cik, 'source_report_date': report_date, 'accession': accession[:10] + '-' + accession[10:12] + '-' + accession[12:],
            'source_format': snapshot['format'], 'source_artifact_sha256': artifact_sha256, 'source_table_index': table['index']}
        def add(label, value, source_row, basis, error=500_000, **extra):
            fact = {**base, 'label': label, 'value': value, 'concept': 'sec-table:XOMRevenue',
                'dimensions': {'reported_category': label, 'basis': basis}, 'source_row_label': source_row, 'error_usd': error, **extra}
            facts.append(fact)
        for i, label in enumerate(GROUPS):
            add(label, sum(numbers[i*2:i*2+2]), 'Segment revenues and other income', 'segment_revenues_and_other_income', 1_000_000,
                reported_geography_cells=group_row[1+i*2:3+i*2], source_geographies=['U.S.', 'Non-U.S.'])
        add('Other revenues', other, 'Other revenues (2)', 'corporate_reconciliation_other_revenues')
        add('分部間收入', elimination, 'Elimination of intersegment revenues', 'consolidation_eliminations')
        for label, original in [('其他收入', 'Other income'), ('Income from equity affiliates', 'Income from equity affiliates')]:
            add(label, -consolidated[kind, y, original], original, 'deduct_consolidated_income_to_reconcile_sales',
                source_table_index=income['index'], source_value_usd=consolidated[kind, y, original], coefficient=-1)
        add('Total revenues and other income', total, 'Total consolidated revenues and other income', 'consolidated_all_income')
        add('Sales and other operating revenue', consolidated[kind, y, 'Sales and other operating revenue'], 'Sales and other operating revenue',
            'consolidated_sales', source_table_index=income['index'])
    if periods != set(columns):
        raise ValueError('Missing segment fiscal period')
    return facts


def parse_sales_page(text, artifact_sha256):
    """正常 web 工具 SEC 頁面文字；只解析有完整標題的 gross sales 列。"""
    source = re.match(r'source_url: (https://[^\n]+)\nsource_format: SEC_page_text_returned_by_web_tool\n', text)
    if not source or not sec_url(source[1]) or '/data/34088/' not in source[1]:
        raise ValueError('Unverified SEC page-text source')
    match = re.search(r'/xom-(20\d\d)(06|12)(30|31)\.htm$', source[1])
    if not match or (match[2], match[3]) not in [('06', '30'), ('12', '31')]:
        raise ValueError('Unreviewed supplemental period')
    expected_year = int(match[1]); month = int(match[2]); facts = []; current = None; geos = False; values = {}; line_numbers = {}
    def flush():
        if current is None:
            return
        if set(values) != {'Sales and other operating revenue', 'Intersegment revenue'}:
            raise ValueError('Missing gross-sales operand row')
        year = current
        for i, label in enumerate(GROUPS):
            parts = [values[row][i*2:i*2+2] for row in ['Sales and other operating revenue', 'Intersegment revenue']]
            facts.append({'label': label, 'kind': 'FY' if month == 12 else 'Q', 'year': year, 'month': month,
                'value': sum(sum(p) for p in parts), 'unit': 'iso4217:USD', 'decimals': '-6', 'error_usd': 2_000_000,
                'concept': 'sec-table:XOMRevenue', 'dimensions': {'reported_category': label, 'basis': 'segment_sales_plus_intersegment'},
                'startdate': f'{year}-{1 if month == 12 else 4:02d}-01', 'enddate': f'{year}-{month:02d}-{match[3]}',
                'source_url': source[1], 'source_cik': '34088', 'source_report_date': f'{expected_year}-{month:02d}-{match[3]}',
                'source_format': 'SEC_page_text_returned_by_web_tool', 'source_artifact_sha256': artifact_sha256,
                'source_line_numbers': dict(line_numbers),
                'accession': source[1].split('/')[-2][:10] + '-' + source[1].split('/')[-2][10:12] + '-' + source[1].split('/')[-2][12:],
                'source_row_labels': ['Sales and other operating revenue', 'Intersegment revenue'],
                'reported_US_nonUS_operand_values_usd': parts})
    for line in text.splitlines()[2:]:
        matched = re.fullmatch(r'L(\d+): (.*)', line)
        if not matched:
            continue
        cells = [s.strip() for s in matched[2].split('|') if s.strip()]
        if cells == ['(millions of dollars)', *GROUPS, 'Segment Total']:
            flush(); current = None; geos = False; values = {}; line_numbers = {}; continue
        if cells == ['U.S.', 'Non-U.S.'] * 4:
            geos = True; continue
        if cells and (cells[0].startswith('Year ended') or cells[0].startswith('Three Months Ended')):
            caption = re.fullmatch(r'(Year ended December 31|Three Months Ended June 30), (20\d\d)', cells[0])
            if not caption or not geos or ((month == 12) != caption[1].startswith('Year')) or int(caption[2]) not in (expected_year, expected_year - 1):
                raise ValueError('Supplemental fiscal or geographic header differs')
            current = int(caption[2]); continue
        if cells and cells[0] in ['Sales and other operating revenue', 'Intersegment revenue']:
            if current is None or len(cells) != 10 or cells[0] in values:
                raise ValueError('Ambiguous supplemental income operand')
            amounts = list(map(money, cells[1:]))
            if abs(sum(amounts[:8]) - amounts[-1]) > 4_500_000:
                raise ValueError('Supplemental geography sum does not reconcile')
            values[cells[0]] = amounts
            line_numbers[cells[0]] = int(matched[1])
    flush()
    if len(facts) != 8 or len({(f['year'], f['label']) for f in facts}) != 8:
        raise ValueError('Incomplete or duplicate supplemental years')
    return facts
