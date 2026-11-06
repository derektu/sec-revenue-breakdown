"""從 SEC 原文抽取快照的內容：HTML 解析、表格編號、xmlns 宣告、context、unit、dei、`ix:nonFraction` 的文字與屬性，
以及申報篩選用到的申報包欄位。

這個模組的行為決定 XBRL fact 快照的內容，快照記錄它的語法樹 hash（見 `snapshot.py`）。讀快照時才執行的規則
（數字換算、QName 解析、期間分類、申報篩選）不在這裡，改這些規則不需要重產快照。證據元件（`evidence.py`）
用同一組 HTML 解析與表格編號，兩者的表格編號因此一致。
"""

from __future__ import annotations

from lxml import html

# 申報篩選（`filings.periodic_filing`）用到的申報包欄位。
FILING_FIELDS = ("form", "reportDate", "filingDate")
PRIMARY_FIELDS = ("name", "primary", "inline_xbrl", "sha256", "source_url", "ixviewer_url")


def parse_html(raw: bytes):
    """以 lxml HTML parser 解析原文，不載入任何外部資源。"""
    return html.fromstring(raw, parser=html.HTMLParser(no_network=True))


def numbered_tables(root) -> list:
    """依文件順序列舉 `<table>`；串列位置就是表格編號。"""
    return list(root.iter("table"))


def clean_text(text: str) -> str:
    return " ".join(text.split())


def package_record(package: dict) -> dict:
    """申報包中申報篩選需要的欄位：申報資訊、是否完整、主文件。"""
    return {
        "filing": {k: package.get("filing", {}).get(k) for k in FILING_FIELDS},
        "complete": bool(package.get("complete")),
        "documents": {
            name: {k: d.get(k) for k in PRIMARY_FIELDS} for name, d in sorted(package["documents"].items()) if d.get("primary")
        },
    }


def extract(root) -> dict:
    """主文件的 namespaces、衝突的前綴、dei 與每個 `ix:nonFraction` fact（依文件順序），皆可 JSON 序列化。

    fact 保存 XBRL 原始欄位與 HTML 位置，不含換算後的數值：`fact_id`、`concept`、`dimensions`（依軸排序的
    [軸, 成員]）、`start`、`end`、`unit`、`raw`（正規化空白的顯示文字）、`scale`、`decimals`、`sign`、`format`
    （屬性原文，沒有時為 null）、`context_id`、`table_index`、`order`；nil fact 另有 `nil: true`。
    """
    # lxml 的元素物件只在有人持有時保持同一個 id，所以表格串列保留到 fact 全部讀完。
    tables = numbered_tables(root)
    table_numbers = {id(table): i for i, table in enumerate(tables)}
    namespaces, conflicts = {}, set()
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        for name, uri in node.attrib.items():
            if name.startswith("xmlns:"):
                prefix = name[len("xmlns:") :]
                if namespaces.setdefault(prefix, uri) != uri:
                    conflicts.add(prefix)
    contexts, units, dei, facts = {}, {}, {}, []
    for node in root.iter():
        name = str(node.tag).lower()
        if name == "xbrli:context":
            contexts[node.get("id")] = read_context(node)
        elif name == "xbrli:unit":
            units[node.get("id")] = read_unit(node)
    for order, node in enumerate(root.iter()):
        name = str(node.tag).lower()
        if name == "ix:nonnumeric" and node.get("name", "").startswith("dei:"):
            dei.setdefault(node.get("name"), clean_text(node.text_content()))
        elif name == "ix:nonfraction":
            facts.append(read_fact(node, order, contexts, units, table_numbers))
    return {
        "namespaces": dict(sorted(namespaces.items())),
        "conflicts": sorted(conflicts),
        "dei": dict(sorted(dei.items())),
        "facts": facts,
    }


def read_context(node) -> dict:
    context = {"dimensions": {}, "start": None, "end": None}
    for child in node.iter():
        kind = str(child.tag).split(":")[-1].lower()
        text = clean_text(child.text_content())
        if kind == "startdate":
            context["start"] = text
        elif kind in ("enddate", "instant"):
            context["end"] = text
        elif kind == "explicitmember":
            context["dimensions"][child.get("dimension")] = text
        elif kind == "typedmember":
            # typed 維度以完整內容參與比對；公司 parser 不會指定 typed 維度，因此這類 fact 不會被選中。
            context["dimensions"][child.get("dimension")] = "typed:" + text
    return context


def read_unit(node) -> str:
    measures = [clean_text(m.text_content()) for m in node.iter() if str(m.tag).lower().endswith("measure")]
    return measures[0] if len(measures) == 1 else "/".join(measures)


def read_fact(node, order: int, contexts: dict, units: dict, table_numbers: dict) -> dict:
    context = contexts.get(node.get("contextref"), {"dimensions": {}, "start": None, "end": None})
    table = next((a for a in node.iterancestors() if a.tag == "table"), None)
    fact = {
        "fact_id": node.get("id"),
        "concept": node.get("name", ""),
        "dimensions": [[axis, member] for axis, member in sorted(context["dimensions"].items())],
        "start": context["start"],
        "end": context["end"],
        "unit": units.get(node.get("unitref")),
        "raw": clean_text(node.text_content()),
        "scale": node.get("scale", "0"),
        "decimals": node.get("decimals"),
        "sign": node.get("sign"),
        "format": node.get("format"),
        "context_id": node.get("contextref"),
        "table_index": table_numbers[id(table)] if table is not None else None,
        "order": order,
    }
    if str(node.get("xsi:nil", node.get("nil", "false"))).lower() == "true":
        fact["nil"] = True
    return fact
