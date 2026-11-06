"""框架取得公司組成的來源：公司 parser（`parser.py`）。

`ParserSource` 對框架提供 `ticker`、`view`、`total_name`、`compose(document, filing, request)` 與 `categories(day)`。
框架流程（`compose.py`、`engine.py`、`review.py`）只透過這組介面取得每份申報的組成。
"""

from __future__ import annotations

from types import MappingProxyType, ModuleType

from .contract import Composition, FilingFacts, ParserFailure, Request
from .filings import Filing
from .xbrl import InlineDocument

# 觀點只取產品或業務別的拆分；地區拆分不是觀點。
VIEWS = ("product", "business_segment")


def facts_only(document: InlineDocument) -> InlineDocument:
    """只有 fact、namespaces 與 dei 的唯讀副本：交給公司 parser，不含 HTML 解析樹與表格，改動它不影響框架的文件。"""
    stripped = InlineDocument.__new__(InlineDocument)
    stripped.locator = None
    stripped.namespaces = MappingProxyType(dict(document.namespaces))
    stripped.conflicts = frozenset(document.conflicts)
    stripped.dei = MappingProxyType(dict(document.dei))
    stripped.facts = tuple(document.facts)
    return stripped


class ParserSource:
    """公司 parser：`parser.py` 定義 `TICKER`、`VIEW`、`TOTAL`、`compose(filing, request)` 與 `categories(day)`。"""

    def __init__(self, module: ModuleType):
        self.module = module
        self.ticker = module.TICKER
        self.view = module.VIEW
        self.total_name = module.TOTAL
        if self.view not in VIEWS:
            raise ValueError(f"{self.ticker} 的 VIEW 必須是 {'、'.join(VIEWS)} 之一，收到 {self.view!r}")

    def compose(self, document: InlineDocument, filing: Filing, request: Request) -> Composition:
        facts = FilingFacts(filing.accession, filing.form, filing.report_date, facts_only(document))
        result = self.module.compose(facts, request)
        if not isinstance(result, Composition):
            raise ParserFailure("定義唯一", f"{self.ticker} 的 compose 沒有回傳 Composition（收到 {type(result).__name__}）")
        names = list(result.categories) + list(result.reconciling)
        if len(names) != len(set(names)) or self.total_name in names:
            raise ParserFailure("定義唯一", f"{self.ticker} 的 compose 回傳重複的分類名稱：{names}")
        return result

    def categories(self, day: str) -> list[str]:
        return list(self.module.categories(day))

