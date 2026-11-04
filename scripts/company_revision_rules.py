"""公司原表的會計版本與 GAAP／調整後收入差異；不以參考金額選版本。"""
import re
import subprocess


def bac_revised_q4(data, engine):
    annual = next(r for r in data['raw_filings'] if r['filing']['reportDate'] == '2025-12-31')
    # FY2025 已追溯改變會計方法；以新方法下的 2025 YTD9 比較欄相減。
    later = [r for r in data['raw_filings'] if r['filing']['reportDate'] > '2025-12-31'
        and any(f.get('startdate') == '2025-01-01' and f.get('enddate') == '2025-09-30' for f in r['facts'])]
    if not later:
        return [], []
    source = min(later, key=lambda r: r['filing']['filingDate'])
    previous = [f for f in source['facts'] if f.get('startdate') == '2025-01-01' and f.get('enddate') == '2025-09-30']
    facts, conflicts = engine.quarter(annual['facts'], '2025-12-31', '10-K', previous)
    for fact in facts:
        fact.update(revision_rule_id='bac-fy2025-retrospective-tax-equity-accounting',
            revision_basis='FY2025 Note 1 的追溯會計方法變更；以變更後申報的同年九個月比較欄相減。',
            comparative_filing_date=source['filing']['filingDate'], retrospective_later_comparative=True)
    return facts, conflicts


def parse_unh_release(pdf, period):
    months = {'2026-06-30': 'June 30, 2026', '2026-09-30': 'September 30, 2026'}
    if period not in months:
        raise ValueError('Unreviewed UNH period')
    text = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], check=True, capture_output=True, text=True).stdout
    page = next((p for p in text.split('\f') if 'REVENUES BY BUSINESS - SUPPLEMENTAL FINANCIAL INFORMATION' in p), None)
    if page is None or '(in millions; unaudited)' not in page:
        raise ValueError('Missing business revenue table')
    start = page.index('Three Months Ended ' + months[period])
    block = page[start:page.index('Three Months Ended ', start + 20)]
    def values(label):
        lines = [line for line in block.splitlines() if line.strip().startswith(label)]
        if len(lines) != 1:
            raise ValueError('Ambiguous UNH row')
        nums = re.findall(r'\$?([\d,]+)', lines[0][lines[0].index('...'):])
        if len(nums) != 6:
            raise ValueError('Unexpected UNH columns')
        return [int(n.replace(',', '')) * 1_000_000 for n in nums]
    gaap, adjusted = values('Total revenues'), values('Adjusted revenues')
    corporate = gaap[5] - gaap[0] - gaap[4]
    note = re.search(r'corporate eliminations of \$([\d,]+)', page)
    if not note or abs(corporate) != int(note[1].replace(',', '')) * 1_000_000:
        raise ValueError('Corporate elimination footnote differs')
    return {'period_end': period, 'gaap': {'UnitedHealthcare': gaap[0], 'Optum': gaap[4], 'Eliminations': corporate,
        'Consolidated': gaap[5]}, 'adjusted': {'UnitedHealthcare': adjusted[0], 'Optum': adjusted[4], 'Consolidated': adjusted[5]},
        'basis': '官方同季同表直接區分 GAAP 與 adjusted；抵銷以公司註腳核對。'}


def parse_ups_latest(pdf):
    text = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], check=True, capture_output=True, text=True).stdout
    if 'UPS Releases 3Q 2026 Earnings' not in text:
        raise ValueError('Unreviewed UPS quarter')
    result = {}
    sections = [('Domestic Package', 'U.S. Domestic Segment'), ('International Package', 'International Segment'),
                ('Supply Chain and Freight', 'Supply Chain Solutions1')]
    for index, (label, title) in enumerate(sections):
        start = text.index(title)
        end = text.index(sections[index + 1][1], start) if index + 1 < len(sections) else len(text)
        block = text[start:end]
        row = re.search(r'^\s*Revenue\s+\$([\d,]+)\s+M', block, re.M)
        if not row or not re.search(r'3Q 2026\s+3Q 2025', block[:row.start()]):
            raise ValueError('Missing UPS quarter revenue')
        result[label] = int(row[1].replace(',', '')) * 1_000_000
    return result
