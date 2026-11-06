"""框架取得公司組成的來源：公司 parser（`parser.py`），或宣告式規格（`spec.py`）。

兩者對框架提供同一組介面：`ticker`、`view`、`total_name`、`compose(document, filing, request)` 與 `categories(day)`。
框架流程（`compose.py`、`engine.py`、`review.py`）只透過這組介面取得每份申報的組成，不讀規格的資料結構。
"""

from __future__ import annotations

from types import MappingProxyType, ModuleType

from .contract import Composition, FilingFacts, ParserFailure, Request, Term
from .filings import Filing, ParseError
from .spec import VIEWS, Category, CompanySpec, Definition, TableCellSelector, fact_variants
from .xbrl import InlineDocument


def facts_only(document: InlineDocument) -> InlineDocument:
    """只有 fact、namespaces 與 dei 的唯讀副本：交給公司 parser，不含 HTML 解析樹與表格，改動它不影響框架的文件。"""
    stripped = InlineDocument.__new__(InlineDocument)
    stripped.locator = None
    stripped.namespaces = MappingProxyType(dict(document.namespaces))
    stripped.conflicts = frozenset(document.conflicts)
    stripped.contexts, stripped.units = MappingProxyType({}), MappingProxyType({})
    stripped.dei = MappingProxyType(dict(document.dei))
    stripped.facts = tuple(document.facts)
    return stripped


class ParserSource:
    """公司 parser：`parser.py` 定義 `TICKER`、`VIEW`、`TOTAL`、`compose(filing, request)` 與 `categories(day)`。"""

    always_reconciling = False

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


class SpecSource:
    """宣告式規格：每份申報依申報期末日生效的定義組成。"""

    def __init__(self, spec: CompanySpec):
        self.spec = spec
        self.ticker = spec.ticker
        self.view = spec.view
        self.total_name = spec.total.name
        self.always_reconciling = bool(spec.reconciling)

    def items(self) -> list[tuple[str, Category]]:
        return (
            [("category", c) for c in self.spec.categories]
            + [("reconciling", c) for c in self.spec.reconciling]
            + [("total", self.spec.total)]
        )

    @staticmethod
    def definition(item: Category, source_period: str) -> Definition | None:
        """`source_period` 是申報的期末日；沒有生效的定義時回傳 None（該期沒有這個項目）。

        生效的定義最多一個，且不是尚未支援的 table_cell。
        """
        active = [d for d in item.definitions if d.period.covers(source_period)]
        if not active:
            return None
        if len(active) > 1:
            raise ParseError("定義唯一", f"{item.name} 在 {source_period} 有 {len(active)} 個生效的定義")
        for addend in active[0].addends:
            if isinstance(addend.selector, TableCellSelector):
                raise ParseError("定義唯一", f"{item.name} 使用 {addend.selector.describe()}：table_cell 運算元尚未支援")
        return active[0]

    def categories(self, day: str) -> list[str]:
        return [item.name for group, item in self.items() if group != "total" and self.definition(item, day) is not None]

    def compose(self, document: InlineDocument, filing: Filing, request: Request) -> Composition:
        """申報期末日生效的定義，每個加數在申報中找期間相符的 fact（`one_of` 的每種寫法都找）。

        任一加數找不到時該項目不列出，原因記在 `missing`。寫法的前綴在文件中沒有宣告時視為不存在；
        前綴宣告衝突時無法確定寫法對應哪些 fact，原因記在 `unparseable`。
        """
        result = Composition()
        for group, item in self.items():
            definition = self.definition(item, filing.report_date)
            if definition is None:
                if group == "total":
                    raise ParseError("定義唯一", f"總營收 {item.name} 在 {filing.report_date} 沒有生效的定義")
                continue
            try:
                terms = addend_terms(document, filing.accession, item.name, definition.addends, request)
            except ParserFailure as error:
                result.unparseable[item.name] = error.message
                continue
            if isinstance(terms, str):
                result.missing[item.name] = terms
                continue
            if group == "total":
                result.total = terms
            else:
                getattr(result, "categories" if group == "category" else "reconciling")[item.name] = terms
        return result


def addend_terms(document: InlineDocument, accession: str, name: str, addends, request: Request) -> list[Term] | str:
    """規格加數在申報中期間相符的 fact，每個加數一項；任一加數找不到時回傳原因（字串）。

    寫法的前綴在文件中沒有宣告時視為不存在；前綴宣告衝突時無法確定寫法對應哪些 fact，以 `ParserFailure` 結束。
    """
    terms = []
    for addend in addends:
        label = f"{name}：{addend.selector.describe()} {request.duration} 期末 {request.end}（{accession}）"
        variants = fact_variants(addend.selector)
        for variant in variants:
            conflicts = document.conflicting_prefixes(variant.concept, variant.dimensions)
            if conflicts:
                raise ParserFailure("fact 存在且唯一", f"{label}：{variant.describe()} 的前綴 {conflicts} 在文件中宣告衝突")
        resolved = [(document.resolve(v.concept), document.resolve_dimensions(v.dimensions)) for v in variants]
        resolved = [keys for keys in resolved if None not in keys]
        if not resolved:
            return f"{label}：規格使用的前綴在文件中沒有宣告或宣告衝突"
        facts = tuple(f for f in document.facts if (f.concept_key, f.dimension_keys) in resolved and request.matches(f))
        if not facts:
            return label
        terms.append(Term(facts, addend.weight, addend.selector.describe()))
    return terms
