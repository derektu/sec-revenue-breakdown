import sys
from decimal import Decimal
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import historical_rule_experiments as experiment


class HistoricalRuleTests(unittest.TestCase):
    def test_missing_operand_cannot_be_added_as_zero(self):
        result = experiment.aggregate([{'status': 'parser_missing', 'value': None, 'facts': []}])
        self.assertEqual(result['status'], 'missing_or_ambiguous_operand')
        self.assertIsNone(result['value'])

    def test_q4_precision_uses_both_original_operands(self):
        fact = {'decimals': '-6', 'derivation': 'annual_minus_nine_months',
                'annual_evidence': {'decimals': '-6'}, 'nine_month_evidence': {'decimals': '-6'}}
        self.assertEqual(experiment.fact_error(fact), Decimal(1_000_000))

    def test_rounding_consistency_is_distinct_from_equality_and_disagreement(self):
        left = {'status': 'observed', 'value': 1_000_000, 'facts': [{'decimals': '-6'}]}
        right = {'status': 'observed', 'value': 2_000_000, 'facts': [{'decimals': '-6'}]}
        self.assertEqual(experiment.reconcile(left, right), 'within_reported_precision')
        self.assertEqual(experiment.reconcile(left, {**right, 'value': 3_000_000}), 'differs')
        self.assertEqual(experiment.reconcile(left, left), 'matches_exact')
        self.assertEqual(experiment.reconcile(left, {**right, 'facts': [{}]}), 'precision_unknown')

    def test_member_bridge_preserves_original_and_rejects_wrong_scope_or_date(self):
        rules = experiment.definitions('NVDA')
        rule = rules['member_aliases'][0]
        original = {'concept': rule['concept'], 'dimensions': rule['original_dimensions']}
        record = {'filing': {'reportDate': '2024-10-27'}, 'facts': [original]}
        bridged = experiment.normalize_history([record], rules)[0]['facts'][0]
        self.assertEqual(bridged['dimensions'], rule['dimensions'])
        self.assertEqual(bridged['original_dimensions'], original['dimensions'])
        self.assertNotIn('normalization_rule_id', original)
        wrong_date = {**record, 'filing': {'reportDate': '2025-10-26'}}
        self.assertEqual(experiment.normalize_history([wrong_date], rules)[0]['facts'][0], original)
        wrong_scope = {**original, 'dimensions': {**original['dimensions'], 'OtherAxis': 'OtherMember'}}
        self.assertEqual(experiment.normalize_history([{**record, 'facts': [wrong_scope]}], rules)[0]['facts'][0], wrong_scope)


if __name__ == '__main__':
    unittest.main()
