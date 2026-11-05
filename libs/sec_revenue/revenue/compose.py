"""組合一期的分類數值：選 fact、Q1–Q3 單季、Q4 = 年度 − 九個月累計，並做結構檢核。

任何結構檢核不通過都以 `ParseError` 結束該期；訊息開頭的 `[檢核名稱]` 與設計文件的檢核表一致。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
from decimal import Decimal

from .filings import Filing, FilingSet, ParseError
from .spec import Definition, Category, CompanySpec, FactSelector, TableCellSelector
from .xbrl import USD, Fact, classify_duration, decimals_rank

QUARTER_FOCUS = {"Q1": 1, "Q2": 2, "Q3": 3, "FY": 4}
# 運算元精度下限：decimals 小於 -6（例如 -8 代表百萬位以上四捨五入）時誤差過大，該期不上線。
MIN_DECIMALS = -6


@dataclass
class Operand:
    """一個 SEC 數字；`kind` 為 `xbrl_fact`，HTML 表格儲存格的 `table_cell` 保留給沒有 XBRL 標記的文件。"""

    kind: str
    filing: Filing
    fact: Fact
    duplicates: list[Fact]
    role: str
    id: str = ""


@dataclass
class Term:
    weight: int
    operand: Operand


@dataclass
class Line:
    name: str
    group: str
    terms: list[Term]

    @property
    def value(self) -> int:
        return sum(t.weight * t.operand.fact.value for t in self.terms)


@dataclass
class PeriodResult:
    period_end: str
    fiscal_year: int
    fiscal_quarter: int
    primary: Filing
    replaced: Filing | None
    nine_month_filing: Filing | None
    lines: list[Line]
    structural: list[dict] = field(default_factory=list)
    sum_check: dict = field(default_factory=dict)
    # Q4 年度與九個月運算元使用不同定義的分類：(名稱, 年度定義, 九個月定義)。
    mixed_definitions: list[tuple[str, Definition, Definition]] = field(default_factory=list)

    @property
    def operands(self) -> list[Operand]:
        seen, result = set(), []
        for line in self.lines:
            for term in line.terms:
                if id(term.operand) not in seen:
                    seen.add(id(term.operand))
                    result.append(term.operand)
        return result


@dataclass
class Candidate:
    """一個規格項目在某份申報中的候選 fact 群（同 concept、dimensions、期間，值必須一致）。"""

    filing: Filing
    facts: list[Fact]
    role: str
    weight: int


class PeriodComposer:
    def __init__(self, spec: CompanySpec, filings: FilingSet):
        self.spec = spec
        self.filings = filings
        self.concepts = {
            d.selector.concept
            for item in self.items()
            for d in item[1].definitions
            if isinstance(d.selector, FactSelector)
        }

    def items(self) -> list[tuple[str, Category]]:
        return (
            [("category", c) for c in self.spec.categories]
            + [("reconciling", c) for c in self.spec.reconciling]
            + [("total", self.spec.total)]
        )

    def compose(self, period: str) -> PeriodResult:
        structural = []
        selection = self.filings.select(period, self.concepts)
        primary = selection.filing
        document = self.filings.document(primary)
        year, focus = document.fiscal()
        if year is None or focus not in QUARTER_FOCUS:
            raise ParseError("財年與季別", f"{primary.accession} 沒有宣告 DocumentFiscalYearFocus／DocumentFiscalPeriodFocus（{year}, {focus}）")
        quarter = QUARTER_FOCUS[focus]
        expected_form = "10-K" if quarter == 4 else "10-Q"
        if not primary.form.startswith(expected_form):
            raise ParseError("財年與季別", f"{primary.accession} 是 {primary.form}，但宣告的期別是 {focus}")
        nine_filing = self.third_quarter(period, year) if quarter == 4 else None

        # 定義依運算元來源申報的期末日選取：Q1–Q3 與 Q4 的年度運算元是本期，Q4 的九個月運算元是 Q3 期末日。
        # 公司在財年中途改 tag 時（例如 10-K 起換新成員、同財年 Q3 10-Q 仍是舊成員），兩個運算元各用各的定義。
        groups, candidates, mixed = {}, {}, []
        for group, item in self.items():
            groups[item.name] = group
            definition = self.definition(item, period)
            if quarter == 4:
                nine_definition = self.definition(item, nine_filing.report_date)
                annual = self.candidate(primary, definition.selector, period, "annual", None, item.name)
                nine = self.candidate(
                    nine_filing, nine_definition.selector, nine_filing.report_date, "nine_months", annual.facts[0].start, item.name
                )
                self.check_q4(item.name, annual.facts[0], nine.facts[0], period)
                annual.weight, nine.weight = definition.weight, -nine_definition.weight
                candidates[item.name] = [annual, nine]
                if nine_definition is not definition:
                    mixed.append((item.name, definition, nine_definition))
            else:
                found = self.candidate(primary, definition.selector, period, "quarter", None, item.name)
                found.weight = definition.weight
                candidates[item.name] = [found]
        structural.append({"check": "定義唯一", "result": "pass"})
        structural.append({"check": "fact 存在且唯一", "result": "pass"})
        structural.append({"check": "單位與精度", "result": "pass"})
        if quarter == 4:
            structural.append({"check": "Q4 期間", "result": "pass"})

        chosen = self.choose(candidates)
        lines = [
            Line(name, groups[name], [Term(c.weight, op) for c, op in zip(candidates[name], chosen[name])])
            for name in candidates
        ]
        result = PeriodResult(period, year, quarter, primary, selection.replaced, nine_filing, lines, structural, mixed_definitions=mixed)
        result.sum_check = self.check_sum(result)
        structural.append({"check": "加總", "result": "pass"})
        return result

    @staticmethod
    def definition(item: Category, source_period: str):
        """`source_period` 是運算元來源申報的期末日；剛好一個定義生效，且不是尚未支援的 table_cell。"""
        active = [d for d in item.definitions if d.period.covers(source_period)]
        if len(active) != 1:
            raise ParseError("定義唯一", f"{item.name} 在 {source_period} 有 {len(active)} 個生效的定義")
        if isinstance(active[0].selector, TableCellSelector):
            raise ParseError("定義唯一", f"{item.name} 使用 {active[0].selector.describe()}：table_cell 運算元尚未支援")
        return active[0]

    def third_quarter(self, period: str, year: int) -> Filing:
        """Q4 的九個月累計來自前一季的 10-Q：期末日在年度期末前一個單季內，且宣告同財年 Q3。"""
        earlier = [
            p for p in self.filings.periods() if p < period and classify_duration(_next_day(p), period) == "quarter"
        ]
        if len(earlier) != 1:
            raise ParseError("Q4 期間", f"{period} 前一季應剛好有一個 10-Q 期別，找到 {earlier}")
        filing = self.filings.select(earlier[0], self.concepts).filing
        found = self.filings.document(filing).fiscal()
        if found != (year, "Q3"):
            raise ParseError("Q4 期間", f"{filing.accession}（{earlier[0]}）宣告 {found}，不是財年 {year} 的 Q3")
        return filing

    def candidate(self, filing, selector: FactSelector, end: str, duration: str, start: str | None, name: str) -> Candidate:
        document = self.filings.document(filing)
        label = f"{name}：{selector.describe()} {duration} 期末 {end}（{filing.accession}）"
        concept = document.resolve(selector.concept)
        dimensions = document.resolve_dimensions(selector.dimensions)
        if concept is None or dimensions is None:
            raise ParseError("fact 存在且唯一", f"{label}：規格使用的前綴在文件中沒有宣告或宣告衝突")
        facts = [
            f
            for f in document.facts
            if f.concept_key == concept
            and f.dimension_keys == dimensions
            and f.end == end
            and classify_duration(f.start, f.end) == duration
            and (start is None or f.start == start)
        ]
        if not facts:
            raise ParseError("fact 存在且唯一", f"找不到 {label}")
        if len({f.start for f in facts}) != 1:
            raise ParseError("fact 存在且唯一", f"{label} 有多個起日：{sorted({f.start for f in facts})}")
        for f in facts:
            if f.value_error:
                raise ParseError("fact 存在且唯一", f"{label} 的 {f.fact_id}：{f.value_error}")
            if f.unit != USD:
                raise ParseError("單位與精度", f"{label} 的 {f.fact_id} 單位是 {f.unit}，不是 USD")
            if f.error_bound() is None:
                raise ParseError("單位與精度", f"{label} 的 {f.fact_id} 沒有 decimals")
        best = max(facts, key=lambda f: decimals_rank(f.decimals))
        if decimals_rank(best.decimals) < MIN_DECIMALS:
            raise ParseError("單位與精度", f"{label} 的 {best.fact_id} decimals={best.decimals}，精度低於百萬位")
        # 重複 fact 以精度最高者為準；精度較低的重複值只需在自己的精度內與它一致。
        inconsistent = [f for f in facts if abs(f.value - best.value) > f.error_bound()]
        if inconsistent:
            values = ", ".join(f"{f.fact_id}={f.value}（decimals {f.decimals}）" for f in facts)
            raise ParseError("fact 存在且唯一", f"{label} 重複 fact 的數值不一致：{values}")
        return Candidate(filing, facts, duration, 1)

    @staticmethod
    def check_q4(name: str, annual: Fact, nine: Fact, period: str):
        if nine.start != annual.start:
            raise ParseError("Q4 期間", f"{name}：九個月起日 {nine.start} 不等於年度起日 {annual.start}")
        if classify_duration(_next_day(nine.end), period) != "quarter":
            raise ParseError("Q4 期間", f"{name}：九個月迄日 {nine.end} 到年度期末 {period} 不是一個季度")

    @staticmethod
    def choose(candidates: dict[str, list[Candidate]]) -> dict[str, list[Operand]]:
        """重複 fact 中選精度最高者；同精度時選所在表格含最多其他項目者，再平手取文件順序第一個。其餘記為 duplicates。"""
        tables: dict[tuple[str, int], set[str]] = {}
        for name, group in candidates.items():
            for candidate in group:
                for f in candidate.facts:
                    if f.table_index is not None:
                        tables.setdefault((candidate.filing.accession, f.table_index), set()).add(name)
        chosen = {}
        for name, group in candidates.items():
            operands = []
            for candidate in group:
                def rank(f: Fact):
                    others = tables.get((candidate.filing.accession, f.table_index), set()) if f.table_index is not None else set()
                    return (-decimals_rank(f.decimals), -len(others), f.order)

                ordered = sorted(candidate.facts, key=rank)
                operands.append(Operand("xbrl_fact", candidate.filing, ordered[0], ordered[1:], candidate.role))
            chosen[name] = operands
        return chosen

    @staticmethod
    def check_sum(result: PeriodResult) -> dict:
        """分類與調節項加總須等於總營收，差距不超過所有運算元四捨五入誤差的總和。"""
        parts = sum(line.value for line in result.lines if line.group in ("category", "reconciling"))
        total = next(line.value for line in result.lines if line.group == "total")
        tolerance = sum(
            (abs(t.weight) * t.operand.fact.error_bound() for line in result.lines for t in line.terms),
            Decimal(0),
        )
        difference = parts - total
        if abs(difference) > tolerance:
            raise ParseError("加總", f"分類加總 {parts} 與總營收 {total} 相差 {difference}，超過精度容許 {tolerance}")
        return {"categories": parts, "total": total, "difference": difference, "tolerance": str(tolerance)}


def _next_day(date: str) -> str:
    return (dt.date.fromisoformat(date) + dt.timedelta(days=1)).isoformat()
