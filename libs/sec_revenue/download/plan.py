"""選擇要下載的申報：目標期別、Q4 依賴期別與財報新聞稿 8-K。"""

from __future__ import annotations

import datetime as dt

from ..common.periods import PeriodSelection

PERIODIC_FORMS = ("10-K", "10-Q")
EARNINGS_ITEM = "2.02"


def release_window(filings: list[dict], targets: list[dict], selection: PeriodSelection) -> list[dict]:
    """可能是所選各期財報新聞稿的 8-K（尚未看 item 代碼）。

    申報日須晚於最早目標期的期末；有 `--end` 時不晚於最後目標期期末後 90 天。
    下一季的新聞稿必在下一季期末（約 91 天後）之後，所以 90 天內只會是範圍內各期的新聞稿。
    沒有 `--end` 時不設上限，包含最新一季尚未申報 10-Q 前的新聞稿。
    """
    if not targets:
        return []
    first = min(f["reportDate"] for f in targets)
    last = dt.date.fromisoformat(max(f["reportDate"] for f in targets))
    upper = (last + dt.timedelta(days=90)).isoformat() if selection.end else None
    return [
        f
        for f in filings
        if f["form"] == "8-K"
        and f["filingDate"] > first
        and (upper is None or f["filingDate"] <= upper)
    ]


def earnings_releases(
    filings: list[dict], items: dict, targets: list[dict], selection: PeriodSelection
) -> list[dict]:
    """申報窗口內 item 2.02（Results of Operations）的 8-K；沒有 item 資料的 8-K 不在結果中。"""
    return [
        f
        for f in release_window(filings, targets, selection)
        if EARNINGS_ITEM in [i.strip() for i in items.get(f["accessionNumber"], "").split(",")]
    ]


def package_filings(filings: list[dict], targets: list[dict], dependency_periods: list[str] = ()) -> list[dict]:
    """目標期別與依賴期別的所有 10-K／10-Q 申報，原始與修訂版都包含。"""
    periods = {f["reportDate"] for f in targets} | set(dependency_periods)
    return [f for f in filings if f["form"] in PERIODIC_FORMS and f["reportDate"] in periods]


def q4_dependencies(filings: list[dict], targets: list[dict]) -> dict:
    """目標 10-K 推算 Q4 與檢查 Q4 口徑所需、但不在目標中的期別。

    期末日有 10-K 的目標期別（年報期別）需要同財年的 10-Q（Q1–Q3）與上一份 10-K。上一份 10-K 是期末早於目標、最晚的一期 10-K；
    同財年的 10-Q 是期末介於上一份 10-K 與目標之間的各期。catalog 中沒有上一份 10-K 時，取目標前 370 天內的 10-Q，
    並把該期列在 `unresolved`。
    """
    periodic = [f for f in filings if f["form"] in PERIODIC_FORMS]
    annual = sorted({f["reportDate"] for f in periodic if f["form"] == "10-K"})
    quarterly = sorted({f["reportDate"] for f in periodic if f["form"] == "10-Q"})
    chosen = {f["reportDate"] for f in targets}
    needed, unresolved = set(), []
    for end in sorted(chosen & set(annual)):
        prior = [d for d in annual if d < end]
        if prior:
            start = prior[-1]
            needed.add(start)
        else:
            start = (dt.date.fromisoformat(end) - dt.timedelta(days=370)).isoformat()
            unresolved.append(f"{end} 的上一份 10-K 不在 SEC catalog 中")
        needed.update(d for d in quarterly if start < d < end)
    return {"periods": sorted(needed - chosen), "unresolved": unresolved}
