#!/usr/bin/env python3
"""離線核對剩餘公司的精確參考缺季；不讀取或評估 XOM 未提交工作。"""
import argparse
import hashlib
import json
from pathlib import Path

from evaluate_eight_quarter_status import period_coverage, VENDORS
import temporal_eval as temporal

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / 'research/comcast-sec-repair-20261104/completion-status.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    summary = temporal.load(SUMMARY)
    companies = []
    for company in summary['companies']:
        ticker = company['ticker']
        if company['status'] == 'OK' or ticker == 'XOM':
            continue
        receipt_path = ROOT / f'research/cohort-rule-replay-20261104/{ticker}-freeze.json'
        receipt = temporal.load(receipt_path)
        path = ROOT / receipt['plan']['baseline_file']
        data = temporal.checked_data(receipt['plan'], path)
        baseline_periods = sorted(q['report_date'] for q in data['quarter_results'])
        if baseline_periods != company['target_periods']:
            raise ValueError(f'{ticker}: summary target window differs from frozen baseline')
        private_path = ROOT / company['local_detail_path']
        companies.append({'ticker': ticker, 'inherited_status': company['status'],
            'reference': company['reference'], 'reference_is_original_vendor': company['reference'] in VENDORS,
            'target_periods': baseline_periods, 'reference_periods': company['reference_periods'],
            **period_coverage(baseline_periods, company['reference_periods']),
            'inherited_fail_reasons': company['fail_reasons'],
            'inherited_primary_source_checks': company['primary_source_checks'],
            'private_detail_available_in_cloud': private_path.exists(),
            'baseline_file': str(path.relative_to(ROOT)), 'baseline_sha256': sha(path),
            'freeze_receipt': str(receipt_path.relative_to(ROOT)), 'freeze_sha256': sha(receipt_path),
            'latest_saved_SEC_filing': max((r['filing'] for r in data['raw_filings']), key=lambda f: f['reportDate']),
            'fresh_SEC_download_performed': False, 'vendor_replay_performed': False})
    return {'source_summary': str(SUMMARY.relative_to(ROOT)), 'source_summary_sha256': sha(SUMMARY),
        'source_ok_count': summary['ok_count'], 'completion_status_changed': False,
        'excluded_company': {'ticker': 'XOM', 'reason': 'Mac 未提交工作；不讀取、不重做。'},
        'blind_test': False, 'fresh_vendor_availability_checked': False,
        'scope': '已保存收據與凍結基準的期間盤點；不重新解析原始財報，也不重新比對供應商金額。',
        'code_sha256': {p: sha(ROOT / p) for p in ['scripts/audit_remaining_company_gaps.py',
            'scripts/evaluate_eight_quarter_status.py']}, 'companies': companies}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(f"Audited {len(result['companies'])} companies; no completion count change")


if __name__ == '__main__':
    main()
