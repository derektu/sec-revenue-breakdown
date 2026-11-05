"""公司規格的資料結構：每家公司以 `companies/<首字母>/<ticker>/spec.py` 宣告 `SPEC = CompanySpec(...)`。

規格只描述數字在 SEC 申報中的位置（concept、dimensions、適用期間），不寫流程。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt

# 觀點只取產品或業務別的拆分；地區拆分不是觀點。
VIEWS = ("product", "business_segment")
# 地區軸不可出現在規格中。
FORBIDDEN_AXES = ("srt:StatementGeographicalAxis",)
# 業務分部軸常被公司用於地區分部（例如 AAPL 的 Americas、Europe），規格使用時 parser.md 必須說明為何是業務別。
SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"


@dataclass(frozen=True)
class FactSelector:
    """一個 inline XBRL fact 的選擇條件：concept 與完整 dimensions 精確相等。

    dimensions 以完整 QName 表示，例如 `{"srt:ProductOrServiceAxis": "aapl:MacMember"}`；
    沒有 dimensions 代表不帶任何維度的合計 fact。fact 多一個或少一個維度都不算相符。
    """

    concept: str
    dimensions: tuple[tuple[str, str], ...] = ()

    @property
    def dimension_map(self) -> dict[str, str]:
        return dict(self.dimensions)

    def describe(self) -> str:
        dims = ", ".join(f"{a}={m}" for a, m in self.dimensions) or "無維度"
        return f"{self.concept} [{dims}]"


@dataclass(frozen=True)
class TableCellSelector:
    """沒有 XBRL 標記的 HTML 表格儲存格（例如 8-K 新聞稿）。

    以文件、表頭文字、列標籤與欄期間定位，不用表格編號。引擎目前不支援，規格用到時該期失敗。
    """

    document: str
    table_header: str
    row_label: str
    column_period: str

    def describe(self) -> str:
        return f"table_cell({self.document}, {self.table_header!r}, {self.row_label!r}, {self.column_period!r})"


Selector = FactSelector | TableCellSelector


def fact(concept: str, dimensions: dict[str, str] | None = None) -> FactSelector:
    """宣告 XBRL fact 運算元；dimensions 省略代表不帶維度。"""
    return FactSelector(concept, tuple(sorted((dimensions or {}).items())))


def table_cell(document: str, table_header: str, row_label: str, column_period: str) -> TableCellSelector:
    """宣告 HTML 表格儲存格運算元。"""
    return TableCellSelector(document, table_header, row_label, column_period)


@dataclass(frozen=True)
class Effective:
    """定義適用的期別範圍，以期末日（含）判斷；None 代表不設限。"""

    start: str | None = None
    end: str | None = None

    def __post_init__(self):
        for value in (self.start, self.end):
            if value is not None:
                dt.date.fromisoformat(value)

    def covers(self, period_end: str) -> bool:
        return (self.start is None or self.start <= period_end) and (
            self.end is None or period_end <= self.end
        )

    def overlaps(self, other: "Effective") -> bool:
        return (self.start is None or other.end is None or self.start <= other.end) and (
            other.start is None or self.end is None or other.start <= self.end
        )


ALWAYS = Effective()


def effective(start: str | None = None, end: str | None = None) -> Effective:
    return Effective(start, end)


@dataclass(frozen=True)
class Definition:
    """某個適用期間內，分類或總營收的運算元與權重。"""

    selector: Selector
    weight: int = 1
    period: Effective = ALWAYS

    def __post_init__(self):
        if self.weight not in (1, -1):
            raise ValueError(f"define 的 weight 只能是 1 或 -1，收到 {self.weight!r}")
        if not isinstance(self.period, Effective):
            raise ValueError(f"define 的第二個參數必須是 effective(...)，收到 {self.period!r}；權重請用 weight= 關鍵字")


def describe_definition(definition: Definition) -> dict:
    """輸出用的定義描述：運算元選擇條件、適用期間與權重。"""
    return {
        "selector": definition.selector.describe(),
        "effective": {"start": definition.period.start, "end": definition.period.end},
        "weight": definition.weight,
    }


def define(selector: Selector, period: Effective = ALWAYS, *, weight: int = 1) -> Definition:
    """宣告一個定義；`weight` 只能是 1 或 -1（以關鍵字傳入）。"""
    return Definition(selector, weight, period)


@dataclass(frozen=True)
class Category:
    """觀點中的一項。`definitions` 可有多個，但同一期只能有一個生效。"""

    name: str
    definitions: tuple[Definition, ...]

    def __init__(self, name: str, *definitions: Selector | Definition):
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self,
            "definitions",
            tuple(d if isinstance(d, Definition) else Definition(d) for d in definitions),
        )


@dataclass(frozen=True)
class CompanySpec:
    ticker: str
    view: str
    categories: tuple[Category, ...]
    total: Category
    reconciling: tuple[Category, ...] = ()

    def __post_init__(self):
        if self.view not in VIEWS:
            raise ValueError(f"{self.ticker} 規格的 view 必須是 {'、'.join(VIEWS)} 之一，收到 {self.view!r}")
        if not self.categories:
            raise ValueError(f"{self.ticker} 規格沒有分類")
        names = [c.name for c in self.categories] + [c.name for c in self.reconciling]
        if len(names) != len(set(names)):
            raise ValueError(f"{self.ticker} 規格的分類名稱重複")
        if self.total.name in names:
            raise ValueError(f"{self.ticker} 規格的總營收名稱 {self.total.name!r} 與分類重名")
        items = list(self.categories) + list(self.reconciling) + [self.total]
        for item in items:
            if not item.definitions:
                raise ValueError(f"{self.ticker} 規格的 {item.name} 沒有定義")
            for definition in item.definitions:
                selector = definition.selector
                if isinstance(selector, FactSelector):
                    for axis, _ in selector.dimensions:
                        if axis in FORBIDDEN_AXES:
                            raise ValueError(f"{self.ticker} 規格的 {item.name} 使用地區軸 {axis}；觀點只取產品或業務別")
        used = [(item.name, d) for item in items for d in item.definitions]
        for i, (name, first) in enumerate(used):
            for other, second in used[i + 1 :]:
                if first.selector == second.selector and first.period.overlaps(second.period):
                    raise ValueError(
                        f"{self.ticker} 規格的 {name} 與 {other} 在重疊的期間使用同一個運算元 {first.selector.describe()}"
                    )

    def uses_axis(self, axis: str) -> bool:
        return any(
            isinstance(d.selector, FactSelector) and axis in d.selector.dimension_map
            for item in list(self.categories) + list(self.reconciling) + [self.total]
            for d in item.definitions
        )
