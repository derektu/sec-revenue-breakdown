"""AMD：依申報結構的業務分部營收，四分部或三分部，無調節項。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別，不是地區。說明見 parser.md。
"""

from sec_revenue.parser_utils import Missing, find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "AMD"
VIEW = "business_segment"
TOTAL = "Total net revenue"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
OPERATING = {"srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}
FOUR_SEGMENTS = (
    ("Data Center", "amd:DatacenterMember"),
    ("Embedded", "amd:EmbeddedMember"),
    ("Client", "amd:ClientMember"),
    ("Gaming", "amd:GamingMember"),
)
THREE_SEGMENTS = (
    ("Data Center", ("amd:DataCenterMember", "amd:DatacenterMember")),
    ("Client and Gaming", ("amd:ClientAndGamingMember",)),
    ("Embedded", ("amd:EmbeddedMember",)),
)
# 2025 Q1 10-Q 0000002488-25-000047（期末 2025-03-29）：從 FY2025 起合併 Client 與 Gaming。
COMBINED_START = "2024-12-29"
# 2024 Q1 10-Q 0000002488-24-000056（期末 2024-03-30）至 Q3 0000002488-24-000163
# （期末 2024-09-28）的本期與比較欄均依各份原文列標籤映射，不能按 member 字面解讀。
MISALIGNED_START = "2024-03-30"
MISALIGNED_END = "2024-09-28"
MISALIGNED_SEGMENTS = (
    ("Data Center", "amd:ClientMember"),
    ("Embedded", "amd:EmbeddedMember"),
    ("Client", "amd:GamingMember"),
    ("Gaming", "amd:DataCenterMember"),
)


def categories(day):
    segments = THREE_SEGMENTS if day >= COMBINED_START else FOUR_SEGMENTS
    return [name for name, _ in segments]


def compose(filing, request):
    result = Composition()
    combined = find(filing, request, REVENUE, {**OPERATING, SEGMENT: "amd:ClientAndGamingMember"})
    if not isinstance(combined, Missing):
        for name, members in THREE_SEGMENTS:
            put(result, "category", name, one_of(
                filing, request, *((REVENUE, {**OPERATING, SEGMENT: member}) for member in members)
            ))
    else:
        segments = (
            MISALIGNED_SEGMENTS
            if MISALIGNED_START <= filing.report_date <= MISALIGNED_END
            else FOUR_SEGMENTS
        )
        for name, member in segments:
            put(result, "category", name, find(filing, request, REVENUE, {SEGMENT: member}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
