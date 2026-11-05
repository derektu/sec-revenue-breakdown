"""比較欄比對：新申報列示的較早期間數字，與已上線輸出中同一期間的分類值逐一比對。

比對只記錄申報列示值與已上線值是否在精度內相同，不判斷差異原因，也不改動已上線的輸出；
不同或無法解析的項目由引擎彙整成舊期別的差異標記（status.json 的 `differences`）。
"""

from __future__ import annotations

from decimal import Decimal

from .spec import fact_variants
from .xbrl import InlineDocument, decimals_rank, error_bound

TOTAL_LABEL = "總營收"
# 已上線運算式中，九個月累計以負號參與 Q4；比對時換回定義本身的符號，與申報列示的九個月累計同號。
ROLE_SIGN = {"nine_months": -1}


def comparatives(document: InlineDocument, accession: str, baselines: list[tuple[str, str, dict]], addends_for) -> list[dict]:
    """新申報涵蓋的已上線期間，逐一比對每個分類在每個角色的值，回傳比對清單。

    `baselines` 是 (序列, 期末日, 已上線的 revenue.json)；`addends_for(名稱)` 回傳該分類（`None` 為總營收）在新申報期別
    生效定義的加數清單（`Addend`，selector 都是 fact），沒有時回傳 None。

    比對單位是「分類 × 角色」：角色是已上線運算元的 `role`（季、年度、九個月累計），已上線值是該角色運算元的加權和；
    申報列示值是新申報中同一期間、以新申報期別生效的定義組出的加權和。加數的個數、順序或成員可以與已上線不同，
    只比分類值。以規格定義而不是已上線運算元的 QName 查找，公司改 tag 或改成員名稱後仍比得到；查找在新申報內以
    namespace URI 比對。

    新申報有某段期間的總營收（總營收的每個加數都有該期間的 fact）時，視為涵蓋該期間。結果是 `consistent`
    （差距不超過雙方所有運算元的精度誤差總和）、`different`（超出）、`unparseable`（新申報或已上線的 fact 無法比較）或
    `not_found`（新申報期別沒有這個分類的定義，或有加數在新申報中找不到該期間的 fact）。沒有涵蓋的期間不列入；
    已上線輸出沒有的期間長度（例如六個月累計）因此不比對。
    """
    covered = set()
    total_addends = addends_for(None)
    if total_addends:
        spans = [{(f.start, f.end) for f in facts_of(document, a.selector)[0]} for a in total_addends]
        covered = set.intersection(*spans)
    found = []
    for series, period, output in baselines:
        lines = list(output["categories"].items()) + list(output.get("reconciling", {}).items()) + [(None, output["total"])]
        for name, line in lines:
            roles: dict[str, list[tuple[int, str, dict]]] = {}
            for term in line["expression"]:
                operand = output["operands"][term["operand"]]
                roles.setdefault(operand.get("role"), []).append((term["weight"], term["operand"], operand))
            for role, terms in roles.items():
                spans = {(o["period"]["start"], o["period"]["end"]) for _, _, o in terms}
                if len(spans) != 1 or any(o["kind"] != "xbrl_fact" or o["accession"] == accession for _, _, o in terms):
                    continue
                span = spans.pop()
                if span not in covered:
                    continue
                sign = ROLE_SIGN.get(role, 1)
                published = [
                    {"operand": op_id, "concept": o["concept"], "dimensions": o["dimensions"], "weight": sign * w,
                     "value": o["value"], "decimals": o["decimals"]}
                    for w, op_id, o in terms
                ]
                entry = {
                    "series": series,
                    "period_end": period,
                    "category": name if name is not None else TOTAL_LABEL,
                    "role": role,
                    "period": {"start": span[0], "end": span[1]},
                    "published_value": sum(a["weight"] * a["value"] for a in published),
                    "published_addends": [{k: a[k] for k in ("operand", "concept", "dimensions", "weight", "value")} for a in published],
                }
                entry.update(listed_value(document, addends_for(name), span, published))
                found.append(entry)
    return found


def listed_value(document: InlineDocument, addends, span: tuple[str, str], published: list[dict]) -> dict:
    """以新申報期別生效的定義，組出新申報中 `span` 期間的分類值，並與已上線值比較。"""
    if addends is None:
        return {"result": "not_found", "note": "新申報期別沒有這個分類的規格定義"}
    listed, missing, conflicts, ambiguous, prefixes = [], [], [], [], []
    for addend in addends:
        found, conflicted = facts_of(document, addend.selector)
        if conflicted:
            prefixes.append(f"{addend.selector.describe()} 的前綴 {conflicted} 在新申報中宣告衝突")
            continue
        matches = [f for f in found if (f.start, f.end) == span]
        if not matches:
            missing.append(addend.selector.describe())
            continue
        fact = max(matches, key=lambda f: decimals_rank(f.decimals))
        # 同一個加數的重複 fact（含多種寫法同時出現）數值必須在各自精度內一致，否則無法判斷申報列示的是哪個數字。
        if any(f.value is None or f.error_bound() is None or fact.value is None or abs(f.value - fact.value) > f.error_bound() for f in matches if f is not fact):
            conflicts.append("、".join(f"{f.fact_id}={f.value}" for f in matches))
            ambiguous += [listing(f, addend.weight) for f in matches]
        listed.append(listing(fact, addend.weight) | {"fact": fact})
    if prefixes:
        return {"result": "unparseable", "listed_value": None, "listed_addends": [], "note": "無法比較：" + "；".join(prefixes)}
    if missing:
        return {"result": "not_found", "note": f"新申報找不到該期間的加數：{'；'.join(missing)}"}
    if conflicts:
        # 列出衝突加數的每一個 fact（數值無法讀取時為 null），其他加數列選用的 fact，讓人追查是哪些 fact 不一致。
        others = [{k: v for k, v in a.items() if k != "fact"} for a in listed if not any(a["fact_id"] == c["fact_id"] for c in ambiguous)]
        return {"result": "unparseable", "listed_value": None, "listed_addends": others + ambiguous,
                "note": f"新申報同一個加數的 fact 數值不一致：{'；'.join(conflicts)}"}
    result = {"listed_addends": [{k: a[k] for k in ("fact_id", "concept", "dimensions", "weight", "value")} for a in listed]}
    bounds = [error_bound(a["decimals"]) for a in published] + [a["fact"].error_bound() for a in listed]
    broken = [a["fact"] for a in listed if a["fact"].value is None or a["fact"].error_bound() is None]
    if broken or None in bounds:
        reason = "、".join(f"{f.fact_id}：{f.value_error or '缺 decimals'}" for f in broken) or "已上線運算元缺 decimals"
        return result | {"result": "unparseable", "listed_value": None, "note": f"無法比較：{reason}"}
    value = sum(a["weight"] * a["value"] for a in listed)
    difference = abs(value - sum(a["weight"] * a["value"] for a in published))
    return result | {"result": "consistent" if difference <= sum(bounds, Decimal(0)) else "different", "listed_value": value}


def listing(fact, weight: int) -> dict:
    return {"fact_id": fact.fact_id, "concept": fact.concept, "dimensions": dict(fact.dimensions), "weight": weight, "value": fact.value}


def facts_of(document: InlineDocument, selector) -> tuple[list, list[str]]:
    """運算元（含 `one_of` 的每種寫法）在申報中的所有 fact，以及宣告衝突的前綴。

    以 namespace URI 比對；前綴未宣告的寫法視為不存在。前綴宣告衝突時無法確定寫法對應哪些 fact，回傳衝突的前綴，
    由呼叫端記為無法比較。
    """
    keys, conflicted = set(), []
    for variant in fact_variants(selector):
        conflicted += document.conflicting_prefixes(variant.concept, variant.dimensions)
        concept, dimensions = document.resolve(variant.concept), document.resolve_dimensions(variant.dimensions)
        if concept is not None and dimensions is not None:
            keys.add((concept, dimensions))
    return [f for f in document.facts if (f.concept_key, f.dimension_keys) in keys], sorted(set(conflicted))
