"""SEC 日期／跨欄表頭與固定匯率排除的 Comcast 回歸測試。"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from parse_comcast_sec_dom import parse_snapshot
from evaluate_comcast_sec import extract_sources, build_quarters


class ComcastSecDomTests(unittest.TestCase):
    def fixture(self):
        return json.loads((ROOT / 'research/sec-dom-sources-20261104/CMCSA-2026Q3.json').read_text())

    def test_quarter_and_ytd_columns_exclude_currency_reconciliation(self):
        result = parse_snapshot(self.fixture(), 'capture-sha')
        facts = {(f['kind'], f['year'], f['label']): f for f in result['facts']}
        self.assertEqual(len(facts), 8)
        self.assertEqual(facts['Q', 2026, 'Connectivity and Platforms']['value'], 19_663_000_000)
        self.assertEqual(facts['YTD9', 2026, 'Connectivity and Platforms']['value'], 59_420_000_000)
        self.assertEqual(facts['Q', 2025, 'Content and Experiences']['value'], 9_898_000_000)
        self.assertEqual(result['rejected_constant_currency_tables'], [47])

    def test_all_original_periods_and_q4_operands_are_reproducible(self):
        manifest = json.loads((ROOT / 'research/sec-dom-sources-20261104/CMCSA-manifest.json').read_text())
        facts, sources = extract_sources(manifest)
        quarters = build_quarters(facts)
        self.assertEqual(len(sources), 7)
        self.assertEqual(len(quarters), 16)
        # 2026 比較欄重編，不得替換 2025 當期申報。
        self.assertEqual(quarters['2025-09-30', 'Content and Experiences']['value'], 11_742_000_000)
        q4 = quarters['2025-12-31', 'Connectivity and Platforms']
        self.assertEqual(q4['value'], q4['annual_evidence']['value'] - q4['nine_month_evidence']['value'])
        broken = copy.deepcopy(facts)
        next(f for f in broken if f['kind'] == 'FY' and f['year'] == 2025)['dimensions']['basis'] = 'external_only'
        with self.assertRaises(ValueError): build_quarters(broken)

    def test_missing_wrong_order_or_ambiguous_columns_are_rejected(self):
        variants = []
        d = self.fixture(); d['tables'][0]['rows'][2][1][1][2] = '2025'; variants.append(d)
        d = self.fixture(); d['tables'][0]['rows'][1][1][0][2] = 'Three Months Ended June 30,'; variants.append(d)
        d = self.fixture(); d['tables'][0]['rows'][3][1].append([5, 1, '999']); variants.append(d)
        d = self.fixture(); d['tables'][0]['rows'][3][1][1][2] = '—'; variants.append(d)
        for data in variants:
            with self.assertRaises(ValueError): parse_snapshot(data, 'sha')

    def test_duplicate_business_group_and_non_sec_source_are_rejected(self):
        d = self.fixture(); d['tables'].append(copy.deepcopy(d['tables'][0]))
        with self.assertRaises(ValueError): parse_snapshot(d, 'sha')
        d = self.fixture(); d['source_url'] = d['source_url'].replace('www.sec.gov', 'company.example')
        with self.assertRaises(ValueError): parse_snapshot(d, 'sha')


if __name__ == '__main__':
    unittest.main()
