import importlib.util
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('vendor_review', SCRIPTS / 'review_vendor_evidence.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class VendorReviewTests(unittest.TestCase):
    def test_equal_amount_in_wrong_scope_is_not_accepted(self):
        fact = {'concept': 'us-gaap:Revenues', 'dimensions': {}, 'unit': 'iso4217:USD', 'value': 100_000_000}
        result = review.review_observation('WMT', '沃爾瑪國際', '1億', [fact])
        self.assertEqual(result['status'], 'undecided')

    def test_direct_and_derived_results_remain_distinct(self):
        concept, scopes = review.reviewed_selector('WMT', '沃爾瑪國際')
        fact = {'concept': concept, 'dimensions': scopes[0], 'unit': 'iso4217:USD', 'value': 100_000_000,
                'derivation': 'reported_quarter'}
        self.assertEqual(review.review_observation('WMT', '沃爾瑪國際', '1億', [fact])['status'], 'exact_match')
        fact['derivation'] = 'annual_minus_nine_months'
        self.assertEqual(review.review_observation('WMT', '沃爾瑪國際', '1億', [fact])['status'], 'needs_derivation')

    def test_conflicting_scope_values_abstain_even_when_one_matches(self):
        concept, scopes = review.reviewed_selector('WMT', '沃爾瑪國際')
        fact = {'concept': concept, 'dimensions': scopes[0], 'unit': 'iso4217:USD', 'value': 100_000_000}
        result = review.review_observation('WMT', '沃爾瑪國際', '1億', [fact, {**fact, 'value': 200_000_000}])
        self.assertEqual(result['status'], 'undecided')


if __name__ == '__main__':
    unittest.main()
