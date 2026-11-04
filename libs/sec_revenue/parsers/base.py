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

    earnings_exhibits: dict = {}

    def catalog_filings(self, filings: list[dict]) -> list[dict]:
        """一般公司以正式 10-K／10-Q（含修訂）查詢；8-K 由公司明列口徑。"""
        selected = []
        for filing in filings:
            if filing["form"] in ("10-K", "10-Q"):
                selected.append(filing)
            elif filing["accessionNumber"] in self.earnings_exhibits:
                selected.append(
                    dict(
                        filing,
                        event_report_date=filing["reportDate"],
                        **self.earnings_exhibits[filing["accessionNumber"]],
                    )
                )
        return selected

    def download_dependencies(self, filing: dict, filings: list[dict]) -> list[dict]:
        """年報 Q4 需同實體上一季 YTD9；不把缺九個月資料當零。"""
        if filing["form"] != "10-K":
            return []
        import datetime as dt

        end = dt.date.fromisoformat(filing["reportDate"])
        candidates = [
            f
            for f in filings
            if f["form"] == "10-Q"
            and f["cik"] == filing["cik"]
            and 70 <= (end - dt.date.fromisoformat(f["reportDate"])).days <= 120
        ]
        return (
            [max(candidates, key=lambda f: (f["filingDate"], f["accessionNumber"]))]
            if candidates
            else []
        )

    def required_document_roles(self, filing: dict) -> list[str]:
        return ["primary"]

    def needs_filing_index(self, filing: dict) -> bool:
        return False

    def document_names(self, filing: dict, names: list[str]) -> dict[str, str]:
        return {"primary": filing["primaryDocument"]}

    def extract_document(self, filing: dict, documents: dict) -> dict:
        """從這次下載 bytes 萃取；絕不退回固定研究 facts。"""
        from sec_revenue.engines import XbrlEngine
        from lxml import html

        raw, receipt = documents["primary"]
        facts = XbrlEngine().parse_html(
            raw, receipt["source_url"], filing["accessionNumber"]
        )
        for fact in facts:
            fact.update(
                source_artifact_sha256=receipt["sha256"],
                source_format="original_html",
                source_cik=filing["cik"],
                form=filing["form"],
                filing_date=filing["filingDate"],
            )
        result = {"filing": filing, "facts": facts}
        root = html.fromstring(raw)
        reported_ends = {
            XbrlEngine().document_date(
                "".join(n.itertext()).strip(), n.get("format", "")
            )
            for n in root.iter()
            if isinstance(n.tag, str) and n.get("name") == "dei:DocumentPeriodEndDate"
        }
        if reported_ends and reported_ends != {filing["reportDate"]}:
            raise ValueError("SEC DocumentPeriodEndDate 與 catalog reportDate 不符")
        for concept, key in [
            ("dei:DocumentFiscalYearFocus", "fiscal_year"),
            ("dei:DocumentFiscalPeriodFocus", "fiscal_focus"),
        ]:
            values = {
                "".join(node.itertext()).strip()
                for node in root.iter()
                if isinstance(node.tag, str) and node.get("name") == concept
            }
            if len(values) == 1:
                result[key] = values.pop()
        return result

    def parse_downloaded(self, records: list[dict], periods: list[str]) -> list[dict]:
        """正式下載工作流只用傳入 records；歷史重播介面另行保留。"""
        return [
            row
            for row in IssuerParser.parse(self, records)
            if row["period_end"] in periods
        ]
