#!/usr/bin/env python3
"""Check recovered source provenance and run all synthetic tests offline.

Does not fetch filings, execute downloaders or require the original archives.
For full data reproduction use recovered-sec/verify_local.py with original inputs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = '4113daa'
CHILD = '''
import json, socket, sys, unittest
def deny(*args, **kwargs):
    raise RuntimeError('Network is disabled for offline verification')
socket.create_connection = deny
socket.socket.connect = deny
socket.socket.connect_ex = deny
suite = unittest.defaultTestLoader.discover('.', pattern=sys.argv[1])
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({'tests_run': result.testsRun, 'failures': len(result.failures),
                  'errors': len(result.errors), 'skipped': len(result.skipped)}))
sys.exit(0 if result.wasSuccessful() and result.testsRun else 1)
'''


def verify():
    import lxml
    recovered = ROOT / 'research/recovered-sec'
    required = (recovered / 'requirements.txt').read_text().strip().split('==')[1]
    if lxml.__version__ != required:
        raise ValueError(f'lxml version mismatch: expected {required}, found {lxml.__version__}')
    manifest = json.loads((ROOT / 'docs/vendor/recovery-manifest.json').read_text())
    checked = []
    for entry in manifest['files']:
        path = (ROOT / entry['destination']).resolve()
        if not path.is_relative_to(recovered.resolve()):
            raise ValueError('Manifest destination escapes recovered source directory')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry['sha256']:
            raise ValueError(f'Source hash mismatch: {entry["destination"]}')
        checked.append(entry['destination'])
    roster = json.loads((recovered / 'eight_quarter_eval/roster.json').read_text())
    if len(roster) != 30 or len({c['ticker'] for c in roster}) != 30:
        raise ValueError('Expected 30 distinct roster companies')
    if not all(isinstance(c['cik'], int) and c['cik'] > 0 for c in roster):
        raise ValueError('Roster requires positive integer CIKs')

    suites = []
    for name, directory, pattern in [
        ('archive_safety', ROOT / 'tests', 'test_*.py'),
        ('recovered_pilot', recovered, 'test_extract.py'),
        ('recovered_quarter_audit', recovered / 'eight_quarter_eval', 'test_run.py'),
    ]:
        process = subprocess.run([sys.executable, '-c', CHILD, pattern], cwd=directory,
                                 text=True, capture_output=True)
        sys.stderr.write(process.stderr)
        if process.returncode:
            raise RuntimeError(f'{name} failed: {process.stdout}')
        outcome = json.loads(process.stdout.strip().splitlines()[-1])
        suites.append({'name': name, **outcome})
    return {
        'verification_date_utc': '2026-11-04',
        'execution': 'cloud_offline_source_and_synthetic_tests_only',
        'recovered_from_commit': SOURCE_COMMIT,
        'python': sys.version.split()[0],
        'lxml': lxml.__version__,
        'manifest_source_files_sha256_verified': checked,
        'roster_companies': len(roster),
        'baseline_as_of_from_recovered_runner': '2026-11-03',
        'test_suites': suites,
        'tests_run': sum(s['tests_run'] for s in suites),
        'network_connections_disabled_in_test_processes': True,
        'original_archive_hashes_verified_in_cloud': False,
        'sec_source_snapshots_reparsed_in_cloud': False,
        'stored_234_quarters_recomputed_in_cloud': False,
        'curated_26_reconciliations_rerun_in_cloud': False,
        'vendor_comparison_performed': False,
        'local_data_verification_reference': 'docs/vendor/offline-verification.json',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = json.dumps(verify(), indent=2) + '\n'
    if args.report:
        # Require a new report path to avoid overwriting somebody else's result.
        with args.report.open('x') as stream:
            stream.write(report)
    print(report, end='')


if __name__ == '__main__':
    main()
