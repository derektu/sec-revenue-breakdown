"""Parser 引擎：一家公司逐期組合數值、結構檢核、證據，寫入正式輸出；每次執行結束時以比較欄比對重建 status.json 的差異標記。

正式輸出在 `data/revenue/<首字母>/<TICKER>/`，分成兩個序列：`Q/<期末日>/`（Q1–Q4）與 `FY/<期末日>/`（10-K 全年）。
每期先寫暫存目錄，完成後整組換上。

- 預設起始日：沒有指定起日時，Q 與 FY 處理期末日不早於 `DEFAULT_START` 的期別。起日之前的申報照常讀取，
  作為運算元（例如 Q4 的九個月）與比較欄比對的來源，只是這次不處理成期別。
- Point in time：一期的主申報是該期最早的原申報；處理時只使用申報日不晚於它的申報。
- 結構檢核不通過或任何例外：不寫入，已上線的該期輸出保留不動，status.json 記錄失敗原因。
- Q4 的年度分類集合與 Q1–Q3 不同：不推算，status.json 記為 `not_derived`。
- 已上線期別不會被一般 parse 改動。重算結果與已上線輸出不同時，status.json 記錄差異；
  由人決定後以 `republish` 指定該期才覆寫，覆寫時 revenue.json 記錄原值與原因。
- 差異標記：每份已下載申報（含修正申報）的比較欄，與它申報當時看得到的已上線輸出逐一比對；
  不同時在舊期別記錄標記，已上線數字不改。標記每次以目前的已上線值重算，不存在 revenue.json。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import tempfile
from typing import Callable

from ..engines import JsonCodec
from ..evidence import TableScreenshotter
from .compose import NotDerived, Operand, PeriodComposer, PeriodResult
from .filings import FilingSet, ParseError
from .review import comparatives
from .spec import CompanySpec, FactSelector

SCHEMA_VERSION = 1
# 預設起始日（期末日，含）：所有公司共用，沒有指定起日時使用；要處理更早的期別時指定起日。
DEFAULT_START = "2023-10-01"
SCREENSHOT_SCALE = 1
SERIES = ("Q", "FY")
PERIOD_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# 輸出中描述數值與其依據的欄位；這些不同代表數值或來源改變。其餘欄位（檢核紀錄、parser、運算元的證據 hash）
# 不同只是中繼資料。
VALUE_FIELDS = ("series", "categories", "total", "reconciling", "operands", "filings", "fiscal_year", "fiscal_quarter", "view")
# 差異標記：比較欄比對中這些結果寫到舊期別。
MARKED_RESULTS = ("different", "unparseable")
PACKAGE = Path(__file__).resolve().parents[1]


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def engine_sha256() -> str:
    """引擎程式（`revenue/` 與證據元件）的 hash，記錄在每份輸出。"""
    files = sorted((PACKAGE / "revenue").glob("*.py")) + [PACKAGE / "evidence.py"]
    return sha256(b"".join(f.name.encode() + sha256(f.read_bytes()).encode() for f in files))


def ticker_dir(root: Path, ticker: str) -> Path:
    return root / ticker[0].upper() / ticker


class RevenueParser:
    """`out` 是寫入的正式輸出根目錄；`reuse` 是沿用已提交 PNG 的輸出根目錄（一般與 `out` 相同）。

    `screenshots=False` 時不啟動 Chromium，PNG 只沿用已提交的檔案（供 `--check` 使用）。
    `republish` 是允許覆寫的 (序列, 期末日)。`default_start` 是沒有指定起日時的起始日，預設為 `DEFAULT_START`。
    """

    def __init__(
        self,
        data: Path,
        out: Path,
        spec: CompanySpec,
        spec_sha256: str,
        reuse: Path | None = None,
        screenshots: bool = True,
        republish: set[tuple[str, str]] | frozenset[tuple[str, str]] = frozenset(),
        progress: Callable[[dict], None] | None = None,
        screenshotter: Callable[[], TableScreenshotter] | None = None,
        default_start: str = DEFAULT_START,
    ):
        self.spec = spec
        self.default_start = default_start
        self.out = ticker_dir(out, spec.ticker)
        self.reuse = ticker_dir(reuse or out, spec.ticker)
        self.filings = FilingSet(data, spec.ticker)
        self.composer = PeriodComposer(spec, self.filings)
        self.screenshots = screenshots
        self.republish = set(republish)
        self.progress = progress
        self.screenshotter = screenshotter or (lambda: TableScreenshotter(device_scale=SCREENSHOT_SCALE))
        self.active = None
        self.parser_info = {"spec_sha256": spec_sha256, "engine_sha256": engine_sha256()}

    # ---- 期別與已上線輸出 ----

    def periods(self, start: str | None = None, end: str | None = None) -> list[str]:
        """期末日在 [start, end] 的已下載期別；沒有指定 `start` 時從預設起始日起。"""
        start = start or self.default_start
        return [p for p in self.filings.periods() if p >= start and (not end or p <= end)]

    def series_of(self, period: str) -> list[str]:
        """期末日是 10-K 的期別同時有 FY 與 Q4；FY 先處理。"""
        return ["FY", "Q"] if self.filings.is_annual(period) else ["Q"]

    @staticmethod
    def published(root: Path) -> dict[tuple[str, str], dict]:
        """已上線輸出，以 (序列, 期末日) 為鍵：只讀以期末日命名的目錄，暫存或殘留目錄不算。"""
        found = {}
        for series in SERIES:
            directory = root / series
            if directory.exists():
                for path in sorted(directory.glob("*/revenue.json")):
                    if PERIOD_RE.fullmatch(path.parent.name):
                        found[(series, path.parent.name)] = JsonCodec.read(path)
        return found

    @staticmethod
    def visible(published: dict[tuple[str, str], dict], as_of: str) -> list[tuple[str, str, dict]]:
        """Point in time：運算元全部來自申報日不晚於 `as_of` 的申報的已上線輸出。"""
        return [
            (series, period, output)
            for (series, period), output in sorted(published.items(), key=lambda kv: (kv[0][1], kv[0][0]))
            if all(o["filing_date"] <= as_of for o in output["operands"].values())
        ]

    def recover(self) -> list[str]:
        """清理中斷的寫入：`.staging-*` 直接刪除；`.retired-<期別>-*` 在該期目錄不存在時還原，否則刪除。"""
        notes = []
        for series in SERIES:
            directory = self.out / series
            if not directory.exists():
                continue
            for path in sorted(directory.iterdir()):
                if path.name.startswith(".staging-"):
                    shutil.rmtree(path)
                    notes.append(f"刪除中斷寫入的暫存目錄 {series}/{path.name}")
                elif path.name.startswith(".retired-"):
                    period = path.name[len(".retired-") : len(".retired-") + 10]
                    final = directory / period
                    if PERIOD_RE.fullmatch(period) and not final.exists():
                        path.rename(final)
                        notes.append(f"還原 {series} {period} 的已上線輸出（{path.name}）")
                    else:
                        shutil.rmtree(path)
                        notes.append(f"刪除已被取代的舊輸出 {series}/{path.name}")
        return notes

    # ---- 執行 ----

    def run(self, periods: list[str]) -> dict:
        """依期末日順序處理；每期只看得到先前已寫入、且符合 point in time 的輸出。"""
        report = {"ticker": self.spec.ticker, "periods": [], "complete": True}
        recovered = self.recover()
        if recovered:
            report["recovered"] = recovered
        status = self.read_status()
        try:
            for period in sorted(periods):
                for series in self.series_of(period):
                    try:
                        entry = self.parse_period(series, period)
                    except Exception as error:
                        # 單期的任何錯誤都記為該期失敗，繼續處理下一期。
                        entry = self.failed(series, period, "例外", f"{type(error).__name__}: {error}")
                    status["periods"][series][period] = entry
                    report["periods"].append({"series": series, "period_end": period, **entry})
                    report["complete"] &= entry["status"] != "failed"
                    if self.progress:
                        self.progress({"ticker": self.spec.ticker, "period": f"{series} {period}", "status": entry["status"]})
        finally:
            if self.active is not None:
                try:
                    self.active.__exit__(None, None, None)
                finally:
                    self.active = None
            self.write_status(status)
        return report

    def failed(self, series: str, period: str, check: str, reason: str) -> dict:
        return {"status": "failed", "check": check, "reason": reason, **self.kept(series, period)}

    def not_derived(self, period: str, error: NotDerived) -> dict:
        return {
            "status": "not_derived",
            "check": error.check,
            "reason": error.message,
            "fy_categories": error.annual,
            "quarter_categories": error.quarters,
            **self.kept("Q", period),
        }

    def kept(self, series: str, period: str) -> dict:
        """失敗或不推算時，該期若有先前上線的輸出，保留不動並記錄它的申報與數值。"""
        path = self.out / series / period / "revenue.json"
        if not path.exists():
            return {"published_output_kept": False}
        existing = JsonCodec.read(path)
        return {
            "published_output_kept": True,
            "published_output": {
                "accession": existing["filings"]["primary"]["accession"],
                "categories": {n: c["value"] for n, c in existing["categories"].items()},
                "total": existing["total"]["value"],
                "note": "已上線輸出保留不動；以目前的申報與規格重算，此期不成立",
            },
        }

    def parse_period(self, series: str, period: str) -> dict:
        try:
            result = self.composer.compose(period) if series == "Q" else self.composer.compose_annual(period)
            output, files = self.build(result)
        except NotDerived as error:
            return self.not_derived(period, error)
        except ParseError as error:
            return self.failed(series, period, error.check, error.message)
        existing_path = self.out / series / period / "revenue.json"
        if existing_path.exists():
            existing = JsonCodec.read(existing_path)
            if "republished" in existing:
                output["republished"] = existing["republished"]
            changes = published_differences(existing, output)
            if not changes["fields"]:
                # 只有 parser（引擎與規格 hash）不同：輸出內容相同，不寫入也不算過時。
                return self.unchanged_entry(existing, changes)
            if (series, period) not in self.republish:
                return self.unchanged_entry(existing, changes)
            output["republished"] = output.get("republished", []) + [
                {
                    "reason": changes["reason"],
                    "previous": {
                        "accession": existing["filings"]["primary"]["accession"],
                        "categories": {n: c["value"] for n, c in existing["categories"].items()},
                        "total": existing["total"]["value"],
                        "parser": existing.get("parser"),
                    },
                }
            ]
        self.write_period(series, period, output, files)
        return self.entry(output)

    @staticmethod
    def entry(output: dict) -> dict:
        found = {"status": "published", "fiscal_year": output["fiscal_year"]}
        if "fiscal_quarter" in output:
            found["fiscal_quarter"] = output["fiscal_quarter"]
        found["accession"] = output["filings"]["primary"]["accession"]
        return found

    def unchanged_entry(self, existing: dict, changes: dict) -> dict:
        """已上線輸出不改。數值或依據不同時記錄 `differs_from_published`；只有中繼資料不同時記錄 `stale_fields`。"""
        entry = self.entry(existing)
        if changes["value_changed"]:
            entry["differs_from_published"] = changes
        elif changes["fields"]:
            entry["stale_fields"] = changes["fields"]
        return entry

    # ---- 輸出內容 ----

    def build(self, result: PeriodResult) -> tuple[dict, dict[str, bytes]]:
        operands = result.operands
        for number, operand in enumerate(operands, 1):
            operand.id = f"op{number}"
        evidence, files = self.evidence(result, operands)
        output = {
            "schema_version": SCHEMA_VERSION,
            "ticker": self.spec.ticker,
            "view": self.spec.view,
            "series": result.series,
            "period_end": result.period_end,
            "fiscal_year": result.fiscal_year,
        }
        if result.fiscal_quarter is not None:
            output["fiscal_quarter"] = result.fiscal_quarter
        output |= {
            "unit": "USD",
            "filings": self.filing_records(result),
            "categories": self.lines(result, "category"),
            "total": self.lines(result, "total")[self.spec.total.name],
        }
        if self.spec.reconciling:
            output["reconciling"] = self.lines(result, "reconciling")
        output |= {
            "operands": {op.id: self.operand_record(op, evidence[op.id]) for op in operands},
            "checks": {
                "structural": result.structural + [{"check": "證據完整", "result": "pass"}],
                "sum": result.sum_check,
            },
            "parser": self.parser_info,
        }
        return output, files

    def selector_for(self, period: str):
        """回傳查詢函式：分類名稱（`None` 為總營收）→ 在 `period` 生效的 FactSelector；沒有或不是 fact 時為 None。"""
        items = {c.name: c for c in self.spec.categories + self.spec.reconciling}

        def lookup(name):
            item = self.spec.total if name is None else items.get(name)
            if item is None:
                return None
            try:
                definition = self.composer.definition(item, period)
            except ParseError:
                return None
            return definition.selector if definition and isinstance(definition.selector, FactSelector) else None

        return lookup

    @staticmethod
    def filing_records(result: PeriodResult) -> dict:
        records = {"primary": result.primary.describe()}
        if result.nine_month_filing:
            records["nine_months"] = result.nine_month_filing.describe()
        return records
    @staticmethod
    def lines(result: PeriodResult, group: str) -> dict:
        return {
            line.name: {
                "value": line.value,
                "expression": [{"weight": t.weight, "operand": t.operand.id} for t in line.terms],
            }
            for line in result.lines
            if line.group == group
        }

    @staticmethod
    def operand_record(operand: Operand, evidence: dict) -> dict:
        fact = operand.fact
        return {
            "kind": operand.kind,
            "role": operand.role,
            "accession": operand.filing.accession,
            "form": operand.filing.form,
            "filing_date": operand.filing.filing_date,
            "document": operand.filing.document_record(),
            "fact_id": fact.fact_id,
            "duplicates": [d.fact_id for d in operand.duplicates],
            "context_id": fact.context_id,
            "concept": fact.concept,
            "dimensions": dict(fact.dimensions),
            "period": {"start": fact.start, "end": fact.end},
            "value": fact.value,
            "raw": fact.raw,
            "scale": fact.scale,
            "decimals": fact.decimals,
            "sign": fact.sign,
            "evidence": evidence,
        }

    # ---- 證據 ----

    def evidence(self, result: PeriodResult, operands: list[Operand]) -> tuple[dict, dict[str, bytes]]:
        """每個運算元找到所在表格；同一張表的運算元一起標示，產生 HTML 與 PNG。"""
        groups: dict[str, list[Operand]] = {}
        for operand in operands:
            document = self.filings.document(operand.filing)
            locator = document.locator
            fact = operand.fact
            status, index = locator.locate(fact.fact_id)
            if status != "in_table" or index != fact.table_index:
                raise ParseError("證據完整", f"{operand.id} {fact.fact_id}（{operand.filing.accession}）不在 HTML 表格內，沒有表格證據")
            mismatch = locator.verify(
                {"fact_id": fact.fact_id, "concept": fact.concept, "context_id": fact.context_id, "scale": fact.scale, "raw": fact.raw, "value": fact.value}
            )
            if mismatch:
                raise ParseError("證據完整", f"{operand.id} {fact.fact_id}：{mismatch}")
            key = f"{operand.filing.accession}-{operand.filing.document['sha256'][:12]}-t{index}"
            groups.setdefault(key, []).append(operand)
        names = {}
        for line in result.lines:
            for term in line.terms:
                names.setdefault(term.operand.id, []).append(line.name)
        records, files = {}, {}
        for key, members in sorted(groups.items()):
            filing = members[0].filing
            locator = self.filings.document(filing).locator
            index = members[0].fact.table_index
            items = [
                {
                    "id": op.fact.fact_id,
                    "badge": op.id.removeprefix("op"),
                    "raw": op.fact.raw,
                    "label": f"{op.id} · {'、'.join(names[op.id])} · {filing.form} {op.role}"
                    f"（{op.fact.start}～{op.fact.end}）{op.fact.raw} · {op.fact.concept} · {op.fact.fact_id}",
                }
                for op in members
            ]
            header = {"ticker": self.spec.ticker, "form": filing.form, "accession": filing.accession, "source_url": filing.document["source_url"]}
            try:
                page = locator.table_html(index, items, header)
            except ValueError as error:
                raise ParseError("證據完整", f"{key}：{error}") from error
            png = self.png(result.series, result.period_end, key, page, filing, items, locator, index)
            files[f"{key}.html"] = page
            if png is not None:
                files[f"{key}.png"] = png
            for op in members:
                records[op.id] = {
                    "table": key,
                    "html_sha256": sha256(page),
                    "png_sha256": sha256(png) if png is not None else None,
                    "png_scale": SCREENSHOT_SCALE if png is not None else None,
                }
        return records, files

    def png(self, series, period, key, page, filing, items, locator, index) -> bytes | None:
        """HTML 與已提交的相同、PNG hash 與截圖倍率都相符時沿用舊 PNG；`screenshots=False` 時只沿用、不截圖。

        同一期末日的 FY 與 Q4 都用到 10-K 的表格，先找本序列、再找另一個序列的已提交證據。
        """
        for source in [series] + [s for s in SERIES if s != series]:
            committed = self.reuse / source / period / "evidence"
            old_page, old_png = committed / f"{key}.html", committed / f"{key}.png"
            if old_page.is_file() and old_png.is_file() and old_page.read_bytes() == page:
                recorded = self.recorded_png(source, period, key)
                if recorded and recorded == (sha256(old_png.read_bytes()), SCREENSHOT_SCALE):
                    return old_png.read_bytes()
        if not self.screenshots:
            return None
        if self.active is None:
            try:
                self.active = self.screenshotter().__enter__()
            except Exception as error:
                raise ParseError("證據完整", f"Chromium 無法啟動：{type(error).__name__}: {error}") from error
        try:
            png, _, text = self.active.capture(self.filings.raw(filing), items)
        except Exception as error:
            raise ParseError("證據完整", f"{key} 截圖失敗：{type(error).__name__}: {error}") from error
        if text != locator.table_text(index):
            raise ParseError("證據完整", f"{key}：瀏覽器截到的表格與原文表格 #{index} 文字不同")
        return png

    def recorded_png(self, series: str, period: str, key: str) -> tuple[str, int] | None:
        path = self.reuse / series / period / "revenue.json"
        if not path.exists():
            return None
        for operand in JsonCodec.read(path)["operands"].values():
            if operand["evidence"]["table"] == key:
                return operand["evidence"]["png_sha256"], operand["evidence"].get("png_scale")
        return None

    # ---- 寫入 ----

    def write_period(self, series: str, period: str, output: dict, files: dict[str, bytes]):
        directory = self.out / series
        directory.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".staging-{period}-", dir=directory))
        try:
            (staging / "evidence").mkdir()
            for name, body in files.items():
                (staging / "evidence" / name).write_bytes(body)
            JsonCodec.write(staging / "revenue.json", output)
            final = directory / period
            retired = None
            if final.exists():
                retired = directory / f".retired-{period}-{secrets.token_hex(4)}"
                final.rename(retired)
            try:
                staging.rename(final)
            except BaseException:
                # 換上新輸出失敗時還原舊輸出，不留下缺期別的狀態。
                if retired is not None and not final.exists():
                    retired.rename(final)
                raise
            if retired is not None:
                shutil.rmtree(retired, ignore_errors=True)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def read_status(self) -> dict:
        path = self.out / "status.json"
        status = JsonCodec.read(path) if path.exists() else {}
        status.update(ticker=self.spec.ticker, view=self.spec.view)
        periods = status.get("periods", {})
        status["periods"] = {series: dict(periods.get(series, {})) for series in SERIES}
        return status

    def write_status(self, status: dict):
        """status.json 列出兩個序列每個處理過的期別，並以目前的已上線輸出重建差異標記（`differences`）。

        已上線輸出在 status.json 沒有紀錄時（例如紀錄被手動刪除），由輸出補上紀錄，標記不會因此遺漏。
        """
        published = self.published(self.out)
        for (series, period), output in published.items():
            status["periods"][series].setdefault(period, self.entry(output))
        markers, errors = self.differences(published)
        for series, entries in status["periods"].items():
            for period, entry in entries.items():
                entry.pop("differences", None)
                if (series, period) in markers:
                    entry["differences"] = markers[(series, period)]
        status.pop("comparison_errors", None)
        if errors:
            status["comparison_errors"] = errors
        status["parser"] = self.parser_info
        self.out.mkdir(parents=True, exist_ok=True)
        JsonCodec.write(self.out / "status.json", status)

    def differences(self, published: dict[tuple[str, str], dict]) -> tuple[dict[tuple[str, str], list[dict]], list[dict]]:
        """每份已下載的申報（依申報日順序），與它申報當時看得到的已上線輸出做比較欄比對，以目前的已上線值計算。

        回傳（期別 → 差異標記, 無法讀取的申報）。比對使用申報期別生效的規格定義。
        """
        markers: dict[tuple[str, str], list[dict]] = {}
        errors = []
        for filing in self.filings.filings:
            baselines = self.visible(published, filing.filing_date)
            if not baselines:
                continue
            try:
                document = self.filings.document(filing)
            except ParseError as error:
                errors.append({"accession": filing.accession, "check": error.check, "reason": error.message})
                continue
            for item in comparatives(document, filing.accession, baselines, self.selector_for(filing.report_date)):
                if item["result"] not in MARKED_RESULTS:
                    continue
                markers.setdefault((item["series"], item["period_end"]), []).append(
                    {
                        "category": item["category"],
                        "operand": item["operand"],
                        "role": item["role"],
                        "period": item["period"],
                        "result": item["result"],
                        "published_value": item["published_value"],
                        "listed_value": item["listed_value"],
                        "source": {
                            "accession": filing.accession,
                            "form": filing.form,
                            "filing_date": filing.filing_date,
                            "fact_id": item["listed_fact_id"],
                        },
                        **({"note": item["note"]} if item.get("note") else {}),
                    }
                )
        return markers, errors


def check_outputs(
    data: Path,
    committed_root: Path,
    spec: CompanySpec,
    spec_sha256: str,
    periods: list[str] | None,
    start=None,
    end=None,
    progress=None,
    default_start: str = DEFAULT_START,
) -> tuple[dict, list[str]]:
    """`--check`：在已提交輸出的副本上照一般 parse 執行（不啟動 Chromium），再與已提交的輸出比對。

    一般 parse 不會改動任何檔案、也不會改變 status.json 時才算一致。
    """
    committed = ticker_dir(committed_root, spec.ticker)
    with tempfile.TemporaryDirectory() as temp:
        if committed.exists():
            shutil.copytree(committed, ticker_dir(Path(temp), spec.ticker))
        parser = RevenueParser(data, Path(temp), spec, spec_sha256, screenshots=False, progress=progress, default_start=default_start)
        if periods is None:
            status = committed / "status.json"
            if status.exists() and not (start or end):
                periods = sorted({p for entries in JsonCodec.read(status)["periods"].values() for p in entries})
            else:
                periods = parser.periods(start, end)
        report = parser.run(periods)
        return report, compare_outputs(committed, ticker_dir(Path(temp), spec.ticker), periods)


def compare_outputs(expected_dir: Path, actual_dir: Path, periods: list[str]) -> list[str]:
    """已提交的輸出（expected）與重跑結果（actual）逐欄比對，兩個序列都比。

    - revenue.json 逐欄比對；`parser` 欄位與 PNG hash、倍率不比（引擎重構或不同機器的字型會改變它們）。
    - status.json 中這些期別的紀錄逐欄比對（含失敗原因、差異標記、stale_fields），`published_output_kept` 除外；
      頂層的 `comparison_errors` 也比對。
    - 證據 HTML 比對 bytes；證據目錄中沒有被 revenue.json 引用的檔案列為差異。
    - 已提交的 PNG 核對檔案 hash 與 revenue.json 的紀錄一致。
    """
    differences = []
    documents = []
    for directory in (expected_dir, actual_dir):
        path = directory / "status.json"
        documents.append(JsonCodec.read(path) if path.exists() else {})
    statuses = [d.get("periods", {}) for d in documents]
    differences += [f"status.{d}" for d in diff(*(d.get("comparison_errors", []) for d in documents), "comparison_errors")]
    for series in SERIES:
        for period in periods:
            where = f"{series} {period}"
            expected_entry, actual_entry = (dict(s.get(series, {}).get(period, {})) for s in statuses)
            for entry in (expected_entry, actual_entry):
                entry.pop("published_output_kept", None)
            differences += [f"{where}: status.{d}" for d in diff(expected_entry, actual_entry)]
            expected_path, actual_path = expected_dir / series / period / "revenue.json", actual_dir / series / period / "revenue.json"
            if not expected_path.exists() and not actual_path.exists():
                continue
            if not expected_path.exists() or not actual_path.exists():
                differences.append(f"{where}: 已提交 {expected_path.exists()}，重跑 {actual_path.exists()}")
                continue
            expected, actual = JsonCodec.read(expected_path), JsonCodec.read(actual_path)
            for output in (expected, actual):
                output.pop("parser", None)
                for operand in output.get("operands", {}).values():
                    operand.get("evidence", {}).pop("png_sha256", None)
                    operand.get("evidence", {}).pop("png_scale", None)
            differences += [f"{where}: {d}" for d in diff(expected, actual)]
            evidence = expected_dir / series / period / "evidence"
            for page in sorted((actual_dir / series / period / "evidence").glob("*.html")):
                committed = evidence / page.name
                if not committed.exists() or committed.read_bytes() != page.read_bytes():
                    differences.append(f"{where}: 證據 {page.name} 與已提交的不同")
            recorded = JsonCodec.read(expected_path)["operands"]
            referenced = {f"{o['evidence']['table']}.{kind}" for o in recorded.values() for kind in ("html", "png")}
            for extra in sorted(evidence.glob("*")):
                if extra.name not in referenced:
                    differences.append(f"{where}: 證據目錄中的 {extra.name} 沒有被 revenue.json 引用")
            for operand_id, operand in recorded.items():
                png = evidence / f"{operand['evidence']['table']}.png"
                if not png.is_file() or sha256(png.read_bytes()) != operand["evidence"]["png_sha256"]:
                    differences.append(f"{where}: {operand_id} 的 PNG 缺少或 hash 與紀錄不符")
    return differences


def diff(expected, actual, path: str = "") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        found = []
        for key in sorted(set(expected) | set(actual)):
            where = f"{path}.{key}" if path else str(key)
            if key not in expected:
                found.append(f"{where} 多出")
            elif key not in actual:
                found.append(f"{where} 缺少")
            else:
                found += diff(expected[key], actual[key], where)
        return found
    if isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual):
        return [d for i, (e, a) in enumerate(zip(expected, actual)) for d in diff(e, a, f"{path}[{i}]")]
    return [] if expected == actual else [f"{path}: 已提交 {json.dumps(expected, ensure_ascii=False)}，重跑 {json.dumps(actual, ensure_ascii=False)}"]


def published_differences(existing: dict, new: dict) -> dict:
    """重算結果與已上線輸出的差異：分類數值、總營收，以及數值依據欄位是否改變與原因。"""
    categories = []
    for name in sorted(set(existing["categories"]) | set(new["categories"])):
        old = existing["categories"].get(name, {}).get("value")
        value = new["categories"].get(name, {}).get("value")
        if old != value:
            categories.append({"category": name, "published": old, "new": value})
    if existing["total"]["value"] != new["total"]["value"]:
        categories.append({"category": "總營收", "published": existing["total"]["value"], "new": new["total"]["value"]})
    # parser 記錄的是產生這份輸出的引擎與規格版本；內容相同時不同版本不算差異。
    fields = sorted(k for k in set(existing) | set(new) if k != "parser" and existing.get(k) != new.get(k))
    values = [f for f in fields if f in VALUE_FIELDS]
    if values == ["operands"] and without_evidence(existing["operands"]) == without_evidence(new["operands"]):
        fields[fields.index("operands")] = "operands.evidence"
        values = []
    old_primary, new_primary = existing["filings"]["primary"], new["filings"]["primary"]
    if new_primary["accession"] != old_primary["accession"]:
        reason = f"選用的申報由 {old_primary['accession']} 改為 {new_primary['accession']}"
    elif values:
        reason = "規則或原文變更"
    else:
        reason = "只有中繼資料更新：" + "、".join(fields)
    return {
        "reason": reason,
        "categories": categories,
        "fields": fields,
        "value_changed": bool(values),
    }


def without_evidence(operands: dict) -> dict:
    return {k: {f: v for f, v in o.items() if f != "evidence"} for k, o in operands.items()}
