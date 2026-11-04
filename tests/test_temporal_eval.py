import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('temporal_eval', ROOT / 'scripts/temporal_eval.py')
eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval)


def filing(accession, end, date, form='10-Q'):
    return {'accession': accession, 'period_end': end, 'filing_date': date,
            'form': form, 'url': 'https://www.sec.gov/' + accession, 'sha256': 'a' * 64}


def fact(accession, start, end, value, date):
    return {'accession': accession, 'concept': 'us-gaap:Revenues', 'unit': 'iso4217:USD',
            'dimensions': {}, 'startdate': start, 'enddate': end, 'value': value,
            'filing_date': date, 'fact_id': accession + '-1', 'source_url': 'https://www.sec.gov/' + accession}


def fixture():
    train = filing('train', '2025-09-30', '2025-11-01')
    hold = filing('hold', '2025-12-31', '2026-02-01', '10-K')
    plan = {'schema_version': 1, 'ticker': 'DEMO', 'cik': '1',
            'cutoff': {'filing_date': '2025-11-01', 'period_end': '2025-09-30'},
            'training': [train], 'holdout': [hold],
            'exposure': {'seen_during_development': 'no', 'evidence': ['test-only attestation']},
            'references': [{'source': source, 'seen_during_development': 'no', 'evidence': ['test-only attestation']} for source in eval.SOURCES]}
    data = {'raw_filings': [
        {'filing': {'accessionNumber': 'train'}, 'facts': [fact('train', '2025-01-01', '2025-09-30', 90, '2025-11-01')]},
        {'filing': {'accessionNumber': 'hold'}, 'facts': [
            fact('hold', '2025-01-01', '2025-12-31', 120, '2026-02-01'),
            fact('hold', '2024-01-01', '2024-12-31', 999, '2026-02-01')]}]}
    rules = {'version': 'synthetic-v1', 'selectors': [{'id': kind, 'concept': 'us-gaap:Revenues', 'unit': 'iso4217:USD',
                           'dimensions': {}, 'semantic_basis': 'consolidated_external_revenue', 'period_kind': kind} for kind in ('Q', 'FY')]}
    return plan, data, rules


def reference(**changes):
    row = {'ticker': 'DEMO', 'selector_id': 'Q', 'period_kind': 'Q', 'period_start': '2025-10-01',
           'period_end': '2025-12-31', 'semantic_basis': 'consolidated_external_revenue',
           'unit': 'iso4217:USD', 'value': 30, 'absolute_tolerance': 0,
           'source_kind': 'vendor', 'source': 'stockanalysis', 'evidence': str(Path(__file__)),
           'sha256': eval.digest(Path(__file__).read_bytes()), 'url': 'https://example.com/fixture',
           'first_seen_at': '2026-03-02T00:00:00Z', 'used_for_rule_development': False}
    return {**row, **changes}


class TemporalTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.data, self.rules = fixture()
        self.freeze = eval.freeze(self.plan, self.data, self.rules, '2026-03-01T00:00:00Z')

    def test_annual_comparison_columns_cannot_enter_training(self):
        pack = eval.training_pack(self.plan, self.data)
        self.assertEqual([r['filing']['accessionNumber'] for r in pack['raw_filings']], ['train'])
        self.assertNotIn('999', json.dumps(pack))
        # Even old-period facts from a future accession are excluded wholesale.
        self.assertNotIn('hold', json.dumps(pack))

    def test_reject_accession_overlap_and_future_filing(self):
        for mutation in ('overlap', 'filing'):
            plan, data, _ = fixture()
            if mutation == 'overlap':
                plan['training'].append(plan['holdout'][0])
            elif mutation == 'filing':
                plan['training'][0]['filing_date'] = '2026-02-01'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                eval.training_pack(plan, data)

    def test_future_period_facts_excluded_with_audit_hash(self):
        self.data['raw_filings'][0]['facts'][0]['enddate'] = '2029-12-31'
        pack = eval.training_pack(self.plan, self.data)
        record = pack['raw_filings'][0]
        self.assertEqual(record['facts'], [])
        self.assertEqual(record['excluded_facts'][0]['reason'], 'period_after_training_cutoff')
        self.assertEqual(len(record['excluded_facts'][0]['sha256']), 64)

    def test_q4_and_fy_are_distinct_and_operands_retained(self):
        result = eval.replay(self.freeze, self.data)
        q, fy = result['results']
        self.assertEqual((q['value'], fy['value']), (30, 120))
        self.assertEqual(q['facts'][0]['annual_evidence']['accession'], 'hold')
        self.assertEqual(q['facts'][0]['nine_month_evidence']['accession'], 'train')
        report = eval.compare(self.freeze, result, [reference()])
        self.assertTrue(report['genuine_holdout_by_recorded_attestations'])
        self.assertFalse(report['semantic_accuracy_measured'])

    def test_missing_operand_is_missing_not_zero(self):
        self.data['raw_filings'][0]['facts'] = []
        receipt = eval.freeze(self.plan, self.data, self.rules)
        result = eval.replay(receipt, self.data)
        self.assertEqual(result['results'][0]['status'], 'parser_missing')
        self.assertIsNone(result['results'][0]['value'])

    def test_conflicting_duplicates_are_not_silently_selected(self):
        annual = self.data['raw_filings'][1]['facts'][0]
        self.data['raw_filings'][1]['facts'].append({**annual, 'value': 130})
        result = eval.replay(self.freeze, self.data)
        self.assertEqual(result['results'][0]['status'], 'ambiguous')
        self.assertEqual(result['results'][1]['status'], 'ambiguous')

    def test_zero_and_reference_missing_are_separate(self):
        result = eval.replay(self.freeze, self.data)
        for value, expected in [(None, 'reference_missing'), (0, 'numeric_difference')]:
            report = eval.compare(self.freeze, result, [reference(value=value)])
            self.assertEqual(report['reference_comparisons'][0]['outcome'], expected)

    def test_seen_unknown_and_development_references_cannot_be_blind(self):
        for state in ('yes', 'unknown'):
            plan = copy.deepcopy(self.plan)
            plan['exposure'] = {'seen_during_development': state, 'evidence': ['fixture']}
            receipt = eval.freeze(plan, self.data, self.rules)
            result = eval.compare(receipt, eval.replay(receipt, self.data), [reference()])
            self.assertFalse(result['genuine_holdout_by_recorded_attestations'])
        for changes in ({'used_for_rule_development': True}, {'first_seen_at': '2026-02-01T00:00:00Z'}):
            result = eval.compare(self.freeze, eval.replay(self.freeze, self.data), [reference(**changes)])
            self.assertEqual(result['exposure_status'], 'contaminated')

    def test_semantic_period_unit_mismatches_are_not_numeric_success(self):
        result = eval.replay(self.freeze, self.data)
        for changes, expected in [({'semantic_basis': 'gross_including_intersegment'}, 'semantic_basis_differs'),
                ({'period_kind': 'FY'}, 'period_start_differs'),
                ({'period_start': '2025-07-01'}, 'period_start_differs'),
                ({'unit': 'shares'}, 'unit_differs')]:
            # FY selector exists but Q id intentionally has no FY match.
            if changes.get('period_kind') == 'FY':
                expected = 'period_or_selector_unaligned'
            report = eval.compare(self.freeze, result, [reference(**changes)])
            self.assertEqual(report['reference_comparisons'][0]['outcome'], expected)
            self.assertFalse(report['genuine_holdout_by_recorded_attestations'])

    def test_changed_rules_training_and_code_are_rejected(self):
        for key in ('rules', 'training', 'code'):
            receipt, data = copy.deepcopy(self.freeze), copy.deepcopy(self.data)
            if key == 'rules':
                receipt['rules']['selectors'][0]['concept'] = 'changed'
            elif key == 'training':
                data['raw_filings'][0]['facts'][0]['value'] = 0
            else:
                receipt['code_sha256']['scripts/temporal_eval.py'] = 'changed'
            with self.subTest(key=key), self.assertRaises(ValueError):
                eval.replay(receipt, data)

    def test_evidence_and_issuer_are_required(self):
        result = eval.replay(self.freeze, self.data)
        for changes in ({'ticker': 'OTHER'}, {'evidence': ''}, {'first_seen_at': '2026-03-01'}, {'sha256': ''}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                eval.compare(self.freeze, result, [reference(**changes)])

    def test_cohort_has_no_retroactive_blind_tests(self):
        plans = eval.seed(eval.BASELINE)
        self.assertEqual(len(plans), 30)
        statuses = {p['ticker']: eval.holdout_status(p) for p in plans}
        self.assertEqual(statuses.pop('AAPL'), 'contaminated')
        self.assertEqual(set(statuses.values()), {'exposure_unknown'})
        for plan in plans:
            path = ROOT / plan['baseline_file']
            data = eval.checked_data(plan, path)
            pack = eval.training_pack(plan, data)
            self.assertEqual(len(pack['raw_filings']), len(plan['training']))

    def test_future_binding_preserves_registration_and_rejects_backdating(self):
        plan = copy.deepcopy(self.plan)
        plan['holdout'] = [filing('future', '2026-03-31', '2026-05-01')]
        data = copy.deepcopy(self.data)
        data['raw_filings'].append({'filing': {'accessionNumber': 'future'}, 'facts': [
            fact('future', '2026-01-01', '2026-03-31', 40, '2026-05-01')]})
        receipt = eval.attach_future(self.freeze, plan, data)
        self.assertEqual(receipt['frozen_at'], self.freeze['frozen_at'])
        self.assertEqual(receipt['rules_sha256'], self.freeze['rules_sha256'])
        self.assertEqual(eval.replay(receipt, data)['results'][0]['value'], 40)
        for change in ('date', 'training', 'rules'):
            altered = copy.deepcopy(receipt)
            if change == 'date':
                altered['plan']['holdout'][0]['filing_date'] = '2026-02-28'
            elif change == 'training':
                altered['plan']['cutoff']['filing_date'] = '2025-11-02'
            else:
                altered['rules']['version'] = 'changed-after-registration'
                altered['rules_sha256'] = eval.digest(eval.canonical(altered['rules']))
            altered['plan_sha256'] = eval.digest(eval.canonical(altered['plan']))
            with self.subTest(change=change), self.assertRaises(ValueError):
                eval.verify_freeze(altered, data)

    def test_outputs_are_create_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'receipt.json'
            eval.save(path, {})
            with self.assertRaises(FileExistsError):
                eval.save(path, {})


if __name__ == '__main__':
    unittest.main()
