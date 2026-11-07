"""框架取得公司組成的來源：公司 parser（`parser.py`）。

`ParserSource` 對框架提供 `ticker`、`view`、`total_name`、`compose(document, filing, request)` 與 `categories(day)`，
以及框架預設的自訂值 `durations`（期間分類的天數範圍）、`fiscal_year`（財年的決定方式）與 `attachments`（fact 清單
納入的附件類型）。框架流程（`compose.py`、`engine.py`、`review.py`）只透過這組介面取得每份申報的組成與這家公司的自訂。
"""

from __future__ import annotations

import re
from types import MappingProxyType, ModuleType

from .contract import Composition, FilingFacts, ParserFailure, Request
from .filings import Filing
from .xbrl import DEFAULT_DURATIONS, InlineDocument

# 觀點只取產品或業務別的拆分；地區拆分不是觀點。
VIEWS = ("product", "business_segment")
# 期間分類的四種期間，也是公司 parser 的 `DURATION_DAYS` 的鍵。
DURATIONS = tuple(name for name, _, _ in DEFAULT_DURATIONS)
# 財年的決定方式（公司 parser 的 `FISCAL_YEAR`）：`declared` 取申報宣告的財年；`prior_annual` 的 10-Q 財年是前一份
# 10-K 宣告的財年 + 1，由框架推算（`compose.PeriodComposer.fiscal`），10-K 的財年取宣告值。
FISCAL_YEARS = ("declared", "prior_annual")
# fact 清單納入的附件（公司 parser 的 `ATTACHMENTS`）以申報包的附件類型指定，例如 `EX-13`；預設不納入任何附件。
ATTACHMENT_TYPE = re.compile(r"EX-\d+(\.\d+)?")


def facts_only(document: InlineDocument) -> InlineDocument:
    """只有 fact、namespaces 與 dei 的唯讀副本：交給公司 parser，不含 HTML 解析樹與表格，改動它不影響框架的文件。"""
    stripped = InlineDocument.__new__(InlineDocument)
    stripped.locator = None
    stripped.attachment_locators = MappingProxyType({})
    stripped.namespaces = MappingProxyType(dict(document.namespaces))
    stripped.conflicts = frozenset(document.conflicts)
    stripped.dei = MappingProxyType(dict(document.dei))
    stripped.facts = tuple(document.facts)
    return stripped


class ParserSource:
    """公司 parser：`parser.py` 定義 `TICKER`、`VIEW`、`TOTAL`、`compose(filing, request)` 與 `categories(day)`。

    選用的自訂點 `DURATION_DAYS`、`FISCAL_YEAR`、`ATTACHMENTS` 沒有定義時用框架的預設；定義了就在這裡檢查格式。數值是否合理
    （例如範圍要多寬）由公司 parser 決定，理由寫在該公司的 parser.md。`VIEW` 或自訂點的格式不對時丟出 `ValueError`，
    只有這個 ticker 不處理（`companies.parser_source` 在處理這家時才建立它）。
    """

    def __init__(self, module: ModuleType):
        self.module = module
        self.ticker = module.TICKER
        self.view = module.VIEW
        self.total_name = module.TOTAL
        if self.view not in VIEWS:
            raise ValueError(f"{self.ticker} 的 VIEW 必須是 {'、'.join(VIEWS)} 之一，收到 {self.view!r}")
        self.durations = self.duration_ranges(getattr(module, "DURATION_DAYS", None))
        self.fiscal_year = getattr(module, "FISCAL_YEAR", "declared")
        if not isinstance(self.fiscal_year, str) or self.fiscal_year not in FISCAL_YEARS:
            raise ValueError(f"{self.ticker} 的 FISCAL_YEAR 必須是 {'、'.join(FISCAL_YEARS)} 之一，收到 {self.fiscal_year!r}")
        self.attachments = self.attachment_types(getattr(module, "ATTACHMENTS", None))

    def attachment_types(self, declared) -> tuple[str, ...]:
        """fact 清單納入的附件類型：沒有宣告時是空的（只取主文件）；宣告時檢查：非空的 tuple，每一項是 `EX-<編號>`
        形式的附件類型（例如 `EX-13`、`EX-99.1`），不重複。申報中有沒有這類附件、附件裡有沒有 inline XBRL 由公司
        parser 判斷。"""
        if declared is None:
            return ()
        prefix = f"{self.ticker} 的 ATTACHMENTS"
        if not isinstance(declared, tuple) or not declared:
            raise ValueError(f"{prefix} 必須是非空的 tuple，收到 {declared!r}")
        for value in declared:
            if not isinstance(value, str) or not ATTACHMENT_TYPE.fullmatch(value):
                raise ValueError(f"{prefix} 的每一項必須是 EX-<編號> 形式的附件類型（例如 EX-13），收到 {value!r}")
        if len(set(declared)) != len(declared):
            raise ValueError(f"{prefix} 有重複的附件類型：{declared!r}")
        return declared

    def duration_ranges(self, declared) -> tuple[tuple[str, int, int], ...]:
        """期間分類的天數範圍：沒有宣告時用預設；宣告時檢查：剛好四種期間，每個範圍是兩個正整數（最短, 最長）、
        最短不大於最長，且依單季、六個月、九個月、年度由短到長，前一種的最長小於後一種的最短。由短到長的範圍互不
        重疊，每個天數至多屬於一種期間。範圍要多寬由公司 parser 決定。"""
        if declared is None:
            return DEFAULT_DURATIONS
        prefix = f"{self.ticker} 的 DURATION_DAYS"
        if not isinstance(declared, dict) or set(declared) != set(DURATIONS):
            found = '、'.join(sorted(map(str, declared))) if isinstance(declared, dict) else type(declared).__name__
            raise ValueError(f"{prefix} 必須是剛好含 {'、'.join(DURATIONS)} 的 dict，收到 {found}")
        ranges = []
        for name in DURATIONS:
            value = declared[name]
            if not (isinstance(value, tuple) and len(value) == 2 and all(type(v) is int for v in value)):
                raise ValueError(f"{prefix} 的 {name} 必須是兩個整數的 tuple（最短天數, 最長天數），收到 {value!r}")
            low, high = value
            if not 1 <= low <= high:
                raise ValueError(f"{prefix} 的 {name} {low}–{high} 天：最短須至少 1 天且不大於最長")
            ranges.append((name, low, high))
        for (name, _, high), (following, low, _) in zip(ranges, ranges[1:]):
            if high >= low:
                raise ValueError(f"{prefix} 的 {name} 最長 {high} 天必須小於 {following} 最短 {low} 天（由短到長、互不重疊）")
        return tuple(ranges)

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

