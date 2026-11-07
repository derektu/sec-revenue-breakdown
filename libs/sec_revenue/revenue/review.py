"""比較欄比對：新申報列示的較早期間數字，與已上線輸出中同一期間的分類值逐一比對。

比對只記錄申報列示值與已上線值是否在精度內相同，不判斷差異原因，也不改動已上線的輸出；
不同或無法解析的項目由引擎彙整成舊期別的差異標記（status.json 的 `differences`）。
"""

from __future__ import annotations

from decimal import Decimal

from .contract import Composition, Request
from .filings import ParseError
from .xbrl import DEFAULT_DURATIONS, InlineDocument, classify_duration, comparison_bound, decimals_rank

TOTAL_LABEL = "總營收"
# 已上線運算式中，九個月累計以負號參與 Q4；比對時換回定義本身的符號，與申報列示的九個月累計同號。
ROLE_SIGN = {"nine_months": -1}


def comparatives(
    document: InlineDocument, accession: str, baselines: list[tuple[str, str, dict]], compose_for, total_name: str | None = None,
    durations=DEFAULT_DURATIONS,
) -> list[dict]:
    """新申報涵蓋的已上線期間，逐一比對每個分類在每個角色的值，回傳比對清單。

    `baselines` 是 (序列, 期末日, 已上線的 revenue.json)；`compose_for(request)` 回傳新申報中該期間的組成
    （`Composition`），來源組不出來時丟出 `ParseError`。`total_name` 是組成中總營收的名稱（`unparseable` 的鍵）。
    `durations` 是這家公司期間分類的天數範圍（`source.durations`，沒有指定時是預設範圍）；`compose_for` 交給公司 parser
    之前核對 Request 帶的是這家公司的範圍（`compose.PeriodComposer.request`）。

    比對單位是「分類 × 角色」：角色是已上線運算元的 `role`（季、年度、九個月累計），已上線值是該角色運算元的加權和；
    申報列示值是來源從新申報組出的同一期間運算式的加權和。加數的個數、順序或成員可以與已上線不同，只比分類值。
    列示值由來源從新申報重新組出，不沿用已上線運算元的 QName，公司改 tag 或改成員名稱後仍比得到。

    來源能從新申報組出某段期間的總營收時，視為涵蓋該期間。結果是 `consistent`（差距不超過雙方所有運算元的
    誤差上限總和；每個 fact 的誤差上限取 decimals 與顯示文字精度中較粗者）、`different`（超出）、`unparseable`
    （新申報或已上線的 fact 無法比較，包括來源組不出這段期間、或無法確定某一項是哪些 fact）或 `not_found`
    （組成中沒有這個分類）。沒有涵蓋的期間不列入；已上線輸出沒有的期間長度（例如六個月累計）因此不比對。
    """
    compositions: dict[tuple[str, str], tuple[Composition | None, str | None]] = {}
    spans_listed = {(f.start, f.end) for f in document.facts}

    def listed(span: tuple[str, str]) -> bool:
        return span in spans_listed

    def composed(span: tuple[str, str]) -> tuple[Composition | None, str | None]:
        """（組成, 無法比較的原因）；兩者都是 None 代表新申報沒有涵蓋這段期間。"""
        if span not in compositions:
            duration = classify_duration(*span, durations)
            found, error = None, None
            if duration:
                try:
                    found = compose_for(Request(span[1], duration, span[0], durations=durations))
                except ParseError as failure:
                    error = f"[{failure.check}] {failure.message}"
            if found is not None and found.total is not None:
                compositions[span] = (found, None)
            elif (error is not None or (found is not None and total_name is not None and total_name in found.unparseable)) and listed(span):
                # 組不出或無法確定總營收時，只在申報確實列示這段期間（有起訖相同的 fact）才記為無法比較。
                compositions[span] = (found, error)
            else:
                compositions[span] = (None, None)
        return compositions[span]

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
                composition, error = composed(span)
                if composition is None and error is None:
                    continue
                sign = ROLE_SIGN.get(role, 1)
                published = [
                    {"operand": op_id, "concept": o["concept"], "dimensions": o["dimensions"], "weight": sign * w,
                     "value": o["value"], "bound": comparison_bound(o["decimals"], o["raw"], o["scale"])}
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
                key = total_name if name is None else name
                if error is not None or key in composition.unparseable:
                    reason = error if error is not None else composition.unparseable[key]
                    entry.update({"result": "unparseable", "listed_value": None, "listed_addends": [], "note": f"無法比較：{reason}"})
                else:
                    terms = composition.total if name is None else composition.categories.get(name, composition.reconciling.get(name))
                    entry.update(listed_value(document, terms, span, published, composition.missing.get(key)))
                found.append(entry)
    return found


def listed_value(document: InlineDocument, terms, span: tuple[str, str], published: list[dict], missing: str | None = None) -> dict:
    """新申報中 `span` 期間的分類值（來源組出的運算式），並與已上線值比較；`missing` 是組成沒有這個分類的原因。"""
    if terms is None:
        return {"result": "not_found", "note": f"新申報找不到該期間的加數：{missing}" if missing else "新申報的組成沒有這個分類"}
    listed, missing, conflicts, ambiguous = [], [], [], []
    for term in terms:
        keys = {(f.concept_key, f.dimension_keys) for f in term.facts}
        matches = [f for f in document.facts if (f.concept_key, f.dimension_keys) in keys and (f.start, f.end) == span]
        if not matches:
            missing.append(term.label)
            continue
        fact = max(matches, key=lambda f: decimals_rank(f.decimals))
        # 同一個加數的重複 fact（含多種寫法同時出現）數值必須在各自精度內一致，否則無法判斷申報列示的是哪個數字。
        if any(f.value is None or f.error_bound() is None or fact.value is None or abs(f.value - fact.value) > f.error_bound() for f in matches if f is not fact):
            conflicts.append("、".join(f"{f.fact_id}={f.value}" for f in matches))
            ambiguous += [listing(f, term.weight) for f in matches]
        listed.append(listing(fact, term.weight) | {"fact": fact})
    if missing:
        return {"result": "not_found", "note": f"新申報找不到該期間的加數：{'；'.join(missing)}"}
    if conflicts:
        # 列出衝突加數的每一個 fact（數值無法讀取時為 null），其他加數列選用的 fact，讓人追查是哪些 fact 不一致。
        others = [{k: v for k, v in a.items() if k != "fact"} for a in listed if not any(a["fact_id"] == c["fact_id"] for c in ambiguous)]
        return {"result": "unparseable", "listed_value": None, "listed_addends": others + ambiguous,
                "note": f"新申報同一個加數的 fact 數值不一致：{'；'.join(conflicts)}"}
    result = {"listed_addends": [{k: a[k] for k in ("fact_id", "concept", "dimensions", "weight", "value")} for a in listed]}
    bounds = [a["bound"] for a in published] + [a["fact"].comparison_bound() for a in listed]
    broken = [a["fact"] for a in listed if a["fact"].value is None or a["fact"].error_bound() is None]
    if broken or None in bounds:
        reason = "、".join(f"{f.fact_id}：{f.value_error or '缺 decimals'}" for f in broken) or "已上線運算元缺 decimals"
        return result | {"result": "unparseable", "listed_value": None, "note": f"無法比較：{reason}"}
    value = sum(a["weight"] * a["value"] for a in listed)
    difference = abs(value - sum(a["weight"] * a["value"] for a in published))
    return result | {"result": "consistent" if difference <= sum(bounds, Decimal(0)) else "different", "listed_value": value}


def listing(fact, weight: int) -> dict:
    return {"fact_id": fact.fact_id, "concept": fact.concept, "dimensions": dict(fact.dimensions), "weight": weight, "value": fact.value}
