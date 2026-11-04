import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'scripts/compare_vendor_cohort.py'
spec = importlib.util.spec_from_file_location('vendor_comparison', path)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class VendorComparisonTests(unittest.TestCase):
    def test_missing_source_is_distinct_from_reported_zero(self):
        zero_fact = {'unit': 'iso4217:USD', 'value': 0, 'dimensions': {}}
        self.assertEqual(comparison.diagnose_value(None, 1, 'Other', [zero_fact])['status'], 'source_missing')
        self.assertEqual(comparison.diagnose_value(0, 1, 'Other', [zero_fact])['status'], 'numeric_candidate')

    def test_trimmed_units_do_not_create_large_tolerance_and_keep_sign(self):
        value, tolerance = comparison.amount('6億', 1)
        self.assertEqual(value, 600_000_000)
        self.assertEqual(tolerance, 500_000)
        self.assertEqual(comparison.amount('-1,600萬', 1)[0], -16_000_000)

    def test_numeric_match_does_not_certify_definition_and_currency_matters(self):
        fact = {'unit': 'iso4217:USD', 'value': 100, 'dimensions': {'Axis': 'demo:CloudMember'}}
        result = comparison.diagnose_value(100, 1, 'Cloud', [fact])
        self.assertEqual(result['status'], 'numeric_candidate')
        self.assertTrue(result['lexical_member_hint'])
        self.assertFalse(result['semantic_mapping_certified'])
        self.assertEqual(comparison.diagnose_value(100, 1, 'Cloud', [{**fact, 'unit': 'shares'}])['status'], 'no_numeric_candidate')

    def test_period_shift_is_a_proposal_and_far_dates_abstain(self):
        quarters = [{'report_date': '2026-08-31'}]
        self.assertEqual(comparison.match_period('Sep 30, 2026', quarters)[1], 'fiscal_label_shift_proposal')
        self.assertIsNone(comparison.match_period('Sep 30, 2025', quarters)[0])

    def test_fy_cannot_be_a_quarter(self):
        with self.assertRaises(ValueError):
            comparison.calendar_fiscal_date('2026/FY')

    def test_walmart_fiscal_year_rollover(self):
        self.assertEqual(comparison.futu_fiscal_date('WMT', '2027/Q2'), '2026-07-31')
        self.assertEqual(comparison.futu_fiscal_date('WMT', '2026/Q4'), '2026-01-31')
        self.assertEqual(comparison.futu_fiscal_date('NEE', '2026/Q3'), '2026-09-30')
        with self.assertRaises(ValueError):
            comparison.futu_fiscal_date('WMT', '2026/FY')

    def test_aggregate_abstains_on_missing_or_wrong_scope(self):
        result = comparison.reviewed_aggregation('CMCSA', 'Connectivity and Platforms', 100, 1,
                                                 [{'value': 100, 'unit': 'iso4217:USD', 'dimensions': {}}])
        self.assertEqual(result['status'], 'missing_or_ambiguous_operand')


if __name__ == '__main__':
    unittest.main()
