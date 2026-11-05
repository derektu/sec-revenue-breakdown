"""讀 inline XBRL 主文件：namespace、contexts、units、dei 與每個 `ix:nonFraction` fact。

表格編號與證據元件（`evidence.TableLocator`）相同：以 lxml HTML parser 依文件順序列舉 `<table>`。
數值規則與證據核對共用 `evidence.ix_number`。

規格與 fact 在同一份文件內以 namespace URI 比對：規格的前綴與 fact 的 QName 都依文件宣告的
`xmlns:*` 解析成 `{URI}名稱`。不同申報之間不比 URI，因為公司與 us-gaap 的 namespace 每年都帶不同日期。
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from decimal import Decimal

from ..evidence import TableLocator, clean_text, ix_number

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


class InlineDocument:
    """一份 inline XBRL HTML 文件的 fact 索引。"""

    def __init__(self, raw: bytes):
        self.locator = TableLocator(raw)
        root = self.locator.root
        self.namespaces, self.conflicts = {}, set()
        for node in root.iter():
            if not isinstance(node.tag, str):
                continue
            for name, uri in node.attrib.items():
                if name.startswith("xmlns:"):
                    prefix = name[len("xmlns:") :]
                    if self.namespaces.setdefault(prefix, uri) != uri:
                        self.conflicts.add(prefix)
        self.contexts, self.units, self.dei, self.facts = {}, {}, {}, []
        for node in root.iter():
            name = str(node.tag).lower()
            if name == "xbrli:context":
                self.contexts[node.get("id")] = self.read_context(node)
            elif name == "xbrli:unit":
                self.units[node.get("id")] = self.read_unit(node)
        for order, node in enumerate(root.iter()):
            name = str(node.tag).lower()
            if name == "ix:nonnumeric" and node.get("name", "").startswith("dei:"):
                self.dei.setdefault(node.get("name"), clean_text(node.text_content()))
            elif name == "ix:nonfraction":
                self.facts.append(self.read_fact(node, order))

    def resolve(self, qname: str) -> str | None:
        """前綴 QName 轉成 `{URI}名稱`；前綴未宣告或宣告衝突時回傳 None。"""
        prefix, _, local = qname.partition(":")
        if not local or prefix in self.conflicts or prefix not in self.namespaces:
            return None
        return "{" + self.namespaces[prefix] + "}" + local

    def resolve_dimensions(self, dimensions) -> tuple[tuple[str, str], ...] | None:
        resolved = []
        for axis, member in dimensions:
            keys = (self.resolve(axis), self.resolve(member) if not member.startswith("typed:") else member)
            if None in keys:
                return None
            resolved.append(keys)
        return tuple(sorted(resolved))

    @staticmethod
    def read_context(node) -> dict:
        context = {"dimensions": {}, "start": None, "end": None}
        for child in node.iter():
            kind = str(child.tag).split(":")[-1].lower()
            text = clean_text(child.text_content())
            if kind == "startdate":
                context["start"] = text
            elif kind in ("enddate", "instant"):
                context["end"] = text
            elif kind == "explicitmember":
                context["dimensions"][child.get("dimension")] = text
            elif kind == "typedmember":
                # typed 維度以完整內容參與比對；規格不會宣告 typed 維度，因此這類 fact 不會被選中。
                context["dimensions"][child.get("dimension")] = "typed:" + text
        return context

    @staticmethod
    def read_unit(node) -> str:
        measures = [clean_text(m.text_content()) for m in node.iter() if str(m.tag).lower().endswith("measure")]
        return measures[0] if len(measures) == 1 else "/".join(measures)

    def read_fact(self, node, order: int) -> Fact:
        context = self.contexts.get(node.get("contextref"), {"dimensions": {}, "start": None, "end": None})
        raw = clean_text(node.text_content())
        transform = node.get("format", "").split(":")[-1].lower()
        if str(node.get("xsi:nil", node.get("nil", "false"))).lower() == "true":
            value, error = None, "fact 為 nil"
        else:
            value, error = ix_number(raw, transform, node.get("scale", "0"), node.get("sign"))
        table = next((a for a in node.iterancestors() if a.tag == "table"), None)
        dimensions = tuple(sorted(context["dimensions"].items()))
        return Fact(
            fact_id=node.get("id"),
            concept=node.get("name", ""),
            dimensions=dimensions,
            concept_key=self.resolve(node.get("name", "")),
            dimension_keys=self.resolve_dimensions(dimensions),
            start=context["start"],
            end=context["end"],
            unit=self.units.get(node.get("unitref")),
            raw=raw,
            scale=node.get("scale", "0"),
            decimals=node.get("decimals"),
            sign=node.get("sign"),
            format=transform,
            value=value,
            value_error=error,
            context_id=node.get("contextref"),
            table_index=self.locator.index[id(table)] if table is not None else None,
            order=order,
        )

    def fiscal(self) -> tuple[int | None, str | None]:
        """申報自己宣告的財年與期別（Q1、Q2、Q3、FY）。"""
        year = self.dei.get("dei:DocumentFiscalYearFocus")
        return (int(year) if year and year.isdigit() else None), self.dei.get("dei:DocumentFiscalPeriodFocus")

    def matching(self, concept: str, dimensions: tuple, start: str | None, end: str) -> list[Fact]:
        """以前綴 QName 比對（跨申報比較用；同一份文件內的規格比對見 `compose`）。"""
        return [
            f
            for f in self.facts
            if f.concept == concept and f.dimensions == dimensions and f.start == start and f.end == end
        ]
