#!/usr/bin/env python3
"""從完整 HTML 表頭跨度擷取 Comcast 淨業務群；拒絕固定匯率表與 EBITDA。"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
LABELS = {'Connectivity and Platforms': 'Total Connectivity & Platforms revenue',
          'Content and Experiences': 'Total Content & Experiences revenue'}


def cells(row):
    result = []; start = 0
    for cell in row.xpath('./td|./th'):
        span = int(cell.get('colspan', '1'))
        text = ' '.join(' '.join(cell.itertext()).split())
        result.append((start, span, text)); start += span
    return result


def parse_groups(body, form, report_year):
    result = {}
    for table in html.fromstring(body).xpath('//table'):
        rows = [cells(r) for r in table.xpath('./tr|./tbody/tr')]
        head = ' '.join(text for row in rows[:6] for _, _, text in row).lower().replace(' ', '')
        if 'inmillions' not in head or 'asreported' in head or 'effectsofforeigncurrency' in head:
            continue
        if form == '10-Q' and not ('threemonthsended' in head and 'ninemonthsended' in head):
            continue
        if form == '10-K' and 'yearendeddecember31' not in head:
            continue
        headers = [r for r in rows[:6] if any(t == str(report_year) for _, _, t in r)
            and any(t == str(report_year - 1) for _, _, t in r)]
        if len(headers) != 1:
            continue
        for label, reported in LABELS.items():
            hits = [r for r in rows if r and r[0][2].lower() == reported.lower()]
            if len(hits) != 1:
                continue
            for year in [report_year, report_year - 1]:
                columns = [(c, span) for c, span, text in headers[0] if text == str(year)]
                kinds = ['Q', 'YTD9'] if form == '10-Q' else ['FY']
                if len(columns) != len(kinds):
                    raise ValueError('Unexpected business-group period columns')
                for kind, (start, span) in zip(kinds, columns):
                    values = [text for col, _, text in hits[0] if start <= col < start + span and re.fullmatch(r'-?\d[\d,]*', text)]
                    if len(values) != 1:
                        raise ValueError('Ambiguous business-group value')
                    key = (kind, year, label); value = int(values[0].replace(',', '')) * 1_000_000
                    if key in result and result[key] != value:
                        raise ValueError('Conflicting direct business-group tables')
                    result[key] = value
    if len(result) != (8 if form == '10-Q' else 4):
        raise ValueError('Incomplete business groups or periods')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--out', type=Path, required=True); args = p.parse_args()
    observations = []; sources = []
    for end, form in [('2025-09-30', '10-Q'), ('2025-12-31', '10-K')]:
        path = ROOT / 'research/shared-raw-semantics/sources' / ('CMCSA-' + end + '.html.gz')
        body = gzip.decompress(path.read_bytes()); source = {'path': str(path.relative_to(ROOT)), 'uncompressed_sha256': hashlib.sha256(body).hexdigest()}
        sources.append(source)
        for (kind, year, label), value in parse_groups(body, form, 2025).items():
            observations.append({'kind': kind, 'year': year, 'label': label, 'value_usd': value, 'source': source})
    q4 = []
    for year in [2024, 2025]:
        for label in LABELS:
            a = next(r for r in observations if (r['kind'], r['year'], r['label']) == ('FY', year, label))
            n = next(r for r in observations if (r['kind'], r['year'], r['label']) == ('YTD9', year, label))
            q4.append({'period_end': f'{year}-12-31', 'label': label, 'value_usd': a['value_usd'] - n['value_usd'],
                'derivation': 'annual_minus_nine_months', 'operands': [a, n]})
    report = {'observations': observations, 'derived_q4': q4, 'source_files': sources,
        'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'full_eight_quarters_verified': False,
        'remaining_blocker': '其餘原始 HTML 未取得；公司 IR 正常單次 GET 回 403，未重試或繞過。僅三個目標季度已可自動擷取／推算。'}
    with args.out.open('x') as f:json.dump(report, f, ensure_ascii=False, indent=2); f.write('\n')
    print('Parsed two raw filings; three target quarters; full eight-quarter status remains Fail')


if __name__ == '__main__':
    main()
