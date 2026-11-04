"""SEC 附件、收入組成、分部欄位及季度證券差異的負例。"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from parse_progressive_sec import parse_snapshot, numeric_row
from evaluate_progressive_sec import period_facts, apply_pgr_sec


class ProgressiveSecTests(unittest.TestCase):
    def fixture(self):
        source = 'https://www.sec.gov/Archives/edgar/data/80661/000008066126000177/pgr-20260331.htm'
        income = [['Three Months Ended March 31,', '2026', '2025'], ['(millions — except per share amounts)'], ['Revenues'],
            ['Net premiums earned', '100', '90'], ['Investment income', '10', '9'],
            ['Net realized gains (losses) on security sales', '(2)', '(3)'],
            ['Net holding period gains (losses) on securities', '3', '2'],
            ['Total net realized gains (losses) on securities', '1', '(1)'],
            ['Fees and other revenues', '2', '2'], ['Service revenues', '3', '3'], ['Total revenues', '116', '103']]
        tables = [{'index': 1, 'rows': income}]
        for year, premiums in [(2026, ['60', '30', '10', '100']), (2025, ['50', '30', '10', '90'])]:
            tables.append({'index': year, 'rows': [['(millions)', 'Personal Lines', 'Commercial Lines', 'Other1', 'Companywide'],
                [f'Three Months Ended March 31, {year}'], ['Net premiums earned'] + premiums,
                ['Fees and other revenues', '2', '1', '(1)', '2'],
                ['Total underwriting revenue', str(int(premiums[0]) + 2), '31', '9', str(int(premiums[3]) + 2)]]})
        return {'format': 'SEC_DOM_nonempty_cell_text', 'source_url': source, 'tables': tables}

    def test_signed_fees_and_income_keep_sec_provenance(self):
        result = parse_snapshot(self.fixture(), 'capture-sha')
        personal = next(f for f in result if f['year'] == 2026 and f['label'] == '個人保險')
        other = next(f for f in result if f['year'] == 2026 and f['label'] == '其他')
        self.assertEqual(personal['value'], 62_000_000)
        self.assertEqual(other['value'], 9_000_000)
        self.assertEqual(personal['source_artifact_sha256'], 'capture-sha')
        self.assertIn('sec.gov/Archives', personal['source_url'])

    def test_issuer_origin_or_annual_parent_document_is_rejected(self):
        for url in ['https://investors.example.com/pgr-20260331.htm',
                    'https://www.sec.gov/Archives/edgar/data/80661/000008066126000086/pgr-20251231.htm']:
            data = self.fixture(); data['source_url'] = url
            with self.assertRaises(ValueError): parse_snapshot(data, 'sha')

    def test_column_order_units_and_missing_period_are_rejected(self):
        for variant in ['years', 'units', 'period', 'segment_order']:
            data = self.fixture()
            if variant == 'years': data['tables'][0]['rows'][0][1:] = ['2025', '2026']
            if variant == 'units': data['tables'][0]['rows'][1] = ['(thousands)']
            if variant == 'period': data['tables'].pop()
            if variant == 'segment_order': data['tables'][1]['rows'][0][1:3] = ['Commercial Lines', 'Personal Lines']
            with self.assertRaises(ValueError): parse_snapshot(data, 'sha')

    def test_cross_table_totals_cannot_disagree_even_when_each_segment_adds_up(self):
        data = self.fixture()
        data['tables'][1]['rows'][2] = ['Net premiums earned', '61', '30', '10', '101']
        data['tables'][1]['rows'][4] = ['Total underwriting revenue', '63', '31', '9', '103']
        with self.assertRaises(ValueError): parse_snapshot(data, 'sha')

    def test_dashes_missing_or_duplicate_rows_are_not_zero(self):
        for rows in [[['Investment income', '—', '1']],
                     [['Investment income', '1', '2'], ['Investment income', '1', '2']], []]:
            with self.assertRaises(ValueError): numeric_row({'rows': rows}, 'Investment income', 2)

    def test_q4_requires_identical_scope_and_fiscal_start(self):
        fact = parse_snapshot(self.fixture(), 'sha')[0]
        annual = {**fact, 'kind': 'FY', 'month': 12, 'value': 200}
        nine = {**fact, 'kind': 'YTD9', 'month': 9, 'value': 150}
        result = period_facts([annual, nine], 2026, 12)
        self.assertEqual(result[fact['label']]['value'], 50)
        changed = {**nine, 'dimensions': {**nine['dimensions'], 'extra_scope': 'Other'}}
        with self.assertRaises(ValueError): period_facts([annual, changed], 2026, 12)

    def test_version_selection_uses_earliest_report_not_reference_amount(self):
        fact = parse_snapshot(self.fixture(), 'sha')[0]
        later = {**fact, 'source_report_date': '2027-03-31', 'value': 999}
        selected = period_facts([later, fact], 2026, 3)
        self.assertEqual(selected[fact['label']]['value'], fact['value'])
