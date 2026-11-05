"""組合一期的分類數值，並做結構檢核。

- Q 序列：Q1–Q3 取 10-Q 的單季 fact；Q4 = 年度 − 九個月累計。Q4 依據的 FY 與同財年 Q1–Q3 任一期結構檢核
  不通過時 Q4 失敗；各期都通過而年度與 Q1–Q3 的分類集合不同時，Q4 不推算。
- FY 序列：10-K 的年度 fact。

每期的分類集合是規格中在該期有生效定義的分類；沒有生效定義的分類該期不列出。
一個定義可以有多個加數（`sum_of`）：每個加數各是一個運算元，任一加數找不到時該期失敗；Q4 的每個加數同樣是
年度減九個月累計。分類的運算式依規格的加數順序列出（Q4 為各加數的年度、九個月累計交錯排列）。
任何結構檢核不通過都以 `ParseError` 結束該期；訊息開頭的 `[檢核名稱]` 與設計文件的檢核表一致。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
from decimal import Decimal

from .filings import Filing, FilingSet, ParseError
from .spec import Category, CompanySpec, Definition, FactSelector, TableCellSelector
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
    series: str
    period_end: str
    fiscal_year: int
    fiscal_quarter: int | None
    primary: Filing
    nine_month_filing: Filing | None
    lines: list[Line]
    structural: list[dict] = field(default_factory=list)
    sum_check: dict = field(default_factory=dict)

    @property
    def operands(self) -> list[Operand]:
        seen, result = set(), []
        for line in self.lines:
            for term in line.terms:
                if id(term.operand) not in seen:
                    seen.add(id(term.operand))
                    result.append(term.operand)
        return result


class NotDerived(ParseError):
    """Q4 年度的分類集合與 Q1–Q3 不同，不推算；不是失敗，status.json 記為 `not_derived`。"""

    def __init__(self, message: str, annual: list[str], quarters: list[dict]):
        super().__init__("Q4 推算條件", message)
        self.annual = annual
        self.quarters = quarters


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

    def items(self) -> list[tuple[str, Category]]:
        return (
            [("category", c) for c in self.spec.categories]
            + [("reconciling", c) for c in self.spec.reconciling]
            + [("total", self.spec.total)]
        )

    def compose(self, period: str) -> PeriodResult:
        """Q 序列的一期：Q1–Q3 或推算的 Q4。"""
        primary, year, quarter = self.primary(period)
        if quarter != 4:
            items = self.active_items(period)
            candidates = {
                item.name: self.addends(primary, definition, period, "quarter", None, item.name) for group, item, definition in items
            }
            return self.finish("Q", period, year, quarter, primary, None, items, candidates)

        # Point in time：九個月與 Q1–Q3 都來自申報日不晚於本期主申報的申報。
        nine_filing = self.third_quarter(period, year, primary.filing_date)
        start = self.dependencies(period, primary.filing_date, nine_filing.report_date)
        items = self.active_items(period)
        annual = {item.name: self.addends(primary, definition, period, "annual", None, item.name) for group, item, definition in items}
        self.check_categories(items, start, nine_filing.report_date, period)
        # 定義依運算元來源申報的期末日選取：年度運算元是本期，九個月運算元是 Q3 期末日。
        # 公司在財年中途改 tag 時（例如 10-K 起換新成員、同財年 Q3 10-Q 仍是舊成員），兩個運算元各用各的定義。
        # 年度與九個月累計的加數個數可以不同（兩者的定義各自選取）；Q4 = 年度各加數之和 − 九個月各加數之和。
        candidates = {}
        for group, item, definition in items:
            nine_definition = self.definition(item, nine_filing.report_date)
            if nine_definition is None:
                raise ParseError("定義唯一", f"{item.name} 在 {nine_filing.report_date} 沒有生效的定義")
            annual_start = annual[item.name][0].facts[0].start
            nine = self.addends(nine_filing, nine_definition, nine_filing.report_date, "nine_months", annual_start, item.name, sign=-1)
            for found in annual[item.name] + nine:
                self.check_q4(item.name, annual_start, found.facts[0], period)
            candidates[item.name] = interleave(annual[item.name], nine)
        return self.finish("Q", period, year, quarter, primary, nine_filing, items, candidates)

    def compose_annual(self, period: str) -> PeriodResult:
        """FY 序列的一期：10-K 的年度 fact。"""
        primary, year, quarter = self.primary(period)
        if quarter != 4:
            raise ParseError("財年與季別", f"{primary.accession} 宣告的期別是 Q{quarter}，FY 序列只取 10-K")
        items = self.active_items(period)
        candidates = {
            item.name: self.addends(primary, definition, period, "annual", None, item.name) for group, item, definition in items
        }
        return self.finish("FY", period, year, None, primary, None, items, candidates)

    def dependencies(self, period: str, as_of: str, nine_end: str) -> str:
        """Q4 依據的 FY 與同財年 Q1–Q3（範圍內有申報者）都必須通過結構檢核；不通過時 Q4 以該期的原因失敗。回傳財年起日。"""
        try:
            annual = self.compose_annual(period)
        except ParseError as error:
            raise ParseError(error.check, f"Q4 依據的 FY {period} 不通過：{error.message}") from error
        start = next(l for l in annual.lines if l.group == "total").terms[0].operand.fact.start
        for quarter in self.filings.periods(as_of):
            if start <= quarter <= nine_end:
                try:
                    self.compose(quarter)
                except ParseError as error:
                    raise ParseError(error.check, f"Q4 依據的 Q {quarter} 不通過：{error.message}") from error
        return start

    def primary(self, period: str) -> tuple[Filing, int, int]:
        primary = self.filings.select(period)
        year, focus = self.filings.document(primary).fiscal()
        if year is None or focus not in QUARTER_FOCUS:
            raise ParseError("財年與季別", f"{primary.accession} 沒有宣告 DocumentFiscalYearFocus／DocumentFiscalPeriodFocus（{year}, {focus}）")
        quarter = QUARTER_FOCUS[focus]
        expected_form = "10-K" if quarter == 4 else "10-Q"
        if not primary.form.startswith(expected_form):
            raise ParseError("財年與季別", f"{primary.accession} 是 {primary.form}，但宣告的期別是 {focus}")
        return primary, year, quarter

    def active_items(self, period: str) -> list[tuple[str, Category, Definition]]:
        """在 `period` 有生效定義的分類、調節項與總營收；總營收必須有定義。"""
        found = []
        for group, item in self.items():
            definition = self.definition(item, period)
            if definition is None:
                if group == "total":
                    raise ParseError("定義唯一", f"總營收 {item.name} 在 {period} 沒有生效的定義")
                continue
            found.append((group, item, definition))
        return found

    def category_names(self, date: str) -> list[str]:
        return [item.name for group, item in self.items() if group != "total" and self.definition(item, date) is not None]

    def check_categories(self, items, start: str, nine_end: str, period: str):
        """年度期末生效的分類集合，必須等於財年起日到 Q3 期末之間每一天生效的分類集合（依規格判斷，不需要 Q1、Q2 的申報）。"""
        annual = [item.name for group, item, _ in items if group != "total"]
        segments = []
        day = dt.date.fromisoformat(start)
        while day.isoformat() <= nine_end:
            names = self.category_names(day.isoformat())
            if segments and segments[-1]["categories"] == names:
                segments[-1]["end"] = day.isoformat()
            else:
                segments.append({"start": day.isoformat(), "end": day.isoformat(), "categories": names})
            day += dt.timedelta(days=1)
        different = [s for s in segments if s["categories"] != annual]
        if different:
            ranges = "；".join(f"{s['start']}～{s['end']} 為 {s['categories']}" for s in different)
            raise NotDerived(f"年度 {period} 的分類為 {annual}，Q1–Q3 期間 {ranges}；Q4 不推算", annual, segments)

    def finish(self, series, period, year, quarter, primary, nine_filing, items, candidates) -> PeriodResult:
        structural = [
            {"check": "定義唯一", "result": "pass"},
            {"check": "fact 存在且唯一", "result": "pass"},
            {"check": "單位與精度", "result": "pass"},
        ]
        if any(definition.geographic_sum() for _, _, definition in items):
            structural.append({"check": "地區成員完整", "result": "pass"})
        if nine_filing is not None:
            structural.append({"check": "Q4 期間", "result": "pass"})
        groups = {item.name: group for group, item, _ in items}
        chosen = self.choose(candidates)
        lines = [
            Line(name, groups[name], [Term(c.weight, op) for c, op in zip(candidates[name], chosen[name])])
            for name in candidates
        ]
        result = PeriodResult(series, period, year, quarter, primary, nine_filing, lines, structural)
        result.sum_check = self.check_sum(result)
        structural.append({"check": "加總", "result": "pass"})
        return result

    @staticmethod
    def definition(item: Category, source_period: str) -> Definition | None:
        """`source_period` 是運算元來源申報的期末日；沒有生效的定義時回傳 None（該期沒有這個項目）。

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

    def third_quarter(self, period: str, year: int, as_of: str) -> Filing:
        """Q4 的九個月累計來自前一季的 10-Q：期末日在年度期末前一個單季內，且宣告同財年 Q3；只看申報日不晚於 `as_of` 的申報。"""
        earlier = [
            p for p in self.filings.periods(as_of) if p < period and classify_duration(_next_day(p), period) == "quarter"
        ]
        if len(earlier) != 1:
            raise ParseError("Q4 期間", f"{period} 前一季應剛好有一個 10-Q 期別（申報日 {as_of} 以前），找到 {earlier}")
        filing = self.filings.select(earlier[0], as_of)
        found = self.filings.document(filing).fiscal()
        if found != (year, "Q3"):
            raise ParseError("Q4 期間", f"{filing.accession}（{earlier[0]}）宣告 {found}，不是財年 {year} 的 Q3")
        return filing

    def addends(self, filing, definition: Definition, end: str, duration: str, start: str | None, name: str, sign: int = 1) -> list[Candidate]:
        """定義的每個加數各找一個候選 fact 群；任一加數找不到時該期失敗。地區軸的加總另檢查成員完整。"""
        found = [self.candidate(filing, a.selector, end, duration, start, name, sign * a.weight) for a in definition.addends]
        starts = sorted({c.facts[0].start for c in found})
        if len(starts) != 1:
            raise ParseError("fact 存在且唯一", f"{name}：{filing.accession} 各加數的 {duration} 起日不同：{starts}")
        self.check_geography(filing, definition, end, duration, found[0].facts[0].start, name)
        return found

    def check_geography(self, filing, definition: Definition, end: str, duration: str, start: str, name: str):
        """地區軸的加總必須涵蓋申報中該軸的全部成員：同 concept、同其他 dimensions、同期間的 fact，地區成員不得有規格沒列的。"""
        geographic = definition.geographic_sum()
        if geographic is None:
            return
        axis, concept, others, members = geographic
        document = self.filings.document(filing)
        axis_key, concept_key = document.resolve(axis), document.resolve(concept)
        other_keys = document.resolve_dimensions(others)
        listed = document.resolve_dimensions(tuple((axis, m) for m in members))
        listed = {member for _, member in listed}
        present = {}
        for f in document.facts:
            if f.concept_key != concept_key or f.end != end or f.start != start:
                continue
            if f.dimension_keys is None:
                # dimensions 解析不了時無法判斷是不是該軸的其他成員，不能當成沒有。
                raise ParseError("地區成員完整", f"{name}：{filing.accession} 的 {f.fact_id} dimensions 前綴無法解析（{dict(f.dimensions)}），無法確認地區成員完整")
            dims = dict(f.dimension_keys)
            if axis_key in dims and tuple(sorted((a, m) for a, m in f.dimension_keys if a != axis_key)) == other_keys:
                present[dims[axis_key]] = next((m for a, m in f.dimensions if document.resolve(a) == axis_key), dims[axis_key])
        missing = sorted(shown for key, shown in present.items() if key not in listed)
        if missing:
            raise ParseError(
                "地區成員完整",
                f"{name}：{filing.accession} 的 {axis} 在 {duration} 期末 {end} 有規格沒有列出的成員 {missing}；地區軸只能以全部成員相加",
            )

    def candidate(self, filing, selector: FactSelector, end: str, duration: str, start: str | None, name: str, weight: int = 1) -> Candidate:
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
        return Candidate(filing, facts, duration, weight)

    @staticmethod
    def check_q4(name: str, annual_start: str, found: Fact, period: str):
        """年度與九個月累計的每個加數都從年度起日開始；九個月累計迄日到年度期末是一個季度。"""
        if found.start != annual_start:
            raise ParseError("Q4 期間", f"{name}：{found.fact_id} 起日 {found.start} 不等於年度起日 {annual_start}")
        if found.duration == "nine_months" and classify_duration(_next_day(found.end), period) != "quarter":
            raise ParseError("Q4 期間", f"{name}：九個月迄日 {found.end} 到年度期末 {period} 不是一個季度")

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


def interleave(annual: list[Candidate], nine: list[Candidate]) -> list[Candidate]:
    """Q4 運算式的順序：第 k 個年度加數之後接第 k 個九個月加數；個數不同時多出的依序接在後面。"""
    ordered = []
    for k in range(max(len(annual), len(nine))):
        ordered += annual[k : k + 1] + nine[k : k + 1]
    return ordered


def _next_day(date: str) -> str:
    return (dt.date.fromisoformat(date) + dt.timedelta(days=1)).isoformat()
