"""參考資料與 SEC 輸出隔離、欄位順序及財務範圍的回歸測試。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compare_missing_ir_references import pdf_lines, numbers, mcd_reference, brk_reference, sec_selections
from enforce_sec_primary_source import selected_is_sec


def capture(lines):
    return '\n'.join(f'L{i}@P1: {line}' for i, line in enumerate(lines))


class MissingReferenceTests(unittest.TestCase):
    def mcd(self):
        return capture(['Quarters Ended Nine Months Ended', 'September 30, September 30,',
            'In millions 2025 2024 2025 2024', 'U.S. $ 1 $ 2 $ 3 $ 4',
            'International Operated Markets 5 6 7 8',
            'International Developmental Licensed Markets & Corporate 9 10 11 12',
            'Total Revenues $ 15 $ 18 $ 21 $ 24', 'Operating expenses'])

    def test_mcd_selects_prior_year_quarter_not_current_or_ytd(self):
        result = mcd_reference(self.mcd())
        self.assertEqual(result['United States (US)'], 2_000_000)
        self.assertEqual(sum(result.values()), 18_000_000)

    def test_mcd_rejects_wrong_year_unit_or_unreconciled_table(self):
        for text in [self.mcd().replace('In millions', 'In thousands'),
                     self.mcd().replace('2025 2024 2025 2024', '2024 2025 2024 2025'),
                     self.mcd().replace('$ 18', '$ 19')]:
            with self.assertRaises(ValueError): mcd_reference(text)

    def test_duplicate_text_lines_must_agree(self):
        self.assertEqual(pdf_lines('L1@P2: a\nL1@P2: a'), 'a')
        with self.assertRaises(ValueError): pdf_lines('L1@P2: a\nL1@P2: b')

    def test_missing_values_are_not_zero_and_signed_values_are_preserved(self):
        self.assertEqual(numbers('(2) 0', 2), [-2_000_000, 0])
        for raw in ['— 1', '1', '1 2 3', '1% 2']:
            with self.assertRaises(ValueError): numbers(raw, 2)

    def brk24(self):
        rows = ['were as follows (in millions).', 'Third Quarter First Nine Months',
            '2024 2023 2024 2023', 'Revenues of Operating Businesses']
        rows += [label + f' {value} 1 2 3' for label, value in [
            ('GEICO', 1), ('Berkshire Hathaway Primary Group', 2), ('Berkshire Hathaway Reinsurance Group', 3),
            ('Investment income', 4), ('Total insurance', 10), ('BNSF', 20), ('BHE', 30), ('Pilot', 40),
            ('Manufacturing', 50), ('McLane', 60), ('Service and retailing', 70), ('Corporate, eliminations and other', '(1)')]]
        return capture(rows + ['$ 279 1 2 3', 'Earnings Before Income Taxes'])

    def test_brk_2024_revenue_table_excludes_profit_table(self):
        result = brk_reference(self.brk24(), 2024)
        self.assertEqual(len(result), 8)
        self.assertEqual(result['保險'], 10_000_000)
        self.assertEqual(result['公司、抵銷和其他'], -1_000_000)
        with self.assertRaises(ValueError): brk_reference(self.brk24().replace('GEICO 1', 'GEICO 2'), 2024)

    def brk25(self):
        rows = ['(in millions).', 'Third Quarter 2025', 'GEICO BH Primary BHRG',
            'Revenues $ 1 $ 2 $ 3 $ 6 $ 4 $ 10', 'Costs and expenses:']
        for label, amount in [('BNSF', 20), ('BHE', 30)]:
            rows += [label, 'Third Quarter First Nine Months', '2025 2024 2025 2024',
                f'Revenues $ {amount} 1 2 3']
        for heading, left, right in [('Manufacturing Service and retailing', 50, 70), ('Pilot McLane', 40, 60)]:
            rows += [heading, 'Third Quarter First Nine Months Third Quarter First Nine Months',
                '2025 2024 2025 2024 2025 2024 2025 2024', f'Revenues $ {left} 1 2 3 {right} 4 5 6']
        rows += ['Revenues Earnings before income taxes', 'Third Quarter First Nine Months Third Quarter First Nine Months',
            '2025 2024 2025 2024 2025 2024 2025 2024', 'Corporate, eliminations and',
            'other (1) 2 3 4 5 6 7 8', '$ 279 1 2 3 4 5 6 7', 'Additional segment data']
        return capture(rows)

    def test_brk_2025_separate_tables_and_reconciliation_use_revenues(self):
        result = brk_reference(self.brk25(), 2025)
        self.assertEqual(result['Pilot'], 40_000_000)
        self.assertEqual(result['McLane'], 60_000_000)
        self.assertEqual(result['服務和零售'], 70_000_000)
        with self.assertRaises(ValueError): brk_reference(self.brk25().replace('Quarter 2025', 'Quarter 2024'), 2025)

    def test_sec_outputs_have_no_reference_input(self):
        for ticker, period in [('MCD', '2024-09-30'), ('BRK-B', '2025-09-30')]:
            selected, digest = sec_selections(ticker, period)
            self.assertEqual(len(digest), 64)
            self.assertTrue(all(selected_is_sec(s) for s in selected.values()))
            self.assertTrue(all(f['enddate'] == period for s in selected.values() for f in s['facts']))
