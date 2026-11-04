#!/usr/bin/env python3
"""CVX net sales 另列核對；不改 gross 系列或八季完成數。"""
import argparse
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from cohort_rule_audit import resolve
from cohort_rule_catalog import R, S, G, leaf, rule
from enforce_sec_primary_source import selected_is_sec

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    'upstream_us': ('cvx:UpstreamSegmentMember', 'country:US'),
    'upstream_international': ('cvx:UpstreamSegmentMember', 'us-gaap:NonUsMember'),
    'downstream_us': ('cvx:DownstreamSegmentMember', 'country:US'),
    'downstream_international': ('cvx:DownstreamSegmentMember', 'us-gaap:NonUsMember'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select_net_sales(facts, conflicts=()):
    # net 列沒有 ConsolidationItemsAxis；不可取 OperatingSegmentsMember 的 gross 列。
    result = {label: resolve(rule(leaf(R, {S: member, G: geo})), facts, conflicts)
              for label, (member, geo) in LABELS.items()}
    result['all_other_net'] = resolve(rule(leaf(R, {S: 'us-gaap:AllOtherSegmentsMember'})), facts, conflicts)
    result['consolidated_sales'] = resolve(rule(leaf(R, {})), facts, conflicts)
    if not all(selected_is_sec(s) for s in result.values()):
        raise ValueError('Incomplete or non-SEC net sales scope')
    if sum(result[label]['value'] for label in [*LABELS, 'all_other_net']) != result['consolidated_sales']['value']:
        raise ValueError('CVX net sales do not reconcile to consolidated sales')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reported-reference', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    receipt_path = ROOT / 'research/cohort-rule-replay-20261104/CVX-freeze.json'
    receipt = temporal.load(receipt_path)
    baseline = ROOT / receipt['plan']['baseline_file']
    data = temporal.checked_data(receipt['plan'], baseline)
    temporal.verify_freeze(receipt, data)
    records = {r['filing']['reportDate']: r for r in data['raw_filings']}
    annual, prior = records['2025-12-31'], records['2025-09-30']
    outputs = {}
    for end, record, preceding in [('2025-09-30', prior, []), ('2025-12-31', annual, prior['facts'])]:
        facts, conflicts = temporal.runner().quarter(record['facts'], end, record['filing']['form'], preceding)
        outputs[end] = select_net_sales(facts, conflicts)
    comparisons = []
    if args.reported_reference:
        reported = temporal.load(args.reported_reference)
        if reported['reference_kind'] != 'cloud_reported_common_filing_upstream_not_independent':
            raise ValueError('Unreviewed reference provenance')
        if set(reported['periods_millions_usd']) != set(outputs):
            raise ValueError('Wrong reported reference periods')
        for end, values in reported['periods_millions_usd'].items():
            if set(values) != set(LABELS):
                raise ValueError('Incomplete reported reference categories')
            for label, value in values.items():
                comparisons.append({'period_end': end, 'category': label,
                    'matches_cloud_reported_common_source_value': outputs[end][label]['value'] == value * 1_000_000,
                    'locally_reparsed_company_Q3_reference': False, 'independent_quarter_validation': False})
    coverage_path = ROOT / 'research/remaining-sec-coverage-20261104/coverage.json'
    gross = next(c for c in temporal.load(coverage_path)['companies'] if c['ticker'] == 'CVX')
    result = {'ticker': 'CVX', 'cohort_OK_count_unchanged': 29, 'completion_status_unchanged': 'Fail',
        'scope': '抵銷後 Sales and Other Operating Revenues，分上游／下游與美國／國際；另列 All Other net 與合併營業收入。',
        'SEC_net_outputs': outputs,
        'existing_gross_outputs_unchanged': [q for q in gross['quarters'] if q['period_end'] in outputs],
        'cloud_reported_comparisons': comparisons, 'independent_quarter_validations_added': 0,
        'same_issuer_filing_upstream': True, 'blind_tests': 0,
        'baseline_path': str(baseline.relative_to(ROOT)), 'baseline_sha256': sha(baseline),
        'freeze_receipt_sha256': sha(receipt_path), 'gross_coverage_sha256': sha(coverage_path),
        'reported_reference_sha256': sha(args.reported_reference) if args.reported_reference else None,
        'code_sha256': sha(__file__)}
    if args.out.exists():
        raise FileExistsError(args.out)
    temporal.save(args.out, json.loads(json.dumps(result, default=str)))
    print(json.dumps({'SEC_net_quarters': 2, 'common_source_comparisons_match': sum(c['matches_cloud_reported_common_source_value'] for c in comparisons),
        'independent_quarter_validations_added': 0, 'cohort_OK_count_unchanged': 29}))


if __name__ == '__main__':
    main()
