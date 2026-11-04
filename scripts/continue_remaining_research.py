#!/usr/bin/env python3
"""以原始收入表及同年度對帳繼續剩餘公司；保留每項來源裁決。"""
import argparse
from collections import Counter
import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from compare_vendor_cohort import amount
from cohort_rule_audit import compare_value
from continue_parser_repairs import ACCEPTED
from evaluate_eight_quarter_status import assess
from extend_issuer_repairs import pools_for, selection
from parse_progressive_reports import parse_pdf

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/completed-parser-repairs-20261104'
PRIVATE = ROOT / 'data/vendor/local/remaining-followup-20261104'
PGR_LABELS = {'投資收益': 'Investment income', 'Service revenues': 'Service revenues',
    'Net holding period gains (losses) on securities': 'Net holding period gains (losses) on securities',
    'Net realized gains (losses) on security sales': 'Net realized gains (losses) on security sales',
    'Net realized gains (losses) on securities': 'Total net realized gains (losses) on securities'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hd_proof(data, ui):
    if ui.get('mode') != 'Quarterly':
        raise ValueError('HD reference must be quarterly')
    records, pools = pools_for('HD', data)
    def values(end, start=None):
        if start:
            record = next(r for r in records if r['filing']['reportDate'] == end)
            facts = [f for f in record['facts'] if f.get('startdate') == start and f.get('enddate') == end]
            conflicts = []
        else:
            facts, conflicts = pools[end]
        result = {}
        for label in ui['columns']:
            chosen = selection('HD', label, facts, conflicts)
            if chosen['status'] != 'observed':
                raise ValueError('Missing HD exact scope')
            result[label] = chosen
        return result
    half = values('2024-07-28', '2024-01-29')
    nine = values('2024-10-27', '2024-01-29')
    annual = values('2025-02-02', '2024-01-29')
    q3 = values('2024-10-27'); q4 = values('2025-02-02')
    points = ui['points_usd']; result = {}
    for index, label in enumerate(ui['columns']):
        h, n, a, third, fourth = [r[label]['value'] for r in [half, nine, annual, q3, q4]]
        prior_reference = points['2024-03-31'][index] + points['2024-06-30'][index]
        if (h + third != n or n + fourth != a or points['2024-09-30'][index] != third
                or sum(points[d][index] for d in points) != a):
            raise ValueError('HD annual and quarter identity not confirmed')
        if points['2024-12-31'][index] - fourth != h - prior_reference:
            raise ValueError('HD difference not explained by first-half discrepancy')
        result[label] = {'half': half[label], 'nine': nine[label], 'annual': annual[label],
                         'q3': q3[label], 'q4': q4[label],
                         'prior_half_reference_difference_usd': prior_reference - h}
    return result


def apply_hd(rows, data, ui):
    proof = hd_proof(data, ui)
    for row in rows:
        label = row['category']
        if (row['source'], row['kind'], row['sec_period_end'], label) not in [
                ('stockanalysis', 'Q', '2025-02-02', l) for l in ['Hardlines', 'Other']]:
            continue
        ref, _ = amount(row['raw'], row['scale']); p = proof[label]
        if ref != ui['points_usd']['2024-12-31'][ui['columns'].index(label)] or p['prior_half_reference_difference_usd'] == 0:
            continue
        # 採同年度原申報分類；不把後來重分類的產品列與原九個月混減。
        if row['selected']['value'] != p['q4']['value']:
            raise ValueError('HD selected result changed unexpectedly')
        row.update(status='explained_reference_error', explanation={
            'kind': 'reference_historical_subtotals_inconsistent_with_same_year_company_rows',
            'primary_operands': p, 'ui_evidence_sha256': digest(PRIVATE / 'hd-quarterly-ui.json'),
            'basis': '公司同年度 H1＋Q3＝YTD9、FY−YTD9＝Q4 均成立；參考 Q1＋Q2 與公司 H1 分類不同，Q4 差額恰為其反向。採公司原申報同口徑，保留差額，不宣稱知道 vendor 內部實作。'})
    return proof


def pgr_period(reports, year, month, kind='Q'):
    name = 'pgr-2025-10k.pdf' if kind == 'FY' else 'pgr-2025-q3.pdf' if year == 2024 else f'pgr-2026-q{month // 3}.pdf'
    report = reports[name]
    def one(section):
        hits = [r for r in report[section] if (r['kind'], r['year'], r['month']) == (kind, year, month)]
        if len(hits) != 1:
            raise ValueError('Missing or duplicate PGR period')
        return hits[0]
    income, segments = one('income'), one('segments')
    return {'values_usd': {**income['values_usd'], **segments['values_usd']},
            'source_file': report['file'], 'source_sha256': report['sha256'],
            'source_url': report['source_url'],
            'income': income, 'segments': segments}


def pgr_quarter(reports, year, month):
    if month != 12:
        return pgr_period(reports, year, month)
    annual = pgr_period(reports, year, 12, 'FY'); nine = pgr_period(reports, year, 9, 'YTD9')
    return {'values_usd': {k: v - nine['values_usd'][k] for k, v in annual['values_usd'].items()},
            'derivation': 'annual_minus_same_basis_nine_months', 'annual_evidence': annual, 'nine_month_evidence': nine,
            'basis': '年度及九個月均採公司後期同分類表，含 Personal Lines 的 Property 與分部 fees；原表版本另存。'}


def apply_pgr(rows, reports):
    for row in rows:
        year, month, _ = map(int, row['sec_period_end'].split('-'))
        table = pgr_quarter(reports, year, month)
        label = PGR_LABELS.get(row['category'], row['category'])
        selected = {'status': 'observed', 'value': table['values_usd'][label],
                    'error': Decimal(1_000_000 if month == 12 else 500_000),
                    'role': 'company_pdf_income_or_underwriting_revenue', 'primary_table': table}
        old = copy.deepcopy(row)
        row.update(compare_value(row['raw'], row['scale'], selected), prior_result=old, role=selected['role'])
        if label == 'Total net realized gains (losses) on securities':
            row['not_additive_with_securities_components'] = True
        if month != 12 or row['status'] == 'exact_scope_candidate_match':
            continue
        reference, _ = amount(row['raw'], row['scale'])
        annual, nine = table['annual_evidence']['values_usd'], table['nine_month_evidence']['values_usd']
        expected_reference = annual[label] if label == 'Total net realized gains (losses) on securities' else -nine[label]
        if label not in ['Total net realized gains (losses) on securities',
                         'Net realized gains (losses) on security sales', 'Net holding period gains (losses) on securities']:
            continue
        if reference == expected_reference:
            row.update(status='explained_reference_error', explanation={
                'kind': 'annual_securities_total_with_negative_ytd_components_in_quarter_reference',
                'primary_table': table, 'basis': 'Q4 參考總額等於 FY 而非單季，兩組成等於負 YTD；公司原表支持正確 FY−YTD。逐欄保留真正單季值，總額與組成不可重複相加；不推論供應商內部實作。'})


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False)
    local = ROOT / 'data/vendor/local/cohort-adjudication-20261104' / args.out.name
    local.mkdir(parents=True, exist_ok=False)
    base = temporal.load(BASE / 'extended-completion-status.json')
    reports = {name: parse_pdf(PRIVATE / name, year, month) for name, year, month in [
        ('pgr-2025-10k.pdf', 2025, None), ('pgr-2025-q3.pdf', 2025, 9), ('pgr-2026-q1.pdf', 2026, 3),
        ('pgr-2026-q2.pdf', 2026, 6), ('pgr-2026-q3.pdf', 2026, 9)]}
    accesses = {r['file']: r for r in temporal.load(PRIVATE / 'pgr-quarterly-access.json')}
    accesses['pgr-2025-q3.pdf'] = temporal.load(PRIVATE / 'pgr-2025-q3-access.json')
    for name, report in reports.items():
        if report['sha256'] != accesses[name]['sha256'] or accesses[name]['status'] != 200:
            raise ValueError('PGR official download evidence mismatch')
        report.update(file=str((PRIVATE / name).relative_to(ROOT)), source_url=accesses[name]['url'])
    temporal.save(args.out / 'PGR-primary-parsed.json', reports)
    ui = temporal.load(PRIVATE / 'hd-quarterly-ui.json'); companies = []
    for company in base['companies']:
        ticker = company['ticker']; rows = temporal.load(ROOT / company['local_detail_path'])
        receipt = temporal.load(BASE / (ticker + '-freeze.json'))
        data = temporal.checked_data(receipt['plan'], ROOT / receipt['plan']['baseline_file']); temporal.verify_freeze(receipt, data)
        if ticker == 'HD':
            proof = apply_hd(rows, data, ui); temporal.save(args.out / 'HD-primary-proof.json', json.loads(json.dumps(proof, default=str)))
        elif ticker == 'PGR':
            apply_pgr(rows, reports)
        elif ticker == 'CVX':
            previous = temporal.load(ROOT / 'research/chevron-q4-repair-20261104/CVX-status.json')
            if digest(ROOT / previous['local_detail_path']) != previous['local_detail_sha256']:
                raise ValueError('CVX prior evidence hash mismatch')
            rows = temporal.load(ROOT / previous['local_detail_path'])
        detail = local / (ticker + '-followup.json'); temporal.save(detail, json.loads(json.dumps(rows, default=str)))
        eligible = [copy.deepcopy(r) for r in rows if r['status'] != 'reference_not_applicable_evidenced']
        for r in eligible:
            if r['status'] in ACCEPTED - {'exact_scope_candidate_match'} and r.get('explanation'):
                r['status'] = 'exact_scope_candidate_match'
        verdict = assess(eligible, company['target_periods'], company['reference'])
        verdict['cell_statuses'] = dict(Counter(r['status'] for r in rows if r['kind'] == 'Q' and r['source'] == company['reference']))
        companies.append({'ticker': ticker, **verdict, 'local_detail_path': str(detail.relative_to(ROOT)), 'local_detail_sha256': digest(detail)})
    summary = {'ok_count': sum(c['status'] == 'OK' for c in companies), 'total': 30, 'companies': companies,
        'blind_tests': 0, 'latest_pgr_sec_quarter_seen': True, 'latest_pgr_reference_quarter_missing': '2026-09-30',
        'base_summary_sha256': digest(BASE / 'extended-completion-status.json'),
        'inherited_cvx_status_sha256': digest(ROOT / 'research/chevron-q4-repair-20261104/CVX-status.json'),
        'code_sha256': {p: digest(ROOT / p) for p in ['scripts/continue_remaining_research.py', 'scripts/parse_progressive_reports.py']},
        'private_evidence_sha256': {str(p.relative_to(ROOT)): digest(p) for p in [PRIVATE / 'hd-quarterly-ui.json', PRIVATE / 'pgr-futu-recheck.json']},
        'note': '固定原三家之一；原始參考數字保留，明列有原表支持的差異。PGR 仍缺最新參考，不能列八季 OK。'}
    temporal.save(args.out / 'completion-status.json', summary)
    print(str(summary['ok_count']) + ' / 30')


if __name__ == '__main__':
    main()
