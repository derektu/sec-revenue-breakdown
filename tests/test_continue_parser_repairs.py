import sys
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import continue_parser_repairs as repair
from cohort_rule_catalog import R, S


class ContinueParserRepairsTests(unittest.TestCase):
    def test_oracle_mapping_is_fiscal_not_nearest_calendar_date(self):
        self.assertTrue(repair.oracle_period('Jun 30, 2026', '2026-05-31'))
        self.assertFalse(repair.oracle_period('Mar 31, 2026', '2026-05-31'))
        self.assertFalse(repair.oracle_period('Jun 30, 2027', '2027-05-31'))

    def test_retired_columns_require_complete_matching_active_set(self):
        rows = [{'category': 'Active', 'raw': 1, 'status': 'exact_scope_candidate_match', 'period_reviewed': True,
                 'selected': {'value': 1}}, {'category': 'Old', 'raw': None, 'period_reviewed': True}]
        repair.mark_inactive(rows, ['Active'], 'source', 'reason', {'status': 'observed', 'value': 2})
        self.assertNotIn('status', rows[-1])
        repair.mark_inactive(rows, ['Active'], 'source', 'reason', {'status': 'observed', 'value': 1})
        self.assertEqual(rows[-1]['status'], 'reference_not_applicable_evidenced')
        self.assertIsNone(rows[-1]['raw'])

    def test_hedging_reconciliation_preserves_all_segment_scopes(self):
        def f(value, dims):
            return {'concept': R, 'dimensions': dims, 'unit': 'iso4217:USD', 'value': value, 'decimals': 'INF'}
        fs = [f(100, {})] + [f(value, {S: member}) for value, member in zip([70, 20, 5],
            ['goog:GoogleServicesMember', 'goog:GoogleCloudMember', 'us-gaap:AllOtherSegmentsMember'])]
        self.assertEqual(repair.google_hedging(fs, [])['value'], 5)
        fs[-1]['dimensions']['UnexpectedAxis'] = 'Other'
        self.assertEqual(repair.google_hedging(fs, [])['status'], 'parser_scope_missing')

    def google_text(self):
        values = [('Google Search & other', 10), ('YouTube ads', 2), ('Google Network', 3), ('Google advertising', 15),
            ('Google subscriptions, platforms, and devices', 5), ('Google Services total', 20),
            ('Google Cloud', 4), ('Other Bets', 2), ('Hedging gains (losses)', -1), ('Total revenues', 25)]
        return ('Q4 2025 Supplemental Information (in millions,\nQuarter Ended December 31,\n2024 2025\n'
            + '\n'.join(label + ' 0 ' + (f'({-value})' if value < 0 else str(value)) for label, value in values)
            + '\nSegment Operating Results')

    def test_google_direct_quarter_reads_signed_current_column(self):
        with patch.object(repair.subprocess, 'run', return_value=SimpleNamespace(stdout=self.google_text())):
            self.assertEqual(repair.parse_google_release(Path('fixture.pdf'))['Hedging gains (losses)'], -1_000_000)

    def test_google_missing_or_wrong_header_fails(self):
        with patch.object(repair.subprocess, 'run', return_value=SimpleNamespace(stdout=self.google_text().replace('2024 2025', '2025 2026'))):
            with self.assertRaises(ValueError): repair.parse_google_release(Path('fixture.pdf'))

    def test_reference_error_requires_primary_scope_and_fresh_original_period(self):
        url = 'https://www.sec.gov/Archives/edgar/data/fixture.htm'
        row = {'source': 'stockanalysis', 'ticker': 'MSFT', 'sec_period_end': '2026-03-31',
            'category': 'More Personal Computing', 'raw': 123, 'scale': 1, 'status': 'scope_candidate_differs',
            'selected': {'value': 90, 'facts': [{'source_url': url, 'enddate': '2026-03-31'}]}}
        primary = {'MSFT': {'reported_revenue_usd': 90, 'other_segment_operating_income_usd': 123, 'source_url': url}}
        ui = {'MSFT': {'columns': ['Date', 'More Personal Computing'], 'rows': [['Jun 30, 2026', '123.00M']]}}
        repair.adjudicate(row, primary, ui)
        self.assertEqual(row['status'], 'scope_candidate_differs')
        ui['MSFT']['rows'] = [['Mar 31, 2026', '0.000000123B']]
        repair.adjudicate(row, primary, ui)
        self.assertEqual(row['status'], 'explained_reference_error')
        self.assertEqual(row['selected']['value'], 90)
