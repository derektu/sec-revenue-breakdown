"""跨期檢核與重編偵測；結果不擋上線，有異常時標示 `review: pending`。

- 期別連續：與上一個已上線期別相隔一個單季，且 dei 的財年季別是緊接的前一季。
- 分類集合：與上一期已上線輸出相同。
- 占比變動與 YoY：與去年同季比較。季節性強的公司（例如 AAPL 的 12 月季）與上一季比較時，
  占比與成長率每年都在相同季度大幅變動；與去年同季比較才能分辨結構變化。去年同季以 dei 財年季別
  配對，且兩期期末日必須相隔一年。已有一年以上的歷史卻缺去年同季時標示 review。
- QoQ：只記錄，不觸發 review。
- 重編：新申報中的比較期 fact（concept、dimensions、期間與已上線運算元相同），
  值的差距超過雙方精度誤差總和，或無法解析時記錄；已上線的舊期輸出不改。
"""

from __future__ import annotations

import datetime as dt

from .spec import Thresholds
from .xbrl import InlineDocument, classify_duration, error_bound


def next_day(date: str) -> str:
    return (dt.date.fromisoformat(date) + dt.timedelta(days=1)).isoformat()


def predecessor(year: int, quarter: int) -> tuple[int, int]:
    return (year, quarter - 1) if quarter > 1 else (year - 1, 4)


def cross_period(current: dict, baselines: dict[str, dict], thresholds: Thresholds) -> list[dict]:
    """`current` 與 `baselines`（期末日 → 已上線的 revenue.json，只含較早的期別）比較。"""
    results = []
    names = sorted(current["categories"])
    end = current["period_end"]
    fiscal = (current["fiscal_year"], current["fiscal_quarter"])
    previous = baselines[max(baselines)] if baselines else None
    if previous is None:
        results.append({"check": "期別連續", "flagged": False, "note": "沒有上一期可比"})
        results.append({"check": "分類集合", "flagged": False, "note": "沒有上一期可比"})
    else:
        gap_ok = classify_duration(next_day(previous["period_end"]), end) == "quarter"
        found = (previous["fiscal_year"], previous["fiscal_quarter"])
        expected = predecessor(*fiscal)
        results.append(
            {
                "check": "期別連續",
                "baseline_period": previous["period_end"],
                "flagged": not gap_ok or found != expected,
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
                "flagged": before != names,
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
            results.append({"check": "去年同季", "category": name, "flagged": True, "note": f"去年同季 {last_year['period_end']} 沒有此分類"})
        elif last_year is not None:
            results += year_over_year(name, value, total, last_year, thresholds)
        if previous is not None and name in previous["categories"] and previous["categories"][name]["value"]:
            base = previous["categories"][name]["value"]
            results.append(
                {
                    "check": "QoQ",
                    "category": name,
                    "baseline_period": previous["period_end"],
                    "change": round(value / base - 1, 4),
                    "flagged": False,
                    "note": "只記錄",
                }
            )
    return results


def same_quarter_last_year(current: dict, baselines: dict[str, dict]) -> tuple[dict | None, dict | None]:
    """回傳（去年同季輸出, 問題）。沒有一年以上的歷史時只記錄；有歷史卻缺、不唯一或日期不符時標示。"""
    target = (current["fiscal_year"] - 1, current["fiscal_quarter"])
    matches = [b for b in baselines.values() if (b["fiscal_year"], b["fiscal_quarter"]) == target]
    if len(matches) > 1:
        return None, {"flagged": True, "note": f"已上線輸出中 FY{target[0]} Q{target[1]} 有 {len(matches)} 期"}
    if not matches:
        end = dt.date.fromisoformat(current["period_end"])
        old_enough = [p for p in baselines if (end - dt.date.fromisoformat(p)).days >= 357]
        if old_enough:
            return None, {"flagged": True, "note": f"已有 {min(old_enough)} 起的歷史，但缺去年同季 FY{target[0]} Q{target[1]}"}
        return None, {"flagged": False, "note": "沒有去年同季可比"}
    match = matches[0]
    if classify_duration(next_day(match["period_end"]), current["period_end"]) != "annual":
        return None, {
            "flagged": True,
            "note": f"去年同季 {match['period_end']} 與本期 {current['period_end']} 相隔不是一年",
        }
    return match, None


def year_over_year(name: str, value: int, total: int, last_year: dict, thresholds: Thresholds) -> list[dict]:
    base = last_year["categories"][name]["value"]
    base_total = last_year["total"]["value"]
    period = last_year["period_end"]
    results = []
    if total == 0 or base_total == 0:
        results.append({"check": "占比變動", "category": name, "baseline_period": period, "flagged": True, "note": "總營收為 0，無法計算占比"})
    else:
        share = 100 * value / total - 100 * base / base_total
        results.append(
            {
                "check": "占比變動",
                "category": name,
                "baseline_period": period,
                "change_pp": round(share, 2),
                "threshold_pp": thresholds.share_change_pp,
                "flagged": abs(share) > thresholds.share_change_pp,
            }
        )
    if base == 0:
        results.append({"check": "YoY", "category": name, "baseline_period": period, "change": None, "flagged": True, "note": "去年同季為 0"})
    else:
        yoy = value / base - 1
        results.append(
            {
                "check": "YoY",
                "category": name,
                "baseline_period": period,
                "change": round(yoy, 4),
                "threshold": thresholds.yoy_change,
                "flagged": abs(yoy) > thresholds.yoy_change,
            }
        )
    return results


def restatements(document: InlineDocument, accession: str, baselines: dict[str, dict]) -> list[dict]:
    """新申報中與已上線運算元同 concept、dimensions、期間的 fact：值超出雙方精度誤差，或無法解析時記錄。"""
    found = []
    for period, output in sorted(baselines.items()):
        for operand_id, operand in sorted(output["operands"].items()):
            if operand["kind"] != "xbrl_fact" or operand["accession"] == accession:
                continue
            dimensions = tuple(sorted(operand["dimensions"].items()))
            matches = document.matching(operand["concept"], dimensions, operand["period"]["start"], operand["period"]["end"])
            entry = compare_fact(operand, matches)
            if entry:
                found.append({"period_end": period, "operand": operand_id, "source_accession": accession, **entry})
    return found


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
