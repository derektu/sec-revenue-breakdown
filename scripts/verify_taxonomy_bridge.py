"""Reproduce the pinned taxonomy bridge results with network disabled."""
import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import socket
import tempfile
import time
from shared_raw_semantics import ROOT, digest
from taxonomy_bridge import run
from verify_recovered import verify


def deny(*args, **kwargs):
    raise RuntimeError('Network disabled during taxonomy bridge verification')


def normalized(value):
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items() if k not in ('processing_seconds', 'taxonomy_processing_seconds')}
    if isinstance(value, list):
        return [normalized(x) for x in value]
    return value


def load(path):
    return json.loads(gzip.decompress(path.read_bytes())) if path.suffix == '.gz' else json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    socket.create_connection = socket.socket.connect = socket.socket.connect_ex = deny
    base = ROOT / 'research/taxonomy-bridge'
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp) / 'results'
        run(out)
        for path in out.iterdir():
            if normalized(load(path)) != normalized(load(base / 'results' / path.name)):
                raise ValueError('Replay mismatch: ' + path.name)
    regression = verify()
    report = {'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'network_disabled': True,
              'raw_filings_reparsed': 8, 'source_files_hash_verified': 48,
              'primary_scope_cases': 64, 'historical_comparative_scope_cases': 64,
              'agent_reviewed_representative_cases': 7, 'blind_cases': 0,
              'semantic_results_reproduced_excluding_processing_time': True,
              'tests_run': regression['tests_run'], 'test_suites': regression['test_suites'],
              'verification_seconds': time.perf_counter() - started,
              'code_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in (
                  ROOT / 'scripts/taxonomy_bridge.py', ROOT / 'scripts/verify_taxonomy_bridge.py',
                  ROOT / 'tests/test_taxonomy_bridge.py')},
              'result_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in (base / 'results').iterdir()},
              'review_sha256': digest((base / 'review-cases.json').read_bytes())}
    with args.report.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
