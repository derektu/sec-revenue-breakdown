#!/usr/bin/env python3
"""以歷史 SEC 證據檢查特定跨範圍 Q4 與未認證的 residual 候選。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from compare_vendor_cohort import ROOT, PRIVATE, futu_fiscal_date, amount
from review_vendor_evidence import reviewed_selector, review_observation, SEGMENT, CONSOLIDATION, OPERATING

NEE_CONCEPT = 'us-gaap:RegulatedAndUnregulatedOperatingRevenue'
FPL = 'nee:FloridaPowerLightCompanyMember'
ENTITY = {'dei:LegalEntityAxis': FPL}
FPL_SEGMENT = {**ENTITY, SEGMENT: FPL, CONSOLIDATION: OPERATING}
BRIDGE_URLS = [
    'https://www.sec.gov/Archives/edgar/data/753308/000075330825000011/nee-20241231.htm',
    'https://www.sec.gov/Archives/edgar/data/753308/000075330824000057/nee-20240930.htm',
]


def unique_scope(facts, concept, dimensions, start=None, end=None):
    found = [f for f in facts if f.get('concept') == concept and f.get('dimensions') == dimensions
             and f.get('unit') == 'iso4217:USD' and isinstance(f.get('value'), int)
             and (start is None or f.get('startdate') == start) and (end is None or f.get('enddate') == end)]
    if not found or len({f['value'] for f in found}) != 1:
        return None
    return found[0]


def derive_nee_fpl_q4(records):
    by_date = {r['filing']['reportDate']: r for r in records}
    annual = by_date.get('2024-12-31', {})
    nine = by_date.get('2024-09-30', {})
    a = unique_scope(annual.get('facts', []), NEE_CONCEPT, FPL_SEGMENT, '2024-01-01', '2024-12-31')
    n = unique_scope(nine.get('facts', []), NEE_CONCEPT, ENTITY, '2024-01-01', '2024-09-30')
    if a is None or n is None:
        return None
    return {**a, 'value': a['value'] - n['value'], 'startdate': '2024-10-01', 'enddate': '2024-12-31',
            'derivation': 'annual_minus_nine_months', 'annual_evidence': a, 'nine_month_evidence': n,
            'scope_bridge_rule_id': 'nee-fpl-2024-reported-segment-to-entity-reviewed',
            'scope_bridge_evidence_urls': BRIDGE_URLS,
            'scope_bridge_review': '指定兩份申報的分部表同時列出 FPL 對應金額；年度說明 FPL 僅單一報導分部。'}


def corporate_residual(facts):
    total = unique_scope(facts, 'us-gaap:Revenues', {})
    segments = [unique_scope(facts, 'us-gaap:Revenues',
                {SEGMENT: 'wmt:' + member, CONSOLIDATION: OPERATING})
                for member in ('WalmartUSMember', 'WalmartInternationalMember', 'SamsClubUSMember')]
    if total is None or any(f is None for f in segments):
        return {'status': 'missing_or_conflicting_operand', 'value': None}
    return {'status': 'arithmetic_candidate_definition_unverified',
            'value': total['value'] - sum(f['value'] for f in segments),
            'total_evidence': total, 'segment_evidence': segments,
            'identity_check_is_tautological': True}


def latest_training_comparative(records, target):
    """選擇截止日前最新、確實包含目標季資料的申報；不按參考金額挑版本。"""
    engine = temporal.runner()
    found = None
    ordered = sorted(records, key=lambda r: r['filing']['filingDate'])
    for index, record in enumerate(ordered):
        previous = [f for r in ordered[:index] for f in r['facts']]
        q, conflicts = engine.quarter(record['facts'], target, record['filing']['form'], previous)
        if q:
            found = {'facts': q, 'conflicts': conflicts, 'source_filing': record['filing']}
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    local = PRIVATE / 'scope-gaps-20261104' / args.out.name
    local.mkdir(parents=True, exist_ok=False)
    capture_path = PRIVATE / 'evidence-review-20261104/futu-second-round.json'
    captures = {c['ticker']: c for c in temporal.load(capture_path)}
    plans = {p['ticker']: p for p in temporal.load(ROOT / 'research/temporal-evaluation/cohort-plans.json')}
    summaries = []
    for ticker in ('NEE', 'WMT'):
        capture = captures[ticker]
        plan = plans[ticker]
        plan['exposure'].update(seen_during_development='yes', evidence=['docs/vendor/training-test-split.json'])
        for ref in plan['references']:
            if ref['source'] == 'futu':
                ref.update(seen_during_development='yes', evidence=[str(capture_path.relative_to(ROOT))])
        data = temporal.checked_data(plan, ROOT / plan['baseline_file'])
        categories = list(dict.fromkeys(row[0] for p in capture['captures'] for row in p['rows']))
        selectors = []
        for index, category in enumerate(categories):
            rule = reviewed_selector(ticker, category)
            if rule:
                concept, scopes = rule
                selectors += [{'id': f'{kind}:{index}:{variant}', 'period_kind': kind, 'concept': concept,
                    'dimensions': dimensions, 'unit': 'iso4217:USD', 'semantic_basis': f'{ticker}:reviewed-scope-{index}'}
                    for kind in ('Q', 'FY') for variant, dimensions in enumerate(scopes)]
        rules = {'version': ticker.lower() + '-bounded-scope-v1', 'selectors': selectors,
            'reviewer': 'local_agent', 'independent_human_review': False,
            'scope_bridge': {'id': 'nee-fpl-2024-reported-segment-to-entity-reviewed',
                'annual_dimensions': FPL_SEGMENT, 'nine_month_dimensions': ENTITY,
                'annual_period': ['2024-01-01', '2024-12-31'], 'nine_month_period': ['2024-01-01', '2024-09-30'],
                'evidence_urls': BRIDGE_URLS} if ticker == 'NEE' else None,
            'residual_is_not_certified_corporate_definition': ticker == 'WMT'}
        if ticker == 'WMT':
            rules['historical_basis_variants'] = ['as_originally_filed', 'latest_comparative_available_before_training_cutoff']
            rules['comparative_selection_policy'] = 'latest_training_filing_with_exact_target_quarter_facts_not_best_numeric_match'
        receipt = temporal.freeze(plan, data, rules)
        temporal.save(args.out / (ticker + '-freeze.json'), receipt)
        temporal.replay(receipt, data)
        pack = temporal.training_pack(plan, data)
        temporal.save(local / (ticker + '-training.json'), pack)
        training = pack['raw_filings']
        records = training + temporal.select_records(plan, data, 'holdout')
        engine = temporal.runner()
        bridge = derive_nee_fpl_q4(training) if ticker == 'NEE' else None
        quarters = {}
        for index, record in enumerate(records):
            end = record['filing']['reportDate']
            previous = [f for r in records[:index] for f in r['facts']]
            q, _ = engine.quarter(record['facts'], end, record['filing']['form'], previous)
            quarters[end] = q
        detailed = []
        latest = plan['holdout'][0]['period_end']
        for p in capture['captures']:
            date = futu_fiscal_date(ticker, p['period'])
            facts = quarters.get(date, [])
            for category, raw, share in p['rows']:
                before = review_observation(ticker, category, raw, facts)
                after = before
                if ticker == 'NEE' and date == '2024-12-31' and category == 'Florida Power & Light Company (FPL)' and bridge:
                    after = review_observation(ticker, category, raw, facts + [bridge])
                    after['requires_reviewed_scope_bridge'] = True
                comparative = latest_training_comparative(training, date) if ticker == 'WMT' and date != latest else None
                comparative_facts = comparative['facts'] if comparative else facts
                after_comparative = review_observation(ticker, category, raw, comparative_facts) if ticker == 'WMT' else after
                residual = None
                residual_before = None
                if ticker == 'WMT' and category == '企業和支持':
                    residual_before = corporate_residual(facts)
                    residual = corporate_residual(comparative_facts)
                    if residual['value'] is not None:
                        value, tolerance = amount(raw, 1)
                        residual['reference_matches_reported_residual'] = abs(residual['value'] - value) <= tolerance
                detailed.append({'date': date, 'phase': 'latest_retrospective' if date == latest else 'historical_training',
                    'category': category, 'raw': raw, 'share': share, 'before': before, 'after': after, 'residual': residual})
                detailed[-1].update(after_training_cutoff_comparative=after_comparative,
                    comparative_source_filing=comparative['source_filing'] if comparative else None,
                    residual_before_comparative=residual_before)
        temporal.save(local / (ticker + '-detailed.json'), {'rows': detailed, 'scope_bridge': bridge})
        summaries.append({'ticker': ticker, 'strict_blind_test': False, 'exposure_status': 'contaminated',
            'before_scope_review': dict(Counter(r['before']['status'] for r in detailed)),
            'after_scope_review': dict(Counter(r['after']['status'] for r in detailed)),
            'after_training_cutoff_comparative': dict(Counter(r['after_training_cutoff_comparative']['status'] for r in detailed)),
            'matching_residual_candidates_not_certified': sum(bool((r['residual'] or {}).get('reference_matches_reported_residual')) for r in detailed),
            'residual_operand_coverage_before_comparatives': sum((r['residual_before_comparative'] or {}).get('value') is not None for r in detailed),
            'residual_candidates_missing_operands': sum((r['residual'] or {}).get('status') == 'missing_or_conflicting_operand' for r in detailed),
            'phase_counts': dict(Counter(r['phase'] for r in detailed)),
            'latest_scope_review': dict(Counter(r['after']['status'] for r in detailed if r['phase'] == 'latest_retrospective')),
            'comparative_filing_dates_checked_before_cutoff': all(
                not r['comparative_source_filing'] or r['comparative_source_filing']['filingDate'] <= plan['cutoff']['filing_date']
                for r in detailed),
            'independent_human_review': False, 'full_disclosure_accuracy_measured': False})
    temporal.save(args.out / 'summary.json', {'companies': summaries,
        'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'dependency_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in ['scripts/review_vendor_evidence.py', 'scripts/compare_vendor_cohort.py']},
        'input_sha256': hashlib.sha256(capture_path.read_bytes()).hexdigest(),
        'sec_raw_download_status': 'WMT latest single GET returned 403; no retry; later downloads not attempted',
        'NEE_primary_text_review': 'Normal public SEC text read separately for the two historical filings; not a raw HTML download or hash verification.'})
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
