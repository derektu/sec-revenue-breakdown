"""一份申報的 fact 索引：namespace、dei 與每個 `ix:nonFraction` fact。

預設只有 inline XBRL 主文件；公司 parser 宣告附件時另含附件的 fact（見 `ixds.py`）。文件內容由 `extract.py`（有附件時
經 `ixds.py`）從原文抽出，或由快照讀回；兩者都經過 `InlineDocument.load`，以目前的數字規則（`ixbrl.py`）算出數值、
依 namespaces 解析 QName。證據元件（`evidence.TableLocator`）用同一棵 HTML 解析樹，每份文件一個。

公司 parser 指定的 concept 與 fact 在同一份申報內以 namespace URI 比對：公司 parser 的前綴與 fact 的 QName 都依文件
宣告的 `xmlns:*` 解析成 `{URI}名稱`。不同申報之間不比 URI，因為公司與 us-gaap 的 namespace 每年都帶不同日期。
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from decimal import Decimal

from .evidence import TableLocator
from .extract import extract, parse_html
from .ixbrl import ix_number, transform_name

# 期間分類的預設天數範圍（含首尾日）：一般 13 週制的單季 12–14 週、六個月 25–27 週、九個月 38–40 週、年度 51–54 週，
# 52／53 週制的 14 週季度也在範圍內。不在任何範圍內的期間不使用。公司的季度不在預設範圍內時，由公司 parser 以
# `DURATION_DAYS` 自訂（見 `source.py` 與 parser.md 的「預設與自訂」）。
DEFAULT_DURATIONS = (
    ("quarter", 84, 98),
    ("six_months", 175, 189),
    ("nine_months", 266, 280),
    ("annual", 357, 378),
)
USD = "iso4217:USD"


def duration_days(start: str, end: str) -> int:
    return (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days + 1


def classify_duration(start: str | None, end: str | None, durations=DEFAULT_DURATIONS) -> str | None:
    """期間的分類（`quarter`、`six_months`、`nine_months`、`annual`）；`durations` 是（分類, 最短天數, 最長天數）。"""
    if not start or not end:
        return None
    days = duration_days(start, end)
    return next((name for name, low, high in durations if low <= days <= high), None)


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
    # fact 所在的文件：None 是主文件，否則是附件的檔名。`table_index` 是這份文件中的表格編號。
    document: str | None = None

    def error_bound(self) -> Decimal | None:
        return error_bound(self.decimals)

    def comparison_bound(self) -> Decimal | None:
        return comparison_bound(self.decimals, self.raw, self.scale)


class InlineDocument:
    """一份申報的 fact 索引：inline XBRL 主文件，與公司 parser 宣告的附件。

    由原文建立時，抽出的內容與每份文件的 HTML 解析樹交給證據元件（主文件是 `locator`，附件在 `attachment_locators`，
    以 `locator_for` 依 `Fact.document` 取得）；`from_snapshot` 由快照的同一份內容重建索引，之後的查找（`resolve`、
    `facts`、`fiscal`）與原文的結果相同。快照沒有原文，沒有證據元件，不能找表格或產生證據。

    有附件時的合併：dei 取自主文件；namespaces 是各文件宣告的聯集，同一個前綴在不同文件對應不同 URI 時與文件內的
    衝突一樣列為衝突；fact 依文件順序排列，主文件在前，附件依宣告順序接在後面，`order` 隨之接續編號。
    """

    def __init__(self, raw: bytes):
        # 解析樹只來自 `extract.parse_html`；fact 全部讀完後，才把同一棵樹交給證據元件。
        root = parse_html(raw)
        self.load(extract(root))
        self.locator = TableLocator.from_root(root)
        self.attachment_locators = {}

    @classmethod
    def from_extracted(cls, content: dict, roots: dict) -> InlineDocument:
        """由抽取內容與（文件名稱 → 解析樹）建立；主文件的名稱是 None（見 `filings.FilingSet.extract`）。"""
        document = cls.__new__(cls)
        document.load(content)
        document.locator = TableLocator.from_root(roots[None])
        document.attachment_locators = {name: TableLocator.from_root(root) for name, root in roots.items() if name is not None}
        return document

    @classmethod
    def from_snapshot(cls, payload: dict) -> InlineDocument:
        document = cls.__new__(cls)
        document.locator = None
        document.attachment_locators = {}
        document.load(payload)
        return document

    def locator_for(self, name: str | None) -> TableLocator | None:
        """`Fact.document` 所在文件的證據元件；快照建立的索引沒有證據元件，回傳 None。"""
        return self.locator if name is None else self.attachment_locators.get(name)

    def load(self, content: dict):
        """由抽取內容建立索引：`format` 正規化、數值換算依目前的數字規則，QName 依合併後的 namespaces 解析。"""
        self.namespaces = dict(content["namespaces"])
        self.conflicts = set(content["conflicts"])
        self.dei = dict(content["dei"])
        attachments = content.get("attachments", [])
        for attachment in attachments:
            self.conflicts |= set(attachment["conflicts"])
            for prefix, uri in attachment["namespaces"].items():
                if self.namespaces.setdefault(prefix, uri) != uri:
                    self.conflicts.add(prefix)
        # 每份文件的 order 自 0 起算；附件的 order 接在前一份文件最大的 order 之後，整份 fact 清單的順序因此唯一。
        offsets, start = {}, 0
        for name in [None] + [a["document"] for a in attachments]:
            offsets[name] = start
            start += max((row["order"] for row in content["facts"] if row.get("document") == name), default=-1) + 1
        self.facts = [self.fact(row, offsets[row.get("document")]) for row in content["facts"]]

    def fact(self, row: dict, offset: int = 0) -> Fact:
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
            order=row["order"] + offset,
            document=row.get("document"),
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
