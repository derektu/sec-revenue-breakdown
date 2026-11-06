"""inline XBRL 主文件的 fact 索引：namespace、dei 與每個 `ix:nonFraction` fact。

文件內容由 `extract.py` 從原文抽出，或由快照讀回；兩者都經過 `InlineDocument.load`，以目前的數字規則（`ixbrl.py`）
算出數值、依 namespaces 解析 QName。證據元件（`evidence.TableLocator`）用同一棵 HTML 解析樹。

公司 parser 指定的 concept 與 fact 在同一份文件內以 namespace URI 比對：公司 parser 的前綴與 fact 的 QName 都依文件
宣告的 `xmlns:*` 解析成 `{URI}名稱`。不同申報之間不比 URI，因為公司與 us-gaap 的 namespace 每年都帶不同日期。
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from decimal import Decimal

from .evidence import TableLocator
from .extract import extract, parse_html
from .ixbrl import ix_number, transform_name

# 期間長度（含首尾日）分類；不在任何範圍內的期間不使用。
DURATIONS = (
    ("quarter", 84, 98),
    ("six_months", 175, 189),
    ("nine_months", 266, 280),
    ("annual", 357, 378),
)
USD = "iso4217:USD"


def duration_days(start: str, end: str) -> int:
    return (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days + 1


def classify_duration(start: str | None, end: str | None) -> str | None:
    if not start or not end:
        return None
    days = duration_days(start, end)
    return next((name for name, low, high in DURATIONS if low <= days <= high), None)


def decimals_rank(decimals: str | None) -> float:
    """精度高低：INF 最高，其次 decimals 數值越大越精確；缺 decimals 最低。"""
    if decimals is None:
        return float("-inf")
    return float("inf") if decimals.upper() == "INF" else int(decimals)


def error_bound(decimals: str | None) -> Decimal | None:
    """四捨五入誤差上限：decimals=-6 代表 ±0.5 百萬；INF 為 0；缺 decimals 時無法推得。"""
    if decimals is None:
        return None
    if str(decimals).upper() == "INF":
        return Decimal(0)
    return Decimal(10) ** (-int(decimals)) / 2


def comparison_bound(decimals: str | None, raw: str, scale: str) -> Decimal | None:
    """跨申報比對用的誤差上限：`decimals` 與顯示文字本身的精度取較粗者。

    公司有時宣告的 decimals 比顯示的位數細（例如顯示 `15,437`、scale 6，卻宣告 decimals=-5），數值實際只到顯示的位數。
    顯示精度由 fact 自己的文字與 scale 推得：小數點後的位數減 scale。文字沒有數字（零值格式）時只看 decimals。
    """
    declared = error_bound(decimals)
    digits = raw.replace(",", "").replace(" ", "")
    if declared is None or not any(c.isdigit() for c in digits):
        return declared
    fraction = len(digits.split(".", 1)[1]) if "." in digits else 0
    return max(declared, error_bound(str(fraction - int(scale))))


@dataclass(frozen=True)
class Fact:
    fact_id: str
    concept: str
    dimensions: tuple[tuple[str, str], ...]
    concept_key: str | None
    dimension_keys: tuple[tuple[str, str], ...] | None
    start: str | None
    end: str | None
    unit: str | None
    raw: str
    scale: str
    decimals: str | None
    sign: str | None
    format: str
    value: int | None
    value_error: str | None
    context_id: str
    table_index: int | None
    order: int

    @property
    def duration(self) -> str | None:
        return classify_duration(self.start, self.end)

    def error_bound(self) -> Decimal | None:
        return error_bound(self.decimals)

    def comparison_bound(self) -> Decimal | None:
        return comparison_bound(self.decimals, self.raw, self.scale)


class InlineDocument:
    """一份 inline XBRL HTML 文件的 fact 索引。

    由原文建立時，`extract` 抽出的內容與 HTML 解析樹交給證據元件（`locator`）；`from_snapshot` 由快照的同一份內容
    重建索引，之後的查找（`resolve`、`facts`、`fiscal`）與原文的結果相同。快照沒有原文，`locator` 為 None，
    不能找表格或產生證據。
    """

    def __init__(self, raw: bytes):
        # 解析樹只來自 `extract.parse_html`；fact 全部讀完後，才把同一棵樹交給證據元件。
        root = parse_html(raw)
        self.load(extract(root))
        self.locator = TableLocator.from_root(root)

    @classmethod
    def from_snapshot(cls, payload: dict) -> InlineDocument:
        document = cls.__new__(cls)
        document.locator = None
        document.load(payload)
        return document

    def load(self, content: dict):
        """由 `extract` 的內容建立索引：`format` 正規化、數值換算依目前的數字規則，QName 依 namespaces 解析。"""
        self.namespaces = dict(content["namespaces"])
        self.conflicts = set(content["conflicts"])
        self.dei = dict(content["dei"])
        self.facts = [self.fact(row) for row in content["facts"]]

    def fact(self, row: dict) -> Fact:
        transform = transform_name(row["format"])
        if row.get("nil"):
            value, error = None, "fact 為 nil"
        else:
            value, error = ix_number(row["raw"], transform, row["scale"], row["sign"])
        dimensions = tuple((axis, member) for axis, member in row["dimensions"])
        return Fact(
            fact_id=row["fact_id"],
            concept=row["concept"],
            dimensions=dimensions,
            concept_key=self.resolve(row["concept"]),
            dimension_keys=self.resolve_dimensions(dimensions),
            start=row["start"],
            end=row["end"],
            unit=row["unit"],
            raw=row["raw"],
            scale=row["scale"],
            decimals=row["decimals"],
            sign=row["sign"],
            format=transform,
            value=value,
            value_error=error,
            context_id=row["context_id"],
            table_index=row["table_index"],
            order=row["order"],
        )

    def resolve(self, qname: str) -> str | None:
        """前綴 QName 轉成 `{URI}名稱`；前綴未宣告或宣告衝突時回傳 None。"""
        prefix, _, local = qname.partition(":")
        if not local or prefix in self.conflicts or prefix not in self.namespaces:
            return None
        return "{" + self.namespaces[prefix] + "}" + local

    def conflicting_prefixes(self, concept: str, dimensions) -> list[str]:
        """concept 與 dimensions（軸與成員）用到、在文件中宣告衝突（同一前綴對應多個 namespace）的前綴。"""
        qnames = [concept] + [q for axis, member in dimensions for q in (axis, member) if not q.startswith("typed:")]
        return sorted({q.partition(":")[0] for q in qnames} & self.conflicts)

    def resolve_dimensions(self, dimensions) -> tuple[tuple[str, str], ...] | None:
        resolved = []
        for axis, member in dimensions:
            keys = (self.resolve(axis), self.resolve(member) if not member.startswith("typed:") else member)
            if None in keys:
                return None
            resolved.append(keys)
        return tuple(sorted(resolved))

    def fiscal(self) -> tuple[int | None, str | None]:
        """申報自己宣告的財年與期別（Q1、Q2、Q3、FY）。"""
        year = self.dei.get("dei:DocumentFiscalYearFocus")
        return (int(year) if year and year.isdigit() else None), self.dei.get("dei:DocumentFiscalPeriodFocus")
