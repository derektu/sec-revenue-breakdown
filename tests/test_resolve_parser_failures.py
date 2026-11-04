import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from resolve_parser_failures import reviewed_period, resolve_retired_columns, parse_meta_direct_quarter


class ParserFailureResolutionTests(unittest.TestCase):
    def test_date_policy_requires_reviewed_issuer_weekday_and_range(self):
        self.assertTrue(reviewed_period('DIS', 'Sep 30, 2025', '2025-09-27'))
        self.assertTrue(reviewed_period('JNJ', 'Sep 30, 2025', '2025-09-28'))
        self.assertFalse(reviewed_period('DIS', 'Sep 30, 2025', '2025-09-28'))
        self.assertFalse(reviewed_period('ORCL', 'Sep 30, 2025', '2025-08-31'))
        self.assertFalse(reviewed_period('DIS', 'Sep 30, 2027', '2027-09-25'))

    def rows(self):
        return [{'source': 'stockanalysis', 'kind': 'Q', 'category': c,
            'display_date': 'Sep 30, 2025', 'sec_period_end': '2025-09-27', 'period_reviewed': False,
            'raw': None if c == 'Media and Entertainment' else 0,
            'status': 'reference_missing' if c == 'Media and Entertainment' else 'exact_scope_candidate_match'}
            for c in ['Entertainment', 'Parks and Experiences', 'Sports', 'Media and Entertainment']]

    def test_retired_empty_column_is_not_zero_and_preserves_original(self):
        rows = self.rows(); resolve_retired_columns('DIS', rows)
        self.assertEqual(rows[-1]['status'], 'reference_not_applicable_evidenced')
        self.assertIsNone(rows[-1]['raw'])
        self.assertEqual(rows[-1]['display_date'], 'Sep 30, 2025')
        self.assertEqual(rows[-1]['sec_period_end'], '2025-09-27')

    def test_missing_active_classification_is_not_excused(self):
        rows = self.rows(); rows[0]['raw'] = None; rows[0]['status'] = 'reference_missing'
        resolve_retired_columns('DIS', rows)
        self.assertEqual(rows[-1]['status'], 'reference_missing')

    def test_nonempty_retired_column_requires_investigation(self):
        rows = self.rows(); rows[-1]['raw'] = 1
        resolve_retired_columns('DIS', rows)
        self.assertNotEqual(rows[-1]['status'], 'reference_not_applicable_evidenced')

    def release(self):
        rows = [['Segment Information'], ['(In millions)'],
            ['', '', 'Three Months Ended December 31,', '', 'Twelve Months Ended December 31,'],
            ['', '', '2025', '', '2024', '', '2025', '', '2024']]
        for label, q, annual in [('Advertising', 10, 100), ('Other revenue', 2, 20),
                                  ('Family of Apps', 12, 120), ('Reality Labs', 3, 30), ('Total revenue', 15, 150)]:
            rows.append([label, '', str(q), '', '0', '', str(annual), '', '0'])
        rows.append(['Income (loss) from operations:'])
        rows.append(['Family of Apps', '', '999'])
        return '<table>' + ''.join('<tr>' + ''.join('<td>' + c + '</td>' for c in r) + '</tr>' for r in rows) + '</table>'

    def test_direct_quarter_not_annual_or_operating_income_column(self):
        self.assertEqual(parse_meta_direct_quarter(self.release())['Advertising'], 10_000_000)

    def test_unreviewed_year_and_duplicate_table_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_meta_direct_quarter(self.release().replace('2025', '2026'))
        with self.assertRaises(ValueError):
            parse_meta_direct_quarter(self.release() * 2)

    def test_inconsistent_direct_quarter_fails_closed(self):
        with self.assertRaises(ValueError):
            parse_meta_direct_quarter(self.release().replace('<td>15</td>', '<td>16</td>'))
