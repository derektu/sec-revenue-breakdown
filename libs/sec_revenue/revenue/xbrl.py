"""讀 inline XBRL 主文件：namespace、contexts、units、dei 與每個 `ix:nonFraction` fact。

HTML 解析、表格編號與數值規則都來自 `ixbrl.py`，與證據元件（`evidence.TableLocator`）共用。

規格與 fact 在同一份文件內以 namespace URI 比對：規格的前綴與 fact 的 QName 都依文件宣告的
`xmlns:*` 解析成 `{URI}名稱`。不同申報之間不比 URI，因為公司與 us-gaap 的 namespace 每年都帶不同日期。
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import datetime as dt
from decimal import Decimal

from .evidence import TableLocator
from .ixbrl import clean_text, ix_number, numbered_tables, parse_html

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


# 快照中每個 fact 保存的欄位；concept_key 與 dimension_keys 由 namespaces 重算。
SNAPSHOT_FACT_FIELDS = tuple(f.name for f in fields(Fact) if f.name not in ("concept_key", "dimension_keys"))


class InlineDocument:
    """一份 inline XBRL HTML 文件的 fact 索引。

    `to_snapshot` 把解析結果中指定 concept 的 fact 連同 namespaces、dei 存成 JSON 可序列化的內容；
    `from_snapshot` 由快照重建同一個索引，之後的查找（`resolve`、`facts`、`fiscal`）與原文解析的結果相同。
    快照沒有原文，`locator` 為 None，不能找表格或產生證據。
    """

    def __init__(self, raw: bytes):
        # 解析樹與表格編號只來自 `ixbrl.py`；fact 全部讀完後，才把同一棵樹交給證據元件。
        root = parse_html(raw)
        # lxml 的元素物件只在有人持有時保持同一個 id，所以保留表格串列。
        self.tables = numbered_tables(root)
        self.table_numbers = {id(table): i for i, table in enumerate(self.tables)}
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
        self.locator = TableLocator.from_root(root)

    @classmethod
    def from_snapshot(cls, payload: dict) -> InlineDocument:
        document = cls.__new__(cls)
        document.locator = None
        document.namespaces = dict(payload["namespaces"])
        document.conflicts = set(payload["conflicts"])
        document.contexts, document.units = {}, {}
        document.dei = dict(payload["dei"])
        document.facts = []
        for row in payload["facts"]:
            dimensions = tuple((axis, member) for axis, member in row["dimensions"])
            document.facts.append(
                Fact(
                    **{name: row[name] for name in SNAPSHOT_FACT_FIELDS if name != "dimensions"},
                    dimensions=dimensions,
                    concept_key=document.resolve(row["concept"]),
                    dimension_keys=document.resolve_dimensions(dimensions),
                )
            )
        return document

    def to_snapshot(self, concepts) -> dict:
        """`concepts`（規格中的 QName）在本文件解析到的 fact，依文件順序；前綴無法解析的 concept 沒有 fact。"""
        keys = {self.resolve(concept) for concept in concepts} - {None}
        return {
            "namespaces": dict(sorted(self.namespaces.items())),
            "conflicts": sorted(self.conflicts),
            "dei": dict(sorted(self.dei.items())),
            "facts": [
                {
                    name: [list(pair) for pair in fact.dimensions] if name == "dimensions" else getattr(fact, name)
                    for name in SNAPSHOT_FACT_FIELDS
                }
                for fact in self.facts
                if fact.concept_key in keys
            ],
        }

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
            table_index=self.table_numbers[id(table)] if table is not None else None,
            order=order,
        )

    def fiscal(self) -> tuple[int | None, str | None]:
        """申報自己宣告的財年與期別（Q1、Q2、Q3、FY）。"""
        year = self.dei.get("dei:DocumentFiscalYearFocus")
        return (int(year) if year and year.isdigit() else None), self.dei.get("dei:DocumentFiscalPeriodFocus")
