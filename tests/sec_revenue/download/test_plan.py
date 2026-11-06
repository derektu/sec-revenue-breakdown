"""要下載的申報：Q4 依賴期別（純函式，不連網）。"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.download.plan import q4_dependencies  # noqa: E402


def row(period, form, sequence, original_form=None):
    """catalog 列：`form` 已正規化（10-K/A 記為 10-K），`original_form` 保留原表單。"""
    return {
        "accessionNumber": f"0000000001-27-{sequence:06d}",
        "reportDate": period,
        "filingDate": period,
        "form": form,
        "original_form": original_form or form,
        "cik": "1",
    }


class Q4DependencyTests(unittest.TestCase):
    def test_annual_target_needs_prior_10k_and_same_year_10qs(self):
        filings = [
            row("2025-12-31", "10-K", 1),
            row("2026-03-31", "10-Q", 2),
            row("2026-06-30", "10-Q", 3),
            row("2026-09-30", "10-Q", 4),
            row("2026-12-31", "10-K", 5),
        ]
        result = q4_dependencies(filings, [filings[-1]])
        self.assertEqual(result, {"periods": ["2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"], "unresolved": []})

    def test_52_53_week_fiscal_year(self):
        filings = [
            row("2024-09-28", "10-K", 1),
            row("2024-12-28", "10-Q", 2),
            row("2025-03-29", "10-Q", 3),
            row("2025-06-28", "10-Q", 4),
            row("2025-09-27", "10-K", 5),
        ]
        result = q4_dependencies(filings, [filings[-1]])
        self.assertEqual(result["periods"], ["2024-09-28", "2024-12-28", "2025-03-29", "2025-06-28"])

    def test_amended_annual_target_and_prior(self):
        filings = [
            row("2025-12-31", "10-K", 1),
            row("2025-12-31", "10-K", 2, original_form="10-K/A"),
            row("2026-09-30", "10-Q", 3),
            row("2026-12-31", "10-K", 4),
            row("2026-12-31", "10-K", 5, original_form="10-K/A"),
        ]
        result = q4_dependencies(filings, [filings[-1]])
        self.assertEqual(result["periods"], ["2025-12-31", "2026-09-30"])

    def test_annual_period_is_decided_by_period_end_not_the_chosen_filing(self):
        # 期末日有 10-K 就是年報期別，即使被選中的申報是同一期末的其他表單。
        filings = [
            row("2025-12-31", "10-K", 1),
            row("2026-09-30", "10-Q", 2),
            row("2026-12-31", "10-K", 3),
            row("2026-12-31", "10-Q", 4),
        ]
        result = q4_dependencies(filings, [filings[-1]])
        self.assertEqual(result["periods"], ["2025-12-31", "2026-09-30"])

    def test_periods_already_targeted_are_not_dependencies(self):
        filings = [
            row("2025-12-31", "10-K", 1),
            row("2026-03-31", "10-Q", 2),
            row("2026-06-30", "10-Q", 3),
            row("2026-09-30", "10-Q", 4),
            row("2026-12-31", "10-K", 5),
        ]
        result = q4_dependencies(filings, filings[1:])
        self.assertEqual(result, {"periods": ["2025-12-31"], "unresolved": []})

    def test_missing_prior_10k_falls_back_to_370_days_and_is_unresolved(self):
        filings = [
            row("2025-09-30", "10-Q", 1),
            row("2026-03-31", "10-Q", 2),
            row("2026-09-30", "10-Q", 3),
            row("2026-12-31", "10-K", 4),
        ]
        result = q4_dependencies(filings, [filings[-1]])
        self.assertEqual(result["periods"], ["2026-03-31", "2026-09-30"])
        self.assertEqual(result["unresolved"], ["2026-12-31 的上一份 10-K 不在 SEC catalog 中"])

    def test_quarterly_targets_have_no_dependencies(self):
        filings = [row("2025-12-31", "10-K", 1), row("2026-03-31", "10-Q", 2)]
        self.assertEqual(q4_dependencies(filings, [filings[-1]]), {"periods": [], "unresolved": []})


if __name__ == "__main__":
    unittest.main()
