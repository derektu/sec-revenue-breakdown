"""CAT gross 分部收入、兩組抵銷及獨立地區表對帳。"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from parse_caterpillar_sec import parse_snapshot


class CaterpillarSecTests(unittest.TestCase):
    def fixture(self):
        return json.loads((ROOT / 'research/sec-dom-sources-20261104/CAT-2026Q3.json').read_text())

    def test_actual_sec_tables_reconcile_all_six_income_outputs(self):
        result = parse_snapshot(self.fixture(), 'capture-sha')
        self.assertEqual(result['selected']['Power & Energy']['value'], 8_784_000_000)
        self.assertEqual(result['selected']['Financial Products']['value'], 1_177_000_000)
        self.assertEqual(result['selected']['Eliminations']['value'], -1_949_000_000)
        self.assertEqual(len(result['selected']['Eliminations']['facts']), 2)
        groups = {f['dimensions']['reported_group'] for f in result['selected']['Eliminations']['facts']}
        self.assertEqual(groups, {'Machinery, Power & Energy', 'Financial Products'})
        self.assertEqual(sum(s['value'] for s in result['selected'].values()), result['consolidated_total'])

    def test_external_sales_cannot_replace_gross_income(self):
        data = self.fixture();data['tables'][0]['rows'][2][6] = '7,288'
        with self.assertRaises(ValueError): parse_snapshot(data, 'sha')

    def test_matching_bridge_alone_cannot_hide_geographical_disagreement(self):
        data = self.fixture(); data['tables'][1]['rows'][4][13] = '8,785'
        with self.assertRaises(ValueError): parse_snapshot(data, 'sha')

    def test_wrong_quarter_missing_scope_duplicate_table_or_unknown_value_fail(self):
        variants = []
        d = self.fixture();d['tables'][0]['rows'][1][6] = 'Third Quarter 2025';variants.append(d)
        d = self.fixture();d['tables'][0]['rows'].pop(9);variants.append(d)
        d = self.fixture();d['tables'].append(copy.deepcopy(d['tables'][0]));variants.append(d)
        d = self.fixture();d['tables'][0]['rows'][5][6] = '—';variants.append(d)
        for data in variants:
            with self.assertRaises(ValueError): parse_snapshot(data, 'sha')
