#!/usr/bin/env python3
"""歷史來源建立明確規則，分開重播歷史及已接觸最新季；第三方逐筆結果只留本機。"""
import argparse
from collections import Counter
import datetime as dt
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from compare_vendor_cohort import ROOT, PRIVATE, amount

REVENUE = 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'
SEGMENT = 'us-gaap:StatementBusinessSegmentsAxis'
CONSOLIDATION = 'srt:ConsolidationItemsAxis'
OPERATING = 'us-gaap:OperatingSegmentsMember'


def definitions(ticker):
    def segment(member):
        return {SEGMENT: member, CONSOLIDATION: OPERATING}
    if ticker == 'TSLA':
        rows = [(key, REVENUE, {'srt:ProductOrServiceAxis': 'tsla:' + member}) for key, member in (
            ('product-auto', 'AutomotiveRevenuesMember'), ('product-energy', 'EnergyGenerationAndStorageMember'),
            ('product-services', 'ServicesAndOtherMember'))]
        rows += [(key, 'us-gaap:Revenues', {SEGMENT: 'tsla:' + member}) for key, member in (
            ('segment-auto', 'AutomotiveSegmentMember'), ('segment-energy', 'EnergyGenerationAndStorageSegmentMember'))]
        rows += [('total', 'us-gaap:Revenues', {})]
        aggregates = {'products-total': ['product-auto', 'product-energy', 'product-services'],
                      'segments-total': ['segment-auto', 'segment-energy'],
                      'automotive-including-services': ['product-auto', 'product-services']}
        checks = {'products-total': 'total', 'segments-total': 'total', 'automotive-including-services': 'segment-auto'}
    elif ticker == 'NVDA':
        rows = [(key, 'us-gaap:Revenues', segment('nvda:' + member)) for key, member in (
            ('compute', 'ComputeAndNetworkingSegmentMember'), ('graphics', 'GraphicsSegmentMember'))]
        rows += [('total', 'us-gaap:Revenues', {})]
        aggregates, checks = {'segments-total': ['compute', 'graphics']}, {'segments-total': 'total'}
    elif ticker == 'LIN':
        rows = [(key, REVENUE, segment(member)) for key, member in (
            ('americas', 'lin:AmericasSegmentMember'), ('emea', 'lin:EMEASegmentMember'),
            ('apac', 'lin:APACSegmentMember'), ('engineering', 'lin:EngineeringSegmentMember'),
            ('other', 'us-gaap:CorporateAndOtherMember'))]
        rows += [('total', REVENUE, {}), ('operating-total', REVENUE, {CONSOLIDATION: OPERATING})]
        aggregates = {'segments-total': ['americas', 'emea', 'apac', 'engineering', 'other']}
        checks = {'segments-total': 'total'}
    elif ticker == 'CMCSA':
        rows = [(key, REVENUE, segment('cmcsa:' + member)) for key, member in (
            ('residential', 'ResidentialConnectivityAndPlatformsSegmentMember'),
            ('business', 'BusinessServicesConnectivitySegmentMember'), ('media', 'MediaSegmentMember'),
            ('studios', 'StudiosSegmentMember'), ('parks', 'ThemeParksSegmentMember'))]
        rows += [('other', REVENUE, {CONSOLIDATION: 'us-gaap:CorporateNonSegmentMember'}),
                 ('eliminations', REVENUE, {CONSOLIDATION: 'srt:ConsolidationEliminationsMember'}), ('total', REVENUE, {})]
        aggregates = {'connectivity': ['residential', 'business'], 'content': ['media', 'studios', 'parks'],
                      'segments-net-total': ['residential', 'business', 'media', 'studios', 'parks', 'other', 'eliminations']}
        checks = {'segments-net-total': 'total'}
    else:
        raise ValueError('Issuer rules have not been reviewed')
    selectors = [{'id': kind + ':' + key, 'period_kind': kind, 'concept': concept, 'dimensions': dimensions,
                  'unit': 'iso4217:USD', 'semantic_basis': ticker + ':' + key}
                 for kind in ('Q', 'FY') for key, concept, dimensions in rows]
    result = {'version': ticker.lower() + '-historical-scope-v2',
            'development_evidence': '歷史 training accession 的概念、完整維度及原列；最新期早已接觸，僅能回溯。',
            'selectors': selectors, 'aggregates': aggregates, 'reconciliations': checks}
    if ticker == 'NVDA':
        result['member_aliases'] = [{'id': 'nvda-fy2025-' + key, 'concept': 'us-gaap:Revenues',
            'original_dimensions': segment('nvda:' + old), 'dimensions': segment('nvda:' + new),
            'report_dates': ['2024-10-27'],
            'evidence_urls': ['https://www.sec.gov/Archives/edgar/data/1045810/000104581024000316/nvda-20241027.htm',
                              'https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm'],
            'review_basis': '兩份歷史申報均列同名兩營運分部；只在指定舊申報與完整維度接合，並非通用名稱模糊匹配。'}
            for key, old, new in [('compute', 'ComputeAndNetworkingMember', 'ComputeAndNetworkingSegmentMember'),
                                  ('graphics', 'GraphicsMember', 'GraphicsSegmentMember')]]
    return result


def normalize_history(records, rules):
    result = []
    for record in records:
        facts = []
        for original in record['facts']:
            fact = dict(original)
            for rule in rules.get('member_aliases', []):
                if (record['filing']['reportDate'] in rule['report_dates']
                    and fact.get('concept') == rule['concept']
                    and fact.get('dimensions') == rule['original_dimensions']):
                    fact.update(original_dimensions=dict(fact['dimensions']), dimensions=dict(rule['dimensions']),
                                normalization_rule_id=rule['id'])
            facts.append(fact)
        result.append({**record, 'facts': facts})
    return result


MAPPINGS = {
    'TSLA': {'stockanalysis': {'Auto': 'product-auto', 'Energy and Storage': 'product-energy', 'Services and Other': 'product-services'},
             'futu': {'汽車分部': 'segment-auto', 'Energy generation and storage segment': 'segment-energy'}},
    'NVDA': {'stockanalysis': {'Compute and Networking': 'compute', 'Graphics': 'graphics'},
             'futu': {'計算與網絡': 'compute', '繪圖': 'graphics'}},
    'LIN': {'stockanalysis': {'Americas': 'americas', 'EMEA': 'emea', 'APAC': 'apac', 'Engineering': 'engineering', 'Other': 'other'},
            'futu': {'美洲': 'americas', 'Europe, Middle East and Africa (EMEA)': 'emea', '亞太地區(APAC)': 'apac', '工程': 'engineering', '其他': 'other'}},
    'CMCSA': {'stockanalysis': {'Connectivity and Platforms': 'connectivity', 'Content and Experiences': 'content'},
              'futu': {'Residential Connectivity & Platforms': 'residential', 'Business Services Connectivity': 'business',
                       '媒體': 'media', '演播室': 'studios', '主題公園': 'parks', '其他收入': 'other', '抵銷': 'eliminations'}},
}


def aggregate(operands):
    if any(o['status'] != 'observed' for o in operands):
        return {'status': 'missing_or_ambiguous_operand', 'value': None, 'facts': []}
    return {'status': 'observed', 'value': sum(o['value'] for o in operands),
            'facts': [f for o in operands for f in o['facts']]}


def select(facts, conflicts, rules, kind):
    selected = {}
    for selector in rules['selectors']:
        if selector['period_kind'] != kind:
            continue
        def matches(f):
            return all(f.get(k) == selector[k] for k in ('concept', 'unit', 'dimensions'))
        found = [f for f in facts if matches(f)]
        conflicting = any(matches(f) for group in conflicts for f in group)
        status = 'ambiguous' if conflicting or len(found) > 1 else 'observed' if found else 'parser_missing'
        selected[selector['id'].split(':', 1)[1]] = {'status': status,
            'value': found[0]['value'] if status == 'observed' else None, 'facts': found}
    for key, operands in rules['aggregates'].items():
        selected[key] = aggregate([selected[o] for o in operands])
    return selected


def period_facts(records, rules):
    engine = temporal.runner()
    out = {}
    for index, record in enumerate(records):
        filing = record['filing']
        previous = [f for r in records[:index] for f in r['facts']]
        q, conflicts = engine.quarter(record['facts'], filing['reportDate'], filing['form'], previous)
        out[('Q', filing['reportDate'])] = select(q, conflicts, rules, 'Q')
        if filing['form'] == '10-K':
            annual, conflicts = engine.dedupe([f for f in record['facts']
                if f.get('enddate') == filing['reportDate'] and 350 <= engine.days(f) <= 380])
            out[('FY', filing['reportDate'])] = select(annual, conflicts, rules, 'FY')
    return out


def reference_result(raw, scale, selected):
    value, tolerance = amount(raw, scale)
    if value is None:
        status = 'reference_missing'
    elif selected is None:
        status = 'period_or_definition_unmapped'
    elif selected['status'] != 'observed':
        status = selected['status']
    else:
        error = selected_error(selected)
        gap = abs(Decimal(selected['value']) - value)
        if gap == 0:
            status = 'matches_exact_reviewed_scope'
        elif error is None:
            status = 'sec_precision_unknown'
        else:
            status = 'matches_precision_reviewed_scope' if gap <= tolerance + error else 'differs_reviewed_scope'
    return {'status': status, 'reference_usd': str(value) if value is not None else None,
            'absolute_tolerance_usd': str(tolerance), 'selected': selected}


def fact_error(fact):
    if fact.get('derivation') == 'annual_minus_nine_months':
        errors = [fact_error(fact[k]) for k in ('annual_evidence', 'nine_month_evidence')]
        return None if None in errors else sum(errors)
    decimals = fact.get('decimals')
    if decimals == 'INF':
        return Decimal(0)
    if decimals is None:
        return None
    return Decimal(10) ** -int(decimals) / 2


def selected_error(selected):
    errors = [fact_error(f) for f in selected['facts']]
    return None if None in errors else sum(errors, Decimal(0))


def reconcile(left, right):
    if any(x['status'] != 'observed' for x in (left, right)):
        return 'missing_or_ambiguous_operand'
    gap = abs(left['value'] - right['value'])
    if gap == 0:
        return 'matches_exact'
    errors = [selected_error(x) for x in (left, right)]
    if None in errors:
        return 'precision_unknown'
    return 'within_reported_precision' if gap <= sum(errors) else 'differs'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--without-member-bridges', action='store_true')
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Choose a fresh output directory')
    args.out.mkdir(parents=True)
    local = PRIVATE / 'historical-rules-20261104'
    captures = {}
    for path in (PRIVATE / 'cohort-20261104').glob('batch*.json'):
        for capture in temporal.load(path):
            captures[capture['ticker']] = (path, capture)
    futu_path = local / 'futu-observations.json'
    futu = {c['ticker']: c for c in temporal.load(futu_path)}
    tv_path = local / 'tradingview-summary.json'
    tv = {c['ticker']: c for c in temporal.load(tv_path)['observations']}
    plans = {p['ticker']: p for p in temporal.load(ROOT / 'research/temporal-evaluation/cohort-plans.json')}
    private_dir = local / args.out.name
    private_dir.mkdir(exist_ok=False)
    summaries = []
    for ticker in MAPPINGS:
        plan = plans[ticker]
        data = temporal.checked_data(plan, ROOT / plan['baseline_file'])
        plan['exposure'] = {'seen_during_development': 'yes', 'evidence': ['docs/vendor/training-test-split.json'],
                            'note': '最新基準期已用於本機診斷；這次規則分開使用歷史 accession，但不能消除既有洩漏。'}
        for ref in plan['references']:
            seen = ref['source'] == 'stockanalysis' or (ref['source'] == 'futu' and ticker != 'LIN')
            ref.update(seen_during_development='yes' if seen else 'unknown',
                       evidence=['docs/vendor/training-test-split.json'] if ref['source'] == 'stockanalysis'
                                else [str(futu_path.relative_to(ROOT))] if seen else [])
        rules = definitions(ticker)
        if args.without_member_bridges:
            rules.pop('member_aliases', None)
            rules['version'] += '-without-member-bridges'
        receipt = temporal.freeze(plan, data, rules)
        temporal.save(args.out / (ticker + '-freeze.json'), receipt)
        prediction = temporal.replay(receipt, data)
        pack = temporal.training_pack(plan, data)
        temporal.save(private_dir / (ticker + '-training-pack.json'), pack)
        normalized = normalize_history(pack['raw_filings'], rules)
        temporal.save(private_dir / (ticker + '-normalized-training.json'), normalized)
        periods = period_facts(normalized, rules)
        hold = temporal.select_records(plan, data, 'holdout')
        for kind in ('Q', 'FY'):
            if kind == 'FY' and hold[0]['filing']['form'] != '10-K':
                continue
            selected = {r['selector_id'].split(':', 1)[1]: {k: r[k] for k in ('status', 'value', 'facts')}
                        for r in prediction['results'] if r['period_kind'] == kind}
            if selected:
                for key, operands in rules['aggregates'].items():
                    selected[key] = aggregate([selected[o] for o in operands])
                periods[(kind, hold[0]['filing']['reportDate'])] = selected
        newest = plan['holdout'][0]['period_end']
        comparisons = []
        source_path, sa = captures[ticker]
        for label, *values in sa['rows']:
            date = dt.datetime.strptime(label, '%b %d, %Y').date().isoformat()
            for category, raw in zip(sa['columns'][1:], values):
                key = MAPPINGS[ticker]['stockanalysis'].get(category)
                selected = periods.get(('Q', date), {}).get(key)
                comparisons.append({'source': 'stockanalysis', 'kind': 'Q', 'date': date, 'category': category,
                    'phase': 'latest_retrospective' if date == newest else 'historical_training',
                    **reference_result(raw, sa['numeric_scale'], selected)})
                if ticker == 'CMCSA':
                    comparisons[-1]['mapping_review'] = 'proposed_aggregation_not_certified_vendor_definition'
                    comparisons[-1]['status'] = comparisons[-1]['status'].replace('reviewed_scope', 'proposed_aggregation')
        for capture in futu[ticker]['captures']:
            label = capture['period']
            kind = 'FY' if label.endswith('/FY') else 'Q'
            if ticker == 'NVDA':
                date = {'2027/Q2': '2026-07-26', '2027/Q1': '2026-04-26', '2026/FY': '2026-01-25'}[label]
            elif kind == 'FY':
                date = label[:4] + '-12-31'
            else:
                year, quarter = int(label[:4]), int(label[-1])
                import calendar
                month = quarter * 3
                date = dt.date(year, month, calendar.monthrange(year, month)[1]).isoformat()
            for category, raw, share in capture['rows']:
                key = MAPPINGS[ticker]['futu'].get(category)
                comparisons.append({'source': 'futu', 'kind': kind, 'date': date, 'category': category, 'share': share,
                    'phase': 'latest_retrospective' if date == newest and kind == 'Q' else 'historical_training',
                    **reference_result(raw, 1, periods.get((kind, date), {}).get(key))})
        reconciliations = []
        for (kind, date), selected in periods.items():
            if kind == 'Q' and date not in {q['report_date'] for q in data['quarter_results']}:
                continue
            for group, total in rules['reconciliations'].items():
                left, right = selected[group], selected[total]
                status = reconcile(left, right)
                reconciliations.append({'kind': kind, 'date': date, 'group': group, 'total': total, 'status': status,
                                        'left': left, 'right': right})
        tv_candidates = []
        if ticker in tv:
            top_key = 'segment-auto' if ticker == 'TSLA' else 'compute'
            for (kind, date), selected in periods.items():
                if kind != 'FY':
                    continue
                pair = [reference_result(tv[ticker]['total'], 1, selected.get('total')),
                        reference_result(tv[ticker]['top_value'], 1, selected.get(top_key))]
                tv_candidates.append({'candidate_fiscal_end': date, 'explicit_vendor_period_verified': False,
                    'both_numeric_checks_match': all(r['status'].startswith('matches_') for r in pair),
                    'checks': pair})
        temporal.save(private_dir / (ticker + '-detailed.json'), {'comparisons': comparisons,
            'reconciliations': reconciliations, 'tradingview_annual_period_candidates': tv_candidates})
        counts = []
        for source in ('stockanalysis', 'futu'):
            for phase in ('historical_training', 'latest_retrospective'):
                for kind in ('Q', 'FY'):
                    rows = [r for r in comparisons if (r['source'], r['phase'], r['kind']) == (source, phase, kind)]
                    if rows:
                        counts.append({'source': source, 'phase': phase, 'kind': kind, 'observations': len(rows),
                                       'statuses': dict(Counter(r['status'] for r in rows))})
        summaries.append({'ticker': ticker, 'exposure_status': prediction['exposure_status'], 'strict_blind_test': False,
            'selector_count': len(rules['selectors']), 'aggregation_rule_count': len(rules['aggregates']),
            'member_alias_rule_count': len(rules.get('member_aliases', [])),
            'normalized_training_sha256': temporal.digest(temporal.canonical(normalized)),
            'reference_comparisons': counts, 'reconciliations': dict(Counter(r['status'] for r in reconciliations)),
            'tradingview': {'status': 'annual_summary_period_unverified' if ticker in tv else 'web_tool_retrieval_unavailable',
                'paired_numeric_candidate_fiscal_ends': [r['candidate_fiscal_end'] for r in tv_candidates if r['both_numeric_checks_match']],
                'complete_annual_composition_compared': False, 'accuracy_measured': False},
            'source_evidence': [{'path': str(p.relative_to(ROOT)), 'sha256': temporal.digest(p.read_bytes())}
                for p in (source_path, futu_path, tv_path)],
            'disclosure_recall_measured': False, 'cross_company_accuracy_measured': False})
    temporal.save(args.out / 'summary.json', {'study_mode': 'retrospective_scope_specific',
        'execution_code_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ['scripts/historical_rule_experiments.py', 'scripts/compare_vendor_cohort.py']},
        'companies': summaries})
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
