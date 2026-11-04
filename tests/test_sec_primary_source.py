"""SEC 數字來源界線及 8-K 表格欄位防誤判。"""
import copy
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import enforce_sec_primary_source as policy


class SecPrimarySourceTests(unittest.TestCase):
    def test_only_actual_https_sec_archive_host_is_accepted(self):
        self.assertTrue(policy.sec_url(policy.UPS_URL))
        for url in [policy.UPS_URL.replace('www.sec.gov', 'www.sec.gov.example.com'),
                    policy.UPS_URL.replace('www.sec.gov', 'www.sec.gov@other.example'),
                    policy.UPS_URL.replace('https:', 'http:'), 'https://www.sec.gov/search-filings']:
            self.assertFalse(policy.sec_url(url))

    def test_sec_parent_cannot_hide_ir_derivation_operand(self):
        f = {'source_url': policy.UPS_URL, 'value': 1}
        derived = {**f, 'derivation': 'annual_minus_nine_months', 'annual_evidence': f,
                   'nine_month_evidence': {**f, 'source_url': 'https://investors.example.com/release'}}
        self.assertFalse(policy.fact_is_sec(derived))
        self.assertFalse(policy.fact_is_sec({**f, 'aggregation_evidence': [derived]}))
        self.assertFalse(policy.selected_is_sec({'status': 'observed', 'source_url': policy.UPS_URL, 'value': 1}))

    def ups_text(self):
        lines = ['Exhibit 99.1', 'UPS RELEASES 3Q 2026 EARNINGS']
        for title, value in [('U.S. Domestic Segment', '14,865'), ('International Segment', '5,007'),
                             ('Supply Chain Solutions1', '2,981')]:
            lines += [title, '3Q 2026  | Non-GAAP Adjusted 3Q 2026  |',
                      '3Q 2025  | Non-GAAP Adjusted 3Q 2025', f'Revenue  | ${value} M  |  | $9 M  |']
        return 'www.sec.gov (' + policy.UPS_URL + ')\n' + '\n'.join(f'L{i}: {s}' for i, s in enumerate(lines))

    def test_sec_exhibit_reads_current_revenue_not_prior_or_adjusted_profit(self):
        result = policy.parse_ups_sec_page(self.ups_text())
        self.assertEqual(result['Domestic Package']['value_usd'], 14_865_000_000)
        self.assertEqual(result['International Package']['value_usd'], 5_007_000_000)
        self.assertEqual(result['Supply Chain and Freight']['value_usd'], 2_981_000_000)

    def test_wrong_origin_period_units_or_duplicate_revenue_are_rejected(self):
        for text in [self.ups_text().replace('www.sec.gov (https://', 'other.example (https://', 1),
                     self.ups_text().replace('UPS RELEASES 3Q 2026', 'UPS RELEASES 2Q 2026'),
                     self.ups_text().replace('$14,865 M', '$14,865 B'),
                     self.ups_text().replace('L5: Revenue', 'L25: Revenue  | $1 M  |  | $9 M  |\nL5: Revenue')]:
            with self.assertRaises(ValueError): policy.parse_ups_sec_page(text)

    def test_precision_explanation_keeps_sec_value_and_rejects_ir_replacement(self):
        row = {'raw': 12, 'scale': 1, 'status': 'exact_scope_candidate_match'}
        selected = {'status': 'observed', 'value': 13, 'error': Decimal(1),
                    'facts': [{'source_url': policy.UPS_URL, 'value': 13}]}
        policy.replace_from_sec(row, selected, 'SEC')
        self.assertEqual(row['selected']['value'], 13)
        self.assertEqual(row['raw'], 12)
        self.assertEqual(row['status'], 'explained_reported_precision')
        changed = copy.deepcopy(selected); changed['facts'][0]['source_url'] = 'https://investors.example.com/report'
        with self.assertRaises(ValueError): policy.replace_from_sec(row, changed, 'IR')
