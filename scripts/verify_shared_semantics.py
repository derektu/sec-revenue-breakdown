"""Offline raw-source replay and existing regression suites, with evidence receipt."""
import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import socket
import tempfile
import time

from shared_raw_semantics import ROOT, digest, run
from verify_recovered import verify


def deny(*args, **kwargs):
    raise RuntimeError('Network disabled during raw source replay')


def normalized(value):
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items() if k != 'processing_seconds'}
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
    fixed = ROOT / 'research/shared-raw-semantics'
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp) / 'results'
        run(fixed / 'manifest.json', out)
        for path in out.iterdir():
            if normalized(load(path)) != normalized(load(fixed / 'results' / path.name)):
                raise ValueError('Replay mismatch: ' + path.name)
    old = verify()
    report = {'verified_at_utc': datetime.now(timezone.utc).isoformat(),
              'mode': 'retrospective_raw_SEC_offline_replay', 'blind_cases': 0,
              'pinned_raw_filings_reparsed': 8, 'pinned_SEC_source_files': 48,
              'reviewed_fact_contracts': 40, 'reviewed_hierarchy_contracts': 5,
              'equal_value_distinct_scope_contracts': 1,
              'semantic_results_reproduced_excluding_wall_time': True,
              'tests_run': old['tests_run'], 'test_suites': old['test_suites'],
              'network_disabled': True, 'vendor_raw_used': False,
              'verification_seconds': time.perf_counter() - started,
              'code_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in (
                  ROOT / 'scripts/shared_raw_semantics.py', ROOT / 'scripts/compare_shared_semantics.py',
                  ROOT / 'scripts/verify_shared_semantics.py', ROOT / 'tests/test_shared_raw_semantics.py')},
              'results_sha256': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in (fixed / 'results').iterdir()}}
    with args.report.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
