#!/usr/bin/env python3
"""接合 Chevron 2024 年兩種完整披露 scope；仍要求固定參考的完整八季。"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

import temporal_eval as temporal
from cohort_rule_audit import resolve, compare_value
from cohort_rule_catalog import catalog, R, S, C, P, G, OP
from evaluate_eight_quarter_status import assess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'research/completed-parser-repairs-20261104'
SOURCE = 'https://www.sec.gov/Archives/edgar/data/93410/000009341024000059/cvx-20240930.htm'


def normalize_old_scope(record):
    result = copy.deepcopy(record)
    if result['filing']['reportDate'] != '2024-09-30':
        return result
    for f in result['facts']:
        if (f['concept'] != R or f.get('enddate') != '2024-09-30'
                or f.get('startdate') not in ('2024-01-01', '2024-07-01')):
            continue
        dims = f['dimensions']; mapped = None
        for member in ('Upstream', 'Downstream'):
            for geo in ('country:US', 'us-gaap:NonUsMember'):
                if dims == {S: 'cvx:' + member + 'Member', G: geo, C: OP, P: 'us-gaap:OilAndGasMember'}:
                    mapped = {S: 'cvx:' + member + 'SegmentMember', G: geo, C: OP}
        if dims == {C: 'us-gaap:CorporateNonSegmentMember', P: 'us-gaap:OilAndGasMember'}:
            mapped = {S: 'us-gaap:AllOtherSegmentsMember', C: OP}
        if mapped is not None:
            f.update(dimensions=mapped, original_dimensions=copy.deepcopy(dims),
                normalization_rule_id='cvx-2024-gross-sales-reported-rows', normalization_source=SOURCE)
    # 舊表最下方的兩個 GeographyEliminations 列是全球抵銷的 US／non-US 拆分。
    # 與分部內的 IntersegmentElimination 列分開，避免把相同抵銷加總兩次。
    for start in ('2024-01-01', '2024-07-01'):
        operands = []
        for geo in ('country:US', 'us-gaap:NonUsMember'):
            hits = [f for f in result['facts'] if f['concept'] == R and f.get('startdate') == start
                and f.get('enddate') == '2024-09-30' and f.get('unit') == 'iso4217:USD'
                and f['dimensions'] == {C: 'srt:GeographyEliminationsMember', G: geo, P: 'us-gaap:OilAndGasMember'}]
            if not hits or len({f['value'] for f in hits}) != 1:
                break
            operands.append(hits[0])
        if len(operands) == 2:
            f = copy.deepcopy(operands[0])
            f.update(dimensions={C: 'us-gaap:IntersegmentEliminationMember'}, value=sum(o['value'] for o in operands),
                aggregation_evidence=operands, normalization_rule_id='cvx-2024-global-geographical-eliminations',
                normalization_source=SOURCE)
            result['facts'].append(f)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    baseline = temporal.load(BASE / 'extended-completion-status.json')
    company = next(c for c in baseline['companies'] if c['ticker'] == 'CVX')
    receipt = temporal.load(BASE / 'CVX-freeze.json')
    data = temporal.checked_data(receipt['plan'], ROOT / receipt['plan']['baseline_file'])
    temporal.verify_freeze(receipt, data)
    records = [normalize_old_scope(r) for r in data['raw_filings']]
    annual = next(r for r in records if r['filing']['reportDate'] == '2024-12-31')
    prior = next(r for r in records if r['filing']['reportDate'] == '2024-09-30')
    facts, conflicts = temporal.runner().quarter(annual['facts'], '2024-12-31', '10-K', prior['facts'])
    rows = temporal.load(ROOT / company['local_detail_path'])
    for row in rows:
        if row['source'] == 'futu' and row['kind'] == 'Q' and row['sec_period_end'] == '2024-12-31':
            old = copy.deepcopy(row)
            selected = resolve(catalog()['CVX']['futu'].get(row['category']), facts, conflicts)
            row.update(compare_value(row['raw'], row['scale'], selected), prior_result=old,
                role='bounded_reported_gross_sales_scope_bridge')
    local = ROOT / 'data/vendor/local/cohort-adjudication-20261104' / args.out.name
    local.mkdir(parents=True, exist_ok=False)
    detail = local / 'CVX-repaired.json'
    temporal.save(detail, json.loads(json.dumps(rows, default=str)))
    result = assess(rows, company['target_periods'], 'futu')
    result.update(ticker='CVX', source_url=SOURCE,
        annual_source_url='https://www.sec.gov/Archives/edgar/data/93410/000009341025000009/cvx-20241231.htm',
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        local_detail_path=str(detail.relative_to(ROOT)), local_detail_sha256=hashlib.sha256(detail.read_bytes()).hexdigest(),
        base_status_sha256=hashlib.sha256((BASE / 'extended-completion-status.json').read_bytes()).hexdigest(),
        note='保存的五季二十項已可程式產出並相同；仍缺三季固定參考，總數維持二十／三十。')
    args.out.mkdir(parents=True, exist_ok=False)
    temporal.save(args.out / 'CVX-status.json', result)
    print(json.dumps({k: result[k] for k in ['status', 'cell_statuses', 'fail_reasons']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
