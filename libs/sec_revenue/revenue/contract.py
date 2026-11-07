"""公司 parser 與框架之間的介面。

框架每次把一份申報的 fact 清單（`FilingFacts`）與一段期間（`Request`）交給公司 parser 的 `compose`，
公司 parser 回傳 `Composition`：每個分類、調節項與總營收由哪些 fact 組成、權重多少。數值由框架依 fact 計算。
完整規則見 `docs/architecture/parser.md` 的「公司 parser 的介面」。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .filings import ParseError
from .xbrl import DEFAULT_DURATIONS, Fact, InlineDocument, classify_duration

DURATIONS = ("quarter", "nine_months", "annual")


@dataclass(frozen=True)
class FilingFacts:
    """交給公司 parser 的一份申報：申報資訊與 fact 清單（facts、namespaces、dei），沒有 HTML 原文。

    fact 清單來自主文件；公司 parser 宣告 `ATTACHMENTS` 時另含這些附件的 fact（`Fact.document` 是附件檔名）。
    """

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
    fact 的期間長度依 `durations` 的天數範圍分類：框架帶入這家公司的範圍（預設範圍，或公司 parser 的 `DURATION_DAYS`，
    見 `source.ParserSource.durations`）。沒有指定時是預設範圍；框架把 Request 交給公司 parser 前核對它帶的是這家公司的範圍
    （`compose.PeriodComposer.request`）。
    """

    end: str
    duration: str
    start: str | None = None
    durations: tuple[tuple[str, int, int], ...] = field(default=DEFAULT_DURATIONS, repr=False)

    def matches(self, fact: Fact) -> bool:
        return (
            fact.end == self.end
            and classify_duration(fact.start, fact.end, self.durations) == self.duration
            and (self.start is None or fact.start == self.start)
        )


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
    `missing` 記錄申報中找不到的項目與原因（名稱 → 原因）；`unparseable` 記錄申報中有、但無法確定是哪些 fact 的項目
    與原因（例如前綴宣告衝突）。總營收以 `TOTAL` 的名稱為鍵。主申報的呼叫兩者都是失敗；比較欄比對時前者記為
    `not_found`，後者記為 `unparseable`。
    """

    categories: dict[str, list[Term]] = field(default_factory=dict)
    reconciling: dict[str, list[Term]] = field(default_factory=dict)
    total: list[Term] | None = None
    missing: dict[str, str] = field(default_factory=dict)
    unparseable: dict[str, str] = field(default_factory=dict)


class ParserFailure(ParseError):
    """公司 parser 組不出這份申報：`check` 是自我檢核表中的名稱，找不到或無法確定 fact 時用「fact 存在且唯一」。"""
