#!/usr/bin/env python3
"""Compare local Apple DOM observations to frozen SEC candidate evidence offline."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

CATEGORIES = {
    'iPhone': 'aapl:IPhoneMember',
    'Services': 'us-gaap:ServiceMember',
    'Mac': 'aapl:MacMember',
    'Wearables, Home and Accessories': 'aapl:WearablesHomeandAccessoriesMember',
    'iPad': 'aapl:IPadMember',
}
FUTU_CATEGORIES = {
    'iPhone ®': 'iPhone', '服務': 'Services', 'Mac ®': 'Mac',
    '可穿戴設備、家居和配件': 'Wearables, Home and Accessories', 'iPad ®': 'iPad',
}
# Apple-specific reviewed alignment; vendor display dates are not fiscal end dates.
PERIODS = {
    '2026-09-30': ('2026-09-26', '2026/Q4'),
    '2026-06-30': ('2026-06-27', '2026/Q3'),
    '2026-03-31': ('2026-03-28', '2026/Q2'),
    '2025-12-31': ('2025-12-27', '2026/Q1'),
    '2025-09-30': ('2025-09-27', '2025/Q4'),
    '2025-06-30': ('2025-06-28', '2025/Q3'),
    '2025-03-31': ('2025-03-29', '2025/Q2'),
    '2024-12-31': ('2024-12-28', '2025/Q1'),
}
REVENUE = 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'
AXIS = 'srt:ProductOrServiceAxis'


def one_value(facts):
    values = {fact['value'] for fact in facts}
    if len(values) != 1:
        raise ValueError('Missing or conflicting SEC evidence')
    return values.pop()


def compare(capture_dir, sec_path):
    stock_path = capture_dir / 'stockanalysis-dom.json'
    futu_path = capture_dir / 'futu-dom.json'
    stock = json.loads(stock_path.read_text())
    futu = json.loads(futu_path.read_text())
    sec = json.loads(sec_path.read_text())
    if stock['basis'] != 'Quarterly' or stock['currency'] != 'USD' or futu['currency'] != 'USD':
        raise ValueError('Expected quarterly Apple USD observations')
    if stock['columns'] != ['display_date', *CATEGORIES]:
        raise ValueError('Unexpected Stock Analysis capture schema')
    if len(stock['rows']) != 8 or {row[0] for row in stock['rows']} != set(PERIODS):
        raise ValueError('Expected the eight reviewed Apple display periods')
    if sec['ticker'] != 'AAPL':
        raise ValueError('SEC evidence must be for AAPL')
    futu_periods = {}
    for capture in futu['captures']:
        period = capture['period']
        if period in futu_periods or period not in {p[1] for p in PERIODS.values()}:
            raise ValueError('Duplicate or unreviewed Futu quarter')
        values = {}
        for raw_category, raw_value, raw_share in capture['rows']:
            category = FUTU_CATEGORIES[raw_category]
            if category in values or not raw_value.endswith('億') or not raw_share.endswith('%'):
                raise ValueError('Unexpected Futu capture schema')
            values[category] = (Decimal(raw_value[:-1].replace(',', '')) * 100_000_000,
                                Decimal(raw_share[:-1]))
        if set(values) != set(CATEGORIES):
            raise ValueError('Futu quarter must contain all five reviewed categories')
        futu_periods[period] = values

    rows = []
    missing = []
    totals_matched = 0
    for display_date, *values in stock['rows']:
        fiscal_end, label = PERIODS[display_date]
        quarter = next(q for q in sec['quarter_results'] if q['report_date'] == fiscal_end)
        if quarter['status'] != 'processed' or len(values) != 5:
            raise ValueError('Incomplete quarter evidence')
        total = one_value([f for f in quarter['candidate_totals'] if f['concept'] == REVENUE])
        total_match = sum(values) == total
        totals_matched += total_match
        if label not in futu_periods:
            missing.append(label)
        for category, value in zip(CATEGORIES, values):
            facts = [f for f in quarter['facts'] if f['concept'] == REVENUE
                     and f.get('unit') == 'iso4217:USD'
                     and f.get('dimensions') == {AXIS: CATEGORIES[category]}]
            sec_value = one_value(facts)
            row = {'display_date': display_date, 'fiscal_end': fiscal_end,
                   'fiscal_label': label, 'category': category,
                   'stockanalysis_usd': value, 'sec_usd': sec_value,
                   'stockanalysis_sec_equal': value == sec_value,
                   'sec_derivation': facts[0]['derivation'],
                   'sec_source_url': facts[0]['source_url'],
                   'sec_context_id': facts[0].get('context_id'),
                   'futu_observed': label in futu_periods}
            if label in futu_periods:
                futu_value, share = futu_periods[label][category]
                row.update(futu_usd=int(futu_value), futu_sec_equal=futu_value == sec_value,
                           futu_stockanalysis_equal=futu_value == value,
                           futu_share_consistent_with_sec_total=(
                               abs(share - Decimal(sec_value) * 100 / total) <= Decimal('0.005')))
            rows.append(row)
    summary = {
        'issuer': 'AAPL', 'comparison_basis': 'reviewed product/service categories and Apple fiscal periods',
        'sec_evidence_as_of': sec['as_of'],
        'stockanalysis_quarters_observed': len(stock['rows']),
        'stockanalysis_values_compared': len(rows),
        'stockanalysis_values_equal_to_saved_sec': sum(r['stockanalysis_sec_equal'] for r in rows),
        'stockanalysis_quarter_sums_equal_to_saved_sec_totals': totals_matched,
        'futu_quarters_observed': len(futu_periods),
        'futu_values_compared': sum(r['futu_observed'] for r in rows),
        'futu_values_equal_to_saved_sec': sum(r.get('futu_sec_equal', False) for r in rows),
        'futu_values_equal_to_stockanalysis': sum(r.get('futu_stockanalysis_equal', False) for r in rows),
        'futu_shares_within_half_display_step_of_sec': sum(r.get('futu_share_consistent_with_sec_total', False) for r in rows),
        'futu_missing_target_quarter_options': missing,
        'native_csv_download_verified': False,
        'fresh_sec_html_reparse_performed': False,
        'cross_company_accuracy_measured': False,
        'inputs': [{'filename': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in [stock_path, futu_path, sec_path]],
    }
    return {'summary': summary, 'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-dir', type=Path, required=True)
    parser.add_argument('--sec-evidence', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.capture_dir, args.sec_evidence)
    output = args.capture_dir / 'comparison.json'
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['summary'], indent=2))


if __name__ == '__main__':
    main()
