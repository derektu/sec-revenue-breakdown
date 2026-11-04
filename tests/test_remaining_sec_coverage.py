"""剩餘六家不依賴 vendor 原值的八季 SEC 擷取與 XOM 雙口徑。"""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import temporal_eval as temporal
from audit_remaining_sec_coverage import inspect, xom_latest
from extend_issuer_repairs import pools_for
from enforce_sec_primary_source import selected_is_sec
from cohort_rule_catalog import S, G


class RemainingSecCoverageTests(unittest.TestCase):
    def facts(self):
        receipt = temporal.load(ROOT / 'research/cohort-rule-replay-20261104/XOM-freeze.json')
        data = temporal.checked_data(receipt['plan'], ROOT / receipt['plan']['baseline_file'])
        return pools_for('XOM', data)[1]['2026-09-30']

    def test_xom_latest_distinct_income_bases_and_unallocated_remainder(self):
        outputs, checks = xom_latest(*self.facts())
        self.assertEqual(outputs['all_income_with_consolidated_deductions']['上游']['value'], 31_156_000_000)
        self.assertEqual(outputs['gross_sales_and_intersegment']['上游']['value'], 29_514_000_000)
        self.assertTrue(checks['reconciles'])
        self.assertEqual(checks['all_income_components_to_consolidated_sales_difference_usd'], 0)
        self.assertEqual(checks['gross_sales_five_fields_unallocated_difference_usd'], 7_000_000)
        self.assertTrue(all(selected_is_sec(s) for series in outputs.values() for s in series.values()))

    def test_wrong_consolidated_total_cannot_pass_reconciliation(self):
        facts, conflicts = copy.deepcopy(self.facts())
        next(f for f in facts if f['concept'] == 'us-gaap:Revenues' and f['dimensions'] == {'srt:ProductOrServiceAxis': 'xom:SalesAndOtherOperatingRevenueMember'})['value'] += 1_000_000_000
        with self.assertRaises(ValueError): xom_latest(facts, conflicts)

    def test_missing_geographic_operand_is_missing_not_zero(self):
        facts, conflicts = self.facts()
        facts = [f for f in facts if f['dimensions'] != {S: 'xom:UpstreamMember', G: 'country:US'}]
        outputs, _ = xom_latest(facts, conflicts)
        self.assertFalse(selected_is_sec(outputs['all_income_with_consolidated_deductions']['上游']))

    def test_all_48_quarters_replay_without_private_reference_files(self):
        original_text, original_bytes = Path.read_text, Path.read_bytes
        def protect(original):
            def read(path, *args, **kwargs):
                if path.resolve().is_relative_to(ROOT / 'data/vendor/local'):
                    raise AssertionError('SEC-only replay attempted private vendor input')
                return original(path, *args, **kwargs)
            return read
        with patch.object(Path, 'read_text', protect(original_text)), patch.object(Path, 'read_bytes', protect(original_bytes)):
            result = inspect()
        self.assertEqual(result['completion_OK_count_unchanged'], 24)
        self.assertEqual({c['ticker'] for c in result['companies']}, {'LLY', 'BRK-B', 'PGR', 'XOM', 'CVX', 'PLD'})
        self.assertEqual(sum(c['SEC_output_fields'] for c in result['companies']), 344)
        for company in result['companies']:
            self.assertEqual(company['quarter_status_counts'], {'SEC_output_available': 8})
            self.assertEqual(company['completion_status_unchanged'], 'Fail')


if __name__ == '__main__':
    unittest.main()
