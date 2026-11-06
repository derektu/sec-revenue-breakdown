"""CLI 期間範圍：包含邊界、沒有範圍時只取最新一期、日期格式。"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.common.periods import PeriodSelection  # noqa: E402


def filing(period, sequence, filed="2027-05-01"):
    return {"accessionNumber": f"0000000001-27-{sequence:06d}", "reportDate": period, "filingDate": filed}


class PeriodSelectionTests(unittest.TestCase):
    def test_date_range_is_inclusive_and_no_range_picks_latest(self):
        a, b = filing("2026-03-31", 1), filing("2026-06-30", 2)
        self.assertEqual(PeriodSelection().choose([a, b]), [b])
        self.assertEqual(PeriodSelection(latest=True).choose([a, b]), [b])
        self.assertEqual(PeriodSelection("2026-03-31", "2026-06-30").choose([a, b]), [a, b])
        self.assertEqual(PeriodSelection("2026-06-30", "2026-06-30").choose([a, b]), [b])
        self.assertEqual(PeriodSelection("2026-04-01").choose([a, b]), [b])

    def test_latest_filing_wins_within_a_period(self):
        original, amended = filing("2026-03-31", 1, "2026-05-01"), filing("2026-03-31", 2, "2026-07-01")
        self.assertEqual(PeriodSelection().choose([amended, original]), [amended])

    def test_invalid_ranges_are_rejected(self):
        for start, end in [("2026-06-30", "2026-03-31"), ("20260331", None), ("2026-02-30", None)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                PeriodSelection(start, end)


if __name__ == "__main__":
    unittest.main()
