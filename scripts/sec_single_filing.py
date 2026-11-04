#!/usr/bin/env python3
"""Fetch and parse one explicit public SEC filing, without retries or discovery.

Use a genuine identifying SEC_USER_AGENT. This is a bounded smoke test, not the
30-company baseline. Raw HTML stays in ignored data/cache; derived facts retain
their original parser limitations and are not validated revenue observations.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research/recovered-sec'))
from extract import parse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--report-dir', required=True, type=Path)
    args = parser.parse_args()
    url = urllib.parse.urlsplit(args.url)
    if (url.scheme != 'https' or url.netloc != 'www.sec.gov'
            or not url.path.startswith('/Archives/edgar/data/') or url.query
            or url.fragment or '..' in url.path.split('/')):
        parser.error('Require an explicit https://www.sec.gov/Archives/edgar/data/ filing URL')
    agent = os.environ.get('SEC_USER_AGENT', '').strip()
    if not agent or any(x in agent.lower() for x in ('example.com', 'your organization', 'your-real-contact')):
        parser.error('Set SEC_USER_AGENT to the genuine operator identity and contact')
    destination = args.report_dir.resolve()
    if not destination.is_relative_to(ROOT):
        parser.error('Report directory must be inside this repository')
    destination.mkdir(parents=True, exist_ok=False)
    report = {
        'retrieved_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'url': args.url,
        'execution': 'single GET; inherited proxy and CA; TLS verification enabled; no retries',
        'parser_source': 'research/recovered-sec/extract.py',
        'parser_sha256': hashlib.sha256((ROOT / 'research/recovered-sec/extract.py').read_bytes()).hexdigest(),
        'is_latest_eight_quarter_baseline': False,
        'vendor_comparison_performed': False,
    }
    try:
        request = urllib.request.Request(args.url, headers={'User-Agent': agent})
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.geturl() != args.url:
                raise ValueError('Unexpected final URL; no redirected content accepted')
            body = response.read()
            report['http_status'] = response.status
        digest = hashlib.sha256(body).hexdigest()
        cache = ROOT / 'data/cache/sec-single-filing'
        cache.mkdir(parents=True, exist_ok=True)
        raw = cache / (digest + '.html')
        if raw.exists():
            if hashlib.sha256(raw.read_bytes()).hexdigest() != digest:
                raise ValueError('Existing cache hash mismatch')
        else:
            with raw.open('xb') as stream:
                stream.write(body)
        parsed = parse(raw)
        parsed['filing'] = Path(url.path).name
        report.update(status='downloaded_and_parsed', bytes=len(body), sha256=digest,
                      raw_cache=str(raw.relative_to(ROOT)),
                      raw_candidate_count=len(parsed['facts']),
                      numeric_parse_error_count=len(parsed['parse_errors']))
        for fact in parsed['facts']:
            fact.update(source_url=args.url, source_sha256=digest)
        with (destination / 'candidates.json').open('x') as stream:
            json.dump(parsed, stream, indent=2)
            stream.write('\n')
    except Exception as error:
        report.update(status='failed', error_type=type(error).__name__, error=str(error))
        if isinstance(error, urllib.error.HTTPError):
            report['http_status'] = error.code
    with (destination / 'manifest.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'downloaded_and_parsed' else 1


if __name__ == '__main__':
    sys.exit(main())
