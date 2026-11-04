"""XOM 跨 CIK、期間、收入口徑與 Q4 的拒絕判定。"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from parse_xom_sec import parse_snapshot, parse_sales_page
from evaluate_xom_sec import quarter
from enforce_sec_primary_source import selected_is_sec


class XomSecTests(unittest.TestCase):
    def fixture(self, name='XOM-2026Q1.json'):
        return json.loads((ROOT / 'research/xom-sec-dom-20261104' / name).read_text())

    def observations(self):
        result = []
        for path in (ROOT / 'research/xom-sec-dom-20261104').glob('XOM-*.json'):
            result.extend(parse_snapshot(json.loads(path.read_text()), hashlib.sha256(path.read_bytes()).hexdigest()))
        return result

    def test_reported_income_and_deductions_reconcile_to_sales(self):
        facts = parse_snapshot(self.fixture(), 'source-sha')
        q = {f['label']: f for f in facts if f['year'] == 2026}
        self.assertEqual(q['Upstream']['value'], 28_824_000_000)
        self.assertEqual(q['其他收入']['value'], -608_000_000)
        self.assertEqual(q['Income from equity affiliates']['value'], -1_369_000_000)
        categories = ['Upstream', 'Energy Products', 'Chemical Products', 'Specialty Products', 'Other revenues', '分部間收入', '其他收入', 'Income from equity affiliates']
        self.assertEqual(sum(q[k]['value'] for k in categories), q['Sales and other operating revenue']['value'])

    def test_q4_uses_full_scope_and_all_actual_operands(self):
        facts = self.observations(); q4 = quarter(facts, '2025-12-31')['Upstream']
        self.assertEqual(q4['value'], 24_487_000_000)
        self.assertEqual(q4['annual_evidence']['value'], 107_151_000_000)
        self.assertEqual(q4['nine_month_evidence']['value'], 82_664_000_000)
        self.assertTrue(selected_is_sec({'status': 'observed', 'facts': [q4]}))
        broken = copy.deepcopy(facts)
        next(f for f in broken if f['kind'] == 'FY' and f['year'] == 2025 and f['label'] == 'Upstream')['source_cik'] = '2115436'
        with self.assertRaises(ValueError): quarter(broken, '2025-12-31')
        with self.assertRaises(ValueError): quarter(facts, '2026-09-30')

    def test_actual_supplemental_sales_and_geography_operands(self):
        path = ROOT / 'research/xom-sec-dom-20261104/XOM-june-sales-web.txt'
        facts = parse_sales_page(path.read_text(), 'web-text-sha')
        q = {(f['year'], f['label']): f for f in facts}
        self.assertEqual(q[2026, 'Upstream']['value'], 34_527_000_000)
        self.assertEqual(q[2025, 'Energy Products']['value'], 71_003_000_000)
        self.assertEqual(q[2025, 'Energy Products']['source_line_numbers']['Intersegment revenue'], 496)
        text = path.read_text().replace('Three Months Ended June 30, 2025', 'Three Months Ended March 31, 2025')
        with self.assertRaises(ValueError): parse_sales_page(text, 'sha')

    def test_reject_wrong_period_units_geography_and_missing_amount(self):
        variants = []
        d = self.fixture();d['tables'][1]['rows'][2].reverse();d['tables'][1]['rows'][2][0] = 'Global';variants.append(d)
        d = self.fixture();d['tables'][0]['rows'][2].reverse();variants.append(d)
        d = self.fixture();d['tables'][1]['rows'][1][0] = '(billions of dollars)';variants.append(d)
        d = self.fixture();d['tables'][1]['rows'][10][1] = '—';variants.append(d)
        d = self.fixture();d['source_url'] = d['source_url'].replace('www.sec.gov', 'company.example');variants.append(d)
        for data in variants:
            with self.assertRaises(ValueError): parse_snapshot(data, 'sha')

    def test_reject_duplicate_period_and_inconsistent_independent_total(self):
        d = self.fixture();d['tables'].append(copy.deepcopy(d['tables'][1]))
        with self.assertRaises(ValueError): parse_snapshot(d, 'sha')
        d = self.fixture();d['tables'][1]['rows'][-1][1] = '999,999'
        with self.assertRaises(ValueError): parse_snapshot(d, 'sha')


if __name__ == '__main__':
    unittest.main()
