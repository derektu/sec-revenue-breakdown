import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from evaluate_eight_quarter_status import assess


class EightQuarterStatusTests(unittest.TestCase):
    def rows(self):
        return [{'source': 'stockanalysis', 'kind': 'Q', 'sec_period_end': str(i),
                 'period_reviewed': True, 'role': 'scope_candidate', 'raw': 0,
                 'status': 'exact_scope_candidate_match'} for i in range(8)]

    def test_all_eight_quarters_and_zero_values_are_valid(self):
        self.assertEqual(assess(self.rows(), list(map(str, range(8))), 'stockanalysis')['status'], 'OK')

    def test_many_matching_cells_cannot_replace_missing_quarter(self):
        rows = self.rows()[:-1] * 5
        self.assertEqual(assess(rows, list(map(str, range(8))), 'stockanalysis')['status'], 'Fail')

    def test_cannot_mix_sources_to_fill_eighth_quarter(self):
        rows = self.rows(); rows[-1]['source'] = 'futu'
        self.assertEqual(assess(rows, list(map(str, range(8))), 'stockanalysis')['status'], 'Fail')

    def test_matching_manual_tables_do_not_complete_parser(self):
        rows = self.rows(); rows[0]['role'] = 'primary_text_reviewed_definition'
        self.assertEqual(assess(rows, list(map(str, range(8))), 'stockanalysis')['status'], 'Fail')

    def test_precision_candidate_needs_explicit_adjudication(self):
        rows = self.rows(); rows[0]['status'] = 'within_scope_candidate_precision'
        self.assertEqual(assess(rows, list(map(str, range(8))), 'stockanalysis')['status'], 'Fail')

    def test_period_proposal_does_not_pass_on_equal_amount(self):
        rows = self.rows(); rows[0]['period_reviewed'] = False
        self.assertEqual(assess(rows, list(map(str, range(8))), 'stockanalysis')['status'], 'Fail')

    def test_old_eight_quarters_do_not_hide_missing_target_quarter(self):
        result = assess(self.rows(), list(map(str, range(1, 9))), 'stockanalysis')
        self.assertEqual(result['status'], 'Fail')
        self.assertEqual(result['reference_quarters_present'], 8)
        self.assertEqual(result['target_quarters_present'], 7)
        self.assertEqual(result['missing_target_periods'], ['8'])
        self.assertEqual(result['reference_periods_outside_target'], ['0'])

    def test_missing_historical_period_is_not_relabelled_latest(self):
        result = assess(self.rows()[1:], list(map(str, range(8))), 'stockanalysis')
        self.assertEqual(result['missing_target_periods'], ['0'])
        self.assertEqual(result['reference_periods_outside_target'], [])
