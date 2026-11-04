#!/usr/bin/env python3
"""直接解析 PGR SEC 原始 HTML，沿用已審閱的收入／分部及期間檢查。"""
import hashlib
import re

from lxml import html

from parse_progressive_sec import parse_snapshot


def parse_html(raw, source_url):
    # 此函式不連網；HTML 只是資料，不執行 script 或讀取外部資源。
    document = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
    tables = []
    for index, table in enumerate(document.xpath('//table')):
        text = table.text_content()
        income = all(label in text for label in ['Investment income', 'Net premiums earned', 'Service revenues'])
        segment = all(label in text for label in ['Personal Lines', 'Commercial Lines', 'Total underwriting revenue'])
        if not (income or segment):
            continue
        rows = []
        for row in table.xpath('.//tr'):
            cells = [re.sub(r'\s+', ' ', cell.text_content()).strip() for cell in row.xpath('./td|./th')]
            if cells and (cells[0] == 'Expenses' or cells[0].startswith('Losses and loss adjustment expenses')):
                break
            cells = [cell for cell in cells if cell and cell != '$']
            if cells:
                rows.append(cells)
        tables.append({'index': index, 'rows': rows})
    # 中間表格格式與既有 DOM collector 一致；來源雜湊始終指向原始 HTML bytes。
    observations = parse_snapshot({'format': 'SEC_DOM_nonempty_cell_text',
        'source_url': source_url, 'tables': tables}, hashlib.sha256(raw).hexdigest())
    for fact in observations:
        fact['source_format'] = 'SEC_raw_HTML_bytes'
    return observations
