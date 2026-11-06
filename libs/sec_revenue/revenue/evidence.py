"""SEC 表格證據元件：以 fact id 在 inline XBRL 原文中找到 fact 與所在表格，核對 fact，抽出單一表格 HTML，並以
headless Chromium 截圖。

表格編號與數值規則來自 `ixbrl.py`，與 `xbrl.InlineDocument` 相同。只讀呼叫端給的原文 bytes，不發網路請求。
"""

from __future__ import annotations

import copy
import html as html_text
import re

from lxml import html

from .ixbrl import clean_text, ix_number, numbered_tables, parse_html

# 截圖高度超過門檻時只保留表頭與標示列附近的列，並以裁切列標出略過的位置。
SCREENSHOT_MAX_HEIGHT = 3000
SCREENSHOT_MARGIN = 600
HEADER_ROWS = 4
VIEWPORT = {"width": 1000, "height": 1400}
DEVICE_SCALE = 2
# 表格檔名：accession、來源文件 sha256 前綴與 parser 的表格編號。
FILE_NAME_RE = re.compile(r"\d{10}-\d{2}-\d{6}-[0-9a-f]{12}-t\d+\.(?:png|html)")

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


def fact_value(node, raw: str) -> int | None:
    """`ix:nonFraction` 的整數美元；規則與 `ix_number` 相同，無法解析時回傳 None。"""
    transform = node.get("format", "").split(":")[-1].lower()
    return ix_number(raw, transform, node.get("scale", "0"), node.get("sign"))[0]


class TableLocator:
    """以 fact id 在 SEC 原文找 `ix:nonFraction` 與所在表格；表格依文件順序編號。"""

    def __init__(self, raw: bytes):
        self.attach(parse_html(raw))

    @classmethod
    def from_root(cls, root) -> TableLocator:
        """以 `ixbrl.parse_html` 解析好的樹建立，不重新解析原文。"""
        locator = cls.__new__(cls)
        locator.attach(root)
        return locator

    def attach(self, root):
        self.root = root
        self.tables = numbered_tables(root)
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

    def __init__(self, device_scale: int = DEVICE_SCALE):
        self.device_scale = device_scale
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
            device_scale_factor=self.device_scale,
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
