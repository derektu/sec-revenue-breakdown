"""證券組成、期間、重編分類與 HD 來源錯誤裁決的負例。"""
import copy
import gzip
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import parse_progressive_reports as pgr
import continue_remaining_research as study


class ProgressiveParserTests(unittest.TestCase):
    def income(self):
        return ('Consolidated Statements of Comprehensive Income\nThree Months Ended March 31, 2026 2025\n'
            '(millions — except per share amounts)\nRevenues\n'
            'Net premiums earned 100 100\nInvestment income 10 10\n'
            'Net realized gains (losses) on security sales (2) 1\n'
            'Net holding period gains (losses) on securities 3 (4)\n'
            'Total net realized gains (losses) on securities 1 (3)\n'
            'Fees and other revenues 2 2\nService revenues 3 3\nTotal revenues 116 112\n')

    def segments(self):
        header = '(millions) Personal Lines Commercial Lines Other1 Companywide\n'
        return '\n'.join(header + 'Three Months Ended March 31, ' + str(y) + '\n'
            'Net premiums earned 70 29 1 100\nFees and other revenues 2 1 (1) 2\n'
            'Total underwriting revenue 72 30 0 102\nLosses and loss adjustment expenses:\n'
            for y in (2026, 2025))

    def test_signed_income_components_and_total_are_independently_reconciled(self):
        rs = pgr.parse_income(self.income(), 2026, 3)
        self.assertEqual(rs[0]['values_usd']['Net realized gains (losses) on security sales'], -2_000_000)
        self.assertEqual(rs[1]['values_usd']['Total net realized gains (losses) on securities'], -3_000_000)
        for text in [self.income().replace('1 (3)\n', '2 (3)\n'),
                     self.income().replace('116 112', '117 112')]:
            with self.assertRaises(ValueError): pgr.parse_income(text, 2026, 3)

    def test_wrong_year_columns_and_duplicate_rows_are_rejected(self):
        for text in [self.income().replace('2026 2025', '2025 2026'),
                     self.income() + 'Investment income 10 10\n']:
            with self.assertRaises(ValueError): pgr.parse_income(text, 2026, 3)

    def test_segment_fees_including_negative_other_are_preserved(self):
        rs = pgr.parse_segments(self.segments(), 2026, 3)
        self.assertEqual(rs[0]['values_usd']['個人保險'], 72_000_000)
        self.assertEqual(rs[0]['values_usd']['其他'], 0)
        self.assertEqual(rs[0]['fees_usd'][2], -1_000_000)

    def test_wrong_segment_order_missing_period_and_conflicting_totals_fail(self):
        for text in [self.segments().replace('Personal Lines Commercial Lines', 'Commercial Lines Personal Lines'),
                     self.segments().split('Three Months Ended March 31, 2025')[0],
                     self.segments().replace('72 30 0 102', '71 30 0 101')]:
            with self.assertRaises(ValueError): pgr.parse_segments(text, 2026, 3)
        with self.assertRaises(ValueError): pgr.parse_segments(self.segments(), 2024, 3)


class HomeDepotAdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(gzip.decompress((ROOT / 'research/sec-30-baseline-2026-11-04/HD.json.gz').read_bytes()))
        records, pools = study.pools_for('HD', cls.data)
        cls.labels = ['Hardlines', 'Building Materials', 'Decor', 'Other']
        def values(end, start=None):
            fs, conflicts = pools[end] if start is None else ([f for r in records if r['filing']['reportDate'] == end
                for f in r['facts'] if f.get('startdate') == start and f.get('enddate') == end], [])
            return [study.selection('HD', label, fs, conflicts)['value'] for label in cls.labels]
        half = values('2024-07-28', '2024-01-29'); q3 = values('2024-10-27'); q4 = values('2025-02-02')
        first = [v // 2 for v in half]; second = [v - a for v, a in zip(half, first)]
        second[0] += 5_000_000; second[3] -= 5_000_000
        fourth = list(q4); fourth[0] -= 5_000_000; fourth[3] += 5_000_000
        cls.ui = {'mode': 'Quarterly', 'columns': cls.labels, 'points_usd': {
            '2024-03-31': first, '2024-06-30': second, '2024-09-30': q3, '2024-12-31': fourth}}

    def test_same_annual_total_is_not_enough_without_same_quarter_scope(self):
        result = study.hd_proof(self.data, self.ui)
        self.assertEqual(result['Hardlines']['prior_half_reference_difference_usd'], 5_000_000)
        changed = copy.deepcopy(self.ui)
        changed['points_usd']['2024-09-30'][0] += 1_000_000
        changed['points_usd']['2024-12-31'][0] -= 1_000_000
        with self.assertRaises(ValueError): study.hd_proof(self.data, changed)

    def test_ttm_and_source_value_disagreement_cannot_be_accepted(self):
        changed = copy.deepcopy(self.ui); changed['mode'] = 'TTM'
        with self.assertRaises(ValueError): study.hd_proof(self.data, changed)
        proof = study.hd_proof(self.data, self.ui)
        row = {'source': 'stockanalysis', 'kind': 'Q', 'sec_period_end': '2025-02-02', 'category': 'Hardlines',
               'raw': self.ui['points_usd']['2024-12-31'][0] + 1, 'scale': 1,
               'status': 'scope_candidate_differs', 'selected': proof['Hardlines']['q4']}
        study.apply_hd([row], self.data, self.ui)
        self.assertEqual(row['status'], 'scope_candidate_differs')
