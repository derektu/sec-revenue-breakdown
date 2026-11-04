#!/usr/bin/env python3
"""Export public SEC-derived research results and replay their quarter arithmetic.

Recovered sources stay unchanged. Raw filing caches are never packaged.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
AUDIT = REPO / 'research/recovered-sec/eight_quarter_eval'
sys.path.insert(0, str(AUDIT))
import run as audit


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(result):
    """Recompute quarter selection, exact Q4 operands, totals and group checks."""
    records = result.get('raw_filings', [])
    checked = 0
    for q in result['quarter_results']:
        if q['status'] != 'processed':
            continue
        current = next(r for r in records if r['filing']['reportDate'] == q['report_date'])
        previous = [f for r in records if r['filing']['reportDate'] < q['report_date']
                    for f in r['facts']]
        facts, conflicts = audit.quarter(current['facts'], q['report_date'], q['form'], previous)
        totals, groups = audit.audit_groups(facts)
        assert facts == q['facts'], (result['ticker'], q['report_date'], 'facts')
        assert len(conflicts) == q['conflicting_duplicates']
        assert totals == q['candidate_totals'] and groups == q['groups']
        checked += 1
    return checked


def csv_bytes(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in rows for k in r)), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def export(destination):
    destination.mkdir(parents=True, exist_ok=False)
    roster = json.loads((AUDIT / 'roster.json').read_text())
    companies, quarters, manifest, exceptions = [], [], [], []
    counts = collections.Counter()
    cutoffs = set()
    for company in roster:
        ticker = company['ticker']
        result = json.loads((AUDIT / 'outputs' / f'{ticker}.json').read_text())
        cutoffs.add(result.get('as_of'))
        counts['replayed_quarters'] += replay(result)
        exceptions.extend(dict(ticker=ticker, kind='download_or_discovery', **e) for e in result['errors'])
        for record in result.get('raw_filings', []):
            for error in record['parse_errors']:
                exceptions.append(dict(ticker=ticker, kind='numeric_parse', filing=record['filing'], **error))
        for entry in result['manifest']:
            path = AUDIT / entry['file']
            assert path.stat().st_size == entry['bytes'] and digest(path) == entry['sha256']
            manifest.append(dict(entry, ticker=ticker))
            counts['source_snapshots_verified'] += 1
            counts['source_bytes'] += entry['bytes']
        payload = json.dumps(result, separators=(',', ':'), ensure_ascii=False).encode()
        (destination / f'{ticker}.json.gz').write_bytes(gzip.compress(payload, mtime=0))
        actual = result['quarter_results']
        groups = [g for q in actual for g in q.get('groups', [])]
        source_groups = [g for g in groups if g['classification_heuristic'] in ('product_service', 'operating_segment')]
        row = dict(ticker=ticker, cik=company['cik'], requested_quarters=8,
                   selected_quarters=len(actual), processed_quarters=sum(q['status'] == 'processed' for q in actual),
                   missing_history_quarters=8-len(actual), download_errors=len(result['errors']),
                   numeric_parse_errors=result.get('numeric_parse_error_count', 0),
                   candidate_groups=len(groups), reconciled_groups=sum(g['reconciles_to_any_candidate_total'] for g in groups),
                   by_source_heuristic_groups=len(source_groups),
                   by_source_heuristic_reconciled_groups=sum(g['reconciles_to_any_candidate_total'] for g in source_groups))
        row['status'] = ('failed' if not actual else 'partial_history' if len(actual) < 8 else
                         'partial_failure' if row['download_errors'] else 'processed')
        row['limitation'] = ('Successor CIK; legacy 34088 deliberately not bridged' if ticker == 'XOM' else '')
        companies.append(row)
        for key, value in row.items():
            if isinstance(value, int) and key != 'cik':
                counts[key] += value
        for index in range(8):
            q = actual[index] if index < len(actual) else {}
            record = next((r for r in result.get('raw_filings', [])
                           if r['filing']['reportDate'] == q.get('report_date')), {})
            filing = record.get('filing', {})
            source = next((m for m in result['manifest']
                           if m.get('accessionNumber') == filing.get('accessionNumber')), {})
            facts = q.get('facts', [])
            gs = q.get('groups', [])
            sg = [g for g in gs if g['classification_heuristic'] in ('product_service', 'operating_segment')]
            quarters.append(dict(ticker=ticker, quarter_rank=index+1, quarter_end=q.get('report_date', ''),
                                 status=q.get('status', 'insufficient_issuer_history' if not result['errors'] else 'discovery_failed_or_incomplete'),
                                 form=q.get('form', ''), filing_date=q.get('filing_date', ''),
                                 accession=filing.get('accessionNumber', ''), source_url=source.get('url', ''),
                                 source_sha256=source.get('sha256', ''),
                                 numeric_parse_errors_in_current_filing=len(record.get('parse_errors', [])),
                                 quarter_start_dates=json.dumps(sorted({f['startdate'] for f in facts})),
                                 candidate_facts=len(facts), q4_derived_facts=q.get('derived_fact_count', 0),
                                 conflicting_duplicates=q.get('conflicting_duplicates', 0),
                                 candidate_totals=len(q.get('candidate_totals', [])), dimensional_groups=len(gs),
                                 reconciled_groups=sum(g['reconciles_to_any_candidate_total'] for g in gs),
                                 by_source_heuristic_groups=len(sg),
                                 by_source_heuristic_reconciled_groups=sum(g['reconciles_to_any_candidate_total'] for g in sg),
                                 limitation=row['limitation']))
            counts['q4_derived_facts'] += q.get('derived_fact_count', 0)
            counts['quarter_candidate_facts'] += len(facts)
            if q.get('conflicting_duplicates'):
                exceptions.append(dict(ticker=ticker, kind='conflicting_duplicate_rejected',
                                       quarter_end=q['report_date'], count=q['conflicting_duplicates'],
                                       evidence='Original alternatives preserved in issuer raw_filings facts'))
            counts['quarters_with_any_reconciled_group'] += any(g['reconciles_to_any_candidate_total'] for g in gs)
            counts['quarters_with_by_source_heuristic_reconciled_group'] += any(g['reconciles_to_any_candidate_total'] for g in sg)
    assert len(cutoffs) == 1 and None not in cutoffs, cutoffs
    summary = dict(as_of=cutoffs.pop(), companies_requested=len(roster), metrics=dict(counts), companies=companies,
                   vendor_comparison_performed=False, accuracy_measured=False,
                   by_source_definition='Heuristic axis names product/service or segment; excludes geography-name axes; not semantic classification',
                   verification='All source sizes/SHA256 checked; all processed quarters replayed from preserved raw candidate facts')
    (destination / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (destination / 'exceptions.json').write_text(json.dumps(exceptions, indent=2)+'\n')
    (destination / 'company_summary.csv').write_bytes(csv_bytes(companies))
    (destination / 'quarter_summary.csv').write_bytes(csv_bytes(quarters))
    for name in ['quarter_candidates.csv']:
        (destination / (name+'.gz')).write_bytes(gzip.compress((AUDIT / 'outputs' / name).read_bytes(), mtime=0))
    source_hashes = {str(p.relative_to(REPO)): digest(p) for p in [
        AUDIT / 'run.py', AUDIT / 'summarize.py', AUDIT / 'roster.json',
        AUDIT.parent / 'extract.py', Path(__file__).resolve()]}
    hashes = {p.name: digest(p) for p in sorted(destination.iterdir()) if p.is_file()}
    (destination / 'verification.json').write_text(json.dumps(dict(source_code_sha256=source_hashes,
        artifact_sha256=hashes, raw_cache_included=False, **dict(counts)), indent=2)+'\n')
    print(json.dumps(summary['metrics'], indent=2))


def verify(destination):
    verification = json.loads((destination / 'verification.json').read_text())
    for name, sha in verification['artifact_sha256'].items():
        assert digest(destination / name) == sha, name
    for name, sha in verification['source_code_sha256'].items():
        assert digest(REPO / name) == sha, name
    checked = sum(replay(json.loads(gzip.decompress(path.read_bytes())))
                  for path in destination.glob('*.json.gz'))
    assert checked == verification['replayed_quarters']
    print(json.dumps(dict(artifacts_verified=len(verification['artifact_sha256']),
                         replayed_quarters=checked, network_used=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['export', 'verify'])
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    (export if args.action == 'export' else verify)(args.destination)
