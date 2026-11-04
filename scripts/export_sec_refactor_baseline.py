#!/usr/bin/env python3
"""在本機匯出 SEC 回歸期望值，讓雲端不必讀取付費參考原文。"""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

from enforce_sec_primary_source import selected_is_sec


class SecRefactorBaselineExporter:
    """匯出既存驗證結果。此資料只供測試，不能作新 parser 的輸入。"""

    def __init__(self, repository: Path):
        self.repository = repository

    def read_json(self, relative_path: str) -> dict:
        return json.loads((self.repository / relative_path).read_text())

    def digest(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def export(self, destination: Path) -> dict:
        destination.mkdir(parents=True, exist_ok=False)
        summary_path = 'research/cross-source-final-20261104/completion-status.json'
        summary = self.read_json(summary_path)
        coverage = self.read_json('research/remaining-sec-coverage-20261104/coverage.json')
        sec_only = {company['ticker']: company for company in coverage['companies']}
        manifest = {'purpose': 'regression_expected_only_not_runtime_parser_input',
            'source_summary_sha256': self.digest(self.repository / summary_path),
            'restricted_reference_values_included': False, 'files': [], 'companies': []}
        for company in summary['companies']:
            ticker = company['ticker']
            detail_path = self.repository / company['local_detail_path']
            if self.digest(detail_path) != company['local_detail_sha256']:
                raise ValueError(f'{ticker}: comparison receipt changed')
            detail = json.loads(detail_path.read_text())
            comparisons = [row for row in detail if row['status'] != 'reference_not_applicable_evidenced'
                and (company.get('cross_source_changed') or row.get('source') == company['reference'])]
            rows = comparisons if company['status'] == 'OK' else [
                {'period_end': quarter['period_end'], 'category': label, 'selected': selected}
                for quarter in sec_only[ticker]['quarters'] for label, selected in quarter['outputs'].items()]
            periods = defaultdict(dict)
            reference_sources = defaultdict(set)
            for row in comparisons:
                end = row.get('period_end', row.get('sec_period_end'))
                reference_sources[end].update(row.get('reference_sources', [row.get('source')]))
            for row in rows:
                selected = row['selected']
                end = row.get('period_end', row.get('sec_period_end'))
                if not selected_is_sec(selected) or any(f['enddate'] != end for f in selected['facts']):
                    raise ValueError(f'{ticker}: missing SEC evidence or incorrect period')
                if row['category'] in periods[end]:
                    raise ValueError(f'{ticker}: duplicate category')
                # 不匯出整個比較 row，避免夾帶 raw、reference_usd 或舊 IR 結果。
                periods[end][row['category']] = {
                    'value_usd': selected['value'], 'reported_error_usd': selected.get('error'),
                    'SEC_operands': selected['facts']}
            if sorted(periods) != sorted(company['target_periods']) or len(periods) != 8:
                raise ValueError(f'{ticker}: incomplete baseline periods')
            for end, outputs in sorted(periods.items()):
                name = f'{ticker}/{end}/{ticker}_{end}_SEC_expected.json.gz'
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                payload = json.dumps({'ticker': ticker, 'period_end': end,
                    'purpose': manifest['purpose'], 'source_format': 'derived_SEC_facts_not_original_HTML',
                    'outputs': outputs}, ensure_ascii=False, sort_keys=True, default=str).encode()
                target.write_bytes(gzip.compress(payload, mtime=0))
                manifest['files'].append({'path': name, 'sha256': self.digest(target),
                    'decompressed_sha256': hashlib.sha256(payload).hexdigest(), 'numeric_outputs': len(outputs)})
            manifest['companies'].append({'ticker': ticker, 'periods': sorted(periods),
                'comparison_status_preserved': company['status'],
                'default_reference': company['reference'],
                'reference_sources_by_period': {end: sorted(sources) for end, sources in sorted(reference_sources.items())},
                'original_local_detail_sha256': company['local_detail_sha256']})
        manifest['company_count'] = len(manifest['companies'])
        manifest['quarter_count'] = len(manifest['files'])
        manifest['numeric_outputs'] = sum(file['numeric_outputs'] for file in manifest['files'])
        (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        return manifest


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--out', required=True, type=Path)
    options = cli.parse_args()
    result = SecRefactorBaselineExporter(Path(__file__).resolve().parents[1]).export(options.out)
    print(json.dumps({key: result[key] for key in ['company_count', 'quarter_count', 'numeric_outputs']}))
