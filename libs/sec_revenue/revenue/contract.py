"""公司 parser 與框架之間的介面。

框架每次把一份申報的 fact 清單（`FilingFacts`）與一段期間（`Request`）交給公司 parser 的 `compose`，
公司 parser 回傳 `Composition`：每個分類、調節項與總營收由哪些 fact 組成、權重多少。數值由框架依 fact 計算。
完整規則見 `docs/architecture/parser.md` 的「公司 parser 的介面」。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .filings import ParseError
from .xbrl import Fact, InlineDocument

DURATIONS = ("quarter", "nine_months", "annual")


@dataclass(frozen=True)
class FilingFacts:
    """交給公司 parser 的一份申報：申報資訊與主文件的 fact 清單（facts、namespaces、dei），沒有 HTML 原文。"""

    accession: str
    form: str
    report_date: str
    document: InlineDocument

    @property
    def facts(self) -> list[Fact]:
        return self.document.facts

    @property
    def namespaces(self) -> dict[str, str]:
        return self.document.namespaces

    @property
    def dei(self) -> dict[str, str]:
        return self.document.dei


@dataclass(frozen=True)
class Request:
    """要組的期間：期末日、期間長度（`quarter`、`nine_months`、`annual`），以及選用的起日。

    沒有起日時，期末日與長度相符的 fact 都算；有起日時起日也必須相同（Q4 的九個月累計、比較欄比對）。
    """

    end: str
    duration: str
    start: str | None = None

    def matches(self, fact: Fact) -> bool:
        return fact.end == self.end and fact.duration == self.duration and (self.start is None or fact.start == self.start)


@dataclass(frozen=True)
class Term:
    """運算式的一項：一個數字在申報中的 fact 與權重（1 或 -1）。

    同一個數字以不同 concept 或成員重複標記時，`facts` 列出每一種寫法找到的 fact；框架另外補上同 concept、
    同 dimensions、同期間的重複 fact，檢查數值一致後選一個作為運算元。`label` 是錯誤訊息中描述這一項的文字。
    """

    facts: tuple[Fact, ...]
    weight: int = 1
    label: str = ""


@dataclass
class Composition:
    """一份申報中一段期間的組成。

    `categories`、`reconciling` 依輸出順序列出；這份申報沒有的分類不列出。`total` 為 None 代表組不出總營收。
    `missing` 記錄沒有列出的項目與原因（名稱 → 原因），框架用於錯誤訊息。
    """

    categories: dict[str, list[Term]] = field(default_factory=dict)
    reconciling: dict[str, list[Term]] = field(default_factory=dict)
    total: list[Term] | None = None
    missing: dict[str, str] = field(default_factory=dict)


class ParserFailure(ParseError):
    """公司 parser 組不出這份申報：`check` 是自我檢核表中的名稱，找不到或無法確定 fact 時用「fact 存在且唯一」。"""
