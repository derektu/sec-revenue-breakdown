"""要下載的申報：Q4 依賴期別與 10-Q 財年依賴期別（純函式，不連網）。"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "libs"))
from sec_revenue.download.plan import dependencies, prior_annual_dependencies, q4_dependencies  # noqa: E402


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


def filed(period, form, sequence, filing_date, original_form=None):
    return dict(row(period, form, sequence, original_form), filingDate=filing_date)


class PriorAnnualDependencyTests(unittest.TestCase):
    def test_quarterly_target_needs_prior_10k(self):
        filings = [
            filed("2026-05-31", "10-K", 1, "2026-06-20"),
            filed("2026-08-31", "10-Q", 2, "2026-09-10"),
            filed("2026-11-30", "10-Q", 3, "2026-12-10"),
        ]
        result = prior_annual_dependencies(filings, filings[1:])
        self.assertEqual(result, {"periods": ["2026-05-31"], "unresolved": []})

    def test_prior_10k_filed_after_the_10q_is_not_used(self):
        filings = [
            filed("2025-05-31", "10-K", 1, "2025-06-20"),
            filed("2026-05-31", "10-K", 2, "2026-10-01"),
            filed("2026-08-31", "10-Q", 3, "2026-09-10"),
        ]
        result = prior_annual_dependencies(filings, [filings[-1]])
        self.assertEqual(result, {"periods": [], "unresolved": ["10-Q 2026-08-31 的上一份 10-K 不在 SEC catalog 中"]})

    def test_amended_10q_uses_its_own_filing_date(self):
        # 變更財年的過渡期 10-K 晚於原 10-Q 申報：原申報看到 2025-12-31，修訂版看到 2026-03-31，兩期都要下載。
        filings = [
            filed("2025-12-31", "10-K", 1, "2026-02-20"),
            filed("2026-03-31", "10-K", 2, "2026-10-01"),
            filed("2026-06-30", "10-Q", 3, "2026-08-01"),
            filed("2026-06-30", "10-Q", 4, "2026-11-01", original_form="10-Q/A"),
        ]
        result = prior_annual_dependencies(filings, [filings[-1]])
        self.assertEqual(result, {"periods": ["2025-12-31", "2026-03-31"], "unresolved": []})

    def test_same_prior_10k_for_original_and_amended_10q_is_listed_once(self):
        filings = [
            filed("2026-05-31", "10-K", 1, "2026-06-20"),
            filed("2026-08-31", "10-Q", 2, "2026-09-10"),
            filed("2026-08-31", "10-Q", 3, "2026-12-01", original_form="10-Q/A"),
        ]
        self.assertEqual(prior_annual_dependencies(filings, [filings[-1]])["periods"], ["2026-05-31"])

    def test_10k_more_than_370_days_earlier_is_unresolved(self):
        filings = [filed("2025-05-31", "10-K", 1, "2025-06-20"), filed("2026-08-31", "10-Q", 2, "2026-09-10")]
        result = prior_annual_dependencies(filings, [filings[-1]])
        self.assertEqual(result, {"periods": [], "unresolved": ["10-Q 2026-08-31 的上一份 10-K 不在 SEC catalog 中"]})

    def test_targeted_10k_is_not_a_dependency_and_annual_targets_are_skipped(self):
        filings = [
            row("2025-12-31", "10-K", 1),
            row("2026-03-31", "10-Q", 2),
            row("2026-12-31", "10-K", 3),
            row("2026-12-31", "10-Q", 4),
        ]
        self.assertEqual(prior_annual_dependencies(filings, filings), {"periods": [], "unresolved": []})


class CombinedDependencyTests(unittest.TestCase):
    def test_q4_and_prior_annual_periods_are_merged_once(self):
        filings = [
            row("2024-12-31", "10-K", 1),
            row("2025-03-31", "10-Q", 2),
            row("2025-06-30", "10-Q", 3),
            row("2025-09-30", "10-Q", 4),
            row("2025-12-31", "10-K", 5),
            row("2026-03-31", "10-Q", 6),
        ]
        # 2025-12-31 的 10-K 需要 2024-12-31 與 Q1–Q3；2026-03-31 的 10-Q 需要的 2025-12-31 已是目標。
        result = dependencies(filings, filings[4:])
        self.assertEqual(
            result,
            {
                "periods": ["2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30"],
                "unresolved": [],
                "prior_annual_unresolved": [],
            },
        )

    def test_mid_year_start_adds_prior_10k(self):
        filings = [row("2025-12-31", "10-K", 1), row("2026-06-30", "10-Q", 2), row("2026-09-30", "10-Q", 3)]
        result = dependencies(filings, filings[1:])
        self.assertEqual(result, {"periods": ["2025-12-31"], "unresolved": [], "prior_annual_unresolved": []})

    def test_10q_without_prior_10k_is_reported_separately(self):
        filings = [row("2026-06-30", "10-Q", 1)]
        result = dependencies(filings, filings)
        self.assertEqual(result["unresolved"], [])
        self.assertEqual(result["prior_annual_unresolved"], ["10-Q 2026-06-30 的上一份 10-K 不在 SEC catalog 中"])


if __name__ == "__main__":
    unittest.main()
