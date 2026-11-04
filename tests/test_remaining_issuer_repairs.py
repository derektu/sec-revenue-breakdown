"""期間、完整 scope、運算元及公司原表欄位的防誤判測試。"""
import copy
import gzip
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import remaining_issuer_rules as rules
import company_revision_rules as revision
import parse_comcast_business_groups as comcast
from extend_issuer_repairs import selection
from cohort_rule_catalog import R, S, C, P, G, OP
from evaluate_eight_quarter_status import assess


def fact(value, dims, concept=R, start='2025-01-01', end='2025-09-30'):
    return dict(value=value, dimensions=dims, concept=concept, unit='iso4217:USD',
                startdate=start, enddate=end, decimals='-6')


class RemainingIssuerRepairsTests(unittest.TestCase):
    def test_scope_bridge_rejects_additional_axis_and_preserves_original(self):
        f = fact(10, {S: 'ups:USDomesticPackageMember', G: 'country:US'})
        data = {'filing': {'reportDate': '2025-09-30'}, 'facts': [f]}
        result = rules.normalize_record('UPS', data)['facts'][0]
        self.assertEqual(result['dimensions'], {S: 'ups:U.S.DomesticPackageSegmentMember', C: OP})
        self.assertEqual(result['original_dimensions'], f['dimensions'])
        self.assertEqual(data['facts'][0], f)
        f['dimensions']['UnexpectedAxis'] = 'DifferentScope'
        self.assertEqual(rules.normalize_record('UPS', data)['facts'][0]['dimensions'], f['dimensions'])

    def product_facts(self):
        member = rules.PRODUCTS['Oncology']
        return [fact(10, {P: member, G: geo}, 'us-gaap:Revenues') for geo in ['country:US', 'us-gaap:NonUsMember']]

    def test_global_product_requires_both_countries_without_conflicting_duplicates(self):
        fs = self.product_facts()
        self.assertEqual(rules.global_product_facts(fs)[0]['value'], 20)
        self.assertEqual(rules.global_product_facts(fs[:1]), [])
        duplicate = copy.deepcopy(fs[0]); duplicate['value'] = 11
        self.assertEqual(rules.global_product_facts(fs + [duplicate]), [])

    def test_global_product_prefers_direct_more_precise_fact(self):
        fs = self.product_facts()
        direct = fact(19, {P: rules.PRODUCTS['Oncology']}, 'us-gaap:Revenues')
        self.assertEqual(rules.global_product_facts(fs + [direct]), [])

    def test_nested_rounding_error_keeps_aggregation_and_q4_operands(self):
        aggregate = rules.global_product_facts(self.product_facts())[0]
        quarter = {'derivation': 'annual_minus_nine_months', 'annual_evidence': aggregate,
                   'nine_month_evidence': fact(3, {}, 'us-gaap:Revenues')}
        self.assertEqual(rules.reported_error(quarter), 1_500_000)

    def test_retail_period_mapping_is_not_nearest_calendar_quarter(self):
        self.assertTrue(rules.retail_label('COST', 'Mar 31, 2026', '2026-02-15'))
        self.assertFalse(rules.retail_label('COST', 'Jun 30, 2026', '2026-02-15'))
        self.assertTrue(rules.retail_label('HD', 'Dec 31, 2025', '2026-02-01'))
        self.assertFalse(rules.retail_label('HD', 'Mar 31, 2026', '2026-02-01'))
        self.assertTrue(rules.coke_label('Sep 30, 2026', '2026-10-02'))
        self.assertFalse(rules.coke_label('Jun 30, 2026', '2026-10-02'))

    def test_walmart_residual_requires_all_three_revenue_scopes(self):
        fs = [fact(100, {}, 'us-gaap:Revenues')] + [fact(30, {S: 'wmt:' + m, C: OP}, 'us-gaap:Revenues')
            for m in ['WalmartUSMember', 'WalmartInternationalMember', 'SamsClubUSMember']]
        result = selection('WMT', '企業和支持', fs, [])
        self.assertEqual(result['value'], 10)
        self.assertTrue(result['derived_not_directly_reported'])
        fs[-1]['concept'] = R  # 淨銷售不可冒充包含其他收入的 Revenues。
        self.assertEqual(selection('WMT', '企業和支持', fs, [])['status'], 'parser_scope_missing')

    def test_bac_revision_chooses_earliest_later_filing_not_matching_amount(self):
        def record(report, filed, value):
            return {'filing': {'reportDate': report, 'filingDate': filed}, 'facts': [fact(value, {})]}
        data = {'raw_filings': [record('2025-12-31', '2026-02-20', 100),
            record('2026-09-30', '2026-11-01', 77), record('2026-06-30', '2026-08-01', 76)]}
        captured = []
        def quarter(annual, end, form, prior):
            captured.extend(prior)
            return [dict(value=100 - prior[0]['value'])], []
        values, _ = revision.bac_revised_q4(data, SimpleNamespace(quarter=quarter))
        self.assertEqual(captured[0]['value'], 76)
        self.assertEqual(values[0]['comparative_filing_date'], '2026-08-01')
        self.assertTrue(values[0]['retrospective_later_comparative'])

    def test_unh_gaap_and_adjusted_remain_distinct_with_footnote_guard(self):
        text = ('REVENUES BY BUSINESS - SUPPLEMENTAL FINANCIAL INFORMATION\n(in millions; unaudited)\n'
            'Three Months Ended June 30, 2026\nTotal revenues ... 80 1 2 3 60 100\n'
            'Adjusted revenues ... 80 1 2 3 59 100\nThree Months Ended June 30, 2025\n'
            'corporate eliminations of $40')
        with patch.object(revision.subprocess, 'run', return_value=SimpleNamespace(stdout=text)):
            result = revision.parse_unh_release(Path('fixture.pdf'), '2026-06-30')
            self.assertEqual(result['gaap']['Optum'], 60_000_000)
            self.assertEqual(result['adjusted']['Optum'], 59_000_000)
            self.assertEqual(result['gaap']['Eliminations'], -40_000_000)
        with patch.object(revision.subprocess, 'run', return_value=SimpleNamespace(stdout=text.replace('$40', '$39'))):
            with self.assertRaises(ValueError): revision.parse_unh_release(Path('fixture.pdf'), '2026-06-30')

    def ups_text(self):
        return ('UPS Releases 3Q 2026 Earnings\n' + '\n'.join(title + '\n3Q 2026 3Q 2025\nRevenue $' + str(n) + ' M $9 M\n'
            for title, n in [('U.S. Domestic Segment', 14), ('International Segment', 5), ('Supply Chain Solutions1', 3)]))

    def test_ups_missing_segment_row_cannot_take_next_segment_value(self):
        with patch.object(revision.subprocess, 'run', return_value=SimpleNamespace(stdout=self.ups_text())):
            self.assertEqual(revision.parse_ups_latest(Path('fixture.pdf'))['Domestic Package'], 14_000_000)
        for text in [self.ups_text().replace('Revenue $14 M $9 M', ''), self.ups_text().replace('3Q 2026 3Q 2025', '3Q 2025 3Q 2026')]:
            with patch.object(revision.subprocess, 'run', return_value=SimpleNamespace(stdout=text)):
                with self.assertRaises(ValueError): revision.parse_ups_latest(Path('fixture.pdf'))

    def test_comcast_actual_html_distinguishes_quarter_from_ytd(self):
        body = gzip.decompress((ROOT / 'research/shared-raw-semantics/sources/CMCSA-2025-09-30.html.gz').read_bytes())
        values = comcast.parse_groups(body, '10-Q', 2025)
        self.assertEqual(values['Q', 2025, 'Connectivity and Platforms'], 20_176_000_000)
        self.assertEqual(values['YTD9', 2025, 'Connectivity and Platforms'], 60_704_000_000)
        with self.assertRaises(ValueError): comcast.parse_groups(body, '10-K', 2025)

    def test_old_eight_quarters_are_not_latest_eight(self):
        dates = [f'{year}-{month:02d}-30' for year in [2024, 2025] for month in [3, 6, 9, 12]]
        rows = [dict(source='stockanalysis', kind='Q', sec_period_end=d, raw=1, period_reviewed=True,
                     role='scope_candidate', status='exact_scope_candidate_match') for d in dates]
        target = dates[1:] + ['2026-03-30']
        self.assertIn('eight_target_quarters_not_complete', assess(rows, target, 'stockanalysis')['fail_reasons'])
