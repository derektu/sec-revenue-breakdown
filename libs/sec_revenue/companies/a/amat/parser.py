"""AMAT：各期原申報的業務分部，Corporate and Other／Other 列為分類。

us-gaap:StatementBusinessSegmentsAxis 的成員是半導體設備、服務與顯示器業務，不是地區。
"""

from sec_revenue.parser_utils import Missing, find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "AMAT"
VIEW = "business_segment"
TOTAL = "Total net revenue"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
SEGMENTS = (
    ("Semiconductor Systems", "amat:SemiconductorSystemsMember", "amat:SemiconductorSystemsSegmentMember"),
    ("Applied Global Services", "amat:AppliedGlobalServicesMember", "amat:AppliedGlobalServicesSegmentMember"),
)
CORPORATE = {CONSOLIDATION: "amat:CorporateAndReconcilingItemsMember"}
OLD_DISPLAY = "Display and Adjacent Markets"
DISPLAY = "Display"

# 0000006951-24-000044（期末 2024-10-27）首次以 Display 列示；切換日是 Q4 起日。
DISPLAY_RENAMED = "2024-07-29"
# 0001628280-25-056742（期末 2025-10-26）將 Display 併入 Corporate and Other；Q4 起日。
DISPLAY_MERGED = "2025-07-28"
# 0001628280-26-009694（期末 2026-01-25）首次以 Other 列示；FY2026 起日。
OTHER_RENAMED = "2025-10-27"
FORMER_NAMES = {DISPLAY: (OLD_DISPLAY,)}
# FY2026 的比較欄沒有 FY2025 年度值，無法與合併後的 Corporate and Other 同期比對，故不宣告 Other。


def categories(day):
    names = [name for name, _, _ in SEGMENTS]
    names.append("Other" if day >= OTHER_RENAMED else "Corporate and Other")
    if day < DISPLAY_MERGED:
        names.append(OLD_DISPLAY if day < DISPLAY_RENAMED else DISPLAY)
    return names


def compose(filing, request):
    result = Composition()
    for name, old_member, new_member in SEGMENTS:
        put(
            result, "category", name,
            one_of(
                filing, request,
                (REVENUE, {**OPERATING, SEGMENT: old_member}),
                (REVENUE, {**OPERATING, SEGMENT: new_member}),
            ),
        )
    other = "Other" if filing.report_date >= OTHER_RENAMED else "Corporate and Other"
    put(result, "category", other, find(filing, request, REVENUE, CORPORATE))
    old_display = find(filing, request, REVENUE, {**OPERATING, SEGMENT: "amat:DisplayandAdjacentMarketsMember"})
    display = one_of(
        filing, request,
        (REVENUE, {**OPERATING, SEGMENT: "amat:DisplayMember"}),
        (REVENUE, {**OPERATING, SEGMENT: "amat:DisplaySegmentMember"}),
    )
    if not isinstance(old_display, Missing):
        put(result, "category", OLD_DISPLAY, old_display)
    elif not isinstance(display, Missing):
        put(result, "category", DISPLAY, display)
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
