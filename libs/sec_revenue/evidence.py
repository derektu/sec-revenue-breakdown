"""SEC 表格證據：由萃取輸出的每個 XBRL fact 回到 SEC 原文，抽出所在表格的 HTML 與截圖。

證據只讀資料根目錄內已下載的 SEC 原文與萃取輸出，不發網路請求，也不改萃取輸出；
結果寫在每期的 `outputs/<TICKER>/<period>/evidence/`，以 `evidence.json` 連回萃取輸出。
fact 不在 HTML 表格內或與運算元不符時只記錄狀態，不產生替代證據。
"""

from __future__ import annotations

import copy
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import html as html_text
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Callable

from lxml import html
from lxml.etree import LxmlError

from .engines import JsonCodec
from .workflow import PeriodSelection

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
# 截圖高度超過門檻時只保留表頭與標示列附近的列，並以裁切列標出略過的位置。
SCREENSHOT_MAX_HEIGHT = 3000
SCREENSHOT_MARGIN = 600
HEADER_ROWS = 4
VIEWPORT = {"width": 1000, "height": 1400}
DEVICE_SCALE = 2
SOURCE_PREFIX = 12
# 表格檔名：accession、來源文件 sha256 前綴與 parser 的表格編號。
FILE_NAME_RE = re.compile(r"\d{10}-\d{2}-\d{6}-[0-9a-f]{12}-t\d+\.(?:png|html)")
FAILED_FACT_STATUSES = {"fact_not_found", "fact_mismatch", "source_missing", "evidence_failed"}

REMOVED_TAGS = {
    "script", "style", "img", "link", "iframe", "object", "embed", "svg", "form", "input",
    "button", "base", "meta", "video", "audio", "source", "picture", "template", "frame",
    "frameset", "noscript", "math",
}
REMOVED_ATTRIBUTES = {
    "href", "src", "srcset", "action", "formaction", "background", "poster", "xlink:href",
    "data", "codebase", "cite", "longdesc", "usemap", "ping", "manifest", "id", "name",
}
# style 內出現可載入資源或跳脫字元時整個屬性移除，不嘗試局部清理。
UNSAFE_STYLE_RE = re.compile(r"url\s*\(|expression\s*\(|@import|\\", re.I)

HIGHLIGHT_CSS = """
.sec-evidence-cell { outline: 3px solid #d93025 !important; outline-offset: -2px;
  background: #fff1a8 !important; }
.sec-evidence-row > td { background-color: #fffbe3; }
.sec-evidence-badge { display: inline-block; min-width: 14px; margin-right: 4px; padding: 0 3px;
  border-radius: 8px; background: #d93025; color: #fff; text-align: center;
  font: 700 12px/16px system-ui, sans-serif; vertical-align: middle; }
.sec-evidence-cut > td { padding: 4px 0 !important; border-top: 2px dashed #d93025 !important;
  border-bottom: 2px dashed #d93025 !important; background: #fdecea !important; color: #a50e0e;
  text-align: center !important; font: 700 12px system-ui, sans-serif; }
"""

# 頁面 script 關閉；本段由 Playwright 的 evaluate 執行。先核對 fact 文字與整張表的文字，
# 再標示儲存格；長表把不需要的列收成裁切列。
HIGHLIGHT_SCRIPT = """
({items, css, maxHeight, margin, headerRows}) => {
  // 比對時去掉所有空白：lxml 以空白串接文字節點，瀏覽器的 textContent 直接相連。
  const clean = (text) => text.replace(/\\s+/g, '');
  let table = null;
  const found = [];
  for (const item of items) {
    const node = document.getElementById(item.id);
    if (!node) throw new Error('瀏覽器找不到 fact：' + item.id);
    if (node.localName.toLowerCase() !== 'ix:nonfraction')
      throw new Error('瀏覽器中的節點不是 ix:nonFraction：' + item.id);
    if (clean(node.textContent) !== clean(item.raw))
      throw new Error('瀏覽器中的 fact 文字與運算元不符：' + item.id);
    const owner = node.closest('table');
    if (!owner || (table && owner !== table)) throw new Error('fact 不在同一張表：' + item.id);
    table = owner;
    found.push([item, node]);
  }
  const text = clean(table.textContent);
  const style = document.createElement('style');
  style.textContent = css;
  (document.head || document.documentElement).append(style);
  const rows = new Set();
  for (const [item, node] of found) {
    const cell = node.closest('td,th') || node;
    cell.classList.add('sec-evidence-cell');
    const row = cell.closest('tr');
    if (row) { row.classList.add('sec-evidence-row'); rows.add(row); }
    const badge = document.createElement('span');
    badge.className = 'sec-evidence-badge';
    badge.textContent = item.badge;
    cell.prepend(badge);
  }
  table.setAttribute('data-sec-evidence-table', '1');
  const all = Array.from(table.rows);
  if (table.getBoundingClientRect().height <= maxHeight) return {text, cropped: false};
  const bands = Array.from(rows).map(r => {
    const box = r.getBoundingClientRect();
    return [box.top - margin, box.bottom + margin];
  });
  const keep = all.map((row, i) => {
    if (i < headerRows) return true;
    const box = row.getBoundingClientRect();
    return bands.some(([top, bottom]) => box.bottom >= top && box.top <= bottom);
  });
  const columns = Math.max(1, ...all.map(r => Array.from(r.cells).reduce((n, c) => n + (c.colSpan || 1), 0)));
  let hidden = 0, run = [];
  const flush = () => {
    if (!run.length) return;
    const marker = document.createElement('tr');
    marker.className = 'sec-evidence-cut';
    const cell = document.createElement('td');
    cell.colSpan = columns;
    cell.textContent = '✂ 已裁切：略過 ' + run.length + ' 列';
    marker.append(cell);
    run[0].before(marker);
    for (const row of run) row.style.display = 'none';
    hidden += run.length;
    run = [];
  };
  all.forEach((row, i) => { if (keep[i]) flush(); else run.push(row); });
  flush();
  return {text, cropped: hidden > 0};
}
"""


def badge(number: int) -> str:
    return CIRCLED[number - 1] if number <= len(CIRCLED) else f"({number})"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def clean_text(text: str) -> str:
    return " ".join(text.split())


def playwright_version() -> str:
    """截圖所用的 Playwright 版本；它決定 Chromium 版本，因此列入證據快取鍵。"""
    try:
        return importlib.metadata.version("playwright")
    except importlib.metadata.PackageNotFoundError:
        return "not_installed"


def duration_label(fact: dict) -> str:
    """以 context 起迄日標示期間長度；只描述日期，不推斷公司財年名稱。"""
    if not fact.get("startdate") or not fact.get("enddate"):
        return "時點"
    days = (dt.date.fromisoformat(fact["enddate"]) - dt.date.fromisoformat(fact["startdate"])).days + 1
    for low, high, label in ((70, 120, "3M"), (160, 200, "6M"), (250, 300, "9M"), (350, 380, "年度")):
        if low <= days <= high:
            return label
    return f"{days} 天"


def expression_terms(operand: dict, weight: int = 1, role: str = "direct") -> list[tuple[int, str, dict]]:
    """把運算元展開成 SEC fact 葉節點：Q4 推算為 +年度 −九個月，多表加總為各項相加。"""
    if operand.get("derivation") == "annual_minus_nine_months":
        return expression_terms(operand["annual_evidence"], weight, "annual") + expression_terms(
            operand["nine_month_evidence"], -weight, "nine_month"
        )
    if operand.get("aggregation_evidence"):
        return [
            term
            for child in operand["aggregation_evidence"]
            for term in expression_terms(child, weight, "aggregation")
        ]
    return [(weight, role, operand)]


def fact_key(fact: dict) -> str:
    """fact id 只在單一文件內唯一；鍵包含來源文件 sha256 前綴，同一申報包的多份 inline 文件不會互相混淆。"""
    source = (fact.get("source_artifact_sha256") or "")[:SOURCE_PREFIX]
    return f"{fact.get('accession')}:{source}#{fact.get('fact_id')}"


def table_key(fact: dict, index: int) -> str:
    return f"{fact['accession']}-{fact['source_artifact_sha256'][:SOURCE_PREFIX]}-t{index}"


def fact_value(node, raw: str) -> int | None:
    """依 parser 的規則由 `ix:nonFraction` 的文字、scale 與 sign 算出整數美元；無法解析時回傳 None。"""
    transform = node.get("format", "").split(":")[-1].lower()
    cleaned = raw.replace(",", "").replace(" ", "").replace("−", "-")
    if transform in ("fixed-zero", "zerodash"):
        cleaned = "0"
    try:
        value = Decimal(cleaned) * Decimal(10) ** int(node.get("scale", "0"))
    except (InvalidOperation, ValueError):
        return None
    if node.get("sign") == "-":
        value = -value
    return int(value) if value == value.to_integral_value() else None


class TableLocator:
    """以 fact id 在 SEC 原文找 `ix:nonFraction` 與所在表格；表格編號與萃取 parser 的編號方式相同。"""

    def __init__(self, raw: bytes):
        self.root = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
        self.tables = list(self.root.iter("table"))
        self.index = {id(table): i for i, table in enumerate(self.tables)}

    def node(self, fact_id: str):
        found = self.root.xpath("//*[@id=$id]", id=fact_id) if fact_id else []
        return found[0] if len(found) == 1 else None

    def locate(self, fact_id: str) -> tuple[str, int | None]:
        node = self.node(fact_id)
        if node is None:
            return "fact_not_found", None
        table = next((a for a in node.iterancestors() if a.tag == "table"), None)
        if table is None:
            return "not_in_table", None
        return "in_table", self.index[id(table)]

    def verify(self, leaf: dict) -> str | None:
        """核對原文節點與運算元是同一個 fact；回傳不符的原因，相符時回傳 None。"""
        node = self.node(leaf["fact_id"])
        if str(node.tag).split(":")[-1].lower() != "nonfraction":
            return f"節點 {node.tag} 不是 ix:nonFraction"
        raw = clean_text(" ".join(node.itertext()))
        checks = [
            ("name", node.get("name"), leaf.get("concept")),
            ("contextref", node.get("contextref"), leaf.get("context_id")),
            ("scale", node.get("scale", "0"), leaf.get("scale")),
            ("顯示文字", raw, leaf.get("raw")),
            ("數值", fact_value(node, raw), leaf.get("value")),
        ]
        for name, found, expected in checks:
            if found != expected:
                return f"{name} 不符：原文 {found!r}，運算元 {expected!r}"
        return None

    def table_text(self, table_index: int) -> str:
        """去掉所有空白的表格文字，用來和瀏覽器中的同一張表比對。"""
        return "".join("".join(self.tables[table_index].itertext()).split())

    def table_html(self, table_index: int, items: list[dict], header: dict) -> bytes:
        """抽出單一表格成獨立 HTML：標示引用的儲存格，移除 script、圖片、外部連結與 XBRL 標籤。"""
        table = copy.deepcopy(self.tables[table_index])
        for item in items:
            found = table.xpath(".//*[@id=$id]", id=item["id"])
            if len(found) != 1:
                raise ValueError("表格內找不到 fact：" + item["id"])
            if clean_text(" ".join(found[0].itertext())) != item["raw"]:
                raise ValueError("表格內 fact 文字與運算元不符：" + item["id"])
            cell = next((a for a in [found[0], *found[0].iterancestors()] if a.tag in ("td", "th")), found[0])
            cell.set("class", (cell.get("class", "") + " sec-evidence-cell").strip())
            row = next((a for a in cell.iterancestors() if a.tag == "tr"), None)
            if row is not None:
                row.set("class", (row.get("class", "") + " sec-evidence-row").strip())
            mark = html.Element("span")
            mark.set("class", "sec-evidence-badge")
            mark.text = item["badge"]
            mark.tail = cell.text
            cell.text = None
            cell.insert(0, mark)
            found[0].set("data-fact-id", item["id"])
        self.sanitize(table)
        body = html.tostring(table, encoding="unicode")
        legend = "".join(
            f"<li><span class=\"sec-evidence-badge\">{html_text.escape(i['badge'])}</span>"
            f"{html_text.escape(i['label'])}</li>"
            for i in items
        )
        meta = html_text.escape(
            f"{header['ticker']} · {header['form']} · accession {header['accession']} · 表格 #{table_index}"
        )
        url = html_text.escape(header["source_url"])
        document = f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>{meta}</title>
<style>body {{ margin: 16px; font: 13px system-ui, sans-serif; color: #182332; }}
header {{ margin-bottom: 12px; }} ul {{ padding-left: 0; list-style: none; }} li {{ margin: 2px 0; }}
{HIGHLIGHT_CSS}</style></head>
<body><header><div>{meta}</div><div>SEC 原文：{url}</div>
<div>本檔由本機快取的 SEC 原文抽出單一表格；移除 script、圖片與外部資源，標示的儲存格是萃取用到的 XBRL fact。</div>
<ul>{legend}</ul></header>
{body}
</body></html>
"""
        return document.encode()

    @staticmethod
    def sanitize(table):
        for element in list(table.iter()):
            if not isinstance(element.tag, str):
                element.drop_tree()
                continue
            tag = element.tag.lower()
            if tag in REMOVED_TAGS:
                element.drop_tree()
                continue
            if ":" in tag or tag == "a":
                fact_id = element.get("data-fact-id")
                element.attrib.clear()
                element.tag = "span"
                if fact_id:
                    element.set("data-fact-id", fact_id)
                continue
            for name in list(element.attrib):
                lowered = name.lower()
                if lowered.startswith("on") or lowered in REMOVED_ATTRIBUTES:
                    del element.attrib[name]
            if UNSAFE_STYLE_RE.search(element.get("style", "")):
                del element.attrib["style"]


class TableScreenshotter:
    """headless Chromium 以離線、關閉頁面 script 的方式載入本機 SEC 原文，標示儲存格後對表格截圖。

    原文以 `set_content` 載入，沒有導覽請求；context 設為 offline，所有資源請求另由攔截器中止。
    """

    def __init__(self):
        self.playwright = None
        self.browser = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.launch(headless=True)
        except BaseException:
            self.playwright.stop()
            raise
        return self

    def __exit__(self, *_):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def capture(self, raw: bytes, items: list[dict]) -> tuple[bytes, bool, str]:
        """回傳 PNG、是否裁切，以及瀏覽器中整張表的文字（供呼叫端核對是同一張表）。"""
        context = self.browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=DEVICE_SCALE,
            service_workers="block",
            offline=True,
            java_script_enabled=False,
        )
        try:
            context.route("**/*", lambda route: route.abort())
            page = context.new_page()
            page.set_content(self.decode(raw), wait_until="load")
            result = page.evaluate(
                HIGHLIGHT_SCRIPT,
                {
                    "items": [{"id": i["id"], "badge": i["badge"], "raw": i["raw"]} for i in items],
                    "css": HIGHLIGHT_CSS,
                    "maxHeight": SCREENSHOT_MAX_HEIGHT,
                    "margin": SCREENSHOT_MARGIN,
                    "headerRows": HEADER_ROWS,
                },
            )
            png = page.locator("[data-sec-evidence-table]").screenshot(animations="disabled")
            return png, bool(result["cropped"]), result["text"]
        finally:
            context.close()

    @staticmethod
    def decode(raw: bytes) -> str:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("windows-1252", errors="replace")


class EvidenceWorkflow:
    """每期一份 `evidence.json`；萃取輸出、來源原文、SEC URL 與證據程式都沒變時跳過。

    每期先在暫存目錄寫好全部表格檔與 `evidence.json`，再整組換上；任何錯誤只讓該期標為失敗。
    """

    def __init__(
        self,
        data: Path,
        progress: Callable[[dict], None] | None = None,
        screenshotter: Callable[[], TableScreenshotter] = TableScreenshotter,
    ):
        self.root = data.resolve()
        self.progress = progress
        self.screenshotter = screenshotter
        self.active = None
        self.launch_error = None

    @staticmethod
    def rules_sha256() -> str:
        return sha256(Path(__file__).read_bytes())

    def read_verified(self, relative: str, expected: str) -> bytes:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("路徑超出資料目錄：" + relative)
        raw = path.read_bytes()
        if sha256(raw) != expected:
            raise ValueError("sha256 不符：" + relative)
        return raw

    def documents(self, ticker: str) -> dict[str, dict]:
        """SEC 原文索引：sha256 → 申報包中的文件紀錄（路徑、SEC URL、XBRL viewer URL）。"""
        path = self.root / "pipeline" / ticker / "packages.json"
        if not path.exists():
            raise ValueError(ticker + " 沒有 packages.json；請先執行 download")
        found = {}
        for package in JsonCodec.read(path)["packages"].values():
            for document in package["documents"].values():
                found.setdefault(document["sha256"], document)
        return found

    def shooter(self):
        """第一次需要截圖時才啟動 Chromium；啟動失敗後同一批不再重試。"""
        if self.active is None and self.launch_error is None:
            try:
                self.active = self.screenshotter().__enter__()
            except Exception as error:
                self.launch_error = f"Chromium 無法啟動：{type(error).__name__}: {error}"
        if self.launch_error:
            raise RuntimeError(self.launch_error)
        return self.active

    def run(self, tickers: list[str], selection: PeriodSelection, force: bool = False) -> dict:
        report = {"stage": "evidence", "companies": [], "complete": True}
        try:
            for ticker in tickers:
                extraction_path = self.root / "pipeline" / ticker / "extractions.json"
                if not extraction_path.exists():
                    raise ValueError(ticker + " 尚未萃取；請先執行 extract")
                extraction = JsonCodec.read(extraction_path)
                periods = selection.choose(
                    [
                        {"reportDate": p, "filingDate": "", "accessionNumber": ""}
                        for p, e in extraction["periods"].items()
                        if e["outputs"]
                    ]
                )
                if not periods:
                    raise ValueError(ticker + " 指定範圍沒有萃取輸出")
                documents = self.documents(ticker)
                company = {"ticker": ticker, "periods": []}
                for item in periods:
                    period = item["reportDate"]
                    status = self.period(ticker, period, extraction["periods"][period]["outputs"], documents, force)
                    report["complete"] &= status in ("complete", "cache_hit")
                    company["periods"].append({"period_end": period, "status": status})
                    if self.progress:
                        self.progress({"ticker": ticker, "period": period, "status": status})
                report["companies"].append(company)
        finally:
            if self.active is not None:
                self.active.__exit__(None, None, None)
                self.active = None
        return report

    def period(self, ticker, period, outputs, documents, force) -> str:
        rows = [(o, json.loads(self.read_verified(o["path"], o["sha256"]))) for o in outputs]
        key = self.cache_key(rows, documents)
        final = self.root / "outputs" / ticker / period / "evidence"
        previous_path = final / "evidence.json"
        try:
            previous = JsonCodec.read(previous_path) if previous_path.exists() else None
        except (OSError, ValueError):
            previous = None
        if (
            not force
            and previous
            and previous.get("cache_key") == key
            and previous.get("status") == "complete"
            and self.files_intact(previous)
        ):
            return "cache_hit"
        final.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".evidence-", dir=final.parent))
        try:
            try:
                evidence = self.build(ticker, period, rows, documents, key, staging)
            except Exception as error:
                # 未預期錯誤時不留下半套表格檔，整期只寫一份標明失敗原因的 evidence.json。
                shutil.rmtree(staging)
                staging.mkdir()
                evidence = self.failure(ticker, period, rows, key, f"{type(error).__name__}: {error}")
            JsonCodec.write(staging / "evidence.json", evidence)
            self.swap(staging, final)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return evidence["status"]

    @staticmethod
    def swap(staging: Path, final: Path):
        retired = None
        if final.exists():
            retired = Path(tempfile.mkdtemp(prefix=".evidence-old-", dir=final.parent))
            retired.rmdir()
            final.rename(retired)
        staging.rename(final)
        if retired is not None:
            shutil.rmtree(retired, ignore_errors=True)

    def cache_key(self, rows: list[tuple[dict, dict]], documents: dict) -> str:
        sources = {}
        for _, row in rows:
            for output in row["outputs"].values():
                for alternative in self.alternatives(output):
                    for operand in alternative["SEC_operands"]:
                        for _, _, leaf in expression_terms(operand):
                            source = leaf.get("source_artifact_sha256") or ""
                            document = documents.get(source, {})
                            sources[source] = {
                                k: document.get(k) for k in ("source_url", "ixviewer_url", "filing_index_url")
                            }
        return sha256(
            JsonCodec.encode(
                {
                    "outputs": sorted((o["path"], o["sha256"]) for o, _ in rows),
                    "sources": sources,
                    "rules": self.rules_sha256(),
                    "playwright": playwright_version(),
                }
            )
        )

    def files_intact(self, evidence: dict) -> bool:
        for table in evidence.get("tables", {}).values():
            for kind in ("html", "png"):
                path = self.root / table[kind]["path"]
                if not path.exists() or sha256(path.read_bytes()) != table[kind]["sha256"]:
                    return False
        return True

    @staticmethod
    def alternatives(output: dict) -> list[dict]:
        if output.get("expression_alternatives"):
            return output["expression_alternatives"]
        if output.get("SEC_operands"):
            return [
                {
                    "value_usd": output.get("value_usd"),
                    "SEC_operands": output["SEC_operands"],
                    "weights": output.get("weights", [1] * len(output["SEC_operands"])),
                }
            ]
        return []

    def envelope(self, ticker, period, key, status, rows, facts, tables, error=None) -> dict:
        evidence = {
            "ticker": ticker,
            "period_end": period,
            "status": status,
            "cache_key": key,
            "rules_sha256": self.rules_sha256(),
            "playwright": playwright_version(),
            "rows": rows,
            "facts": facts,
            "tables": tables,
        }
        if error:
            evidence["error"] = error
        return evidence

    def failure(self, ticker, period, rows, key, error) -> dict:
        evidence_rows = [
            {
                "output": {"path": receipt["path"], "sha256": receipt["sha256"]},
                "basis": row["basis"],
                "fields": {
                    label: {
                        "value_usd": output.get("value_usd"),
                        "status": "failed",
                        "reasons": ["證據產生失敗：" + error],
                        "expressions": [],
                    }
                    for label, output in row["outputs"].items()
                },
            }
            for receipt, row in rows
        ]
        return self.envelope(ticker, period, key, "failed", evidence_rows, {}, {}, error)

    def build(self, ticker, period, rows, documents, key, staging: Path) -> dict:
        facts, order, located, labels = {}, [], {}, {}
        evidence_rows = []
        for receipt, row in rows:
            fields = {}
            for label, output in row["outputs"].items():
                field = {"value_usd": output.get("value_usd"), "status": "ok", "reasons": [], "expressions": []}
                alternatives = self.alternatives(output)
                if not alternatives:
                    field.update(status="no_operands", reasons=["萃取沒有運算元：" + str(output.get("status"))])
                elif output.get("value_usd") is None:
                    field.update(status="failed", reasons=["萃取值為空；替代式僅供參考"])
                for alternative in alternatives:
                    operands = alternative["SEC_operands"]
                    weights = alternative.get("weights") or [1] * len(operands)
                    if len(weights) != len(operands):
                        field["status"] = "failed"
                        field["reasons"].append(f"權重 {len(weights)} 個與運算元 {len(operands)} 個數量不同")
                        continue
                    terms = []
                    for weight, operand in zip(weights, operands):
                        for term_weight, role, leaf in expression_terms(operand, weight):
                            name = fact_key(leaf)
                            if name not in facts:
                                order.append(name)
                                facts[name] = self.fact_entry(leaf, documents, located)
                            labels.setdefault(name, [])
                            if label not in labels[name]:
                                labels[name].append(label)
                            terms.append({"weight": term_weight, "role": role, "fact": name})
                    total = sum(t["weight"] * facts[t["fact"]]["value"] for t in terms)
                    field["expressions"].append({"value_usd": alternative.get("value_usd"), "terms": terms})
                    if output.get("value_usd") is not None and (
                        total != alternative.get("value_usd") or total != output.get("value_usd")
                    ):
                        field["status"] = "failed"
                        field["reasons"].append(f"運算式總和 {total} 不等於萃取值 {output.get('value_usd')}")
                fields[label] = field
            evidence_rows.append(
                {"output": {"path": receipt["path"], "sha256": receipt["sha256"]}, "basis": row["basis"], "fields": fields}
            )
        for number, name in enumerate(order, 1):
            facts[name].update(number=number, badge=badge(number), labels=labels.get(name, []))
        tables = self.write_tables(ticker, period, facts, located, staging)
        for row in evidence_rows:
            for field in row["fields"].values():
                for name in dict.fromkeys(t["fact"] for e in field["expressions"] for t in e["terms"]):
                    fact = facts[name]
                    if fact["status"] in FAILED_FACT_STATUSES:
                        field["status"] = "failed"
                        field["reasons"].append(f"{name}：{fact['reason']}")
                    elif fact["status"] == "not_in_table" and field["status"] == "ok":
                        field["status"] = "not_in_table"
                        field["reasons"].append(f"{name}：fact 不在 HTML 表格內，沒有表格證據")
        statuses = [f["status"] for r in evidence_rows for f in r["fields"].values()]
        status = "failed" if "failed" in statuses else ("complete" if set(statuses) <= {"ok"} else "incomplete")
        return self.envelope(ticker, period, key, status, evidence_rows, facts, tables)

    def fact_entry(self, leaf: dict, documents: dict, located: dict) -> dict:
        source = leaf.get("source_artifact_sha256")
        document = documents.get(source)
        entry = {
            "accession": leaf.get("accession"),
            "form": leaf.get("form"),
            "filing_date": leaf.get("filing_date"),
            "fact_id": leaf.get("fact_id"),
            "context_id": leaf.get("context_id"),
            "concept": leaf.get("concept"),
            "dimensions": leaf.get("dimensions"),
            "raw": leaf.get("raw"),
            "scale": leaf.get("scale"),
            "value": leaf["value"],
            "startdate": leaf.get("startdate"),
            "enddate": leaf.get("enddate"),
            "duration": duration_label(leaf),
            "row_text": leaf.get("row_text"),
            "source_url": leaf.get("source_url"),
            "source_sha256": source,
            "ixviewer_url": document.get("ixviewer_url") if document else None,
            "filing_index_url": document.get("filing_index_url") if document else None,
            "status": "in_table",
            "table": None,
            "reason": None,
        }
        if leaf.get("source_format") != "original_html":
            entry.update(status="source_missing", reason=f"來源格式不是 HTML 原文：{leaf.get('source_format')!r}")
            return entry
        if document is None:
            entry.update(status="source_missing", reason="申報包中找不到這個 SEC 原文（sha256）")
            return entry
        if not leaf.get("fact_id"):
            entry.update(status="fact_not_found", reason="運算元沒有 fact id")
            return entry
        try:
            if source not in located:
                located[source] = (document, TableLocator(self.read_verified(document["path"], source)))
            locator = located[source][1]
            status, index = locator.locate(leaf["fact_id"])
        except (OSError, ValueError, LxmlError) as error:
            entry.update(status="source_missing", reason=str(error))
            return entry
        if status == "fact_not_found":
            entry.update(status=status, reason="SEC 原文中找不到 fact id " + leaf["fact_id"])
            return entry
        mismatch = locator.verify(leaf)
        if mismatch:
            entry.update(status="fact_mismatch", reason=mismatch)
        elif status == "not_in_table":
            entry.update(status=status, reason="fact 不在 HTML 表格內")
        elif leaf.get("table_index") != index:
            entry.update(
                status="fact_mismatch",
                reason=f"fact 所在表格 #{index} 與萃取紀錄的表格 #{leaf.get('table_index')} 不同",
            )
        else:
            entry["table"] = table_key(leaf, index)
            entry["table_index"] = index
        return entry

    def write_tables(self, ticker, period, facts, located, staging: Path) -> dict:
        """逐表產生 HTML 與 PNG；單張表失敗時把該表的 fact 標為 evidence_failed，不中斷其他表。"""
        directory = Path("outputs") / ticker / period / "evidence"
        groups = {}
        for name, fact in facts.items():
            if fact["table"]:
                groups.setdefault(fact["table"], []).append(name)
        tables = {}
        for table, names in sorted(groups.items()):
            first = facts[names[0]]
            document, locator = located[first["source_sha256"]]
            items = [
                {
                    "id": facts[n]["fact_id"],
                    "badge": str(facts[n]["number"]),
                    "raw": facts[n]["raw"],
                    "label": f"{'、'.join(facts[n]['labels'])} · {facts[n]['form']} {facts[n]['duration']}"
                    f"（{facts[n]['startdate']}～{facts[n]['enddate']}）{facts[n]['raw']} · {facts[n]['concept']} · {facts[n]['fact_id']}",
                }
                for n in names
            ]
            header = {"ticker": ticker, "form": first["form"], "accession": first["accession"], "source_url": first["source_url"]}
            try:
                page = locator.table_html(first["table_index"], items, header)
                raw = self.read_verified(document["path"], first["source_sha256"])
                png, cropped, browser_text = self.shooter().capture(raw, items)
                if browser_text != locator.table_text(first["table_index"]):
                    raise ValueError(f"瀏覽器截到的表格與原文表格 #{first['table_index']} 文字不同")
            except Exception as error:
                for name in names:
                    facts[name].update(
                        status="evidence_failed", table=None, reason=f"表格證據產生失敗：{type(error).__name__}: {error}"
                    )
                continue
            record = {"accession": first["accession"], "table_index": first["table_index"], "source_sha256": first["source_sha256"], "cropped": cropped, "facts": names}
            for kind, body in (("html", page), ("png", png)):
                name = f"{table}.{kind}"
                (staging / name).write_bytes(body)
                record[kind] = {"path": str(directory / name), "sha256": sha256(body), "bytes": len(body)}
            tables[table] = record
        return tables
