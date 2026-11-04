#!/usr/bin/env python3
"""依已人工查核的 SEC 定義重播第二輪比對；原始結果僅能寫入本機忽略目錄。"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from compare_vendor_cohort import PRIVATE, ROOT, amount, futu_fiscal_date

SEGMENT = 'us-gaap:StatementBusinessSegmentsAxis'
CONSOLIDATION = 'srt:ConsolidationItemsAxis'
OPERATING = 'us-gaap:OperatingSegmentsMember'


def reviewed_selector(ticker, category):
    """僅列入已檢查語意的範圍；其餘分類保留未判定。"""
    if ticker == 'NEE':
        concept = 'us-gaap:RegulatedAndUnregulatedOperatingRevenue'
        if category == 'Florida Power & Light Company (FPL)':
            base = {SEGMENT: 'nee:FloridaPowerLightCompanyMember', CONSOLIDATION: OPERATING}
            return concept, [base, {**base, 'dei:LegalEntityAxis': 'nee:FloridaPowerLightCompanyMember'}]
        if category == 'NextEra Energy Resources (NEER)':
            return concept, [{SEGMENT: 'nee:NEERSegmentMember', CONSOLIDATION: OPERATING}]
        if category == '公司和其他':
            return concept, [{CONSOLIDATION: 'nee:CorporateAndEliminationsMember'}]
    elif ticker == 'BRK-B':
        members = {
            '保險': 'BerkshireHathawayInsuranceGroupMember',
            '製造業': 'ManufacturingBusinessesMember', 'Pilot': 'PilotTravelCentersLLCMember',
            'McLane': 'McLaneCompanyMember', '服務和零售': 'ServiceAndRetailingBusinessesMember',
            'Berkshire Hathaway Energy (BHE)': 'BerkshireHathawayEnergyCompanyMember',
            'Burlington Northern Santa Fe, LLC (BNSF)': 'BurlingtonNorthernSantaFeCorporationMember',
        }
        if category in members:
            return 'us-gaap:Revenues', [{SEGMENT: 'brka:' + members[category], CONSOLIDATION: OPERATING}]
        if category == '公司、抵銷和其他':
            return 'us-gaap:Revenues', [{CONSOLIDATION: 'brka:CorporateReconcilingItemsAndEliminationsMember'}]
    elif ticker == 'WMT':
        members = {'Walmart United States (U.S.)': 'WalmartUSMember', '沃爾瑪國際': 'WalmartInternationalMember',
                   "Sam's Club United States (U.S.)": 'SamsClubUSMember'}
        if category in members:
            return 'us-gaap:Revenues', [{SEGMENT: 'wmt:' + members[category], CONSOLIDATION: OPERATING}]
    return None


def review_observation(ticker, category, raw, facts):
    rule = reviewed_selector(ticker, category)
    if rule is None:
        return {'status': 'undecided', 'reason': 'definition_not_reviewed'}
    concept, scopes = rule
    selected = [f for f in facts if f.get('concept') == concept and f.get('dimensions') in scopes
                and f.get('unit') in ('USD', 'iso4217:USD') and isinstance(f.get('value'), int)]
    if len({f['value'] for f in selected}) != 1:
        return {'status': 'undecided', 'reason': 'missing_or_conflicting_reviewed_scope'}
    value, tolerance = amount(raw, 1)
    if value is None:
        return {'status': 'source_missing', 'reason': 'missing_value'}
    if abs(selected[0]['value'] - value) > tolerance:
        return {'status': 'undecided', 'reason': 'reviewed_scope_value_differs', 'evidence': selected}
    derived = any(f.get('derivation') == 'annual_minus_nine_months' for f in selected)
    return {'status': 'needs_derivation' if derived else 'exact_match',
            'reason': 'reviewed_concept_dimensions_period_and_display_precision', 'evidence': selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captures', type=Path, required=True)
    parser.add_argument('--private-report', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    args = parser.parse_args()
    if not args.private_report.resolve().is_relative_to(PRIVATE.resolve()):
        raise ValueError('Detailed evidence must remain under ignored data/vendor/local/')
    private, summaries = [], []
    for capture in json.loads(args.captures.read_text()):
        ticker = capture['ticker']
        if capture.get('currency') != 'USD':
            raise ValueError('Only reviewed USD captures are supported')
        sec = json.loads(gzip.decompress((ROOT / 'research/sec-30-baseline-2026-11-04' / (ticker + '.json.gz')).read_bytes()))
        quarters = {q['report_date']: q for q in sec['quarter_results']}
        rows = []
        for period in capture['captures']:
            date = futu_fiscal_date(ticker, period['period'])
            for category, raw, _ in period['rows']:
                result = review_observation(ticker, category, raw, quarters.get(date, {}).get('facts', []))
                if date not in quarters:
                    result = {'status': 'undecided', 'reason': 'sec_baseline_period_unavailable'}
                rows.append({'sec_date': date, 'category': category, 'raw': raw, **result})
        private.append({'ticker': ticker, 'source_url': capture['source_url'], 'observations': rows})
        summaries.append({'ticker': ticker, 'review_status_counts': dict(Counter(r['status'] for r in rows)),
                          'review_reason_counts': dict(Counter(r['reason'] for r in rows)),
                          'full_latest_eight_semantically_verified': False})
    with args.private_report.open('x') as stream:
        json.dump(private, stream, ensure_ascii=False, indent=2)
    with args.summary.open('x') as stream:
        json.dump({'scope': 'reviewed_selected_definitions_not_cross_company_accuracy',
                   'input_sha256': hashlib.sha256(args.captures.read_bytes()).hexdigest(),
                   'companies': summaries}, stream, indent=2)
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
