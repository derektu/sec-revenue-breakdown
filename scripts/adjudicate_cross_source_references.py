#!/usr/bin/env python3
"""跨合法來源逐期裁決；參考只用於比較，主要輸出固定來自 SEC。"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from cohort_rule_audit import compare_value
from continue_parser_repairs import ACCEPTED
from continue_remaining_research import pgr_quarter
from enforce_sec_primary_source import selected_is_sec
from parse_progressive_reports import parse_pdf
from parse_company_reference_excerpts import lly_reference, xom_reference, LLY_URL, XOM_URL
from cohort_rule_catalog import catalog
from parse_progressive_reports import INCOME

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/reference-gap-completion-20261104/completion-status.json'
SEC = ROOT / 'research/remaining-sec-coverage-20261104/coverage.json'
PRIVATE = ROOT / 'data/vendor/local/cross-source-20261104'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required_categories(ticker, end):
    if ticker == 'PGR':
        return set(INCOME) | {'個人保險', '商業保險', '其他', 'Total underwriting revenue'}
    if ticker == 'XOM':
        labels = {'上游', '能源產品', '化工產品', '特種產品', '分部間收入'}
        if end not in ['2025-06-30', '2026-06-30']:
            labels |= {'Other revenues', '其他收入', 'Income from equity affiliates'}
        if end == '2026-09-30':
            labels |= {'Total revenues and other income', 'Sales and other operating revenue'}
        return labels
    if ticker == 'LLY':
        return {'Cardiometabolic', 'Oncology', 'Immunology', 'Neuroscience', 'Other'}
    return set(catalog()[ticker]['issuer_ir' if ticker == 'PLD' else 'futu'])


def verdict(rows, targets, required):
    active = [r for r in rows if r['status'] != 'reference_not_applicable_evidenced']
    failures = []
    if len(set(targets)) != 8 or {r['period_end'] for r in active} != set(targets):
        failures.append('eight_target_quarters_not_complete')
    if any(not selected_is_sec(r.get('selected', {})) for r in active):
        failures.append('SEC_output_missing')
    if any(r['status'] not in ACCEPTED or (r['status'] != 'exact_scope_candidate_match' and not r.get('explanation')) for r in active):
        failures.append('unresolved_comparison_or_scope')
    if any(not r.get('period_reviewed') or not r.get('semantic_review') for r in active):
        failures.append('period_or_category_not_reviewed')
    if len({(r['period_end'], r['category']) for r in active}) != len(active):
        failures.append('duplicate_category_comparison')
    if set(required) != set(targets) or any({r['category'] for r in active if r['period_end'] == end} != set(required[end]) for end in targets):
        failures.append('required_category_coverage_incomplete')
    return {'status': 'Fail' if failures else 'OK', 'fail_reasons': failures,
        'target_periods': targets, 'reference_periods': sorted({r['period_end'] for r in active}),
        'quarterly_cells': len(active), 'cell_statuses': dict(Counter(r['status'] for r in active))}


def load_pgr_references():
    folder = ROOT / 'data/vendor/local/remaining-followup-20261104'
    accesses = {r['file']: r for r in temporal.load(folder / 'pgr-quarterly-access.json')}
    accesses['pgr-2025-q3.pdf'] = temporal.load(folder / 'pgr-2025-q3-access.json')
    reports = {}
    for name, year, month in [('pgr-2025-10k.pdf', 2025, None), ('pgr-2025-q3.pdf', 2025, 9),
                            ('pgr-2026-q1.pdf', 2026, 3), ('pgr-2026-q2.pdf', 2026, 6), ('pgr-2026-q3.pdf', 2026, 9)]:
        report = parse_pdf(folder / name, year, month)
        if report['sha256'] != accesses[name]['sha256'] or accesses[name]['status'] != 200:
            raise ValueError('PGR saved reference PDF differs from download receipt')
        report.update(source_url=accesses[name]['url']); reports[name] = report
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--references', type=Path, default=PRIVATE)
    parser.add_argument('--out', type=Path, required=True);args = parser.parse_args()
    args.references = args.references.resolve()
    base = temporal.load(BASE); coverage = temporal.load(SEC); sec = {c['ticker']: c for c in coverage['companies']}
    new = {}; reports = load_pgr_references()
    lly_files = [args.references / n for n in ['LLY-unit.txt', 'LLY-2026Q3.txt']]
    xom_files = [args.references / n for n in ['XOM-consolidated.txt', 'XOM-2026Q3.txt']]
    new['LLY'] = lly_reference('\n'.join(p.read_text() for p in lly_files))
    new['XOM'] = xom_reference('\n'.join(p.read_text() for p in xom_files))
    cloud_path = ROOT / 'research/missing-ir-reference-20261104/summary.json'; cloud = temporal.load(cloud_path)
    local = args.references / args.out.name; local.mkdir(parents=True, exist_ok=False)
    args.out.mkdir(parents=True, exist_ok=False); companies = []; diagnostics = []
    for company in base['companies']:
        ticker = company['ticker']
        if company['status'] == 'OK' or ticker == 'CVX':
            companies.append({**company, 'cross_source_changed': False}); continue
        prior_path = ROOT / company['local_detail_path']
        if sha(prior_path) != company['local_detail_sha256']:
            raise ValueError('Prior comparison artifact changed')
        prior = temporal.load(prior_path); rows = []
        primary = {q['period_end']: q['outputs'] for q in sec[ticker]['quarters']}
        # 只讀參考原值來比較；主要選值由 SEC coverage 或先前 SEC-only 選取產生。
        if ticker != 'PGR':
            for r in prior:
                if r.get('sec_period_end') not in company['target_periods']:
                    continue
                rows.append({**r, 'period_end': r['sec_period_end'], 'semantic_review': '沿用已裁決 SEC-only 規則與來源口徑：' + r['role'],
                    'reference_sources': [r['source']], 'reference_independent_of_issuer_filing': None if r['source'] != 'issuer_ir' else False})
        def add(end, label, reference, selected, url, artifacts, semantic):
            if not selected_is_sec(selected):
                raise ValueError('Reference cannot supply the primary numeric output')
            rows.append({'period_end': end, 'category': label, 'reference_usd': reference,
                'reference_source_url': url, 'reference_artifacts': artifacts, 'period_reviewed': True,
                'semantic_review': semantic, 'reference_independent_of_issuer_filing': False,
                'reference_sources': ['issuer_report_copy'], **compare_value(reference, 1, selected)})
        if ticker == 'LLY':
            artifacts = [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for p in lly_files]
            for label, value in new['LLY'].items():
                add('2026-09-30', label, value, primary['2026-09-30'][label], LLY_URL, artifacts,
                    '全球總計欄；含 net product 及 collaboration／other，五治療類別合計等於收入；不是單一藥品。')
        elif ticker == 'BRK-B':
            for row in cloud['comparisons']:
                if row['ticker'] != ticker:
                    continue
                chosen = primary[row['period_end']][row['category']]
                if row['status'] != 'exact_match' or chosen['value'] != row['selected']['value']:
                    raise ValueError('Shared BRK reference evidence and local SEC extraction disagree')
                # 雲端已實際解析參考及比對；本機不假稱持有未同步的 PDF 摘錄。
                rows.append({'period_end': row['period_end'], 'category': row['category'], 'selected': chosen,
                    'status': 'exact_scope_candidate_match', 'period_reviewed': True,
                    'semantic_review': '八分類含保險投資收入與公司抵銷；同表加總由雲端 PR #25 核對。',
                    'reference_source_url': row['reference_source_url'], 'reference_artifacts': [{'path': row['reference_artifact'], 'sha256': row['reference_sha256']}],
                    'inherited_cloud_comparison_sha256': sha(cloud_path), 'local_reference_reparsed': False,
                    'reference_sources': ['issuer_report_copy'], 'reference_independent_of_issuer_filing': False})
        elif ticker == 'PGR':
            for end in company['target_periods']:
                year, month, _ = map(int, end.split('-')); ref = pgr_quarter(reports, year, month)
                artifacts = ([ref['annual_evidence'], ref['nine_month_evidence']] if month == 12 else [ref])
                evidence = [{'path': str(Path(r['source_file']).relative_to(ROOT)), 'sha256': r['source_sha256'], 'source_url': r['source_url']} for r in artifacts]
                for label, value in ref['values_usd'].items():
                    add(end, label, value, primary[end][label], [r['source_url'] for r in artifacts], evidence,
                        '合併收入與承保收入分開；Property 納 Personal Lines、含 fees；Q4 同版 FY 減九個月，總額與組成不重複加總。')
            diagnostics.append({'ticker': ticker, 'prior_futu_detail_sha256': sha(prior_path),
                'prior_futu_status_counts': dict(Counter(r['status'] for r in prior)),
                'decision': '採八季一致的公司 PDF 十二列作主要參考；保留富途 Q4 六項差異證據，不改原供應商成績。'})
        elif ticker == 'XOM':
            artifacts = [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for p in xom_files]
            for label, value in new['XOM']['all_income'].items():
                add('2026-09-30', label, value, primary['2026-09-30'][label], XOM_URL, artifacts,
                    '原表 all-income 分部與合併投資／其他收益扣回；地區與合併收入對帳，非 earnings 或 gross sales。')
            gross = next(q for q in sec[ticker]['quarters'] if q['period_end'] == '2026-09-30')['alternative_definitions']['gross_sales_and_intersegment']
            diagnostics.append({'ticker': ticker, 'gross_sales_reference_comparisons': {label: compare_value(value, 1, gross[label])['status'] for label, value in new['XOM']['gross_sales'].items()},
                'decision': '公司副本同時支持兩口徑；最新主要系列採可完整對帳的 all-income，gross 五欄另列，不以數字命中決定語意。'})
        elif ticker == 'PLD':
            # 原三類加總及總額的 IR 八季已取得；只重比對既有原值，不重抓。
            for row in rows:
                label = row['category']; chosen = primary[row['period_end']][label]
                result = compare_value(row['raw'], row['scale'], chosen)
                row.update(result, semantic_review='三個合併收入列與 Total revenues；非營運地區分部，總額不可重複相加。',
                    reference_independent_of_issuer_filing=False)
        required = {end: sorted(required_categories(ticker, end)) for end in company['target_periods']}
        result = verdict(rows, company['target_periods'], required)
        path = local / f'{ticker}-cross-source.json';temporal.save(path, json.loads(json.dumps(rows, default=str)))
        companies.append({'ticker': ticker, **result, 'cross_source_changed': True,
            'reference': 'cross_source_adjudication', 'reference_sources': sorted({s for r in rows for s in r['reference_sources']}),
            'local_detail_path': str(path.relative_to(ROOT)), 'local_detail_sha256': sha(path),
            'required_categories_by_period': required,
            'common_issuer_upstream_disclosed': True, 'independent_human_second_review': False})
    diagnostics.append({'ticker':'CVX', 'missing_periods':['2025-09-30','2025-12-31'], 'attempts':[
        {'url':'https://www.chevron.com/newsroom/2025/q4/chevron-reports-3q-2025-results','status':'HTTP_403_stopped'},
        {'url':'https://www.businesswire.com/news/home/20251031139973/en/Chevron-Reports-Third-Quarter-2025-Results','status':'readable_segment_earnings_not_requested_segment_revenue'},
        {'url':'https://www.businesswire.com/news/home/20260130488543/en/Chevron-Reports-Fourth-Quarter-2025-Results','status':'fetch_timeout_no_reference_extracted'},
        {'url':'https://www.annualreports.com/Company/chevron-corporation','status':'annual_report_index_read_no_quarterly_segment_reference_obtained'},
        {'url':'https://www.chevron.com/-/media/chevron/stories/documents/3Q-2025-earnings-press-release.pdf','status':'normal_Edge_read_10_pages_segment_earnings_capex_production_not_segment_revenue'}],
        'decision':'已確認現有六季，缺兩季收入範圍參考；不以 earnings 或合併收入代替四分類。'})
    result = {'criterion': '合法跨來源逐期裁決，八個目標季度具 SEC 輸出及已確認語意與期間的參考；差異具證據，缺漏不算完成。',
        'ok_count': sum(c['status'] == 'OK' for c in companies), 'total':30, 'companies':companies,
        'historical_fixed_vendor_ok_count':base['ok_count'], 'historical_fixed_vendor_receipt_sha256':sha(BASE),
        'SEC_coverage_receipt_sha256':sha(SEC), 'source_reference_values_published':False,
        'diagnostics':diagnostics, 'blind_tests':0, 'all_periods_seen_during_development':True, 'not_independent_vendor_accuracy':True,
        'manual_minutes_measured':False, 'operator_actions_requested':0,
        'code_sha256':{p:sha(ROOT/p) for p in ['scripts/adjudicate_cross_source_references.py','scripts/parse_company_reference_excerpts.py','scripts/parse_progressive_reports.py']}}
    temporal.save(args.out / 'completion-status.json',result)
    print(json.dumps({'cross_source_OK':result['ok_count'],'fixed_vendor_OK':base['ok_count'],
        'updated':[{'ticker':c['ticker'],'status':c['status'],'counts':c.get('cell_statuses'),'fail_reasons':c.get('fail_reasons')} for c in companies if c.get('cross_source_changed')]},ensure_ascii=False))


if __name__ == '__main__':
    main()
