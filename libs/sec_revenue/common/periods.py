"""CLI 的期間範圍：`--start`、`--end` 與 `--latest`。"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import re


@dataclass(frozen=True)
class PeriodSelection:
    """範圍以實際 SEC reportDate 為準；沒有範圍時只選最新一期。"""

    start: str | None = None
    end: str | None = None
    latest: bool = False

    def __post_init__(self):
        for value in (self.start, self.end):
            if value is not None:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError("日期需使用 YYYY-MM-DD")
                dt.date.fromisoformat(value)
        if self.start and self.end and self.start > self.end:
            raise ValueError("start 不可晚於 end")

    def choose(self, filings: list[dict]) -> list[dict]:
        # 同一期多個 accession 保留所有下載版本，預設採最新申報／修訂。
        periods = {}
        for filing in filings:
            end = filing["reportDate"]
            if (self.start and end < self.start) or (self.end and end > self.end):
                continue
            existing = periods.get(end)
            if existing is None or (filing["filingDate"], filing["accessionNumber"]) > (
                existing["filingDate"],
                existing["accessionNumber"],
            ):
                periods[end] = filing
        selected = [periods[end] for end in sorted(periods)]
        return selected[-1:] if not self.start and not self.end else selected
