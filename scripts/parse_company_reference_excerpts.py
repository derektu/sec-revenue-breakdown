"""公司網站 PDF 文字只作參考；不產生主要 SEC 輸出。"""
import re
from compare_missing_ir_references import pdf_lines, numbers, one

LLY_URL = 'https://investor.lilly.com/static-files/4413f2f3-6625-42b5-851e-ae9201e3bb95'
XOM_URL = 'https://investor.exxonmobil.com/sec-filings/all-sec-filings/content/0002115436-26-000020/0002115436-26-000020.pdf'


def lly_reference(text):
    if LLY_URL not in text:
        raise ValueError('Wrong Lilly reference origin')
    body = pdf_lines(text)
    if ('Tables present dollars and shares in millions' not in body or
        'Three Months Ended September 30,\n2026 2025\nU.S. Outside U.S. Total U.S. Outside U.S. Total' not in body):
        raise ValueError('Lilly quarterly period, global columns or units not verified')
    labels = {'Cardiometabolic': 'Total cardiometabolic health', 'Oncology': 'Total oncology',
              'Immunology': 'Total immunology', 'Neuroscience': 'Neuroscience', 'Other': 'Other'}
    values = {}
    for label, reported in labels.items():
        row = numbers(one(body, '^' + re.escape(reported) + r' (\$?[\d(][^\n]*)$'), 6)
        if abs(row[0] + row[1] - row[2]) > 1_500_000:
            raise ValueError('Lilly geographic columns do not reconcile within reported precision')
        values[label] = row[2]
    total = numbers(one(body, r'^Revenue (.+)$'), 6)[2]
    if sum(values.values()) != total:
        raise ValueError('Lilly five reference classes do not equal global revenue')
    return values


def xom_reference(text):
    if XOM_URL not in text:
        raise ValueError('Wrong ExxonMobil reference origin')
    body = pdf_lines(text)
    if ('(millions of dollars, unless noted)' not in body or
        'Three Months Ended\nSeptember 30,\nNine Months Ended\nSeptember 30,\n2026 2025 2026 2025' not in body or
        'Upstream Energy Products Chemical Products Specialty Products Segment\nU.S. Non-U.S. U.S. Non-U.S. U.S. Non-U.S. U.S. Non-U.S. Total\nThree Months Ended September 30, 2026' not in body):
        raise ValueError('XOM segment period, geography order or income columns differ')
    income, segment = body.split('Our four reportable segments', 1)
    segment = 'Our four reportable segments' + segment
    table, reconciliation = segment.split('Reconciliation of consolidated revenues', 1)
    gross_parts = numbers(one(table, r'^Sales and other operating revenue (.+)$'), 9)
    internal = numbers(one(table, r'^Intersegment revenue (.+)$'), 9)
    all_parts = numbers(one(table, r'^Segment revenues and other income (.+)$'), 9)
    if numbers(one(reconciliation, r'^Segment revenues and other income (.+)$'), 1)[0] != all_parts[-1]:
        raise ValueError('XOM reconciliation subtotal differs from segment table')
    if any(abs(sum(row[:8]) - row[-1]) > 4_500_000 for row in [gross_parts, internal, all_parts]):
        raise ValueError('XOM geographic columns do not reconcile')
    labels = ['上游', '能源產品', '化工產品', '特種產品']
    all_income = {label: sum(all_parts[i*2:i*2+2]) for i, label in enumerate(labels)}
    gross = {label: sum(gross_parts[i*2:i*2+2]) + sum(internal[i*2:i*2+2]) for i, label in enumerate(labels)}
    other = numbers(one(segment, r'^Other revenues \(2\) (.+)$'), 1)[0]
    elimination = numbers(one(segment, r'^Elimination of intersegment revenues (.+)$'), 1)[0]
    total = numbers(one(segment, r'^Total consolidated revenues and other income (.+)$'), 1)[0]
    if all_parts[-1] + other + elimination != total or internal[-1] != -elimination:
        raise ValueError('XOM reported segment reconciliation differs')
    equity = numbers(one(income, r'^Income from equity affiliates (.+)$'), 4)[0]
    other_income = numbers(one(income, r'^Other income (.+)$'), 4)[0]
    # 表中的 3 是註腳編號，不是第五個財務期間。
    sales = numbers(one(income, r'^Sales and other operating revenue 3 (.+)$'), 4)[0]
    consolidated = numbers(one(income, r'^Total revenues and other income (.+)$'), 4)[0]
    all_income.update({'Other revenues': other, '分部間收入': elimination,
        '其他收入': -other_income, 'Income from equity affiliates': -equity})
    if sum(all_income.values()) != sales or consolidated != total or sales + equity + other_income != total:
        raise ValueError('XOM all-income reference does not reconcile to sales')
    all_income.update({'Total revenues and other income': total, 'Sales and other operating revenue': sales})
    gross['分部間收入'] = elimination
    return {'all_income': all_income, 'gross_sales': gross}
