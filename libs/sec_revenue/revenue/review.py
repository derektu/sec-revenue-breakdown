"""比較欄比對：新申報列示的較早期間數字，與已上線輸出中同一期間的運算元逐一比對。

比對只記錄申報列示值與已上線值是否在精度內相同，不判斷差異原因，也不改動已上線的輸出；
不同或無法解析的項目由引擎彙整成舊期別的差異標記（status.json 的 `differences`）。
"""

from __future__ import annotations

from .xbrl import InlineDocument, error_bound

TOTAL_LABEL = "總營收"


def comparatives(document: InlineDocument, accession: str, baselines: list[tuple[str, str, dict]], selector_for) -> list[dict]:
    """新申報涵蓋的已上線期間，逐一比對每個運算元，回傳比對清單。

    `baselines` 是 (序列, 期末日, 已上線的 revenue.json)；`selector_for(名稱)` 回傳該分類（`None` 為總營收）在新申報期別
    生效的 `FactSelector`，沒有時回傳 None。以規格定義而不是已上線運算元的 QName 查找，公司改 tag 或改成員名稱後仍比得到；
    查找在新申報內以 namespace URI 比對。

    新申報有某段期間的總營收時，視為涵蓋該期間：已上線運算元中期間相同者都列入清單，結果是
    `consistent`（在雙方精度內相同）、`different`（超出精度）、`unparseable`（新 fact 無法解析）或 `not_found`
    （新申報期別沒有對應的定義，或以該定義找不到同期間的 fact）。沒有涵蓋的期間不列入；
    已上線輸出沒有的期間長度（例如六個月累計）因此不比對。
    """
    total_selector = selector_for(None)
    covered = set()
    total_keys = resolve(document, total_selector) if total_selector else None
    if total_keys:
        covered = {(f.start, f.end) for f in document.facts if (f.concept_key, f.dimension_keys) == total_keys}
    found = []
    for series, period, output in baselines:
        lines = list(output["categories"].items()) + list(output.get("reconciling", {}).items()) + [(None, output["total"])]
        for name, line in lines:
            selector = selector_for(name)
            keys = resolve(document, selector) if selector else None
            for term in line["expression"]:
                operand_id = term["operand"]
                operand = output["operands"][operand_id]
                span = (operand["period"]["start"], operand["period"]["end"])
                if operand["kind"] != "xbrl_fact" or operand["accession"] == accession or span not in covered:
                    continue
                matches = [
                    f for f in document.facts if keys and (f.concept_key, f.dimension_keys) == keys and (f.start, f.end) == span
                ]
                entry = {
                    "series": series,
                    "period_end": period,
                    "category": name if name is not None else TOTAL_LABEL,
                    "operand": operand_id,
                    "role": operand.get("role"),
                    "period": operand["period"],
                }
                if not matches:
                    entry["result"] = "not_found"
                    entry["note"] = "本期生效的規格定義在新申報中找不到同期間的 fact" if selector else "本期沒有這個分類的規格定義"
                else:
                    change = compare_fact(operand, matches)
                    if change is None:
                        entry["result"] = "consistent"
                    else:
                        entry.update(change)
                        entry["result"] = "unparseable" if change["listed_value"] is None else "different"
                found.append(entry)
    return found


def resolve(document: InlineDocument, selector):
    concept = document.resolve(selector.concept)
    dimensions = document.resolve_dimensions(selector.dimensions)
    return None if concept is None or dimensions is None else (concept, dimensions)


def compare_fact(operand: dict, matches) -> dict | None:
    """已上線運算元與新申報中同一 fact 的比較；在雙方精度內相同時回傳 None。"""
    base = {
        "concept": operand["concept"],
        "dimensions": operand["dimensions"],
        "published_value": operand["value"],
        "published_accession": operand["accession"],
    }
    old_bound = error_bound(operand["decimals"])
    for fact in matches:
        if fact.value is None or fact.error_bound() is None or old_bound is None:
            return {**base, "listed_fact_id": fact.fact_id, "listed_value": None, "note": f"新申報的 fact 無法比較：{fact.value_error or '缺 decimals'}"}
        if abs(fact.value - operand["value"]) > old_bound + fact.error_bound():
            return {**base, "listed_fact_id": fact.fact_id, "listed_value": fact.value}
    return None
