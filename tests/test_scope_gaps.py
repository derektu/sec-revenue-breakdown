import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import review_scope_gaps as scope


class ScopeGapTests(unittest.TestCase):
    def test_comparative_uses_latest_source_even_when_input_order_or_amount_differs(self):
        old = {'filing': {'filingDate': '2025-01-01'}, 'facts': [{'value': 100}]}
        new = {'filing': {'filingDate': '2026-01-01'}, 'facts': [{'value': 80}]}
        engine = SimpleNamespace(quarter=lambda facts, target, form, previous: (facts, []))
        old['filing']['form'] = new['filing']['form'] = '10-Q'
        with patch.object(scope.temporal, 'runner', return_value=engine):
            result = scope.latest_training_comparative([new, old], '2024-10-31')
        self.assertEqual(result['source_filing']['filingDate'], '2026-01-01')
        self.assertEqual(result['facts'][0]['value'], 80)

    def test_residual_requires_revenues_and_all_three_exact_scopes(self):
        def fact(value, dims, concept='us-gaap:Revenues'):
            return {'concept': concept, 'unit': 'iso4217:USD', 'dimensions': dims, 'value': value}
        facts = [fact(100, {})] + [fact(v, {scope.SEGMENT: 'wmt:' + m, scope.CONSOLIDATION: scope.OPERATING})
            for v, m in zip([50, 30, 18], ['WalmartUSMember', 'WalmartInternationalMember', 'SamsClubUSMember'])]
        r = scope.corporate_residual(facts)
        self.assertEqual(r['value'], 2)
        self.assertTrue(r['identity_check_is_tautological'])
        self.assertEqual(r['status'], 'arithmetic_candidate_definition_unverified')
        facts[-1]['concept'] = 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'
        self.assertIsNone(scope.corporate_residual(facts)['value'])

    def test_bridge_only_accepts_the_two_reviewed_periods_and_full_scopes(self):
        def f(value, dims, end):
            return {'concept': scope.NEE_CONCEPT, 'unit': 'iso4217:USD', 'dimensions': dims,
                    'value': value, 'startdate': '2024-01-01', 'enddate': end}
        a = f(100, scope.FPL_SEGMENT, '2024-12-31')
        n = f(70, scope.ENTITY, '2024-09-30')
        records = [{'filing': {'reportDate': '2024-12-31'}, 'facts': [a]},
                   {'filing': {'reportDate': '2024-09-30'}, 'facts': [n]}]
        result = scope.derive_nee_fpl_q4(records)
        self.assertEqual(result['value'], 30)
        self.assertEqual(result['nine_month_evidence']['dimensions'], scope.ENTITY)
        n['dimensions'] = {}
        self.assertIsNone(scope.derive_nee_fpl_q4(records))

    def test_conflicting_exact_scope_cannot_be_selected_by_matching_amount(self):
        f = {'concept': 'us-gaap:Revenues', 'unit': 'iso4217:USD', 'dimensions': {}, 'value': 1}
        self.assertIsNone(scope.unique_scope([f, {**f, 'value': 2}], f['concept'], {}))


if __name__ == '__main__':
    unittest.main()
