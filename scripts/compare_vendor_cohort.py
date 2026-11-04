#!/usr/bin/env python3
"""Offline numeric candidate diagnostics; these checks do not certify category meaning."""
import argparse
import calendar
import collections
import datetime as dt
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / 'data/vendor/local'


def amount(raw, scale):
    if raw is None:
        return None, Decimal(0)
    if isinstance(raw, (int, float)):
        return Decimal(str(raw)) * scale, Decimal(0)
    text = raw.replace(',', '').strip()
    match = re.fullmatch(r'(-?\d+(?:\.\d+)?)(B|M|億|萬)', text)
    if not match:
        raise ValueError(f'Unsupported displayed amount: {raw!r}')
    number, unit = match.groups()
    factor = {'B': 10**9, 'M': 10**6, '億': 10**8, '萬': 10**4}[unit]
    # Futu trims trailing zeroes. Do not infer coarse precision from e.g. "6億".
    places = 2 if unit == '億' else 0 if unit == '萬' else len(number.partition('.')[2])
    return Decimal(number) * factor, Decimal(factor) / 2 / (10**places)


def normalized_label(label):
    text = label.split(':')[-1].replace('&', 'and').lower()
    text = re.sub(r'[^a-z0-9]', '', text)
    for suffix in ('member', 'segment', 'revenues', 'revenue', 'business'):
        if text.endswith(suffix):
            text = text[:-len(suffix)]
    return text


def diagnose_value(raw, scale, category, facts):
    value, tolerance = amount(raw, scale)
    if value is None:
        return {'status': 'source_missing', 'matches': []}
    matches = []
    for fact in facts:
        if fact.get('unit') not in ('USD', 'iso4217:USD') or not isinstance(fact.get('value'), int):
            continue
        if abs(Decimal(fact['value']) - value) > tolerance:
            continue
        matches.append({key: fact.get(key) for key in (
            'concept', 'unit', 'value', 'dimensions', 'context_id', 'source_url',
            'row_text', 'startdate', 'enddate', 'derivation')})
    hint = any(normalized_label(category) == normalized_label(member)
               for fact in matches for member in fact.get('dimensions', {}).values())
    return {'status': 'numeric_candidate' if matches else 'no_numeric_candidate',
            'vendor_usd': str(value), 'display_tolerance_usd': str(tolerance),
            'lexical_member_hint': hint, 'matches': matches,
            'semantic_mapping_certified': False}


def match_period(display_date, quarters):
    date = dt.datetime.strptime(display_date, '%b %d, %Y').date()
    ranked = sorted((abs((dt.date.fromisoformat(q['report_date']) - date).days),
                     q['report_date'], q) for q in quarters)
    if not ranked or ranked[0][0] > 45 or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]):
        return None, 'no_unique_nearby_period'
    gap, _, quarter = ranked[0]
    return quarter, 'exact_date' if gap == 0 else 'nearby_date_proposal' if gap <= 7 else 'fiscal_label_shift_proposal'


def reviewed_aggregation(ticker, category, raw, scale, facts):
    concept = 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'
    segment_axis = 'us-gaap:StatementBusinessSegmentsAxis'
    consolidation = {'srt:ConsolidationItemsAxis': 'us-gaap:OperatingSegmentsMember'}
    if ticker == 'CMCSA' and category == 'Connectivity and Platforms':
        expected = [{segment_axis: 'cmcsa:' + member, **consolidation} for member in (
            'ResidentialConnectivityAndPlatformsSegmentMember', 'BusinessServicesConnectivitySegmentMember')]
        rule = 'comcast_two_operating_segments_including_intersegment_revenue'
    elif ticker == 'CVX' and category in ('上游', '下游'):
        member = 'cvx:UpstreamSegmentMember' if category == '上游' else 'cvx:DownstreamSegmentMember'
        expected = [{segment_axis: member, 'srt:StatementGeographicalAxis': geo, **consolidation}
                    for geo in ('country:US', 'us-gaap:NonUsMember')]
        rule = 'chevron_us_plus_non_us_gross_sales_before_intersegment_eliminations'
    else:
        return None
    operands = []
    for dimensions in expected:
        selected = [f for f in facts if f.get('concept') == concept and f.get('dimensions') == dimensions
                    and f.get('unit') == 'iso4217:USD' and isinstance(f.get('value'), int)]
        if len(selected) != 1:
            return {'rule': rule, 'status': 'missing_or_ambiguous_operand'}
        operands.extend(selected)
    value, tolerance = amount(raw, scale)
    if value is None:
        return None
    total = sum(f['value'] for f in operands)
    return {'rule': rule, 'status': 'matches' if abs(Decimal(total) - value) <= tolerance else 'differs',
            'sum_usd': total, 'operands': operands}


def calendar_fiscal_date(label):
    match = re.fullmatch(r'(\d{4})/Q([1-4])', label)
    if not match:
        raise ValueError('Annual/FY or unknown period cannot enter a quarter comparison')
    year, quarter = map(int, match.groups())
    month = quarter * 3
    return dt.date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def check_capture(capture, sec):
    rows = []
    periods = []
    active_sets = []
    if not capture.get('quarterly_confirmed'):
        return {'ticker': capture['ticker'], 'source': 'stockanalysis',
                'status': capture['status'], 'quarters_observed': 0}, rows
    if capture.get('currency') != 'USD' or len(capture['rows']) > 8:
        raise ValueError('Expected at most eight USD quarter observations')
    columns = capture['columns'][1:]
    for date, *values in capture['rows']:
        if len(values) != len(columns):
            raise ValueError('Column/value count mismatch')
        quarter, alignment = match_period(date, sec['quarter_results'])
        periods.append({'vendor_date': date, 'sec_date': quarter['report_date'] if quarter else None,
                        'alignment': alignment})
        active_sets.append(tuple(c for c, v in zip(columns, values) if v is not None))
        for category, value in zip(columns, values):
            check = diagnose_value(value, capture['numeric_scale'], category,
                                   quarter.get('facts', []) if quarter else [])
            check['reviewed_aggregation'] = reviewed_aggregation(
                capture['ticker'], category, value, capture['numeric_scale'],
                quarter.get('facts', []) if quarter else [])
            if value is not None and not quarter:
                check['status'] = 'period_unaligned'
            rows.append({'vendor_date': date, 'category': category, 'alignment': alignment, **check})
    summary = summarize(capture['ticker'], 'stockanalysis', len(periods), rows)
    summary.update(period_alignment_counts=dict(collections.Counter(p['alignment'] for p in periods)),
                   sec_target_quarters_without_proposed_match=len(sec['quarter_results']) - len({p['sec_date'] for p in periods if p['sec_date']}),
                   category_availability_changes=len(set(active_sets)) > 1,
                   chart_missing_zero_labels_suppressed=capture.get('chart_missing_zero_labels_suppressed', 0))
    return summary, {'periods': periods, 'observations': rows}


def summarize(ticker, source, quarters, rows):
    counts = collections.Counter(row['status'] for row in rows)
    return {'ticker': ticker, 'source': source, 'status': 'diagnosed', 'quarters_observed': quarters,
            'numeric_observations': sum(row['status'] != 'source_missing' for row in rows),
            'source_missing_cells': counts['source_missing'],
            'numeric_candidate_observations': counts['numeric_candidate'],
            'no_numeric_candidate_observations': counts['no_numeric_candidate'],
            'period_unaligned_observations': counts['period_unaligned'],
            'numeric_candidates_with_lexical_member_hint': sum(row.get('lexical_member_hint', False) for row in rows),
            'reviewed_aggregation_matches': sum((row.get('reviewed_aggregation') or {}).get('status') == 'matches' for row in rows),
            'semantic_accuracy_measured': False}


def check_futu(capture, sec):
    # Reviewed calendar issuers; WMT's fiscal year ends in January of its named year.
    if capture['ticker'] not in ('MCD', 'CVX', 'PGR', 'NEE', 'BRK-B', 'XOM', 'WMT') or capture['currency'] != 'USD':
        raise ValueError('Futu issuer fiscal mapping has not been reviewed')
    quarters = {q['report_date']: q for q in sec['quarter_results']}
    rows = []
    matched_periods = set()
    for period in capture['captures']:
        date = futu_fiscal_date(capture['ticker'], period['period'])
        quarter = quarters.get(date)
        if quarter:
            matched_periods.add(date)
        for category, raw_value, raw_share in period['rows']:
            check = diagnose_value(raw_value, 1, category, quarter.get('facts', []) if quarter else [])
            check['reviewed_aggregation'] = reviewed_aggregation(
                capture['ticker'], category, raw_value, 1, quarter.get('facts', []) if quarter else [])
            if not quarter:
                check['status'] = 'period_unaligned'
            rows.append({'period': period['period'], 'sec_date': date, 'category': category,
                         'raw_share': raw_share, **check})
    summary = summarize(capture['ticker'], 'futu', len(capture['captures']), rows)
    summary['sec_target_quarters_without_futu_capture'] = len(quarters.keys() - matched_periods)
    return summary, rows


def futu_fiscal_date(ticker, label):
    if ticker != 'WMT':
        return calendar_fiscal_date(label)
    match = re.fullmatch(r'(\d{4})/Q([1-4])', label)
    if not match:
        raise ValueError('Annual/FY or unknown period cannot enter a quarter comparison')
    year, quarter = map(int, match.groups())
    month = (4, 7, 10, 1)[quarter - 1]
    year -= quarter != 4
    return dt.date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captures', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, default=ROOT / 'research/sec-30-baseline-2026-11-04')
    parser.add_argument('--private-report', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--roster', type=Path, default=ROOT / 'research/recovered-sec/eight_quarter_eval/roster.json')
    args = parser.parse_args()
    if not args.private_report.resolve().is_relative_to(PRIVATE.resolve()):
        raise ValueError('Detailed vendor report must remain under ignored data/vendor/local/')
    summaries, details, hashes = [], [], []
    def evidence(ticker):
        path = args.baseline / (ticker + '.json.gz')
        return json.loads(gzip.decompress(path.read_bytes()))
    seen = set()
    for path in sorted(args.captures.glob('batch*.json')):
        hashes.append({'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        for capture in json.loads(path.read_text()):
            if capture['ticker'] in seen:
                raise ValueError('Duplicate Stock Analysis issuer capture')
            seen.add(capture['ticker'])
            summary, detail = check_capture(capture, evidence(capture['ticker']))
            summaries.append(summary)
            details.append({'ticker': capture['ticker'], 'source': 'stockanalysis', 'detail': detail})
    roster = {company['ticker'] for company in json.loads(args.roster.read_text())}
    if seen != roster:
        raise ValueError('Capture coverage must account for every roster issuer, including failed attempts')
    for name in ('futu-observations.json', 'futu-gaps.json'):
        path = args.captures / name
        hashes.append({'file': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    for capture in json.loads((args.captures / 'futu-observations.json').read_text()):
        summary, detail = check_futu(capture, evidence(capture['ticker']))
        summaries.append(summary)
        details.append({'ticker': capture['ticker'], 'source': 'futu', 'detail': detail})
    gaps = json.loads((args.captures / 'futu-gaps.json').read_text())
    report = {'candidate_matches_are_not_accuracy': True, 'companies': summaries,
              'futu_gap_checks': gaps, 'input_hashes': hashes, 'private_details': details}
    with args.private_report.open('x') as stream:
        json.dump(report, stream, indent=2)
    # The shareable schema intentionally contains no vendor values, labels, facts or rows.
    safe = {'candidate_matches_are_not_accuracy': True, 'roster_companies_accounted_for': len(roster), 'companies': summaries,
            'futu_gaps': [{k: g[k] for k in ('ticker', 'status')} for g in gaps]}
    with args.summary.open('x') as stream:
        json.dump(safe, stream, indent=2)
    print(json.dumps({'roster_companies_accounted_for': len(roster),
                      'source_issuer_diagnostics': len(summaries),
                      'numeric_candidate_matches_are_not_accuracy': True,
                      'private_report': str(args.private_report), 'summary': str(args.summary)}, indent=2))


if __name__ == '__main__':
    main()
