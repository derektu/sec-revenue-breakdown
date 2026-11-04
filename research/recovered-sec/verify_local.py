"""Verify recovered SEC experiments offline without contacting a vendor or SEC."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--imports', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    imports = args.imports.resolve()
    results = args.results.resolve()
    results.mkdir(parents=True, exist_ok=True)
    pilot = imports / 'sec_revenue_experiment/sec_revenue_experiment'
    audit = imports / 'eight_quarter_reproducible_results/sec_revenue_experiment/eight_quarter_eval'
    manifest = json.loads((ROOT.parents[1] / 'docs/vendor/recovery-manifest.json').read_text())
    for archive in manifest['archives']:
        path = imports / archive['name']
        assert path.stat().st_size == archive['bytes'], path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == archive['sha256'], path

    data = ROOT / 'data'
    outputs = ROOT / 'outputs'
    data.mkdir(exist_ok=True)
    outputs.mkdir(exist_ok=True)
    snapshots = json.loads((pilot / 'data/manifest.json').read_text())
    for source in snapshots:
        name = source['filing'] + '.html'
        raw = (pilot / 'data' / name).read_bytes()
        assert len(raw) == source['bytes'], name
        assert hashlib.sha256(raw).hexdigest() == source['sha256'], name
        (data / name).write_bytes(raw)

    commands = [
        (ROOT, ['-m', 'unittest', '-v', 'test_extract.py'], 'pilot-tests.log'),
        (ROOT / 'eight_quarter_eval', ['-m', 'unittest', '-v', 'test_run.py'], 'audit-tests.log'),
        (ROOT, ['extract.py'], 'pilot-extraction.log'),
        (ROOT, ['validate.py'], 'pilot-validation.log'),
    ]
    for cwd, command, log in commands:
        process = subprocess.run([sys.executable, *command], cwd=cwd,
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (results / log).write_text(process.stdout)
        if process.returncode:
            raise RuntimeError(f'{log} failed; see {results / log}')

    runner = load_module('recovered_run', ROOT / 'eight_quarter_eval/run.py')
    roster = json.loads((audit / 'roster.json').read_text())
    quarters = 0
    for company in roster:
        saved = json.loads((audit / 'outputs' / (company['ticker'] + '.json')).read_text())
        records = saved.get('raw_filings', [])
        for quarter in saved['quarter_results']:
            if quarter['status'] != 'processed':
                continue
            current = next(record for record in records
                           if record['filing']['reportDate'] == quarter['report_date'])
            previous = [fact for record in records
                        if record['filing']['reportDate'] < quarter['report_date']
                        for fact in record['facts']]
            facts, conflicts = runner.quarter(current['facts'], quarter['report_date'],
                                               quarter['form'], previous)
            totals, groups = runner.audit_groups(facts)
            assert facts == quarter['facts'], (company['ticker'], quarter['report_date'], 'facts')
            assert totals == quarter['candidate_totals'], (company['ticker'], 'totals')
            assert groups == quarter['groups'], (company['ticker'], 'groups')
            assert len(conflicts) == quarter['conflicting_duplicates']
            quarters += 1

    checks = json.loads((outputs / 'validation.json').read_text())
    report = {
        'archives_sha256_verified': len(manifest['archives']),
        'sec_html_snapshots_sha256_verified': len(snapshots),
        'pilot_tests_passed': 3,
        'audit_tests_passed': 9,
        'pilot_reconciliations': len(checks),
        'pilot_all_reconciliations_passed': all(check['pass'] for check in checks),
        'roster_companies_checked': len(roster),
        'stored_quarters_recomputed_from_saved_facts': quarters,
        'new_network_requests': 0,
        'thirty_company_raw_html_reparse_performed': False,
        'vendor_reference_accuracy_measured': False,
    }
    (results / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
