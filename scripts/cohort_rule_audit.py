#!/usr/bin/env python3
"""完整三十家公司範圍候選重播；原始參考列與逐筆結果僅留本機。"""
import argparse
import calendar
from collections import Counter
import datetime as dt
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from cohort_rule_catalog import catalog, R, P
from compare_vendor_cohort import ROOT, PRIVATE, amount, match_period, futu_fiscal_date
from historical_rule_experiments import definitions, normalize_history, fact_error
from review_scope_gaps import derive_nee_fpl_q4, latest_training_comparative, corporate_residual

UNKNOWN = {'LLY', 'PGR', 'XOM'}
DESTINATION = ROOT / 'research/cohort-rule-adjudication'


FRESH_COMCAST = PRIVATE / 'cohort-adjudication-20261104/comcast-fresh-ui-check.json'


def fresh_comcast_confirms(ref):
    """新頁面須支持原日期的原始值；另一季數值命中本身不足以裁決。"""
    column = {'Connectivity and Platforms': 1, 'Content and Experiences': 2}.get(ref['category'])
    if column is None:
        return False
    rows = temporal.load(FRESH_COMCAST)['rows']
    for row in rows:
        if row[0] == ref.get('display_date'):
            original, tolerance = amount(ref['raw'], ref['scale'])
            fresh, fresh_tolerance = amount(row[column], 1)
            return original is not None and fresh is not None and abs(original - fresh) <= tolerance + fresh_tolerance
    return False


def resolve(rule, facts, conflicts=()):
    if rule is None:
        return {'status': 'definition_unimplemented'}
    alternatives = []
    for terms in rule['alternatives']:
        selected = []
        ambiguous = False
        for term in terms:
            def matches(f):
                return all(f.get(k) == term[k] for k in ('concept', 'dimensions', 'unit'))
            found = [f for f in facts if matches(f) and isinstance(f.get('value'), int)]
            if len({f['value'] for f in found}) > 1 or any(matches(f) for group in conflicts for f in group):
                ambiguous = True
            if not found:
                selected = []
                break
            selected.append((term['weight'], found[0]))
        if ambiguous:
            return {'status': 'ambiguous_scope'}
        if selected:
            errors = [fact_error(f) for _, f in selected]
            alternatives.append({'value': sum(w * f['value'] for w, f in selected),
                'error': None if None in errors else sum(abs(w) * e for (w, _), e in zip(selected, errors)),
                'facts': [f for _, f in selected]})
    if not alternatives:
        return {'status': 'parser_scope_missing'}
    if len({a['value'] for a in alternatives}) > 1:
        return {'status': 'ambiguous_scope'}
    return {'status': 'observed', 'value': alternatives[0]['value'],
            'error': None if any(a['error'] is None for a in alternatives) else max(a['error'] for a in alternatives),
            'facts': [f for a in alternatives for f in a['facts']], 'role': rule['role']}


def compare_value(raw, scale, selected):
    value, tolerance = amount(raw, scale)
    if value is None:
        return {'status': 'reference_missing'}
    if selected['status'] != 'observed':
        return {'status': selected['status']}
    gap = abs(value - Decimal(selected['value']))
    status = 'exact_scope_candidate_match' if gap == 0 else 'precision_unknown' if selected.get('error') is None else (
        'within_scope_candidate_precision' if gap <= tolerance + selected['error'] else 'scope_candidate_differs')
    return {'status': status, 'reference_usd': str(value), 'difference_usd': str(value - Decimal(selected['value'])),
            'source_display_tolerance_usd': str(tolerance), 'selected': selected}


def manual_series():
    cmcsa = temporal.load(DESTINATION / 'comcast-sec-business-groups.json')['observations']
    wmt = temporal.load(DESTINATION / 'walmart-corporate-income.json')['observations']
    result = {}
    for ticker, rows, fields in [('CMCSA', cmcsa, {'Connectivity and Platforms': 'connectivity_and_platforms',
            'Content and Experiences': 'content_and_experiences'}), ('WMT', wmt, {'企業和支持': 'value_usd_millions'})]:
        reported = {(r['period_kind'], r['period_end']): r for r in rows}
        for (kind, end), row in reported.items():
            if kind not in ('Q', 'FY'):
                continue
            for label, key in fields.items():
                result[(ticker, kind, end, label)] = {'status': 'observed', 'value': row[key] * 1_000_000,
                    'error': Decimal(500_000), 'primary_evidence': [row], 'role': 'primary_text_reviewed_definition'}
        for year in ('2024', '2025', '2026'):
            end = year + ('-01-31' if ticker == 'WMT' else '-12-31')
            nine_end = str(int(year) - 1) + '-10-31' if ticker == 'WMT' else year + '-09-30'
            a, n = reported.get(('FY', end)), reported.get(('YTD9', nine_end))
            if a and n:
                for label, key in fields.items():
                    result[(ticker, 'Q', end, label)] = {'status': 'observed', 'value': (a[key] - n[key]) * 1_000_000,
                        'error': Decimal(1_000_000), 'primary_evidence': [a, n],
                        'role': 'primary_text_reviewed_definition_q4_derived'}
    return result


def load_references():
    refs, attempts = [], {}
    for path in sorted((PRIVATE / 'cohort-20261104').glob('batch*.json')):
        for c in temporal.load(path):
            attempts[c['ticker']] = c['status']
            if not c.get('quarterly_confirmed'):
                continue
            if c['currency'] != 'USD':
                raise ValueError('Only reviewed USD input is allowed')
            for date, *values in c['rows']:
                for label, value in zip(c['columns'][1:], values):
                    refs.append({'ticker': c['ticker'], 'source': 'stockanalysis', 'kind': 'Q', 'display_date': date,
                        'category': label, 'raw': value, 'scale': c['numeric_scale'], 'evidence_path': str(path.relative_to(ROOT))})
    for relative in ['cohort-20261104/futu-observations.json', 'evidence-review-20261104/futu-second-round.json',
                     'historical-rules-20261104/futu-observations.json']:
        path = PRIVATE / relative
        for c in temporal.load(path):
            if c['currency'] != 'USD':
                raise ValueError('Only reviewed USD input is allowed')
            for p in c['captures']:
                label = p['period']
                kind = 'FY' if label.endswith('/FY') else 'Q'
                if c['ticker'] == 'NVDA':
                    date = {'2027/Q2': '2026-07-26', '2027/Q1': '2026-04-26', '2026/FY': '2026-01-25'}[label]
                else:
                    date = label[:4] + '-12-31' if kind == 'FY' else futu_fiscal_date(c['ticker'], label)
                for category, value, share in p['rows']:
                    refs.append({'ticker': c['ticker'], 'source': 'futu', 'kind': kind, 'date': date, 'period_label': label,
                        'category': category, 'raw': value, 'scale': 1, 'share': share, 'evidence_path': str(path.relative_to(ROOT))})
    path = PRIVATE / 'evidence-review-20261104/pld-ir-review.json'
    for p in temporal.load(path):
        for category, value in zip(['Rental', 'Strategic capital', 'Development management and other', 'Total revenues'], p['values']):
            refs.append({'ticker': 'PLD', 'source': 'issuer_ir', 'kind': 'Q', 'date': p['date'], 'category': category,
                'raw': value, 'scale': 1000, 'evidence_path': str(path.relative_to(ROOT))})
    return refs, attempts


def make_rules(ticker, groups):
    specs = {}
    for source in groups.values():
        for rule in source.values():
            for terms in rule['alternatives']:
                for term in terms:
                    spec = {k: term[k] for k in ('concept', 'dimensions', 'unit')}
                    specs[temporal.canonical(spec)] = spec
    rules = {'version': ticker.lower() + '-explicit-candidate-catalog-v1', 'category_catalog': groups,
        'selectors': [{'id': f'{kind}:{index}', 'period_kind': kind, 'semantic_basis': f'{ticker}:explicit-scope-candidate-{index}', **s}
            for kind in ('Q', 'FY') for index, s in enumerate(specs.values())],
        'independent_human_review': False}
    if ticker == 'NVDA':
        rules['member_aliases'] = definitions('NVDA')['member_aliases']
    if ticker == 'AMZN':
        rules['member_aliases'] = [{'id': 'amzn-historical-annual-advertising', 'concept': R,
            'original_dimensions': {P: 'us-gaap:AdvertisingMember'}, 'dimensions': {P: 'amzn:AdvertisingServicesMember'},
            'report_dates': ['2024-12-31', '2025-12-31'],
            'review_basis': '既有 pilot 及八季實驗已記錄同一廣告類別的年度／九個月 member 差異；僅限指定歷史年報。'}]
    return rules


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    local = PRIVATE / 'cohort-adjudication-20261104' / args.out.name
    local.mkdir(exist_ok=False)
    refs, attempts = load_references()
    curated = manual_series()
    groups = catalog()
    plans = {p['ticker']: p for p in temporal.load(ROOT / 'research/temporal-evaluation/cohort-plans.json')}
    if set(plans) != set(groups) or len(groups) != 30:
        raise ValueError('All thirty issuers must have explicit rules or explicit gaps')
    summaries, engine = [], temporal.runner()
    for ticker, mappings in groups.items():
        plan = plans[ticker]
        if ticker not in UNKNOWN:
            plan['exposure'].update(seen_during_development='yes', evidence=['docs/vendor/training-test-split.json'])
        data = temporal.checked_data(plan, ROOT / plan['baseline_file'])
        rules = make_rules(ticker, mappings)
        receipt = temporal.freeze(plan, data, rules)
        temporal.save(args.out / (ticker + '-freeze.json'), receipt)
        training = temporal.training_pack(plan, data)['raw_filings']
        normalized = normalize_history(training, rules)
        records = normalized + ([] if ticker in UNKNOWN else temporal.select_records(plan, data, 'holdout'))
        pools = {}
        for index, record in enumerate(records):
            filing = record['filing']; end = filing['reportDate']
            q, conflicts = engine.quarter(record['facts'], end, filing['form'], [f for r in records[:index] for f in r['facts']])
            pools[('Q', end)] = (q, conflicts)
            if filing['form'] == '10-K':
                pools[('FY', end)] = engine.dedupe([f for f in record['facts']
                    if f.get('enddate') == end and 350 <= engine.days(f) <= 380])
        if ticker == 'NEE':
            bridge = derive_nee_fpl_q4(training)
            if bridge:
                q, conflicts = pools[('Q', '2024-12-31')]
                pools[('Q', '2024-12-31')] = (q + [bridge], conflicts)
        latest = plan['holdout'][0]['period_end']
        eligible = [q for q in data['quarter_results'] if ticker not in UNKNOWN or q['report_date'] != latest]
        detailed = []
        issuer_refs = [r for r in refs if r['ticker'] == ticker]
        for ref in issuer_refs:
            alignment = 'explicit_reviewed_fiscal_label'
            date = ref.get('date')
            if 'display_date' in ref:
                candidate, alignment = match_period(ref['display_date'], eligible)
                date = candidate['report_date'] if candidate else None
                if ticker == 'AAPL' and candidate:
                    alignment = 'reviewed_apple_display_mapping'
            if date == latest and ticker in UNKNOWN:
                date = None
                alignment = 'latest_exposure_unknown_not_evaluated'
            if date and (ref['kind'], date) not in pools:
                date = None
                alignment = 'source_period_outside_available_baseline'
            facts, conflicts = pools.get((ref['kind'], date), ([], []))
            if ticker == 'WMT' and ref['kind'] == 'Q' and date and date != latest:
                comparative = latest_training_comparative(training, date)
                if comparative:
                    facts, conflicts = comparative['facts'], comparative['conflicts']
            selected = curated.get((ticker, ref['kind'], date, ref['category']))
            if selected is None and ticker == 'WMT' and ref['category'] == '企業和支持':
                residual = corporate_residual(facts)
                selected = {'status': 'observed', 'value': residual['value'], 'error': Decimal(2_000_000),
                    'role': 'inferred_corporate_income_pending_raw_verification', 'residual_evidence': residual} if residual['value'] is not None else {'status': 'parser_scope_missing'}
            if selected is None:
                selected = resolve(mappings.get(ref['source'], {}).get(ref['category']), facts, conflicts)
            result = compare_value(ref['raw'], ref['scale'], selected)
            if not date:
                result = {'status': 'period_unaligned_or_not_evaluated'} if ref['raw'] is not None else {'status': 'reference_missing'}
            role = selected.get('role', 'unimplemented')
            period_reviewed = alignment in ('explicit_reviewed_fiscal_label', 'exact_date', 'reviewed_apple_display_mapping')
            if ticker == 'CMCSA' and ref['source'] == 'stockanalysis' and date in ('2026-03-31', '2026-06-30'):
                other = '2026-06-30' if date == '2026-03-31' else '2026-03-31'
                other_check = compare_value(ref['raw'], ref['scale'], curated[(ticker, 'Q', other, ref['category'])])
                if result['status'] == 'scope_candidate_differs' and other_check['status'] in ('exact_scope_candidate_match', 'within_scope_candidate_precision') and fresh_comcast_confirms(ref):
                    result.update(status='confirmed_saved_period_label_mismatch', other_period_diagnostic=other,
                        original_period_preserved=True, fresh_UI_evidence='data/vendor/local/cohort-adjudication-20261104/comcast-fresh-ui-check.json')
            detailed.append({**ref, 'sec_period_end': date, 'alignment': alignment, 'period_reviewed': period_reviewed,
                'phase': 'latest_retrospective' if date == latest else 'historical_or_outside_target', 'role': role, **result})
        fy_states = Counter()
        for (kind, date), (facts, conflicts) in pools.items():
            if kind == 'FY':
                for source in mappings.values():
                    for rule in source.values():
                        fy_states[resolve(rule, facts, conflicts)['status']] += 1
        safe_counts = []
        for source in sorted({r['source'] for r in detailed}):
            for kind in ('Q', 'FY'):
                rows = [r for r in detailed if r['source'] == source and r['kind'] == kind]
                if rows:
                    safe_counts.append({'source': source, 'kind': kind, 'reference_slots': len(rows),
                        'numeric_reference_slots': sum(r['raw'] is not None for r in rows),
                        'statuses': dict(Counter(r['status'] for r in rows)),
                        'unreviewed_period_numeric_slots': sum(r['raw'] is not None and not r['period_reviewed'] for r in rows),
                        'role_counts': dict(Counter(r['role'] for r in rows if r['raw'] is not None))})
        temporal.save(local / (ticker + '-detailed.json'), json.loads(json.dumps(detailed, default=str)))
        paths = sorted({r['evidence_path'] for r in issuer_refs} | ({str(FRESH_COMCAST.relative_to(ROOT))} if ticker == 'CMCSA' else set()))
        summary = {'ticker': ticker, 'stockanalysis_attempt': attempts[ticker], 'reference_checks': safe_counts,
            'latest_evaluation': 'not_run_exposure_unknown' if ticker in UNKNOWN else 'contaminated_retrospective',
            'strict_blind_test': False, 'selector_count_Q_and_FY': len(rules['selectors']),
            'FY_scope_slots_not_reference_accuracy': dict(fy_states), 'member_bridge_rules': len(rules.get('member_aliases', [])),
            'independent_human_review_done': False, 'manual_minutes_measured': False,
            'full_disclosure_recall_measured': False, 'source_evidence': [{'path': p, 'sha256': hashlib.sha256((ROOT / p).read_bytes()).hexdigest()} for p in paths],
            'tradingview': 'partial_annual_summary_period_unverified' if ticker in ('AAPL', 'TSLA', 'NVDA') else 'not_acquired_in_this_replay'}
        summaries.append(summary)
    temporal.save(args.out / 'summary.json', {'companies': summaries, 'roster_count': 30, 'genuine_unseen_tests': 0,
        'code_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in (
            'scripts/cohort_rule_audit.py', 'scripts/cohort_rule_catalog.py', 'scripts/historical_rule_experiments.py',
            'scripts/review_scope_gaps.py', 'scripts/compare_vendor_cohort.py')},
        'manual_primary_source_files_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (
            DESTINATION / 'comcast-sec-business-groups.json', DESTINATION / 'walmart-corporate-income.json')}})
    print(json.dumps([{'ticker': c['ticker'], 'checks': c['reference_checks']} for c in summaries], ensure_ascii=False))


if __name__ == '__main__':
    main()
