"""跨期檢核與重編偵測；結果不擋上線，異常寫成標註（`annotated: true`），由引擎彙整到 `annotations`。

- 期別連續：與上一個已上線期別相隔一個單季，且 dei 的財年季別是緊接的前一季。
- 分類集合：與上一期已上線輸出相同。
- 占比變動與 YoY：與去年同季比較。季節性強的公司（例如 AAPL 的 12 月季）與上一季比較時，
  占比與成長率每年都在相同季度大幅變動；與去年同季比較才能分辨結構變化。去年同季以 dei 財年季別
  配對，且兩期期末日必須相隔一年。已有一年以上的歷史卻缺去年同季時寫標註。
- QoQ：只記錄，不寫標註。
- 比較期：新申報涵蓋的已上線期間逐一比對，記錄一致、重編、無法解析或找不到；
  重編、無法解析與找不到都寫標註，已上線的舊期輸出不改。去年同季的總營收必須比得到。
"""

from __future__ import annotations

import datetime as dt

from .xbrl import InlineDocument, classify_duration, error_bound


# 全部公司共用的門檻；超過時只寫標註，不擋上線。
SHARE_CHANGE_PP = 5.0
YOY_CHANGE = 0.50


def next_day(date: str) -> str:
    return (dt.date.fromisoformat(date) + dt.timedelta(days=1)).isoformat()


def predecessor(year: int, quarter: int) -> tuple[int, int]:
    return (year, quarter - 1) if quarter > 1 else (year - 1, 4)


def cross_period(current: dict, baselines: dict[str, dict]) -> list[dict]:
    """`current` 與 `baselines`（期末日 → 已上線的 revenue.json，只含較早的期別）比較。"""
    results = []
    names = sorted(current["categories"])
    end = current["period_end"]
    fiscal = (current["fiscal_year"], current["fiscal_quarter"])
    previous = baselines[max(baselines)] if baselines else None
    if previous is None:
        results.append({"check": "期別連續", "annotated": False, "note": "沒有上一期可比"})
        results.append({"check": "分類集合", "annotated": False, "note": "沒有上一期可比"})
    else:
        gap_ok = classify_duration(next_day(previous["period_end"]), end) == "quarter"
        found = (previous["fiscal_year"], previous["fiscal_quarter"])
        expected = predecessor(*fiscal)
        results.append(
            {
                "check": "期別連續",
                "baseline_period": previous["period_end"],
                "annotated": not gap_ok or found != expected,
                **({} if gap_ok and found == expected else {
                    "note": f"上一個已上線期別是 FY{found[0]} Q{found[1]}（{previous['period_end']}），預期 FY{expected[0]} Q{expected[1]} 且相隔一個單季"
                }),
            }
        )
        before = sorted(previous["categories"])
        results.append(
            {
                "check": "分類集合",
                "baseline_period": previous["period_end"],
                "annotated": before != names,
                **({"added": sorted(set(names) - set(before)), "removed": sorted(set(before) - set(names))} if before != names else {}),
            }
        )
    last_year, problem = same_quarter_last_year(current, baselines)
    total = current["total"]["value"]
    for name in names:
        value = current["categories"][name]["value"]
        if problem:
            results.append({"check": "去年同季", "category": name, **problem})
        elif last_year is not None and name not in last_year["categories"]:
            results.append({"check": "去年同季", "category": name, "annotated": True, "note": f"去年同季 {last_year['period_end']} 沒有此分類"})
        elif last_year is not None:
            results += year_over_year(name, value, total, last_year)
        if previous is not None and name in previous["categories"] and previous["categories"][name]["value"]:
            base = previous["categories"][name]["value"]
            results.append(
                {
                    "check": "QoQ",
                    "category": name,
                    "baseline_period": previous["period_end"],
                    "change": round(value / base - 1, 4),
                    "annotated": False,
                    "note": "只記錄",
                }
            )
    return results


def same_quarter_last_year(current: dict, baselines: dict[str, dict]) -> tuple[dict | None, dict | None]:
    """回傳（去年同季輸出, 問題）。沒有一年以上的歷史時只記錄；有歷史卻缺、不唯一或日期不符時寫標註。"""
    target = (current["fiscal_year"] - 1, current["fiscal_quarter"])
    matches = [b for b in baselines.values() if (b["fiscal_year"], b["fiscal_quarter"]) == target]
    if len(matches) > 1:
        return None, {"annotated": True, "note": f"已上線輸出中 FY{target[0]} Q{target[1]} 有 {len(matches)} 期"}
    if not matches:
        end = dt.date.fromisoformat(current["period_end"])
        old_enough = [p for p in baselines if (end - dt.date.fromisoformat(p)).days >= 357]
        if old_enough:
            return None, {"annotated": True, "note": f"已有 {min(old_enough)} 起的歷史，但缺去年同季 FY{target[0]} Q{target[1]}"}
        return None, {"annotated": False, "note": "沒有去年同季可比"}
    match = matches[0]
    if classify_duration(next_day(match["period_end"]), current["period_end"]) != "annual":
        return None, {
            "annotated": True,
            "note": f"去年同季 {match['period_end']} 與本期 {current['period_end']} 相隔不是一年",
        }
    return match, None


def year_over_year(name: str, value: int, total: int, last_year: dict) -> list[dict]:
    base = last_year["categories"][name]["value"]
    base_total = last_year["total"]["value"]
    period = last_year["period_end"]
    results = []
    if total == 0 or base_total == 0:
        results.append({"check": "占比變動", "category": name, "baseline_period": period, "annotated": True, "note": "總營收為 0，無法計算占比"})
    else:
        share = 100 * value / total - 100 * base / base_total
        results.append(
            {
                "check": "占比變動",
                "category": name,
                "baseline_period": period,
                "change_pp": round(share, 2),
                "threshold_pp": SHARE_CHANGE_PP,
                "annotated": abs(share) > SHARE_CHANGE_PP,
            }
        )
    if base == 0:
        results.append({"check": "YoY", "category": name, "baseline_period": period, "change": None, "annotated": True, "note": "去年同季為 0"})
    else:
        yoy = value / base - 1
        results.append(
            {
                "check": "YoY",
                "category": name,
                "baseline_period": period,
                "change": round(yoy, 4),
                "threshold": YOY_CHANGE,
                "annotated": abs(yoy) > YOY_CHANGE,
            }
        )
    return results


TOTAL_LABEL = "總營收"


def comparatives(document: InlineDocument, accession: str, baselines: dict[str, dict], selector_for) -> list[dict]:
    """新申報涵蓋的已上線期間，逐一比對每個運算元，回傳比對清單。

    `selector_for(名稱)` 回傳該分類（`None` 為總營收）在新申報期別生效的 `FactSelector`，沒有時回傳 None。
    以規格定義而不是已上線運算元的 QName 查找，公司改 tag 或改成員名稱後仍比得到；查找在新申報內以 namespace URI 比對。

    新申報有某段期間的總營收時，視為涵蓋該期間：該期間的每個運算元都列入清單，結果是
    `consistent`（在雙方精度內一致）、`restated`（超出精度）、`unparseable`（新 fact 無法解析）或 `not_found`
    （例如公司改名或合併分類而規格沒有對應的定義）。沒有涵蓋的期間不列入。
    """
    total_selector = selector_for(None)
    covered = set()
    total_keys = resolve(document, total_selector) if total_selector else None
    if total_keys:
        covered = {(f.start, f.end) for f in document.facts if (f.concept_key, f.dimension_keys) == total_keys}
    found = []
    for period, output in sorted(baselines.items()):
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
                        entry["result"] = "unparseable" if change["restated_value"] is None else "restated"
                found.append(entry)
    return found


def resolve(document: InlineDocument, selector):
    concept = document.resolve(selector.concept)
    dimensions = document.resolve_dimensions(selector.dimensions)
    return None if concept is None or dimensions is None else (concept, dimensions)


def restatements(document: InlineDocument, accession: str, baselines: dict[str, dict], selector_for) -> list[dict]:
    """比對清單中重編或無法解析的項目，格式與修正申報的重編紀錄相同。"""
    return [
        {k: v for k, v in entry.items() if k not in ("category", "role", "period", "result")} | {"source_accession": accession}
        for entry in comparatives(document, accession, baselines, selector_for)
        if entry["result"] in ("restated", "unparseable")
    ]


def compare_fact(operand: dict, matches) -> dict | None:
    """已上線運算元與新申報中同一 fact 的比較；一致時回傳 None。"""
    base = {
        "concept": operand["concept"],
        "dimensions": operand["dimensions"],
        "published_value": operand["value"],
        "published_accession": operand["accession"],
    }
    old_bound = error_bound(operand["decimals"])
    for fact in matches:
        if fact.value is None or fact.error_bound() is None or old_bound is None:
            return {**base, "restated_fact_id": fact.fact_id, "restated_value": None, "note": f"新申報的 fact 無法比較：{fact.value_error or '缺 decimals'}"}
        if abs(fact.value - operand["value"]) > old_bound + fact.error_bound():
            return {**base, "restated_fact_id": fact.fact_id, "restated_value": fact.value}
    return None
