"""公司規格的資料結構：每家公司以 `companies/<首字母>/<ticker>/spec.py` 宣告 `SPEC = CompanySpec(...)`。

規格只描述數字在 SEC 申報中的位置（concept、dimensions、適用期間），不寫流程。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt

# 觀點只取產品或業務別的拆分；地區拆分不是觀點。
VIEWS = ("product", "business_segment")
# 地區軸只能以「該軸全部成員相加」的加總出現（見 `geographic_sum`），不能單獨成為分類的運算元。
GEOGRAPHIC_AXES = ("srt:StatementGeographicalAxis",)
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


@dataclass(frozen=True)
class OneOf:
    """同一個運算元在不同申報中的多種寫法（concept、成員或 dimensions 組合不同），由 `one_of` 建立。

    每種寫法都在規格中明列，比對仍是精確的：不忽略大小寫、不比對相近名稱。一份申報中找得到一種寫法時用它；
    找得到多種時，各寫法的數值必須在各自精度內一致（同一個數字以不同 tag 重複標記），否則該期失敗。
    """

    variants: tuple[FactSelector, ...]

    def describe(self) -> str:
        return "one_of(" + "；".join(v.describe() for v in self.variants) + ")"


Selector = FactSelector | TableCellSelector | OneOf


def one_of(*variants: FactSelector) -> OneOf:
    """宣告一個運算元的多種寫法；至少兩種、不可重複，每種都是 `fact(...)`。"""
    if len(variants) < 2:
        raise ValueError("one_of 至少要有兩種寫法；單一寫法直接寫 fact(...)")
    if not all(isinstance(v, FactSelector) for v in variants):
        raise ValueError("one_of 的每種寫法都必須是 fact(...)")
    if len(set(variants)) != len(variants):
        raise ValueError("one_of 的寫法重複")
    return OneOf(tuple(variants))


def fact_variants(selector: Selector) -> tuple[FactSelector, ...]:
    """運算元的每種 fact 寫法；`table_cell` 沒有 fact 寫法，回傳空 tuple。"""
    if isinstance(selector, OneOf):
        return selector.variants
    return (selector,) if isinstance(selector, FactSelector) else ()


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
class Addend:
    """定義中的一個加數：一個運算元與權重（1 或 -1）。"""

    selector: Selector
    weight: int = 1

    def __post_init__(self):
        if self.weight not in (1, -1):
            raise ValueError(f"加數的 weight 只能是 1 或 -1，收到 {self.weight!r}")


@dataclass(frozen=True)
class Sum:
    """多個加數的加權和；由 `sum_of` 建立。"""

    addends: tuple[Addend, ...]


def minus(selector: Selector) -> Addend:
    """權重 -1 的加數，用於 `sum_of`。"""
    return Addend(selector, -1)


def sum_of(*parts: Selector | Addend) -> Sum:
    """一個分類在同一期由多個 fact 加權相加；規格逐一列出每個加數，任一加數該期找不到時該期失敗。"""
    addends = tuple(p if isinstance(p, Addend) else Addend(p) for p in parts)
    if len(addends) < 2:
        raise ValueError("sum_of 至少要有兩個加數；單一運算元直接寫 fact(...)")
    variants = [v for a in addends for v in fact_variants(a.selector)]
    if len(set(a.selector for a in addends)) != len(addends) or len(set(variants)) != len(variants):
        raise ValueError("sum_of 的加數重複")
    return Sum(addends)


@dataclass(frozen=True)
class Definition:
    """某個適用期間內，分類或總營收的加數（一個或多個運算元與各自的權重）。"""

    addends: tuple[Addend, ...]
    period: Effective = ALWAYS

    def __post_init__(self):
        if not isinstance(self.period, Effective):
            raise ValueError(f"define 的第二個參數必須是 effective(...)，收到 {self.period!r}；權重請用 weight= 關鍵字")

    def geographic_sum(self) -> tuple[str, str, tuple[tuple[str, str], ...], tuple[str, ...]] | None:
        """使用地區軸時回傳 (地區軸, concept, 其他 dimensions, 成員)；不使用時回傳 None。

        地區軸只能以「該軸全部成員相加」出現：所有加數都是 fact、權重 1、concept 與地區軸以外的 dimensions 相同，
        只差地區成員。成員是否為該軸全部成員，由引擎在每份申報中檢查。
        """
        for a in self.addends:
            if isinstance(a.selector, OneOf) and any(axis in GEOGRAPHIC_AXES for v in a.selector.variants for axis, _ in v.dimensions):
                raise ValueError("地區軸的加數不可使用 one_of")
        axes = {
            axis
            for a in self.addends
            if isinstance(a.selector, FactSelector)
            for axis, _ in a.selector.dimensions
            if axis in GEOGRAPHIC_AXES
        }
        if not axes:
            return None
        if len(axes) != 1 or len(self.addends) < 2:
            raise ValueError("地區軸只能以 sum_of 列出同一地區軸的全部成員相加")
        axis = axes.pop()
        shapes = set()
        members = []
        for a in self.addends:
            selector = a.selector
            if not isinstance(selector, FactSelector) or a.weight != 1 or axis not in selector.dimension_map:
                raise ValueError("地區軸的加總中，每個加數都必須是帶地區軸、權重 1 的 fact")
            shapes.add((selector.concept, tuple(d for d in selector.dimensions if d[0] != axis)))
            members.append(selector.dimension_map[axis])
        if len(shapes) != 1:
            raise ValueError("地區軸的加總中，各加數的 concept 與地區軸以外的 dimensions 必須相同")
        concept, others = shapes.pop()
        return axis, concept, others, tuple(members)


def define(target: Selector | Sum, period: Effective = ALWAYS, *, weight: int = 1) -> Definition:
    """宣告一個定義；`target` 是單一運算元或 `sum_of(...)`。`weight` 只能是 1 或 -1（以關鍵字傳入），乘上每個加數的權重。"""
    if weight not in (1, -1):
        raise ValueError(f"define 的 weight 只能是 1 或 -1，收到 {weight!r}")
    addends = target.addends if isinstance(target, Sum) else (Addend(target),)
    return Definition(tuple(Addend(a.selector, a.weight * weight) for a in addends), period)


@dataclass(frozen=True)
class Category:
    """觀點中的一項。`definitions` 可有多個，同一期最多一個生效；沒有生效的定義時該期沒有這一項（總營收除外，必須有）。

    定義可以直接寫 `fact(...)` 或 `sum_of(...)`，代表不限期間、權重 1 的定義。
    """

    name: str
    definitions: tuple[Definition, ...]

    def __init__(self, name: str, *definitions: Selector | Sum | Definition):
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self,
            "definitions",
            tuple(d if isinstance(d, Definition) else define(d) for d in definitions),
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
                try:
                    definition.geographic_sum()
                except ValueError as error:
                    raise ValueError(f"{self.ticker} 規格的 {item.name}：{error}；觀點只取產品或業務別") from None
        # 同一種寫法（含 one_of 中的每一種）在重疊的期間只能屬於一個運算元。
        used = [
            (item.name, d, a.selector, set(fact_variants(a.selector)) or {a.selector})
            for item in items
            for d in item.definitions
            for a in d.addends
        ]
        for i, (name, first, selector, forms) in enumerate(used):
            for other, second, other_selector, other_forms in used[i + 1 :]:
                if forms & other_forms and first.period.overlaps(second.period):
                    shared = sorted(f.describe() for f in forms & other_forms)
                    raise ValueError(
                        f"{self.ticker} 規格的 {name} 與 {other} 在重疊的期間使用同一個運算元 {'、'.join(shared)}"
                    )

    def uses_axis(self, axis: str) -> bool:
        return any(
            axis in variant.dimension_map
            for item in list(self.categories) + list(self.reconciling) + [self.total]
            for d in item.definitions
            for a in d.addends
            for variant in fact_variants(a.selector)
        )
