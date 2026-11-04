"""缺季參考文字的期間／單位拒絕判定，及舊 Chevron SEC scope 重播。"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from complete_reference_gaps import parse_reference
import temporal_eval as temporal
from repair_chevron_q4 import normalize_old_scope
from cohort_rule_catalog import catalog
from cohort_rule_audit import resolve
from enforce_sec_primary_source import selected_is_sec


class ReferenceGapCaptureTests(unittest.TestCase):
    def sample(self):
        # 人造輸入只測格式；不發布第三方原始參考數字。
        return {'ticker': 'MCD', 'source_url': 'https://www.futunn.com/hk/stock/MCD-US/financials-revenue',
            'text': 'heading 業務, Value: 3\n1 text 貨幣單位:美元\n2 text 2024/Q3\n3 text 名稱 營收 比例\n'
            '4 text 國際運營的市場\n5 text 7億\n6 text 10%\n7 text United States (US)\n8 text 8億\n9 text 20%\n'
            '10 text 國際開發許可市場和公司\n11 text 9億\n12 text 30%'}

    def test_native_quarter_capture_keeps_reported_text(self):
        self.assertEqual(parse_reference(self.sample()), [('國際運營的市場', '7億'), ('United States (US)', '8億'), ('國際開發許可市場和公司', '9億')])

    def test_missing_values_wrong_period_units_and_repeated_category_fail(self):
        for before, after in [('2024/Q3', '2024/FY'), ('美元', '港元'), ('7億', '—'), ('United States (US)', '國際運營的市場')]:
            item = self.sample();item['text'] = item['text'].replace(before, after)
            with self.assertRaises(ValueError): parse_reference(item)

    def test_chevron_q3_scope_bridge_preserves_separate_elimination_operands(self):
        receipt = temporal.load(ROOT / 'research/cohort-rule-replay-20261104/CVX-freeze.json')
        data = temporal.checked_data(receipt['plan'], ROOT / receipt['plan']['baseline_file'])
        record = normalize_old_scope(next(r for r in data['raw_filings'] if r['filing']['reportDate'] == '2024-09-30'))
        facts, conflicts = temporal.runner().quarter(record['facts'], '2024-09-30', '10-Q', [])
        outputs = {label: resolve(rule, facts, conflicts) for label, rule in catalog()['CVX']['futu'].items()}
        self.assertEqual(outputs['下游']['value'], 39_655_000_000)
        self.assertEqual(outputs['上游']['value'], 22_060_000_000)
        elimination = outputs['部門間收入抵銷']
        self.assertEqual(elimination['value'], -12_928_000_000)
        self.assertEqual(len(elimination['facts'][0]['aggregation_evidence']), 2)
        self.assertTrue(all(selected_is_sec(s) for s in outputs.values()))


if __name__ == '__main__':
    unittest.main()
