"""跨來源裁決檢查期間、完整分類、語意與 SEC 輸出邊界。"""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from parse_company_reference_excerpts import lly_reference, xom_reference, LLY_URL, XOM_URL
from adjudicate_cross_source_references import verdict


def excerpt(url, lines):
    return url + '\n' + '\n'.join(f'L{i}@P1: {line}' for i, line in enumerate(lines))


class CrossSourceAdjudicationTests(unittest.TestCase):
    def lly(self):
        return excerpt(LLY_URL, ['Tables present dollars and shares in millions',
            'Three Months Ended September 30,', '2026 2025', 'U.S. Outside U.S. Total U.S. Outside U.S. Total',
            'Total cardiometabolic health 1 2 3 1 2 3', 'Total oncology 2 4 6 2 4 6',
            'Total immunology 3 6 9 3 6 9', 'Neuroscience 4 8 12 4 8 12',
            'Other oncology 1 1 2 1 1 2', 'Other 5 10 15 5 10 15', 'Revenue 15 30 45 15 30 45'])

    def xom(self):
        return excerpt(XOM_URL, ['(millions of dollars, unless noted)', 'Three Months Ended', 'September 30,',
            'Nine Months Ended', 'September 30,', '2026 2025 2026 2025',
            'Sales and other operating revenue 3 80 80 240 240', 'Income from equity affiliates 1 1 3 3',
            'Other income 1 1 3 3', 'Total revenues and other income 82 82 246 246',
            'Our four reportable segments are Upstream, Energy Products, Chemical Products, and Specialty Products.',
            'Upstream Energy Products Chemical Products Specialty Products Segment',
            'U.S. Non-U.S. U.S. Non-U.S. U.S. Non-U.S. U.S. Non-U.S. Total',
            'Three Months Ended September 30, 2026',
            'Sales and other operating revenue 10 10 10 10 10 10 10 10 80',
            'Intersegment revenue 1 1 1 1 1 1 1 1 8',
            'Segment revenues and other income 11 11 11 11 11 11 11 11 88',
            'Reconciliation of consolidated revenues', 'Segment revenues and other income 88',
            'Other revenues (2) 2', 'Elimination of intersegment revenues (8)',
            'Total consolidated revenues and other income 82'])

    def test_lly_exact_global_other_is_not_other_oncology(self):
        values = lly_reference(self.lly())
        self.assertEqual(values['Other'], 15_000_000)
        self.assertEqual(sum(values.values()), 45_000_000)

    def test_lly_wrong_year_units_and_missing_class_are_rejected(self):
        for before, after in [('2026 2025', '2025 2026'), ('millions', 'billions'), ('Total immunology', 'Omitted')]:
            with self.assertRaises(ValueError): lly_reference(self.lly().replace(before, after))

    def test_xom_two_income_bases_and_consolidated_deductions(self):
        result = xom_reference(self.xom())
        self.assertEqual(result['all_income']['上游'], 22_000_000)
        self.assertEqual(result['gross_sales']['上游'], 22_000_000)
        self.assertEqual(result['all_income']['其他收入'], -1_000_000)

    def test_xom_wrong_source_period_or_consolidated_total_is_rejected(self):
        for before, after in [(XOM_URL, 'https://example.com/report.pdf'),
                              ('Three Months Ended September 30, 2026', 'Nine Months Ended September 30, 2026'),
                              ('Total consolidated revenues and other income 82', 'Total consolidated revenues and other income 99')]:
            with self.assertRaises(ValueError): xom_reference(self.xom().replace(before, after))

    def gate_fixture(self):
        targets = [f'{year}-{end}' for year in (2025, 2026) for end in ('03-31', '06-30', '09-30', '12-31')]
        rows = [{'period_end': end, 'category': 'a', 'status': 'exact_scope_candidate_match',
            'selected': {'status': 'observed', 'value': 1, 'facts': [{'source_url': 'https://www.sec.gov/Archives/edgar/data/1/000000000000000001/a.htm'}]},
            'period_reviewed': True, 'semantic_review': 'reviewed reported category'} for end in targets]
        return targets, rows

    def test_eight_numeric_hits_do_not_replace_required_category_coverage(self):
        targets, rows = self.gate_fixture()
        result = verdict(rows, targets, {end: {'a', 'b'} for end in targets})
        self.assertIn('required_category_coverage_incomplete', result['fail_reasons'])

    def test_unreviewed_meaning_or_non_sec_output_cannot_pass(self):
        targets, rows = self.gate_fixture(); required = {end: {'a'} for end in targets}
        self.assertEqual(verdict(rows, targets, required)['status'], 'OK')
        broken = copy.deepcopy(rows);broken[0]['semantic_review'] = False
        self.assertIn('period_or_category_not_reviewed', verdict(broken, targets, required)['fail_reasons'])
        broken = copy.deepcopy(rows);broken[0]['selected']['facts'][0]['source_url'] = LLY_URL
        self.assertIn('SEC_output_missing', verdict(broken, targets, required)['fail_reasons'])


if __name__ == '__main__':
    unittest.main()
