"""Parser 引擎：一家公司逐期組合數值、結構檢核、證據、跨期檢核，寫入正式輸出與 status.json。

正式輸出在 `data/revenue/<首字母>/<TICKER>/`。每期先寫暫存目錄，完成後整組換上。

- 結構檢核不通過或任何例外：不寫入，已上線的該期輸出保留不動，status.json 記錄失敗原因。
- 已上線期別不會被一般 parse 改動。重算結果與已上線輸出不同時，status.json 記錄差異並標示待 review；
  由人決定後以 `republish` 指定該期才覆寫，覆寫時 revenue.json 記錄原值與原因。
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
from .compose import Operand, PeriodComposer, PeriodResult
from .filings import FilingSet, ParseError
from .review import compare_fact, cross_period, restatements
from .spec import CompanySpec

SCHEMA_VERSION = 1
SCREENSHOT_SCALE = 1
PERIOD_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# 輸出中描述數值與其依據的欄位；這些不同代表數值或來源改變。其餘欄位（檢核紀錄、parser、運算元的證據 hash）
# 不同只是中繼資料。
VALUE_FIELDS = ("categories", "total", "reconciling", "operands", "filings", "fiscal_year", "fiscal_quarter", "view")
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
    """`out` 是寫入的正式輸出根目錄；`baseline` 是跨期比較讀取的已上線輸出（一般與 `out` 相同）。

    `screenshots=False` 時不啟動 Chromium，PNG 沿用 baseline 中已提交的檔案（供 `--check` 使用）。
    """

    def __init__(
        self,
        data: Path,
        out: Path,
        spec: CompanySpec,
        spec_sha256: str,
        baseline: Path | None = None,
        screenshots: bool = True,
        republish: set[str] | frozenset[str] = frozenset(),
        progress: Callable[[dict], None] | None = None,
        screenshotter: Callable[[], TableScreenshotter] | None = None,
    ):
        self.spec = spec
        self.out = ticker_dir(out, spec.ticker)
        self.baseline = ticker_dir(baseline or out, spec.ticker)
        self.filings = FilingSet(data, spec.ticker)
        self.composer = PeriodComposer(spec, self.filings)
        self.screenshots = screenshots
        self.republish = set(republish)
        self.progress = progress
        self.screenshotter = screenshotter or (lambda: TableScreenshotter(device_scale=SCREENSHOT_SCALE))
        self.active = None
        self.parser_info = {"spec_sha256": spec_sha256, "engine_sha256": engine_sha256()}

    # ---- 期別與 baseline ----

    def periods(self, start: str | None = None, end: str | None = None) -> list[str]:
        return [p for p in self.filings.periods() if (not start or p >= start) and (not end or p <= end)]

    @staticmethod
    def published(root: Path) -> dict[str, dict]:
        """已上線輸出：只讀以期末日命名的目錄，暫存或殘留目錄不算。"""
        found = {}
        if root.exists():
            for path in sorted(root.glob("*/revenue.json")):
                if PERIOD_RE.fullmatch(path.parent.name):
                    found[path.parent.name] = JsonCodec.read(path)
        return found

    def recover(self) -> list[str]:
        """清理中斷的寫入：`.staging-*` 直接刪除；`.retired-<期別>-*` 在該期目錄不存在時還原，否則刪除。"""
        notes = []
        if not self.out.exists():
            return notes
        for path in sorted(self.out.iterdir()):
            if path.name.startswith(".staging-"):
                shutil.rmtree(path)
                notes.append(f"刪除中斷寫入的暫存目錄 {path.name}")
            elif path.name.startswith(".retired-"):
                period = path.name[len(".retired-") : len(".retired-") + 10]
                final = self.out / period
                if PERIOD_RE.fullmatch(period) and not final.exists():
                    path.rename(final)
                    notes.append(f"還原 {period} 的已上線輸出（{path.name}）")
                else:
                    shutil.rmtree(path)
                    notes.append(f"刪除已被取代的舊輸出 {path.name}")
        return notes

    # ---- 執行 ----

    def run(self, periods: list[str]) -> dict:
        report = {"ticker": self.spec.ticker, "periods": [], "complete": True}
        recovered = self.recover()
        if recovered:
            report["recovered"] = recovered
        status = self.read_status()
        try:
            for period in periods:
                try:
                    entry = self.parse_period(period)
                except Exception as error:
                    # 單期的任何錯誤都記為該期失敗，繼續處理下一期。
                    entry = self.failed(period, "例外", f"{type(error).__name__}: {error}")
                status["periods"][period] = entry
                report["periods"].append({"period_end": period, **entry})
                report["complete"] &= entry["status"] != "failed"
                if self.progress:
                    self.progress({"ticker": self.spec.ticker, "period": period, "status": entry["status"]})
        finally:
            if self.active is not None:
                try:
                    self.active.__exit__(None, None, None)
                finally:
                    self.active = None
            self.write_status(status)
        return report

    def failed(self, period: str, check: str, reason: str) -> dict:
        return {
            "status": "failed",
            "check": check,
            "reason": reason,
            "published_output_kept": (self.out / period / "revenue.json").exists(),
        }

    def parse_period(self, period: str) -> dict:
        try:
            result = self.composer.compose(period)
            baselines = {p: o for p, o in self.published(self.baseline).items() if p < period}
            output, files = self.build(result, baselines)
        except ParseError as error:
            return self.failed(period, error.check, error.message)
        existing_path = self.out / period / "revenue.json"
        if existing_path.exists():
            existing = JsonCodec.read(existing_path)
            if "republished" in existing:
                output["republished"] = existing["republished"]
            if output != existing:
                changes = published_differences(existing, output)
                if period not in self.republish:
                    return self.unchanged_entry(existing, output, changes)
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
        self.write_period(period, output, files)
        return self.entry(output)

    @staticmethod
    def entry(output: dict) -> dict:
        return {
            "status": "review_pending" if output["review"]["status"] == "pending" else "published",
            "fiscal_year": output["fiscal_year"],
            "fiscal_quarter": output["fiscal_quarter"],
            "accession": output["filings"]["primary"]["accession"],
            **({"review_reasons": output["review"]["reasons"]} if output["review"]["reasons"] else {}),
        }

    def unchanged_entry(self, existing: dict, output: dict, changes: dict) -> dict:
        """已上線輸出不改。數值或依據不同時標示待 review；只有中繼資料不同時記錄 `stale_fields`。

        跨期檢核以目前已上線的資料重算（例如之後補上更早的期別，才有去年同季可比）；
        重算出已上線輸出沒有的 review 原因時，該期在 status.json 標示待 review。
        """
        entry = self.entry(existing)
        if changes["value_changed"]:
            entry["status"] = "review_pending"
            entry["differs_from_published"] = changes
            entry["review_reasons"] = entry.get("review_reasons", []) + [
                f"重算結果與已上線輸出不同（{changes['reason']}）；確認後以 --republish {self.spec.ticker} {existing['period_end']} 覆寫"
            ]
        else:
            entry["stale_fields"] = changes["fields"]
        added = [r for r in output["review"]["reasons"] if r not in existing["review"]["reasons"]]
        if added:
            entry["status"] = "review_pending"
            entry["review_reasons"] = entry.get("review_reasons", []) + [f"重算跨期檢核：{r}" for r in added]
        return entry

    # ---- 輸出內容 ----

    def build(self, result: PeriodResult, baselines: dict[str, dict]) -> tuple[dict, dict[str, bytes]]:
        operands = result.operands
        for number, operand in enumerate(operands, 1):
            operand.id = f"op{number}"
        evidence, files = self.evidence(result, operands)
        output = {
            "schema_version": SCHEMA_VERSION,
            "ticker": self.spec.ticker,
            "view": self.spec.view,
            "period_end": result.period_end,
            "fiscal_year": result.fiscal_year,
            "fiscal_quarter": result.fiscal_quarter,
            "unit": "USD",
            "filings": self.filing_records(result),
            "categories": self.lines(result, "category"),
            "total": self.lines(result, "total")[self.spec.total.name],
            "operands": {op.id: self.operand_record(op, evidence[op.id]) for op in operands},
            "checks": {
                "structural": result.structural + [{"check": "證據完整", "result": "pass"}],
                "sum": result.sum_check,
            },
            "parser": self.parser_info,
        }
        if self.spec.reconciling:
            output["reconciling"] = self.lines(result, "reconciling")
        cross = cross_period(output, baselines, self.spec.thresholds)
        restated = [
            {"kind": "comparative", **r}
            for r in restatements(self.filings.document(result.primary), result.primary.accession, baselines)
        ] + self.amendment_changes(result, output)
        output["checks"]["cross_period"] = cross
        output["checks"]["restatements"] = restated
        reasons = [self.reason(c) for c in cross if c["flagged"]] + [
            f"重編：{r['period_end']} {r['operand']} 原為 {r['published_value']}（{r['published_accession']}），"
            f"{r['source_accession']} 為 {r['restated_value']}" + (f"；{r['note']}" if r.get("note") else "")
            for r in restated
        ]
        output["review"] = {"status": "pending" if reasons else "none", "reasons": reasons}
        return output, files

    def amendment_changes(self, result: PeriodResult, output: dict) -> list[dict]:
        """主申報是修正申報時，逐一比對運算元與原申報中同一 fact；不同、無法比較或原申報沒有時記為重編。"""
        if result.replaced is None:
            return []
        original = self.filings.document(result.replaced)
        amended = {f.fact_id: f for f in self.filings.document(result.primary).facts}
        found = []
        for operand_id, operand in output["operands"].items():
            if operand["accession"] != result.primary.accession:
                continue
            new = amended[operand["fact_id"]]
            matches = original.matching(new.concept, new.dimensions, new.start, new.end)
            entry = {
                "kind": "amendment",
                "period_end": result.period_end,
                "operand": operand_id,
                "concept": new.concept,
                "dimensions": dict(new.dimensions),
                "published_accession": result.replaced.accession,
                "source_accession": result.primary.accession,
                "restated_fact_id": new.fact_id,
                "restated_value": new.value,
            }
            if not matches:
                found.append({**entry, "published_value": None, "note": "原申報沒有此 fact"})
                continue
            old = matches[0]
            if old.value is None or old.error_bound() is None:
                found.append({**entry, "published_value": None, "note": f"原申報的 fact 無法比較：{old.value_error or '缺 decimals'}"})
            elif abs(new.value - old.value) > old.error_bound() + new.error_bound():
                found.append({**entry, "published_value": old.value})
        return found

    @staticmethod
    def reason(check: dict) -> str:
        if check["check"] == "分類集合":
            return f"分類集合與 {check['baseline_period']} 不同：新增 {check.get('added')}，移除 {check.get('removed')}"
        if check["check"] == "占比變動" and "change_pp" in check:
            return f"{check['category']} 占比較去年同季 {check['baseline_period']} 變動 {check['change_pp']} 個百分點"
        if check["check"] == "YoY" and check.get("change") is not None:
            return f"{check['category']} YoY {check['change']}，超過 ±{check['threshold']}"
        return f"{check['check']}{(' ' + check['category']) if check.get('category') else ''}：{check.get('note', '異常')}"

    @staticmethod
    def filing_records(result: PeriodResult) -> dict:
        records = {"primary": result.primary.describe()}
        if result.replaced:
            records["primary"]["replaces"] = result.replaced.describe()
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
            png = self.png(result.period_end, key, page, filing, items, locator, index)
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

    def png(self, period, key, page, filing, items, locator, index) -> bytes | None:
        """HTML 與已提交的相同、PNG hash 與截圖倍率都相符時沿用舊 PNG；`screenshots=False` 時只沿用、不截圖。"""
        committed = self.baseline / period / "evidence"
        old_page, old_png = committed / f"{key}.html", committed / f"{key}.png"
        if old_page.is_file() and old_png.is_file() and old_page.read_bytes() == page:
            recorded = self.recorded_png(period, key)
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

    def recorded_png(self, period: str, key: str) -> tuple[str, int] | None:
        path = self.baseline / period / "revenue.json"
        if not path.exists():
            return None
        for operand in JsonCodec.read(path)["operands"].values():
            if operand["evidence"]["table"] == key:
                return operand["evidence"]["png_sha256"], operand["evidence"].get("png_scale")
        return None

    # ---- 寫入 ----

    def write_period(self, period: str, output: dict, files: dict[str, bytes]):
        self.out.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".staging-{period}-", dir=self.out))
        try:
            (staging / "evidence").mkdir()
            for name, body in files.items():
                (staging / "evidence" / name).write_bytes(body)
            JsonCodec.write(staging / "revenue.json", output)
            final = self.out / period
            retired = None
            if final.exists():
                retired = self.out / f".retired-{period}-{secrets.token_hex(4)}"
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
        status.setdefault("periods", {})
        return status

    def write_status(self, status: dict):
        """status.json 列出每個處理過的期別；被較新申報重編的期別另記 `restated_by`。"""
        restated_by = {}
        for period, output in self.published(self.out).items():
            for item in output["checks"].get("restatements", []):
                if item.get("kind") == "comparative":
                    restated_by.setdefault(item["period_end"], set()).add(period)
        for period, entry in status["periods"].items():
            entry.pop("restated_by", None)
            if period in restated_by:
                entry["restated_by"] = sorted(restated_by[period])
        status["parser"] = self.parser_info
        self.out.mkdir(parents=True, exist_ok=True)
        JsonCodec.write(self.out / "status.json", status)


def check_outputs(
    data: Path, committed_root: Path, spec: CompanySpec, spec_sha256: str, periods: list[str] | None, start=None, end=None, progress=None
) -> tuple[dict, list[str]]:
    """`--check`：在已提交輸出的副本上照一般 parse 執行（不啟動 Chromium），再與已提交的輸出比對。

    一般 parse 不會改動任何檔案、也不會改變 status.json 時才算一致。
    """
    committed = ticker_dir(committed_root, spec.ticker)
    with tempfile.TemporaryDirectory() as temp:
        if committed.exists():
            shutil.copytree(committed, ticker_dir(Path(temp), spec.ticker))
        parser = RevenueParser(data, Path(temp), spec, spec_sha256, screenshots=False, progress=progress)
        if periods is None:
            status = committed / "status.json"
            periods = sorted(JsonCodec.read(status)["periods"]) if status.exists() and not (start or end) else parser.periods(start, end)
        report = parser.run(periods)
        return report, compare_outputs(committed, ticker_dir(Path(temp), spec.ticker), periods)


def compare_outputs(expected_dir: Path, actual_dir: Path, periods: list[str]) -> list[str]:
    """已提交的輸出（expected）與重跑結果（actual）逐欄比對。

    - revenue.json 逐欄比對；`parser` 欄位與 PNG hash、倍率不比（引擎重構或不同機器的字型會改變它們）。
    - status.json 中這些期別的紀錄逐欄比對（含失敗原因、review、restated_by、stale_fields），`published_output_kept` 除外。
    - 證據 HTML 比對 bytes；證據目錄中沒有被 revenue.json 引用的檔案列為差異。
    - 已提交的 PNG 核對檔案 hash 與 revenue.json 的紀錄一致。
    """
    differences = []
    statuses = []
    for directory in (expected_dir, actual_dir):
        path = directory / "status.json"
        statuses.append(JsonCodec.read(path)["periods"] if path.exists() else {})
    for period in periods:
        expected_entry, actual_entry = (dict(s.get(period, {})) for s in statuses)
        for entry in (expected_entry, actual_entry):
            entry.pop("published_output_kept", None)
        differences += [f"{period}: status.{d}" for d in diff(expected_entry, actual_entry)]
        expected_path, actual_path = expected_dir / period / "revenue.json", actual_dir / period / "revenue.json"
        if not expected_path.exists() and not actual_path.exists():
            continue
        if not expected_path.exists() or not actual_path.exists():
            differences.append(f"{period}: 已提交 {expected_path.exists()}，重跑 {actual_path.exists()}")
            continue
        expected, actual = JsonCodec.read(expected_path), JsonCodec.read(actual_path)
        for output in (expected, actual):
            output.pop("parser", None)
            for operand in output.get("operands", {}).values():
                operand.get("evidence", {}).pop("png_sha256", None)
                operand.get("evidence", {}).pop("png_scale", None)
        differences += [f"{period}: {d}" for d in diff(expected, actual)]
        for page in sorted((actual_dir / period / "evidence").glob("*.html")):
            committed = expected_dir / period / "evidence" / page.name
            if not committed.exists() or committed.read_bytes() != page.read_bytes():
                differences.append(f"{period}: 證據 {page.name} 與已提交的不同")
        recorded = JsonCodec.read(expected_path)["operands"]
        referenced = {f"{o['evidence']['table']}.{kind}" for o in recorded.values() for kind in ("html", "png")}
        for extra in sorted((expected_dir / period / "evidence").glob("*")):
            if extra.name not in referenced:
                differences.append(f"{period}: 證據目錄中的 {extra.name} 沒有被 revenue.json 引用")
        for operand_id, operand in recorded.items():
            png = expected_dir / period / "evidence" / f"{operand['evidence']['table']}.png"
            if not png.is_file() or sha256(png.read_bytes()) != operand["evidence"]["png_sha256"]:
                differences.append(f"{period}: {operand_id} 的 PNG 缺少或 hash 與紀錄不符")
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
    fields = sorted(k for k in set(existing) | set(new) if existing.get(k) != new.get(k))
    values = [f for f in fields if f in VALUE_FIELDS]
    if values == ["operands"] and without_evidence(existing["operands"]) == without_evidence(new["operands"]):
        fields[fields.index("operands")] = "operands.evidence"
        values = []
    old_primary, new_primary = existing["filings"]["primary"], new["filings"]["primary"]
    if new_primary["accession"] != old_primary["accession"]:
        reason = "修正申報取代原申報" if new_primary.get("replaces") else f"選用的申報由 {old_primary['accession']} 改為 {new_primary['accession']}"
    else:
        reason = "規則或原文變更"
    return {
        "reason": reason,
        "categories": categories,
        "fields": fields,
        "value_changed": bool(values),
    }


def without_evidence(operands: dict) -> dict:
    return {k: {f: v for f, v in o.items() if f != "evidence"} for k, o in operands.items()}
