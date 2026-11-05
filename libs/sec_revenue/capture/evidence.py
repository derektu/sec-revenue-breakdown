"""證據檔：表格截圖壓縮、`table.html` 清理或重建、`table.txt`，以及寫檔與 sha256。

`table.html` 一律只含表格結構與文字，不是網頁原始 bytes。兩種產生方式由 adapter 依網站結構選擇：

- `clean`：保留原始片段中與表格有關的標籤與文字，刪除所有屬性（只留 `colspan`、`rowspan`），
  其他標籤只留文字，script、圖片、表單等連同內容刪除。適用真正以 `<table>` 呈現的表格。
- `rebuild`：以表格文字重建只含 `<table><tr><th><td>` 的表格。適用以 div 排版的表格。

帳號資訊、追蹤參數與外部資源都藏在屬性或被刪除的標籤中，因此兩種方式都不需要逐項列舉。
"""

from __future__ import annotations

import hashlib
import html
import io
from pathlib import Path

from lxml import etree
from lxml import html as lxml_html
from PIL import Image

from ..universe import CAPTURE_FILES, capture_file_path
from .model import HtmlMode

# 保留的標籤；其他標籤只留下文字與子元素。
KEEP_TAGS = frozenset(
    {"table", "caption", "colgroup", "col", "thead", "tbody", "tfoot", "tr", "th", "td",
     "div", "span", "p", "br"}
)
# 連同內容一併刪除的標籤：可執行內容、外部資源與互動元件。
DROP_TREE_TAGS = frozenset(
    {"script", "style", "noscript", "template", "svg", "math", "img", "picture", "source",
     "video", "audio", "canvas", "iframe", "object", "embed", "link", "meta", "base",
     "button", "input", "select", "textarea", "form"}
)
KEEP_ATTRS = ("colspan", "rowspan")
# 單檔超過此大小時在輸出中警告。
PNG_WARN_BYTES = 500 * 1024


def clean_html(fragment: str) -> str:
    """清理原始表格片段：只留表格相關標籤與文字，刪除所有屬性（`colspan`、`rowspan` 除外）。"""
    root = lxml_html.fragment_fromstring(fragment, create_parent="div")
    etree.strip_elements(root, etree.Comment, etree.ProcessingInstruction, with_tail=False)
    for node in list(root.iter()):
        if node is root or node.getparent() is None:
            continue
        tag = node.tag.lower()
        if tag in DROP_TREE_TAGS:
            node.drop_tree()
        elif tag not in KEEP_TAGS:
            node.drop_tag()
    for node in root.iter():
        keep = {k: v for k, v in node.attrib.items() if k in KEEP_ATTRS and v.isdigit()}
        node.attrib.clear()
        node.attrib.update(keep)
    parts = [html.escape(root.text or "", quote=False)]
    parts += [lxml_html.tostring(child, encoding="unicode") for child in root]
    return "".join(parts).strip() + "\n"


def rebuild_html(rows: list[list[str]], caption: str | None = None) -> str:
    """以表格文字重建 `<table>`：第一列為表頭（`th`），其餘為資料列（`td`）。"""
    out = ["<table>"]
    if caption:
        out.append(f"<caption>{html.escape(caption)}</caption>")
    for index, row in enumerate(rows):
        cell = "th" if index == 0 else "td"
        out.append("<tr>" + "".join(f"<{cell}>{html.escape(text)}</{cell}>" for text in row) + "</tr>")
    out.append("</table>")
    return "\n".join(out) + "\n"


def table_text(rows: list[list[str]], caption: str | None = None) -> str:
    """表格文字：有 caption 時為第一行，其後一列一行，欄位以 tab 分隔。"""
    lines = [caption] if caption else []
    lines += ["\t".join(cell.replace("\t", " ").replace("\n", " ") for cell in row) for row in rows]
    return "".join(line + "\n" for line in lines)


def compress_png(data: bytes) -> bytes:
    """轉成 256 色調色盤 PNG 並最佳化壓縮。表格顏色少，不 dither 可保持文字邊緣清楚。"""
    image = Image.open(io.BytesIO(data)).convert("RGB")
    palette = image.quantize(colors=256, dither=Image.Dither.NONE)
    out = io.BytesIO()
    palette.save(out, format="PNG", optimize=True)
    return out.getvalue()


def table_html(fragment: str, rows: list[list[str]], mode: HtmlMode, caption: str | None = None) -> str:
    """`clean` 用於帶有自身表頭的原始表格，不加 caption；`rebuild` 時 caption 寫入 `<caption>`。"""
    if mode == "clean":
        return clean_html(fragment)
    if mode == "rebuild":
        return rebuild_html(rows, caption)
    raise ValueError(f"未知的 html_mode：{mode!r}")


def write_evidence(
    ticker_dir: Path, source: str, capture: str, png: bytes, html_text: str, txt: str
) -> dict:
    """寫入三個證據檔，回傳 reference.json 的 `files` 欄位。"""
    contents = {"png": png, "html": html_text.encode("utf-8"), "txt": txt.encode("utf-8")}
    files = {}
    for kind in CAPTURE_FILES:
        relative = capture_file_path(source, capture, kind)
        path = Path(ticker_dir) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents[kind])
        files[kind] = {"path": relative, "sha256": hashlib.sha256(contents[kind]).hexdigest()}
    return files

