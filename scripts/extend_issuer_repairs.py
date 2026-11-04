#!/usr/bin/env python3
"""接續已完成五家，重播其餘公司可核實的期間、scope 與計算修復。"""
import argparse
from collections import Counter
import copy
import datetime as dt
from decimal import Decimal
from pathlib import Path
import json
import subprocess
import sys

import temporal_eval as temporal
from cohort_rule_audit import resolve, compare_value
from cohort_rule_catalog import catalog, R, S, C, P, OP, leaf, rule
from compare_vendor_cohort import ROOT, PRIVATE, amount
from continue_parser_repairs import digest, mark_inactive, ACCEPTED
from evaluate_eight_quarter_status import assess, CHOSEN
from remaining_issuer_rules import normalize_record, PRODUCTS, KO_MEMBERS, retail_label, coke_label, reported_error, EVIDENCE
from review_scope_gaps import latest_training_comparative
from company_revision_rules import bac_revised_q4, parse_unh_release, parse_ups_latest

TARGETS = {'HD', 'COST', 'KO', 'LLY', 'WMT', 'BAC', 'UNH', 'XOM', 'UPS', 'CAT', 'MCD'}
WMT_EVIDENCE = 'https://www.sec.gov/Archives/edgar/data/104169/000010416926000102/wmt-20260430.htm'


def pools_for(ticker, data):
    records = [normalize_record(ticker, r) for r in sorted(data['raw_filings'], key=lambda r: r['filing']['filingDate'])]
    engine = temporal.runner()
    pools = {r['filing']['reportDate']: engine.quarter(r['facts'], r['filing']['reportDate'], r['filing']['form'],
        [f for old in records[:index] for f in old['facts']]) for index, r in enumerate(records)}
    if ticker == 'BAC':
        pools['2025-12-31'] = bac_revised_q4(data, engine)
    if ticker == 'UPS':
        annual = next(r for r in records if r['filing']['reportDate'] == '2024-12-31')
        comparative = next(r for r in records if r['filing']['reportDate'] == '2025-09-30')
        pools['2024-12-31'] = engine.quarter(annual['facts'], '2024-12-31', '10-K', [f for f in comparative['facts']
            if f.get('startdate') == '2024-01-01' and f.get('enddate') == '2024-09-30'])
    return records, pools


def selection(ticker, label, facts, conflicts):
    spec = catalog()[ticker].get('stockanalysis', {}).get(label)
    if ticker == 'KO':
        spec = rule(leaf('us-gaap:Revenues', {S: KO_MEMBERS[label], C: OP})) if label in KO_MEMBERS else (
            rule(leaf('us-gaap:Revenues', {C: 'us-gaap:CorporateNonSegmentMember'})) if label == 'Corporate' else
            rule(leaf('us-gaap:Revenues', {C: 'srt:ConsolidationEliminationsMember'})) if label == 'Eliminations' else None)
    if ticker == 'LLY':
        spec = rule(leaf('us-gaap:Revenues', {P: PRODUCTS[label]})) if label in PRODUCTS else None
    if ticker == 'MCD':
        spec = catalog()['MCD']['futu'].get(label)
    if ticker == 'CAT' and label == 'Energy and Transportation':
        spec = rule(leaf('us-gaap:Revenues', {S: 'cat:PowerEnergyMember', C: OP}))
    if ticker == 'WMT':
        if label != '企業和支持':
            spec = catalog()['WMT']['futu'].get(label)
        else:
            spec = rule([leaf('us-gaap:Revenues', {}), *[leaf('us-gaap:Revenues', {S: 'wmt:' + member, C: OP}, -1)
                for member in ['WalmartUSMember', 'WalmartInternationalMember', 'SamsClubUSMember']]],
                role='named_corporate_membership_and_other_income_residual')
    if ticker == 'XOM':
        member = {'上游': 'UpstreamMember', '能源產品': 'EnergyProductsMember', '化工產品': 'ChemicalProductsMember', '特種產品': 'SpecialtyProductsMember'}.get(label)
        if member:
            spec = rule([*[leaf('us-gaap:Revenues', {S: 'xom:' + member, 'srt:StatementGeographicalAxis': geo,
                    P: 'xom:SalesAndOtherOperatingRevenueMember'}) for geo in ['country:US', 'us-gaap:NonUsMember']],
                *[leaf('us-gaap:Revenues', {S: 'xom:' + member, 'srt:StatementGeographicalAxis': geo,
                    C: 'us-gaap:IntersegmentEliminationMember'}, -1) for geo in ['country:US', 'us-gaap:NonUsMember']]], role='segment_gross_sales_before_eliminations')
        elif label == '分部間收入':
            spec = rule(leaf('us-gaap:Revenues', {C: 'us-gaap:IntersegmentEliminationMember'}))
    selected = resolve(spec, facts, conflicts)
    if selected['status'] == 'observed':
        errors = [reported_error(f) for f in selected['facts']]
        selected['error'] = None if None in errors else sum(errors, Decimal(0))
    if ticker == 'WMT' and label == '企業和支持':
        selected.update(role='named_corporate_membership_and_other_income_residual',
            definition_evidence=WMT_EVIDENCE, derived_not_directly_reported=True,
            basis='合併 Revenues 減三營運部門 Revenues 的公司層級會員及其他收入；七個歷史直接／Q4 公司列另行佐證此定義。')
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT / 'scripts/continue_parser_repairs.py'), '--out', str(args.out)], check=True)
    base = temporal.load(args.out / 'completion-status.json')
    local = PRIVATE / 'cohort-adjudication-20261104' / args.out.name
    source_folder = PRIVATE / 'remaining-repairs-20261104'
    unh = {end: parse_unh_release(source_folder / filename, end) for end, filename in
        [('2026-06-30', 'unh-2026-q2.pdf'), ('2026-09-30', 'unh-2026-q3.pdf')]}
    temporal.save(args.out / 'unh-gaap-adjusted-quarter-tables.json', unh)
    ups = parse_ups_latest(source_folder / 'ups-q3-2026.pdf')
    temporal.save(args.out / 'ups-latest-quarter.json', {'period_end': '2026-09-30', 'values_usd': ups,
        'source_url': 'https://investors.ups.com/_assets/_82dd7397931c18431557facb5a665332/ups/news/2026-10-27_UPS_Releases_3Q_2026_2172.pdf',
        'raw_pdf_sha256': digest(source_folder / 'ups-q3-2026.pdf')})
    companies = []
    for company in base['companies']:
        ticker = company['ticker']; rows = temporal.load(local / (ticker + '-repaired.json'))
        receipt = temporal.load(args.out / (ticker + '-freeze.json'))
        data = temporal.checked_data(receipt['plan'], ROOT / receipt['plan']['baseline_file'])
        if ticker in TARGETS:
            records, pools = pools_for(ticker, data)
            training = temporal.training_pack(receipt['plan'], data)['raw_filings']
            latest = receipt['plan']['holdout'][0]['period_end']
            for row in rows:
                if row['kind'] != 'Q':
                    continue
                old = copy.deepcopy(row); date = row['sec_period_end']
                if ticker in ('HD', 'COST'):
                    dates = [d for d in pools if retail_label(ticker, row['display_date'], d)]
                    date = dates[0] if len(dates) == 1 else None
                    row.update(sec_period_end=date, period_reviewed=bool(date), alignment='reviewed_retail_fiscal_label' if date else 'unresolved_retail_period')
                if ticker == 'KO' and date and coke_label(row['display_date'], date):
                    row.update(period_reviewed=True, alignment='reviewed_friday_calendar_quarter_label')
                if ticker == 'LLY':
                    date = dt.datetime.strptime(row['display_date'], '%b %d, %Y').date().isoformat()
                    row.update(sec_period_end=date, period_reviewed=date in pools, alignment='exact_date',
                        latest_exposure='seen_in_this_retrospective_repair', phase='latest_retrospective' if date == latest else 'historical')
                if ticker == 'UPS' and row['display_date'] == 'Sep 30, 2026':
                    date = '2026-09-30'
                    row.update(sec_period_end=date, period_reviewed=True, alignment='direct_company_release_quarter', phase='latest_retrospective')
                facts, conflicts = pools.get(date, ([], []))
                if ticker == 'WMT' and date != latest:
                    comparative = latest_training_comparative(training, date)
                    if comparative:
                        facts, conflicts = comparative['facts'], comparative['conflicts']
                selected = selection(ticker, row['category'], facts, conflicts)
                if ticker == 'UPS' and date == '2026-09-30':
                    selected = {'status': 'observed', 'value': ups[row['category']], 'error': Decimal(500_000),
                        'role': 'direct_company_release_pdf_parsed', 'source_period': date}
                if ticker == 'UNH' and date in unh and row['category'] in unh[date]['gaap']:
                    selected = {'status': 'observed', 'value': unh[date]['gaap'][row['category']],
                        'error': Decimal(1_500_000 if row['category'] == 'Eliminations' else 500_000),
                        'role': 'company_direct_gaap_revenue_parsed', 'official_quarter_table': unh[date]}
                row.update(compare_value(row['raw'], row['scale'], selected))
                row.update(role=selected.get('role', 'scope_candidate'), prior_result=old)
                if date is None and row['raw'] is not None:
                    row.update(status='period_unaligned_or_not_evaluated')
                if ticker == 'UNH' and date in unh and row['raw'] is not None and row['status'] != 'exact_scope_candidate_match':
                    value, _ = amount(row['raw'], row['scale']); table = unh[date]
                    if row['category'] == 'Optum' and value == table['adjusted']['Optum']:
                        row.update(status='explained_reference_error', explanation={'kind': 'adjusted_revenue_in_reference_gaap_breakdown',
                            'primary_table': table, 'basis': '來源採 adjusted Optum，本輸出固定 GAAP；公司同表支持兩者差額，不混為同口徑。'})
                    elif (row['category'] == 'Eliminations' and value == table['gaap']['Consolidated']
                          - table['gaap']['UnitedHealthcare'] - table['adjusted']['Optum']):
                        row.update(status='explained_reference_error', explanation={'kind': 'mixed_gaap_adjusted_residual',
                            'primary_table': table, 'basis': '來源抵銷數可重現為 GAAP 總收入減 UHC 與 adjusted Optum；公司註腳支持真正 GAAP 抵銷。此算式不聲稱已知 vendor 內部實作。'})
                if ticker == 'LLY' and row['status'] == 'within_scope_candidate_precision' and selected['error'] is not None:
                    value, tolerance = amount(row['raw'], row['scale'])
                    if abs(value - selected['value']) <= tolerance + selected['error']:
                        row.update(status='explained_reported_precision', explanation={'kind': 'annual_geographical_aggregation_precision',
                            'source_url': EVIDENCE['LLY'], 'basis': '年度美國與非美國各自四捨五入，Q4 再減直接全球九個月；保留所有運算元及精度，沒有以參考值調整規則。'})
            for end in sorted({r['sec_period_end'] for r in rows if r['sec_period_end']}):
                group = [r for r in rows if r['sec_period_end'] == end and r['source'] == 'stockanalysis' and r['kind'] == 'Q']
                if ticker == 'KO':
                    active = ['North America', 'Europe, Middle East, and Africa', 'Latin America', 'Asia Pacific', 'Bottling Investments', 'Corporate', 'Eliminations']
                    if end == '2024-12-31': active += ['Global Ventures']
                    mark_inactive(group, active, EVIDENCE['KO'], '按 SEC 第三方＋分部間收入的總額及抵銷；Global Ventures 後續不再單列。')
                if ticker == 'LLY':
                    mark_inactive(group, list(PRODUCTS), EVIDENCE['LLY'], '公司本期五項收入分類齊備；Animal Health／Cardiovascular 是舊版空欄，保留 N/A。')
                if ticker == 'CAT':
                    active = ['Construction', 'Resource', 'Financial Products', 'Other', 'Eliminations',
                              'Power & Energy' if end >= '2026-03-31' else 'Energy and Transportation']
                    mark_inactive(group, active, EVIDENCE['CAT'], '保留當期分部名稱與公司對帳列；另一版本分部欄位不重複計入。')
        output = local / (ticker + '-extended.json')
        temporal.save(output, json.loads(json.dumps(rows, default=str)))
        eligible = [copy.deepcopy(r) for r in rows if r['status'] != 'reference_not_applicable_evidenced']
        for r in eligible:
            if r['status'] in ACCEPTED - {'exact_scope_candidate_match'} and r.get('explanation'):
                r['status'] = 'exact_scope_candidate_match'
        targets = [q['report_date'] for q in data['quarter_results']]
        if ticker == 'UPS':
            targets = sorted(targets + ['2026-09-30'])[-8:]
        verdict = assess(eligible, targets, CHOSEN.get(ticker, 'stockanalysis'))
        verdict['cell_statuses'] = dict(Counter(r['status'] for r in rows if r['source'] == verdict['reference'] and r['kind'] == 'Q'))
        companies.append({'ticker': ticker, **verdict, 'local_detail_path': str(output.relative_to(ROOT)), 'local_detail_sha256': digest(output)})
    result = {'ok_count': sum(c['status'] == 'OK' for c in companies), 'total': len(companies), 'companies': companies,
        'blind_tests': 0, 'LLY_latest_exposure': '已接觸 SEC 最新季 facts；SA 最新已保存參考只到 2026-06-30，沒有宣稱 2026-09-30 通過或未見測試。',
        'code_sha256': {p: digest(ROOT / p) for p in ['scripts/extend_issuer_repairs.py', 'scripts/remaining_issuer_rules.py',
            'scripts/continue_parser_repairs.py', 'scripts/resolve_parser_failures.py', 'scripts/cohort_rule_audit.py']},
        'revision_code_sha256': digest(ROOT / 'scripts/company_revision_rules.py'),
        'additional_evidence_sha256': {str(p.relative_to(ROOT)): digest(p) for p in [source_folder / 'unh-2026-q2.pdf',
            source_folder / 'unh-2026-q3.pdf', source_folder / 'ups-q3-2026.pdf', source_folder / 'source-gap-recheck.json', source_folder / 'xom-legacy-access.json']},
        'UPS_target_update': '依公司直接 Q3 發行稿補入 2026-09-30，移除最舊 2024-09-30，保留固定 SA 的最近八季；新季度來源另存，不冒稱來自舊基準。',
        'prior_stage_status': 'completion-status.json', 'base_freeze_note': base['base_receipts_note']}
    temporal.save(args.out / 'extended-completion-status.json', result)
    print(f"Extended: {result['ok_count']} / {result['total']}")


if __name__ == '__main__':
    main()
