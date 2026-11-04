"""以實際凍結收據確認缺季，不把歷史缺口寫成最新季缺口。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_remaining_company_gaps import audit


class RemainingGapAuditTests(unittest.TestCase):
    def test_saved_targets_and_missing_periods(self):
        result = audit()
        companies = {c['ticker']: c for c in result['companies']}
        self.assertNotIn('XOM', companies)
        self.assertFalse(result['completion_status_changed'])
        self.assertEqual(companies['MCD']['missing_target_periods'], ['2024-09-30'])
        self.assertEqual(companies['BRK-B']['missing_target_periods'], ['2024-09-30', '2025-09-30'])
        self.assertEqual(companies['CVX']['missing_target_periods'], ['2024-09-30', '2025-09-30', '2025-12-31'])
        self.assertEqual(companies['LLY']['target_quarters_present'], 7)
        self.assertEqual(companies['LLY']['reference_periods_outside_target'], ['2024-09-30'])
        self.assertEqual(companies['PLD']['missing_target_periods'], [])
        self.assertFalse(companies['PLD']['reference_is_original_vendor'])
