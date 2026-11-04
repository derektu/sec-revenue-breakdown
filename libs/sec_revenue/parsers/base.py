"""公司規則介面；共用流程不判斷 ticker。"""

from __future__ import annotations
import copy
from sec_revenue.engines import QuarterEngine, SelectionEngine


class IssuerParser:
    ticker: str
    rules: dict
    aliases: list = []

    def __init__(self, repository=None, output=None):
        self.repository, self.output = repository, output
        self.source_receipts = []

    def normalize(self, record: dict) -> dict:
        record = copy.deepcopy(record)
        for fact in record["facts"]:
            for alias in self.aliases:
                end = fact.get("enddate", "")
                if (
                    alias.get("start", "") <= end <= alias.get("end", "9999")
                    and (
                        not alias.get("report_dates")
                        or record["filing"]["reportDate"] in alias["report_dates"]
                    )
                    and fact["concept"] == alias["concept"]
                    and fact["dimensions"] == alias["original_dimensions"]
                ):
                    fact.update(
                        original_dimensions=fact["dimensions"],
                        dimensions=alias["dimensions"],
                        normalization_rule_id=alias["id"],
                    )
        return record

    def prepare(self, records: list[dict]) -> list[dict]:
        return [self.normalize(record) for record in records]

    def pool(self, records: list[dict], index: int, engine: QuarterEngine) -> tuple:
        record = records[index]
        return engine.quarter(
            record["facts"],
            record["filing"]["reportDate"],
            [f for r in records[:index] for f in r["facts"]],
        )

    def categories(self, period: str, basis: str) -> dict:
        return self.rules[basis]

    def parse(self, records: list[dict]) -> list[dict]:
        records = self.prepare(records)
        engine, selector, results = QuarterEngine(), SelectionEngine(), []
        for index, record in enumerate(records):
            period = record["filing"]["reportDate"]
            facts, conflicts = self.pool(records, index, engine)
            for basis in self.rules:
                outputs = {
                    label: selector.select(rule, facts, conflicts)
                    for label, rule in self.categories(period, basis).items()
                }
                results.append(
                    {
                        "ticker": self.ticker,
                        "period_end": period,
                        "period_kind": "Q",
                        "basis": basis,
                        "outputs": outputs,
                    }
                )
        return results

    fiscal_year_label_offset: int = 0

    def fiscal_label(self, period: str, records: list[dict]) -> dict:
        """以實際年報結帳日定位會計年度與季度；52/53 週制用天數而非曆月硬對齊。"""
        import datetime as dt
        import calendar

        target = dt.date.fromisoformat(period)
        annuals = sorted(
            dt.date.fromisoformat(r["filing"]["reportDate"])
            for r in records
            if r["filing"]["form"] == "10-K"
        )
        if not annuals:
            return {
                "fiscal_year": None,
                "fiscal_quarter": None,
                "label_status": "annual_anchor_missing",
            }
        candidates = [end for end in annuals if end >= target]
        end = min(candidates) if candidates else annuals[-1]
        projected = False
        while end < target:
            year = end.year + 1
            end = end.replace(
                year=year, day=min(end.day, calendar.monthrange(year, end.month)[1])
            )
            projected = True
        quarters_away = round((end - target).days / 91)
        quarter = 4 - quarters_away
        if quarter not in (1, 2, 3, 4):
            return {
                "fiscal_year": None,
                "fiscal_quarter": None,
                "label_status": "outside_annual_anchor",
            }
        return {
            "fiscal_year": end.year + self.fiscal_year_label_offset,
            "fiscal_quarter": quarter,
            "label_status": (
                "projected_from_last_annual_calendar"
                if projected
                else "actual_annual_anchor"
            ),
            "annual_end_anchor": end.isoformat(),
        }
