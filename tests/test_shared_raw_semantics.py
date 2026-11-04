"""Pinned real filings plus failure contracts; no vendor access required."""
import copy
import json
from pathlib import Path
import sys
import unittest
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import shared_raw_semantics as shared


class RealFilingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'research/shared-raw-semantics/manifest.json').read_text())
        cls.results = {f'{f["ticker"]}-{f["reportDate"]}': shared.analyze(f) for f in cls.manifest['filings']}
        cls.review = json.loads((ROOT / 'research/shared-raw-semantics/review-cases.json').read_text())

    def test_reviewed_raw_rows(self):
        for check in self.review['checks']:
            with self.subTest(filing=check['filing'], fact=check['fact_id']):
                facts = {f['fact_id']: f for f in self.results[check['filing']]['facts']}
                f = facts[check['fact_id']]
                self.assertEqual(f['nature'], check['expected_nature'])
                self.assertEqual(f['context']['period_kind'], check['expected_period'])
                self.assertEqual(len(f['context']['dimensions']), check['expected_axis_count'])
                self.assertIn(check['row_contains'], f['row_text'])
                self.assertEqual(f['rollup_status'], 'abstain_partition_not_proven')

    def test_pinned_sources_and_xpath(self):
        for filing in self.manifest['filings']:
            root = html.fromstring(shared.read_pinned(filing))
            result = self.results[f'{filing["ticker"]}-{filing["reportDate"]}']
            for f in result['facts']:
                nodes = root.xpath(f['xpath'])
                self.assertEqual(len(nodes), 1)
                self.assertEqual(nodes[0].get('id'), f['fact_id'])
            for support in filing['support']:
                shared.read_pinned(support)

    def test_taxonomy_parent_child_warnings(self):
        for check in self.review['hierarchy_checks']:
            warnings = self.results[check['filing']]['hierarchy_warnings']
            self.assertTrue(any(w['parent_member'] == check['parent'] and w['descendant_member'] == check['child'] for w in warnings), check)

    def test_equal_values_do_not_merge_legal_entity_and_segment(self):
        check = self.review['scope_separation_checks'][0]
        facts = {f['fact_id']: f for f in self.results[check['filing']]['facts']}
        a, b = facts[check['left']], facts[check['right']]
        self.assertEqual(a['value'], b['value'])
        self.assertNotEqual(a['context']['scope_key'], b['context']['scope_key'])
        self.assertIn('dei:LegalEntityAxis', a['context']['dimensions'])
        self.assertIn('us-gaap:StatementBusinessSegmentsAxis', b['context']['dimensions'])

    def test_q4_requires_taxonomy_identity(self):
        for ticker in ('TSLA', 'CMCSA', 'UNH', 'NEE'):
            result = shared.q4_evidence(self.results[ticker + '-2025-12-31'], self.results[ticker + '-2025-09-30'])
            self.assertGreater(result['statuses'].get('same_scope_arithmetic_only', 0), 0)
            self.assertGreater(result['statuses'].get('abstain_taxonomy_version_bridge_required', 0), 0)
            self.assertTrue(all(not c.get('partition_verified', False) for c in result['candidates']))

    def test_legacy_cost_contamination(self):
        from compare_shared_semantics import compare
        filing = self.manifest['filings'][0]
        result = compare(filing, self.results['TSLA-2025-09-30'])
        self.assertEqual(result['legacy_candidate_natures']['cost'], 32)
        self.assertEqual(result['numeric_mismatch_ids'], [])


class FailureContracts(unittest.TestCase):
    def setUp(self):
        filing = json.loads((ROOT / 'research/shared-raw-semantics/manifest.json').read_text())['filings'][0]
        self.body = shared.read_pinned(filing)

    def test_unknown_transform_abstains(self):
        root = html.fromstring(self.body)
        node = root.xpath('//*[@id="f-116"]')[0]
        node.set('format', 'ixt:unsupported')
        facts, _ = shared.parse_document(html.tostring(root))
        f = next(f for f in facts if f['fact_id'] == 'f-116')
        self.assertFalse(f['admissible'])
        self.assertIsNone(f['value'])

    def test_forged_standard_namespace_abstains(self):
        body = self.body.replace(b'http://fasb.org/us-gaap/2025', b'http://invalid.test/us-gaap/2025')
        facts, _ = shared.parse_document(body)
        self.assertTrue(all(f['nature'] == 'abstain' for f in facts))

    def test_missing_context_abstains(self):
        root = html.fromstring(self.body)
        root.xpath('//*[@id="f-116"]')[0].set('contextref', 'missing')
        facts, _ = shared.parse_document(html.tostring(root))
        f = next(f for f in facts if f['fact_id'] == 'f-116')
        self.assertFalse(f['admissible'])
        self.assertIn('missing_context', f['abstain_reasons'])

    def test_conflicting_q4_duplicate_abstains(self):
        manifest = json.loads((ROOT / 'research/shared-raw-semantics/manifest.json').read_text())
        q, annual = [shared.analyze(f) for f in manifest['filings'][:2]]
        target = next(f for f in annual['facts'] if f['admissible'] and f['nature'] == 'revenue' and not f['context']['dimensions'] and f['context']['enddate'] == annual['report_date'])
        bad = copy.deepcopy(target)
        bad['value'] = str(int(bad['value']) + 1)
        annual['facts'].append(bad)
        result = shared.q4_evidence(annual, q)
        self.assertGreater(result['statuses'].get('abstain_conflicting_duplicates', 0), 0)


if __name__ == '__main__':
    unittest.main()
