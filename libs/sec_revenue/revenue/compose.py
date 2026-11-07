"""組合一期的分類數值，並做結構檢核。

- Q 序列：Q1–Q3 取 10-Q 的單季 fact；Q4 = 年度 − 九個月累計。Q4 依據的 FY 與同財年 Q1–Q3 任一期結構檢核
  不通過時 Q4 失敗；各期都通過而年度與 Q1–Q3 的分類集合不同時，Q4 不推算。
- FY 序列：10-K 的年度 fact。

每一期向公司 parser（見 `source.py`）要主申報中該期間的組成：分類集合必須等於來源的
`categories(期末日)`，每一項由一個或多個運算元組成。框架補上每個運算元同 concept、dimensions、期間的重複 fact，
檢查數值一致、單位與精度後選定一個。Q4 的每個運算元同樣是年度減九個月累計，運算式依來源列出的順序（Q4 為各項的
年度、九個月累計交錯排列）。任何結構檢核不通過都以 `ParseError` 結束該期；訊息開頭的 `[檢核名稱]` 與設計文件的
檢核表一致。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
from decimal import Decimal

from .contract import Composition, Request
from .contract import Term as ComposedTerm
from .filings import Filing, FilingSet, ParseError
from .source import ParserSource
from .xbrl import USD, Fact, InlineDocument, classify_duration, decimals_rank

QUARTER_FOCUS = {"Q1": 1, "Q2": 2, "Q3": 3, "FY": 4}
# 地區軸只能以「該軸全部成員相加」出現在運算式中；觀點只取產品或業務別。
GEOGRAPHIC_AXIS = "srt:StatementGeographicalAxis"
# 運算元精度下限：decimals 小於 -6（例如 -8 代表百萬位以上四捨五入）時誤差過大，該期不上線。
MIN_DECIMALS = -6


@dataclass
class Operand:
    """一個 SEC 數字；`kind` 一定是 `xbrl_fact`。"""

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
    # 財年推算值與主申報宣告不同時的紀錄（`PeriodComposer.fiscal`）；相同時為 None。
    fiscal_basis: dict | None = None

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
    """Q4 不推算：不是失敗，status.json 記為 `not_derived`，附檢核名稱、原因與 `details` 的欄位。"""

    def __init__(self, check: str, message: str, details: dict):
        super().__init__(check, message)
        self.details = details


@dataclass
class Candidate:
    """一個運算元在某份申報中的候選 fact 群（同 concept、dimensions、期間，值必須一致）。"""

    filing: Filing
    facts: list[Fact]
    role: str
    weight: int


class PeriodComposer:
    def __init__(self, source: ParserSource, filings: FilingSet):
        self.source = source
        self.filings = filings
        self.fact_sets: dict[int, set[Fact]] = {}

    def request(self, filing: Filing, request: Request) -> Composition:
        """向來源要一份申報中一段期間的組成；fact 清單的集合在交給來源之前建立，供核對交回的 fact。"""
        document = self.filings.document(filing)
        self.facts_of(document)
        return self.source.compose(document, filing, request)

    def compose(self, period: str) -> PeriodResult:
        """Q 序列的一期：Q1–Q3 或推算的 Q4。"""
        primary, year, quarter, basis = self.primary(period)
        if quarter != 4:
            items = self.collect(primary, Request(period, "quarter"), "quarter")
            return self.finish("Q", period, year, quarter, primary, None, items, basis)

        # Point in time：九個月與 Q1–Q3 都來自申報日不晚於本期主申報的申報。
        nine_filing = self.third_quarter(period, year, primary.filing_date)
        start = self.dependencies(period, primary.filing_date, nine_filing.report_date)
        annual = self.collect(primary, Request(period, "annual"), "annual")
        self.check_categories(annual, start, nine_filing.report_date, period)
        # 年度與九個月累計各自向來源要，加數個數可以不同；Q4 = 年度各加數之和 − 九個月各加數之和。
        total_start = annual[-1][2][0].facts[0].start
        nine = {
            name: candidates
            for group, name, candidates in self.collect(
                nine_filing, Request(nine_filing.report_date, "nine_months", total_start), "nine_months", sign=-1
            )
        }
        items = []
        for group, name, candidates in annual:
            if name not in nine:
                raise ParseError("定義唯一", f"{name} 在 {nine_filing.report_date} 沒有九個月累計的組成")
            annual_start = candidates[0].facts[0].start
            for found in candidates + nine[name]:
                self.check_q4(name, annual_start, found.facts[0], period)
            items.append((group, name, interleave(candidates, nine[name])))
        return self.finish("Q", period, year, quarter, primary, nine_filing, items, basis)

    def compose_annual(self, period: str) -> PeriodResult:
        """FY 序列的一期：10-K 的年度 fact。"""
        primary, year, quarter, basis = self.primary(period)
        if quarter != 4:
            raise ParseError("財年與季別", f"{primary.accession} 宣告的期別是 Q{quarter}，FY 序列只取 10-K")
        items = self.collect(primary, Request(period, "annual"), "annual")
        return self.finish("FY", period, year, None, primary, None, items, basis)

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

    def primary(self, period: str) -> tuple[Filing, int, int, dict | None]:
        """該期的主申報、財年、季別，與財年推算值和宣告不同時的紀錄（見 `fiscal`）。"""
        primary = self.filings.select(period)
        year, focus, basis = self.fiscal(primary)
        quarter = QUARTER_FOCUS[focus]
        expected_form = "10-K" if quarter == 4 else "10-Q"
        if not primary.form.startswith(expected_form):
            raise ParseError("財年與季別", f"{primary.accession} 是 {primary.form}，但宣告的期別是 {focus}")
        return primary, year, quarter, basis

    def fiscal(self, filing: Filing) -> tuple[int, str, dict | None]:
        """申報的財年與期別（Q1、Q2、Q3、FY）。

        期別取申報宣告的 `DocumentFiscalPeriodFocus`。10-K 的財年取宣告的 `DocumentFiscalYearFocus`；10-Q 的財年是
        前一份 10-K 宣告的財年 + 1，因為有公司在 10-Q 宣告錯的財年（ORCL 2026-08-31 的 10-Q 宣告 2026，實為 2027）。
        前一份 10-K 是申報日不晚於這份 10-Q、期末日早於它的原申報中期末日最晚的 10-K；它的期末日隔天到 10-Q 期末
        必須是單季、六個月或九個月，確認它是上一財年的年報。找不到或不相接時報錯，不退回宣告值。推算值與宣告不同時
        回傳紀錄（宣告值、推算值、前一份 10-K），以推算值為準；相同時紀錄為 None。
        """
        year, focus = self.filings.document(filing).fiscal()
        if year is None or focus not in QUARTER_FOCUS:
            raise ParseError("財年與季別", f"{filing.accession} 沒有宣告 DocumentFiscalYearFocus／DocumentFiscalPeriodFocus（{year}, {focus}）")
        if not filing.form.startswith("10-Q"):
            return year, focus, None
        annual = self.prior_annual(filing)
        try:
            prior_year, _ = self.filings.document(annual).fiscal()
        except ParseError as error:
            raise ParseError(error.check, f"{filing.accession} 推算財年所需的上一財年 10-K {annual.accession}：{error.message}") from error
        if prior_year is None:
            raise ParseError("財年與季別", f"{filing.accession} 的前一份 10-K {annual.accession} 沒有宣告 DocumentFiscalYearFocus，推不出財年")
        derived = prior_year + 1
        if derived == year:
            return year, focus, None
        basis = {
            "declared": year,
            "derived": derived,
            "prior_annual": {"accession": annual.accession, "period_end": annual.report_date, "fiscal_year": prior_year},
        }
        return derived, focus, basis

    def prior_annual(self, filing: Filing) -> Filing:
        """10-Q 推算財年依據的前一份 10-K：只看申報日不晚於這份 10-Q 的申報（見 `fiscal`）。"""
        as_of = filing.filing_date
        earlier = [p for p in self.filings.periods(as_of) if p < filing.report_date]
        annual = [f for p in earlier if (f := self.filings.select(p, as_of)).form == "10-K"]
        if not annual:
            raise ParseError(
                "財年與季別",
                f"{filing.accession}（{filing.report_date}）之前沒有申報日不晚於 {as_of} 的 10-K，推不出財年；請下載上一財年的 10-K",
            )
        found = annual[-1]
        if classify_duration(_next_day(found.report_date), filing.report_date) not in ("quarter", "six_months", "nine_months"):
            raise ParseError(
                "財年與季別",
                f"{filing.accession}（{filing.report_date}）之前最近的 10-K 是 {found.accession}（{found.report_date}），"
                "兩者期末之間不是單季、六個月或九個月，不是上一財年的年報；請下載上一財年的 10-K",
            )
        return found

    def collect(self, filing: Filing, request: Request, role: str, sign: int = 1) -> list[tuple[str, str, list[Candidate]]]:
        """主申報中一段期間的組成，依輸出順序回傳（群組, 名稱, 各運算元的候選 fact 群），總營收在最後。

        分類與調節項的集合必須等於來源的 `categories(申報期末日)`；總營收一定要有。
        """
        composition = self.request(filing, request)
        document = self.filings.document(filing)
        expected = self.source.categories(filing.report_date)
        groups = {name: "category" for name in composition.categories} | {name: "reconciling" for name in composition.reconciling}
        extra = [name for name in groups if name not in expected]
        if extra:
            raise ParseError("定義唯一", f"{filing.accession} 的組成有 {extra}，不在 {filing.report_date} 的分類 {expected} 中")
        found = {}
        for name in expected:
            if name not in groups:
                self.absent(composition, name, filing, request)
            terms = composition.categories[name] if name in composition.categories else composition.reconciling[name]
            if not terms:
                raise ParseError("定義唯一", f"{name}：{filing.accession} 的組成沒有任何運算元")
            found[name] = self.candidates(document, filing, name, terms, request, role, sign)
        if list(groups) != expected:
            raise ParseError("定義唯一", f"{filing.accession} 的組成順序 {list(groups)} 與 {filing.report_date} 的分類 {expected} 不同")
        if composition.total is None:
            self.absent(composition, self.source.total_name, filing, request)
        if not composition.total:
            raise ParseError("定義唯一", f"{self.source.total_name}：{filing.accession} 的組成沒有任何運算元")
        total = self.candidates(document, filing, self.source.total_name, composition.total, request, role, sign)
        ordered = [(groups[name], name, found[name]) for name in groups]
        return ordered + [("total", self.source.total_name, total)]

    @staticmethod
    def absent(composition: Composition, name: str, filing: Filing, request: Request):
        """主申報的組成沒有某一項：依來源記錄的原因結束該期。"""
        if name in composition.unparseable:
            raise ParseError("fact 存在且唯一", f"{name}：{composition.unparseable[name]}")
        if name in composition.missing:
            raise ParseError("fact 存在且唯一", f"找不到 {composition.missing[name]}")
        raise ParseError("定義唯一", f"{name} 在 {filing.report_date} 的分類中，但 {filing.accession} {request.duration} 期末 {request.end} 的組成沒有它")

    def check_categories(self, items, start: str, nine_end: str, period: str):
        """年度期末的分類集合，必須等於財年起日到 Q3 期末之間每一天的分類集合（依來源的 `categories`，不需要 Q1、Q2 的申報）。"""
        annual = [name for group, name, _ in items if group != "total"]
        segments = []
        day = dt.date.fromisoformat(start)
        while day.isoformat() <= nine_end:
            names = self.source.categories(day.isoformat())
            if segments and segments[-1]["categories"] == names:
                segments[-1]["end"] = day.isoformat()
            else:
                segments.append({"start": day.isoformat(), "end": day.isoformat(), "categories": names})
            day += dt.timedelta(days=1)
        different = [s for s in segments if s["categories"] != annual]
        if different:
            ranges = "；".join(f"{s['start']}～{s['end']} 為 {s['categories']}" for s in different)
            raise NotDerived(
                "Q4 推算條件",
                f"年度 {period} 的分類為 {annual}，Q1–Q3 期間 {ranges}；Q4 不推算",
                {"fy_categories": annual, "quarter_categories": segments},
            )

    def finish(self, series, period, year, quarter, primary, nine_filing, items, basis=None) -> PeriodResult:
        structural = [
            {"check": "定義唯一", "result": "pass"},
            {"check": "fact 存在且唯一", "result": "pass"},
            {"check": "單位與精度", "result": "pass"},
        ]
        if any(self.geographic(f) for _, _, candidates in items for c in candidates for f in c.facts):
            structural.append({"check": "地區成員完整", "result": "pass"})
        if nine_filing is not None:
            structural.append({"check": "Q4 期間", "result": "pass"})
        chosen = self.choose({name: candidates for _, name, candidates in items})
        lines = [Line(name, group, [Term(c.weight, op) for c, op in zip(candidates, chosen[name])]) for group, name, candidates in items]
        result = PeriodResult(series, period, year, quarter, primary, nine_filing, lines, structural, fiscal_basis=basis)
        result.sum_check = self.check_sum(result)
        structural.append({"check": "加總", "result": "pass"})
        return result

    def third_quarter(self, period: str, year: int, as_of: str) -> Filing:
        """Q4 的九個月累計來自前一季的 10-Q：期末日在年度期末前一個單季內，且是同財年的 Q3（財年依 `fiscal`）；只看申報日不晚於 `as_of` 的申報。"""
        earlier = [
            p for p in self.filings.periods(as_of) if p < period and classify_duration(_next_day(p), period) == "quarter"
        ]
        if len(earlier) != 1:
            raise ParseError("Q4 期間", f"{period} 前一季應剛好有一個 10-Q 期別（申報日 {as_of} 以前），找到 {earlier}")
        filing = self.filings.select(earlier[0], as_of)
        found = self.fiscal(filing)[:2]
        if found != (year, "Q3"):
            raise ParseError("Q4 期間", f"{filing.accession}（{earlier[0]}）的財年與期別是 {found}，不是財年 {year} 的 Q3")
        return filing

    def candidates(
        self, document: InlineDocument, filing: Filing, name: str, terms: list[ComposedTerm], request: Request, role: str, sign: int
    ) -> list[Candidate]:
        """一項的每個運算元各一個候選 fact 群；同一份申報中各運算元的起日必須相同，使用地區軸時檢查成員完整。"""
        found = [self.candidate(document, filing, name, term, request, role, sign * term.weight) for term in terms]
        starts = sorted({c.facts[0].start for c in found})
        if len(starts) != 1:
            raise ParseError("fact 存在且唯一", f"{name}：{filing.accession} 各加數的 {request.duration} 起日不同：{starts}")
        self.check_geography(document, filing, name, found, request)
        return found

    @staticmethod
    def geographic_axis(dimension_key: str) -> bool:
        """地區軸以 namespace URI 判斷：srt taxonomy（每年不同日期）的 StatementGeographicalAxis，與文件用的前綴無關。"""
        return dimension_key.startswith("{http://fasb.org/srt/") and dimension_key.endswith("}" + GEOGRAPHIC_AXIS.split(":")[1])

    def geographic(self, fact: Fact) -> bool:
        return fact.dimension_keys is not None and any(self.geographic_axis(axis) for axis, _ in fact.dimension_keys)

    def check_geography(self, document: InlineDocument, filing: Filing, name: str, found: list[Candidate], request: Request):
        """使用地區軸的運算元必須涵蓋申報中該軸的全部成員：同 concept、同其他 dimensions、同期間的 fact，地區成員都要在運算式中。"""
        shapes: dict[tuple, set[str]] = {}
        for candidate in found:
            for fact in candidate.facts:
                if not self.geographic(fact):
                    continue
                axis_key = next(axis for axis, _ in fact.dimension_keys if self.geographic_axis(axis))
                dims = dict(fact.dimension_keys)
                others = tuple(sorted((a, m) for a, m in fact.dimension_keys if a != axis_key))
                shapes.setdefault((fact.concept_key, axis_key, others, fact.start, fact.end), set()).add(dims[axis_key])
        for (concept_key, axis_key, others, start, end), listed in shapes.items():
            present = {}
            for f in document.facts:
                if f.concept_key != concept_key or f.end != end or f.start != start:
                    continue
                if f.dimension_keys is None:
                    # dimensions 解析不了時無法判斷是不是該軸的其他成員，不能當成沒有。
                    raise ParseError("地區成員完整", f"{name}：{filing.accession} 的 {f.fact_id} dimensions 前綴無法解析（{dict(f.dimensions)}），無法確認地區成員完整")
                dims = dict(f.dimension_keys)
                if axis_key in dims and tuple(sorted((a, m) for a, m in f.dimension_keys if a != axis_key)) == others:
                    present[dims[axis_key]] = next((m for a, m in f.dimensions if document.resolve(a) == axis_key), dims[axis_key])
            missing = sorted(shown for key, shown in present.items() if key not in listed)
            if missing:
                raise ParseError(
                    "地區成員完整",
                    f"{name}：{filing.accession} 的 {GEOGRAPHIC_AXIS} 在 {request.duration} 期末 {end} 有運算式沒有列出的成員 {missing}；地區軸只能以全部成員相加",
                )

    def facts_of(self, document: InlineDocument) -> set[Fact]:
        key = id(document)
        if key not in self.fact_sets:
            self.fact_sets[key] = set(document.facts)
        return self.fact_sets[key]

    def candidate(self, document: InlineDocument, filing: Filing, name: str, term: ComposedTerm, request: Request, role: str, weight: int) -> Candidate:
        """一個運算元在申報中的候選 fact 群。

        `term.facts` 是來源找到的 fact（多種寫法時每種寫法各有）；框架補上同 concept、dimensions、期間的重複 fact，
        合成一群：數值必須在各自精度內一致，選精度最高、所在表格含最多其他項目的那一個，其餘記在 duplicates。
        """
        label = f"{name}：{term.label or '、'.join(f.fact_id or '?' for f in term.facts)} {request.duration} 期末 {request.end}（{filing.accession}）"
        if term.weight not in (1, -1):
            raise ParseError("定義唯一", f"{label} 的權重是 {term.weight}，只能是 1 或 -1")
        if not term.facts:
            raise ParseError("fact 存在且唯一", f"找不到 {label}")
        known = self.facts_of(document)
        for f in term.facts:
            if f not in known:
                raise ParseError("fact 存在且唯一", f"{label}：{f.fact_id} 不在這份申報的 fact 清單中")
            if f.concept_key is None or f.dimension_keys is None:
                raise ParseError("fact 存在且唯一", f"{label}：{f.fact_id} 的前綴在文件中沒有宣告或宣告衝突")
            if not request.matches(f):
                raise ParseError("fact 存在且唯一", f"{label}：{f.fact_id} 的期間 {f.start}～{f.end} 不是要求的期間")
        geographic = [self.geographic(f) for f in term.facts]
        if any(geographic) and (not all(geographic) or term.weight != 1):
            raise ParseError("地區成員完整", f"{label}：地區軸的 fact 只能以權重 1、不與其他寫法混合的方式相加")
        keys = {(f.concept_key, f.dimension_keys) for f in term.facts}
        facts = [f for f in document.facts if (f.concept_key, f.dimension_keys) in keys and request.matches(f)]
        forms = {(f.concept_key, f.dimension_keys) for f in facts}
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
            values = ", ".join(f"{f.fact_id} {f.concept} {dict(f.dimensions)}={f.value}（decimals {f.decimals}）" for f in facts)
            kind = "多種寫法同時出現且數值不一致" if len(forms) > 1 else "重複 fact 的數值不一致"
            raise ParseError("fact 存在且唯一", f"{label} {kind}：{values}")
        return Candidate(filing, facts, role, weight)

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
