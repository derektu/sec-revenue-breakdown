"""CVX net 與 gross 分開，缺分類及對帳矛盾須拒絕。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_cvx_net_scope import LABELS, select_net_sales
from cohort_rule_catalog import R, S, G, C, OP


def facts():
    def fact(value, dims):
        return {'concept': R, 'dimensions': dims, 'unit': 'iso4217:USD', 'value': value,
            'decimals': '0', 'source_url': 'https://www.sec.gov/Archives/edgar/data/93410/000009341025000108/cvx-20250930.htm'}
    rows = [fact(i, {S: member, G: geo}) for i, (member, geo) in enumerate(LABELS.values(), 1)]
    rows += [fact(5, {S: 'us-gaap:AllOtherSegmentsMember'}), fact(15, {})]
    return rows


class ChevronNetScopeTests(unittest.TestCase):
    def test_gross_values_cannot_replace_net(self):
        rows = facts()
        rows += [{**f, 'value': 100, 'dimensions': {**f['dimensions'], C: OP}} for f in rows[:4]]
        result = select_net_sales(rows)
        self.assertEqual([result[label]['value'] for label in LABELS], [1, 2, 3, 4])

    def test_missing_net_field_abstains_even_when_gross_exists(self):
        rows = facts()
        rows[0]['dimensions'][C] = OP
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            select_net_sales(rows)

    def test_failed_consolidated_reconciliation_abstains(self):
        rows = facts()
        rows[-1]['value'] = 16
        with self.assertRaisesRegex(ValueError, 'reconcile'):
            select_net_sales(rows)
