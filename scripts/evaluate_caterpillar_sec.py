#!/usr/bin/env python3
"""以實際 SEC 8-K 補 CAT 最新季，保留前輪結果與固定參考。"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from cohort_rule_audit import compare_value
from continue_parser_repairs import mark_inactive, ACCEPTED
from enforce_sec_primary_source import selected_is_sec, assess
from parse_caterpillar_sec import parse_snapshot, URL

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/progressive-sec-completion-20261104'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True); args = parser.parse_args()
    manifest = temporal.load(args.manifest); source = ROOT / manifest['path']
    if digest(source) != manifest['sha256']:
        raise ValueError('SEC snapshot hash mismatch')
    parsed = parse_snapshot(temporal.load(source), manifest['sha256'])
    args.out.mkdir(parents=True, exist_ok=False)
    local = ROOT / 'data/vendor/local/cohort-adjudication-20261104' / args.out.name
    local.mkdir(parents=True, exist_ok=False)
    temporal.save(args.out / 'CAT-latest-parsed-SEC.json', json.loads(json.dumps(parsed, default=str)))
    base = temporal.load(BASE / 'completion-status.json'); companies = []
    for company in base['companies']:
        if company['ticker'] != 'CAT':
            companies.append(company); continue
        path = ROOT / company['local_detail_path']
        if digest(path) != company['local_detail_sha256']:
            raise ValueError('CAT previous result hash mismatch')
        rows = temporal.load(path); latest = []
        for row in rows:
            if row['source'] != 'stockanalysis' or row.get('display_date') != 'Sep 30, 2026':
                continue
            old = copy.deepcopy(row)
            row.update(sec_period_end='2026-09-30', period_reviewed=True, alignment='SEC_exhibit_direct_quarter',
                       phase='latest_seen_retrospective', prior_sec_result=old)
            if row['category'] in parsed['selected']:
                selected = parsed['selected'][row['category']]
                if not selected_is_sec(selected):
                    raise ValueError('CAT value lacks SEC operands')
                row.update(compare_value(row['raw'], row['scale'], selected),
                           role='SEC_exhibit_direct_segment_revenue', primary_source_check='SEC_operands_verified')
            latest.append(row)
        mark_inactive(latest, list(parsed['selected']), URL,
                      'Power & Energy 為當期列名，舊 Energy and Transportation 空欄不重複計入；六個現行結果合計核對 SEC 總收入。',
                      {'status': 'observed', 'value': parsed['consolidated_total']})
        for row in latest:
            if row['status'] == 'reference_not_applicable_evidenced':
                row['primary_source_check'] = 'not_applicable_no_numeric_output'
        out = local / 'CAT-sec-repaired.json'; temporal.save(out, json.loads(json.dumps(rows, default=str)))
        targets = sorted(set(company['target_periods']) | {'2026-09-30'})[-8:]
        eligible = [copy.deepcopy(r) for r in rows if r['status'] != 'reference_not_applicable_evidenced']
        for row in eligible:
            if row['status'] in ACCEPTED - {'exact_scope_candidate_match'} and row.get('explanation'):
                row['status'] = 'exact_scope_candidate_match'
        verdict = assess(eligible, targets, company['reference'])
        verdict.update(cell_statuses=dict(Counter(r['status'] for r in rows)),
            primary_source_checks=dict(Counter(r['primary_source_check'] for r in rows)))
        if any(not selected_is_sec(r.get('selected', {})) for r in eligible):
            verdict['status'] = 'Fail'; verdict['fail_reasons'].append('SEC_primary_source_not_complete')
        companies.append({'ticker': 'CAT', **verdict, 'local_detail_path': str(out.relative_to(ROOT)), 'local_detail_sha256': digest(out)})
    result = {**base, 'companies': companies, 'ok_count': sum(c['status'] == 'OK' for c in companies),
        'source_summary_sha256': digest(BASE / 'completion-status.json'),
        'CAT_new_period_source': manifest, 'CAT_target_update': '以 SEC 8-K 實際取得 2026-09-30，最新八季改為 2024Q4～2026Q3；不改舊基準／凍結收據，不宣稱盲測。',
        'CAT_code_sha256': {p: digest(ROOT / p) for p in ['scripts/parse_caterpillar_sec.py', 'scripts/evaluate_caterpillar_sec.py',
                                                       'scripts/collect_caterpillar_sec_dom.js']}}
    temporal.save(args.out / 'completion-status.json', result)
    print(str(result['ok_count']) + ' / 30 SEC-only')


if __name__ == '__main__':
    main()
