#!/usr/bin/env python3
"""補入正常瀏覽器的缺季參考，只以已凍結 SEC facts 產生營收數字。"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re

import temporal_eval as temporal
from cohort_rule_audit import compare_value, resolve
from cohort_rule_catalog import catalog
from enforce_sec_primary_source import selected_is_sec, assess
from extend_issuer_repairs import pools_for, selection
from repair_chevron_q4 import normalize_old_scope

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/xom-sec-verified-20261104/completion-status.json'
LABELS = {'MCD': ['國際運營的市場', 'United States (US)', '國際開發許可市場和公司'],
          'CVX': ['下游', '上游', '所有其他', '部門間收入抵銷']}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_reference(company):
    ticker = company['ticker']
    if company['source_url'] != f'https://www.futunn.com/hk/stock/{ticker}-US/financials-revenue':
        raise ValueError('Wrong reference origin')
    lines = company['text'].splitlines()
    if not lines or lines[0] != 'heading 業務, Value: 3':
        raise ValueError('Not the business section')
    texts = [m[1].strip() for line in lines if (m := re.fullmatch(r'\s*\d+ text (.*)', line))]
    if '貨幣單位:美元' not in texts or texts.count('2024/Q3') != 1 or texts.count('名稱 營收 比例') != 1:
        raise ValueError('Missing unique quarterly period or USD header')
    values = texts[texts.index('名稱 營收 比例') + 1:]
    if len(values) != len(LABELS[ticker]) * 3 or values[::3] != LABELS[ticker]:
        raise ValueError('Unreviewed category order, missing or duplicate reference row')
    for value, share in zip(values[1::3], values[2::3]):
        if not re.fullmatch(r'-?\d[\d,]*(?:\.\d+)?億', value) or not re.fullmatch(r'-?\d+(?:\.\d+)?%', share):
            raise ValueError('Missing amount, unit or share; blank is not zero')
    return list(zip(values[::3], values[1::3]))


def main():
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('--observations', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True);args = parser.parse_args()
    args.observations = args.observations.resolve()
    captured = temporal.load(args.observations)
    if captured['source_format'] != 'native_Edge_accessibility_business_text' or {c['ticker'] for c in captured['companies']} != set(LABELS) or len(captured['companies']) != 2:
        raise ValueError('Unreviewed capture format or roster')
    references = {c['ticker']: parse_reference(c) for c in captured['companies']}
    args.out.mkdir(parents=True, exist_ok=False)
    local = ROOT / 'data/vendor/local/cohort-adjudication-20261104' / args.out.name; local.mkdir(parents=True, exist_ok=False)
    base = temporal.load(BASE); companies = []; outputs = {}
    for company in base['companies']:
        ticker = company['ticker']
        if ticker not in references:
            companies.append(company); continue
        path = ROOT / company['local_detail_path']
        if digest(path) != company['local_detail_sha256']:
            raise ValueError('Prior comparison changed')
        rows = temporal.load(path)
        if any(r.get('sec_period_end') == '2024-09-30' for r in rows):
            raise ValueError('Gap reference already present; refusing duplicate')
        receipt = temporal.load(ROOT / f'research/cohort-rule-replay-20261104/{ticker}-freeze.json')
        data = temporal.checked_data(receipt['plan'], ROOT / receipt['plan']['baseline_file']);temporal.verify_freeze(receipt, data)
        if ticker == 'CVX':
            record = normalize_old_scope(next(r for r in data['raw_filings'] if r['filing']['reportDate'] == '2024-09-30'))
            facts, conflicts = temporal.runner().quarter(record['facts'], '2024-09-30', '10-Q', [])
        else:
            _, pools = pools_for(ticker, data); facts, conflicts = pools['2024-09-30']
        public = {}
        for label, raw in references[ticker]:
            chosen = selection(ticker, label, facts, conflicts) if ticker == 'MCD' else resolve(catalog()[ticker]['futu'][label], facts, conflicts)
            if not selected_is_sec(chosen):
                raise ValueError('Missing SEC output; reference cannot supply primary value')
            row = {'ticker': ticker, 'source': 'futu', 'kind': 'Q', 'date': '2024-09-30', 'period_label': '2024/Q3',
                'category': label, 'raw': raw, 'scale': 1, 'evidence_path': str(args.observations.relative_to(ROOT)),
                'reference_artifact_sha256': digest(args.observations), 'sec_period_end': '2024-09-30',
                'period_reviewed': True, 'alignment': 'reviewed_futu_calendar_quarter', 'phase': 'seen_retrospective',
                'role': 'SEC_frozen_facts_replayed_for_new_reference', 'primary_source_check': 'SEC_operands_verified',
                **compare_value(raw, 1, chosen)}
            rows.append(row); public[label] = chosen
        detail = local / f'{ticker}-gap-repaired.json';temporal.save(detail, json.loads(json.dumps(rows, default=str)))
        eligible = [copy.deepcopy(r) for r in rows if r['status'] != 'reference_not_applicable_evidenced']
        verdict = assess(eligible, company['target_periods'], company['reference'])
        verdict.update(cell_statuses=dict(Counter(r['status'] for r in rows)),
            primary_source_checks=dict(Counter(r.get('primary_source_check') for r in rows)))
        companies.append({'ticker': ticker, **verdict, 'local_detail_path': str(detail.relative_to(ROOT)), 'local_detail_sha256': digest(detail)})
        outputs[ticker] = {'period_end': '2024-09-30', 'selected_SEC_outputs': public,
            'new_reference_cells': len(public), 'comparison_statuses': dict(Counter(r['status'] for r in rows[-len(public):]))}
    temporal.save(args.out / 'new-SEC-outputs.json', json.loads(json.dumps(outputs, default=str)))
    result = {**base, 'companies': companies, 'ok_count': sum(c['status'] == 'OK' for c in companies),
        'source_summary_sha256': digest(BASE), 'new_reference_artifact_sha256': digest(args.observations),
        'reference_capture_method': captured['source_format'], 'new_reference_raw_published': False,
        'gap_code_sha256': {'scripts/complete_reference_gaps.py': digest(__file__)}, 'blind_tests': 0}
    temporal.save(args.out / 'completion-status.json', result)
    print(json.dumps({'ok_count': result['ok_count'], 'updated': [c for c in companies if c['ticker'] in LABELS]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
