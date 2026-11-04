"""Chevron 受限 scope 接合與抵銷不可重複計算。"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from repair_chevron_q4 import normalize_old_scope
from cohort_rule_catalog import R, S, C, P, G, OP


def record(facts):
    return {'filing': {'reportDate': '2024-09-30'}, 'facts': facts}


def fact(value, dims):
    return dict(value=value, dimensions=dims, concept=R, startdate='2024-01-01',
                enddate='2024-09-30', unit='iso4217:USD')


class ChevronQ4Tests(unittest.TestCase):
    def test_only_complete_reviewed_scope_and_period_are_mapped(self):
        f = fact(100, {S: 'cvx:UpstreamMember', C: OP, P: 'us-gaap:OilAndGasMember', G: 'country:US'})
        result = normalize_old_scope(record([f]))['facts'][0]
        self.assertEqual(result['dimensions'], {S: 'cvx:UpstreamSegmentMember', C: OP, G: 'country:US'})
        self.assertEqual(result['original_dimensions'], f['dimensions'])
        for changed in [dict(f, enddate='2025-09-30'), dict(f, concept='us-gaap:Revenues'),
                        dict(f, dimensions={**f['dimensions'], 'ExtraAxis': 'Other'})]:
            self.assertEqual(normalize_old_scope(record([changed]))['facts'][0], changed)

    def test_global_eliminations_do_not_also_add_segment_eliminations(self):
        fs = [fact(n, {C: 'srt:GeographyEliminationsMember', G: geo, P: 'us-gaap:OilAndGasMember'})
              for n, geo in [(-30, 'country:US'), (-10, 'us-gaap:NonUsMember')]]
        fs.append(fact(-20, {S: 'cvx:UpstreamMember', C: 'us-gaap:IntersegmentEliminationMember',
                            G: 'country:US', P: 'us-gaap:OilAndGasMember'}))
        result = normalize_old_scope(record(fs))['facts']
        global_rows = [f for f in result if f['dimensions'] == {C: 'us-gaap:IntersegmentEliminationMember'}]
        self.assertEqual(len(global_rows), 1)
        self.assertEqual(global_rows[0]['value'], -40)
        self.assertEqual(len(global_rows[0]['aggregation_evidence']), 2)

    def test_missing_or_conflicting_geography_abstains(self):
        fs = [fact(-30, {C: 'srt:GeographyEliminationsMember', G: geo, P: 'us-gaap:OilAndGasMember'})
              for geo in ['country:US', 'us-gaap:NonUsMember']]
        duplicate = copy.deepcopy(fs[0]); duplicate['value'] = -31
        for source in [fs[:1], fs + [duplicate]]:
            self.assertFalse(any(f['dimensions'] == {C: 'us-gaap:IntersegmentEliminationMember'}
                                 for f in normalize_old_scope(record(source))['facts']))
