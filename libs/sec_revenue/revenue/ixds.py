"""inline XBRL 文件集（IXDS）：主文件與公司 parser 宣告的附件合成一份申報的 fact 清單。

一份申報的 inline XBRL 可以分在多份 HTML 文件中，例如 PGR 10-K 的財報在 EX-13，context 與 unit 只定義在主文件的
`ix:header`。抽取時每份文件看得到整個文件集的 context 與 unit：其他文件定義的 `xbrli:context`、`xbrli:unit` 暫時
複製進這份文件的解析樹，以 `extract.extract` 抽出後移除，所以表格編號、fact 的文件順序與證據元件用的解析樹都與單獨
抽取這份文件相同。

合併規則：

- context 與 unit 的 id 只能由文件集中的一份文件定義；同一個 id 出現在兩份文件時整份申報無法合併。同一份文件內
  重複定義的處理與單獨抽取這份文件相同。
- fact id 在文件集中唯一；同一個 fact id 出現在兩份文件時整份申報無法合併。
- dei 取自主文件。namespaces 與衝突的前綴在讀取時合併（`xbrl.InlineDocument.load`）。

這個模組與 `extract.py` 一起決定涵蓋附件的快照內容；這類快照另記錄這個模組的語法樹 hash（見 `snapshot.py`），
不涵蓋附件的快照不受這個模組影響。它只 import lxml、標準函式庫與 `extract.py`。
"""

from __future__ import annotations

import copy

from lxml import html

from .extract import extract

RESOURCE_TAGS = ("xbrli:context", "xbrli:unit")
# 申報包中附件的欄位：檔名、表單類型、是否為主文件、來源格式、sha256 與 URL。
ATTACHMENT_FIELDS = ("name", "type", "primary", "source_format", "sha256", "source_url", "ixviewer_url")


class MergeError(ValueError):
    """主文件與附件無法合成一份 fact 清單：context、unit 或 fact 的 id 在兩份文件中重複。"""


def attachment_records(package: dict, types: tuple[str, ...]) -> list[dict]:
    """申報包中類型屬於 `types` 的附件：不是主文件、來源是原始 HTML。依 `types` 的順序，同類型依檔名。"""
    found = [
        {k: d.get(k) for k in ATTACHMENT_FIELDS}
        for name, d in sorted(package["documents"].items())
        if d.get("type") in types and not d.get("primary") and d.get("source_format") == "original_html"
    ]
    return sorted(found, key=lambda d: types.index(d["type"]))


def resources(root) -> list:
    return [node for node in root.iter() if str(node.tag).lower() in RESOURCE_TAGS]


def extract_set(primary, attachments: list[tuple[str, object]]) -> dict:
    """主文件（解析樹）與附件（檔名, 解析樹）的抽取內容。

    主文件的 namespaces、衝突的前綴與 dei 在最上層，`attachments` 依序列出每份附件的 `document`（檔名）、namespaces、
    衝突的前綴與 dei；`facts` 先列主文件的 fact，再依序列出各附件的 fact，附件的 fact 另有 `document`。
    """
    roots = [(None, primary)] + list(attachments)
    defined: dict[str, str | None] = {}
    for name, root in roots:
        for node in resources(root):
            key = f"{str(node.tag).lower()}#{node.get('id')}"
            if defined.setdefault(key, name) != name:
                raise MergeError(f"{node.tag} {node.get('id')} 同時定義在{label(defined[key])}與{label(name)}")
    contents = []
    for name, root in roots:
        shared = html.Element("div")
        for other, other_root in roots:
            if other != name:
                shared.extend(copy.deepcopy(node) for node in resources(other_root))
        root.append(shared)
        try:
            contents.append(extract(root))
        finally:
            root.remove(shared)
    seen: dict[str, str | None] = {}
    for (name, _), content in zip(roots, contents):
        for row in content["facts"]:
            if row["fact_id"] is None:
                continue
            if row["fact_id"] in seen:
                raise MergeError(f"fact id {row['fact_id']} 同時出現在{label(seen[row['fact_id']])}與{label(name)}")
            seen[row["fact_id"]] = name
    merged = dict(contents[0])
    merged["facts"] = list(contents[0]["facts"])
    merged["attachments"] = []
    for (name, _), content in zip(roots[1:], contents[1:]):
        merged["attachments"].append({"document": name, **{k: content[k] for k in ("namespaces", "conflicts", "dei")}})
        merged["facts"] += [{**row, "document": name} for row in content["facts"]]
    return merged


def label(name: str | None) -> str:
    return "主文件" if name is None else f"附件 {name}"
