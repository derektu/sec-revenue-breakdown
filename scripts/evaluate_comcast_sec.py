#!/usr/bin/env python3
"""以七份 SEC 原始文件完成 Comcast 八季淨業務群程式解析與差異裁決。"""
import argparse
from collections import Counter
import copy
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from cohort_rule_audit import compare_value, fresh_comcast_confirms, FRESH_COMCAST
from compare_vendor_cohort import amount
from continue_parser_repairs import ACCEPTED
from enforce_sec_primary_source import selected_is_sec, assess
from parse_comcast_business_groups import parse_groups, LABELS
from parse_comcast_sec_dom import parse_snapshot

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/caterpillar-sec-completion-20261104'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract_sources(manifest):
    facts = []; sources = []
    for entry in manifest['files']:
        path = ROOT / entry['path']
        if digest(path) != entry['sha256']:
            raise ValueError('DOM source hash mismatch')
        parsed = parse_snapshot(temporal.load(path), entry['sha256'])
        facts.extend(parsed['facts']); sources.append({**entry, 'rejected_constant_currency_tables': parsed['rejected_constant_currency_tables']})
    original = temporal.load(ROOT / 'research/shared-raw-semantics/manifest.json')
    for report in original['filings']:
        if report['ticker'] != 'CMCSA':
            continue
        body = gzip.decompress((ROOT / report['path']).read_bytes())
        if hashlib.sha256(body).hexdigest() != report['sha256']:
            raise ValueError('Original SEC HTML hash mismatch')
        values = parse_groups(body, report['form'], 2025)
        sources.append({k: report[k] for k in ['path', 'url', 'sha256', 'reportDate', 'form']})
        for (kind, year, label), value in values.items():
            month = 12 if kind == 'FY' else 9
            facts.append({'kind': kind, 'year': year, 'month': month, 'label': label,
                'concept': 'sec-table:NetBusinessGroupRevenue', 'dimensions': {'reported_business_group': label, 'basis': 'reported_net_group_total'},
                'value': value, 'unit': 'iso4217:USD', 'decimals': '-6',
                'startdate': f'{year}-{7 if kind == "Q" else 1:02d}-01', 'enddate': f'{year}-{month:02d}-{31 if month == 12 else 30}',
                'source_url': report['url'], 'source_report_date': report['reportDate'], 'accession': report['accessionNumber'],
                'source_artifact_sha256': report['sha256'], 'source_format': 'SEC_HTML_from_verified_gzip',
                'source_row_label': LABELS[label], 'source_parser': 'parse_comcast_business_groups.parse_groups'})
    return facts, sources


def build_quarters(observations):
    quarters = {}
    for f in observations:
        # 後期比較欄可能重編；一般 Q 只用原期申報，避免用後來數字配合參考。
        if f['kind'] == 'Q' and f['enddate'] == f['source_report_date']:
            key = (f['enddate'], f['label'])
            if key in quarters:
                raise ValueError('Duplicate original-period business-group source')
            quarters[key] = f
    for year in [2024, 2025]:
        for label in LABELS:
            def one(kind):
                found = [f for f in observations if (f['kind'], f['year'], f['label']) == (kind, year, label)
                         and f['source_format'] == 'SEC_HTML_from_verified_gzip']
                if len(found) != 1:
                    raise ValueError('Missing unique FY or nine-month raw-table operand')
                return found[0]
            annual, nine = one('FY'), one('YTD9')
            if any(annual[k] != nine[k] for k in ['concept', 'dimensions', 'unit', 'startdate']):
                raise ValueError('Fiscal year, unit or full business-group scope differs')
            quarters[(f'{year}-12-31', label)] = {**annual, 'kind': 'Q', 'startdate': f'{year}-10-01',
                'value': annual['value'] - nine['value'], 'derivation': 'annual_minus_nine_months',
                'annual_evidence': annual, 'nine_month_evidence': nine, 'comparative_used': year == 2024}
    targets = ['2024-12-31', '2025-03-31', '2025-06-30', '2025-09-30', '2025-12-31', '2026-03-31', '2026-06-30', '2026-09-30']
    if set(quarters) != {(end, label) for end in targets for label in LABELS}:
        raise ValueError('Eight original target quarters not complete')
    return quarters


def selected(fact):
    return {'status': 'observed', 'value': fact['value'], 'error': Decimal(1_000_000 if fact.get('derivation') else 500_000),
            'facts': [fact], 'role': 'SEC_parsed_reported_net_business_group'}


def apply_comcast(rows, quarters):
    chosen = [r for r in rows if r['source'] == 'stockanalysis' and r['kind'] == 'Q']
    for row in chosen:
        fact = quarters[row['sec_period_end'], row['category']]; selection = selected(fact)
        if not selected_is_sec(selection):
            raise ValueError('Non-SEC operand')
        old = copy.deepcopy(row)
        row.update(compare_value(row['raw'], row['scale'], selection), prior_sec_result=old,
                   role=selection['role'], primary_source_check='SEC_operands_verified')
        if row['status'] == 'within_scope_candidate_precision' and fact.get('derivation'):
            reference, tolerance = amount(row['raw'], row['scale'])
            if abs(reference - fact['value']) <= selection['error'] + tolerance:
                row.update(status='explained_reported_precision', explanation={
                    'kind': 'SEC_annual_minus_nine_month_reported_precision',
                    'maximum_SEC_error_usd': str(selection['error']),
                    'basis': '兩個 SEC 原表運算元各以百萬申報；Q4 保留真實差額與合計精度，不以參考金額覆蓋。'})
    for period, other in [('2026-03-31', '2026-06-30'), ('2026-06-30', '2026-03-31')]:
        group = [r for r in chosen if r['sec_period_end'] == period]
        if len(group) != 2 or set(r['category'] for r in group) != set(LABELS):
            continue
        pair_matches = all(compare_value(r['raw'], r['scale'], selected(quarters[other, r['category']]))['status'] == 'exact_scope_candidate_match'
                           and r['status'] == 'scope_candidate_differs' and fresh_comcast_confirms(r) for r in group)
        if pair_matches:
            for row in group:
                row.update(status='explained_reference_error', explanation={
                    'kind': 'two_reference_quarter_pairs_match_opposite_SEC_quarters',
                    'SEC_this_quarter': quarters[period, row['category']], 'SEC_other_quarter': quarters[other, row['category']],
                    'original_period_preserved': True, 'saved_reference_fresh_UI_sha256': digest(FRESH_COMCAST),
                    'basis': '已保存參考及先前正常畫面重看一致；兩個業務群在兩季呈相反季度對應，SEC 原表各有明確日期表頭。輸出仍保留 SEC 本季金額，視為參考期別差異，不宣稱知道 vendor 內部原因。'})


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True); args = parser.parse_args()
    observations, sources = extract_sources(temporal.load(args.manifest)); quarters = build_quarters(observations)
    args.out.mkdir(parents=True, exist_ok=False)
    local = ROOT / 'data/vendor/local/cohort-adjudication-20261104' / args.out.name; local.mkdir(parents=True, exist_ok=False)
    temporal.save(args.out / 'CMCSA-parsed-SEC-facts.json', {'observations': observations, 'sources': sources,
        'quarter_facts': [{'period_end': end, 'label': label, 'fact': fact} for (end, label), fact in sorted(quarters.items())]})
    base = temporal.load(BASE / 'completion-status.json'); companies = []
    for company in base['companies']:
        if company['ticker'] != 'CMCSA':
            companies.append(company); continue
        path = ROOT / company['local_detail_path']
        if digest(path) != company['local_detail_sha256']:
            raise ValueError('Prior reference hash mismatch')
        rows = temporal.load(path); apply_comcast(rows, quarters)
        detail = local / 'CMCSA-sec-repaired.json'; temporal.save(detail, json.loads(json.dumps(rows, default=str)))
        eligible = copy.deepcopy(rows)
        for row in eligible:
            if row['status'] in ACCEPTED - {'exact_scope_candidate_match'} and row.get('explanation'):
                row['status'] = 'exact_scope_candidate_match'
        verdict = assess(eligible, company['target_periods'], company['reference'])
        chosen = [r for r in rows if r['source'] == company['reference'] and r['kind'] == 'Q']
        verdict.update(cell_statuses=dict(Counter(r['status'] for r in chosen)),
                       primary_source_checks=dict(Counter(r['primary_source_check'] for r in chosen)))
        if any(not selected_is_sec(r.get('selected', {})) for r in chosen):
            verdict['status'] = 'Fail'; verdict['fail_reasons'].append('SEC_primary_source_not_complete')
        companies.append({'ticker': 'CMCSA', **verdict, 'local_detail_path': str(detail.relative_to(ROOT)), 'local_detail_sha256': digest(detail)})
    result = {**base, 'companies': companies, 'ok_count': sum(c['status'] == 'OK' for c in companies),
        'source_summary_sha256': digest(BASE / 'completion-status.json'), 'CMCSA_source_files': sources,
        'CMCSA_reference_UI_sha256': digest(FRESH_COMCAST),
        'CMCSA_code_sha256': {p: digest(ROOT / p) for p in ['scripts/parse_comcast_sec_dom.py', 'scripts/evaluate_comcast_sec.py',
            'scripts/collect_comcast_sec_dom.js', 'scripts/parse_comcast_business_groups.py']},
        'CMCSA_note': '八季程式擷取／運算，非人工補表；保留原期申報，後期重編比較欄不覆蓋原季。已接觸最新季，沒有盲測。'}
    temporal.save(args.out / 'completion-status.json', result)
    print(str(result['ok_count']) + ' / 30 SEC-only')


if __name__ == '__main__':
    main()
