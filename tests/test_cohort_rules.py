import sys
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cohort_rule_audit as audit
from cohort_rule_catalog import leaf, rule, catalog


class CohortRuleTests(unittest.TestCase):
    def fact(self, value, dims=None):
        return {'concept': 'Revenue', 'dimensions': dims or {}, 'unit': 'iso4217:USD',
                'value': value, 'decimals': 'INF'}

    def test_conflicting_alternatives_abstain_before_reference_comparison(self):
        spec = rule(leaf('Revenue', {}), leaf('Revenue', {'Axis': 'Other'}))
        selected = audit.resolve(spec, [self.fact(100), self.fact(80, {'Axis': 'Other'})])
        self.assertEqual(audit.compare_value(100, 1, selected)['status'], 'ambiguous_scope')

    def test_full_dimensions_required_and_missing_is_not_zero(self):
        selected = audit.resolve(rule(leaf('Revenue', {})), [self.fact(0, {'Axis': 'Other'})])
        self.assertEqual(selected['status'], 'parser_scope_missing')
        self.assertEqual(audit.compare_value(None, 1, selected)['status'], 'reference_missing')
        self.assertEqual(audit.compare_value(0, 1, selected)['status'], 'parser_scope_missing')

    def test_reported_conflict_cannot_be_hidden_by_alternative(self):
        selected = audit.resolve(rule(leaf('Revenue', {})), [self.fact(10)], [[self.fact(10), self.fact(20)]])
        self.assertEqual(selected['status'], 'ambiguous_scope')

    def test_q4_uses_annual_minus_nine_and_sums_precision(self):
        data = audit.manual_series()
        q4 = data[('WMT', 'Q', '2025-01-31', '企業和支持')]
        self.assertEqual(q4['value'], 14_000_000)
        self.assertEqual(q4['error'], Decimal(1_000_000))
        self.assertEqual(len(q4['primary_evidence']), 2)
        self.assertNotIn(('WMT', 'Q', '2026-07-31', '企業和支持'), data)

    def test_another_period_match_does_not_confirm_fresh_page(self):
        ref = {'category': 'Connectivity and Platforms', 'display_date': 'Jun 30, 2026',
               'raw': 12340000, 'scale': 1}
        with patch.object(audit.temporal, 'load', return_value={'rows': [['Jun 30, 2026', '12.34M', '7.89M']]}):
            self.assertTrue(audit.fresh_comcast_confirms(ref))
            self.assertEqual(ref['display_date'], 'Jun 30, 2026')
        with patch.object(audit.temporal, 'load', return_value={'rows': [['Mar 31, 2026', '12.34M', '7.89M']]}):
            self.assertFalse(audit.fresh_comcast_confirms(ref))

    def test_catalog_covers_30_and_unknown_latest_remains_unknown(self):
        self.assertEqual(len(catalog()), 30)
        self.assertEqual(audit.UNKNOWN, {'LLY', 'PGR', 'XOM'})
        self.assertIn('國際運營的市場', catalog()['MCD']['futu'])


if __name__ == '__main__':
    unittest.main()
