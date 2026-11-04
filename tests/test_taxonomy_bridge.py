"""Real source contracts and value-independent negative bridge tests."""
import copy
import gzip
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import taxonomy_bridge as bridge


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((bridge.BASE / 'manifest.json').read_text())
        cls.tax = {(f['ticker'], f['form']): bridge.taxonomy(f) for f in manifest['filings']}
        cls.cases = json.loads(gzip.decompress((ROOT / 'research/taxonomy-bridge/results/cases.json.gz').read_bytes()))
        cls.by_id = {c['id']: c for c in cls.cases}

    def pair(self, key='TSLA:0'):
        c = self.by_id[key]
        q, a = self.tax[(c['ticker'], '10-Q')], self.tax[(c['ticker'], '10-K')]
        qf = next(f for f in q['facts'] if f['fact_id'] == c['nine_month_fact_ids'][0])
        af = next(f for f in a['facts'] if f['fact_id'] == c['annual_fact_ids'][0])
        return q, a, qf, af

    def test_representative_source_review(self):
        review = json.loads((ROOT / 'research/taxonomy-bridge/review-cases.json').read_text())
        for expected in review['cases']:
            c = self.by_id[expected['id']]
            with self.subTest(case=c['id']):
                q, a, qf, af = self.pair(c['id'])
                result = bridge.evaluate_pair(q, a, qf, af)
                self.assertEqual(result['decision'], expected['expected'])
                self.assertTrue(set(expected.get('required_reasons', [])) <= set(result['reasons']))
                if 'member' in expected:
                    e = next(e for e in result['elements'] if e['before'] == expected['member'])
                    self.assertIn((bridge.ROLE + 'label', 'en-US', expected['standard_label']), [tuple(x) for x in e['labels_before']])
                    self.assertIn((bridge.ROLE + 'documentation', 'en-US', expected['documentation']), [tuple(x) for x in e['labels_before']])
                    self.assertEqual(result['row_labels']['Q_YTD9'], expected['row_label'])

    def test_all_64_scopes_and_both_fiscal_years(self):
        self.assertEqual(len(self.cases), 64)
        self.assertEqual(sum(c['decision'] == 'evidence_supported_version_bridge' for c in self.cases), 23)
        for c in self.cases:
            q, a, qf, af = self.pair(c['id'])
            self.assertEqual(bridge.evaluate_pair(q, a, qf, af)['decision'], c['decision'])
            historical = bridge.comparison_period(q, a, c)
            self.assertEqual(historical['decision'], c['historical_comparison']['decision'])
            for item in (c, historical):
                if item['decision'] == 'evidence_supported_version_bridge':
                    self.assertEqual(item['legacy_numeric_comparison']['status'], 'numeric_equal_only')

    def test_values_never_choose_a_bridge(self):
        # Positive and refusal scopes retain their decisions after equalizing all
        # compared numbers; otherwise a numeric match could conceal a scope gap.
        for c in self.cases:
            q, a, qf, af = self.pair(c['id'])
            qf, af = copy.deepcopy(qf), copy.deepcopy(af)
            qf['value'] = af['value'] = '123456789'
            self.assertEqual(bridge.evaluate_pair(q, a, qf, af)['decision'], c['decision'])

    def test_number_changes_affect_only_arithmetic(self):
        q, a, qf, af = self.pair()
        qf, af = copy.deepcopy(qf), copy.deepcopy(af)
        qf['value'], af['value'] = '7', '23'
        self.assertEqual(bridge.evaluate_pair(q, a, qf, af)['decision'], 'evidence_supported_version_bridge')
        self.assertEqual(bridge.arithmetic_check([af], [qf])['value'], '16')
        altered = copy.deepcopy(af)
        altered['value'] = '24'
        self.assertEqual(bridge.arithmetic_check([af, altered], [qf])['decision'], 'abstain_conflicting_duplicates')

    def test_schema_type_change_refused(self):
        q, a, qf, af = self.pair()
        a = copy.deepcopy(a)
        a['elements']['AutomotiveSalesMember']['type'] = '{invalid}stringItemType'
        self.assertIn('schema_attributes_changed', bridge.evaluate_pair(q, a, qf, af)['reasons'])

    def test_label_and_definition_changes_refused_even_with_equal_values(self):
        q, a, qf, af = self.pair()
        for role, expected in [('label', 'standard_label_changed'), ('documentation', 'documentation_changed')]:
            with self.subTest(role=role):
                altered = copy.deepcopy(a)
                altered['labels']['AutomotiveSalesMember'] = [(r, lang, 'different economic definition' if r == bridge.ROLE + role else value)
                                                             for r, lang, value in altered['labels']['AutomotiveSalesMember']]
                qf, af = copy.deepcopy(qf), copy.deepcopy(af)
                qf['value'] = af['value'] = '999'
                self.assertIn(expected, bridge.evaluate_pair(q, altered, qf, af)['reasons'])

    def test_missing_documentation_refused(self):
        q, a, qf, af = self.pair()
        a = copy.deepcopy(a)
        a['labels']['AutomotiveSalesMember'] = [x for x in a['labels']['AutomotiveSalesMember'] if x[0] != bridge.ROLE + 'documentation']
        self.assertIn('missing_documentation', bridge.evaluate_pair(q, a, qf, af)['reasons'])

    def test_definition_hierarchy_change_refused(self):
        q, a, qf, af = self.pair()
        a = copy.deepcopy(a)
        arc = next(x for x in a['arcs'] if x['kind'] == 'def' and x['child'] == 'tsla:AutomotiveSalesMember')
        arc['parent'] = 'tsla:DifferentEconomicScopeMember'
        self.assertIn('axis_member_paths_or_neighbors_changed', bridge.evaluate_pair(q, a, qf, af)['reasons'])

    def test_presentation_label_role_change_refused(self):
        q, a, qf, af = self.pair()
        a = copy.deepcopy(a)
        arc = next(x for x in a['arcs'] if x['kind'] == 'pre' and x['child'] == 'tsla:AutomotiveSalesMember')
        arc['preferred_label'] = bridge.ROLE + 'negatedLabel'
        self.assertIn('presentation_neighborhood_changed', bridge.evaluate_pair(q, a, qf, af)['reasons'])

    def test_prohibited_relationship_refused(self):
        q, a, qf, af = self.pair()
        a = copy.deepcopy(a)
        arc = next(x for x in a['arcs'] if x['kind'] == 'def' and x['child'] == 'tsla:AutomotiveSalesMember')
        arc['use'] = 'prohibited'
        self.assertIn('unsupported_definition_relationships', bridge.evaluate_pair(q, a, qf, af)['reasons'])

    def test_child_definition_change_refuses_unchanged_parent(self):
        q, a, qf, af = self.pair('TSLA:3')
        a = copy.deepcopy(a)
        a['labels']['AutomotiveSalesMember'] = [(r, lang, 'Changed child economic definition' if r == bridge.ROLE + 'documentation' else value)
                                               for r, lang, value in a['labels']['AutomotiveSalesMember']]
        self.assertIn('neighbor_metadata_changed', bridge.evaluate_pair(q, a, qf, af)['reasons'])

    def test_source_and_namespace_ownership(self):
        q, a, qf, af = self.pair()
        altered = copy.deepcopy(a)
        altered['filing']['url'] = altered['filing']['url'].replace('www.sec.gov', 'invalid.test')
        self.assertIn('unapproved_source_host', bridge.evaluate_pair(q, altered, qf, af)['reasons'])
        altered = copy.deepcopy(a)
        altered['namespace'] = 'http://different.test/20251231'
        self.assertIn('namespace_owner_changed', bridge.evaluate_pair(q, altered, qf, af)['reasons'])

    def test_full_scope_semantic_negatives(self):
        q, a, qf, af = self.pair()
        for field, expected in [('entity', 'entity_identifier_changed_or_missing'), ('dimensions', 'full_dimensions_changed'),
                                ('startdate', 'incompatible_fiscal_periods')]:
            with self.subTest(field=field):
                altered = copy.deepcopy(af)
                altered['value'] = qf['value']
                altered['context'][field] = {'entity': {'scheme': 'http://www.sec.gov/CIK', 'identifier': '0000000001'},
                                            'dimensions': {}, 'startdate': '2024-01-01'}[field]
                self.assertIn(expected, bridge.evaluate_pair(q, a, qf, altered)['reasons'])
        altered = copy.deepcopy(af)
        altered['concept'], altered['nature'] = 'us-gaap:CostOfRevenue', 'cost'
        altered['value'] = qf['value']
        self.assertIn('not_admissible_revenue', bridge.evaluate_pair(q, a, qf, altered)['reasons'])

    def test_same_wrong_entity_on_both_sides_refused(self):
        q, a, qf, af = self.pair()
        qf, af = copy.deepcopy(qf), copy.deepcopy(af)
        for f in (qf, af):
            f['context']['entity']['identifier'] = '0000000001'
        self.assertIn('entity_does_not_match_SEC_source', bridge.evaluate_pair(q, a, qf, af)['reasons'])

    def test_same_label_does_not_override_real_hierarchy_change(self):
        q, a, qf, af = self.pair('UNH:40')
        e = bridge.evaluate_pair(q, a, qf, af)['elements'][0]
        self.assertEqual(e['labels_before'], e['labels_after'])
        self.assertEqual(e['definition_difference']['changed_shared_roles'], ['http://www.uhg.com/role/SegmentFinancialInformationDetails'])
        self.assertIn('axis_member_paths_or_neighbors_changed', e['reasons'])


if __name__ == '__main__':
    unittest.main()
