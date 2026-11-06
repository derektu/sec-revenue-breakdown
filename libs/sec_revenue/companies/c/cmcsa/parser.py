"""CMCSA：五個營運分部與 Corporate and Other，另有 Eliminations 調節項。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（住宅寬頻、企業連網、媒體、片廠、主題樂園），不是地區。
"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "CMCSA"
VIEW = "business_segment"
TOTAL = "Total"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
REVENUES = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
BUSINESS_UNIT = "cmcsa:BusinessUnitAxis"
CONNECTIVITY = {BUSINESS_UNIT: "cmcsa:ConnectivityAndPlatformsMember"}
CONTENT = {BUSINESS_UNIT: "cmcsa:ContentAndExperiencesMember"}
CORPORATE = "us-gaap:CorporateNonSegmentMember"
SEGMENTS = (
    ("Residential Connectivity & Platforms", "cmcsa:ResidentialConnectivityAndPlatformsSegmentMember", CONNECTIVITY),
    ("Business Services Connectivity", "cmcsa:BusinessServicesConnectivitySegmentMember", CONNECTIVITY),
    ("Media", "cmcsa:MediaSegmentMember", CONTENT),
    ("Studios", "cmcsa:StudiosSegmentMember", CONTENT),
    ("Theme Parks", "cmcsa:ThemeParksSegmentMember", CONTENT),
)
OTHER = "Corporate and Other"
ELIMINATIONS = "Eliminations"
# FY2023 10-K（期末 2023-12-31）的分部、公司層級與總營收 fact 是 us-gaap:Revenues，分部另帶事業群軸。
FY2023_10K = "2023-12-31"
# 期末 2024-03-31 的 10-Q 是最後一份把 Corporate and Other、Eliminations 依事業群分成兩個 fact 的申報。
LAST_SPLIT = "2024-03-31"


def categories(day):
    return [name for name, _, _ in SEGMENTS] + [OTHER, ELIMINATIONS]


def compose(filing, request):
    period = filing.report_date
    concept = REVENUES if period == FY2023_10K else REVENUE
    result = Composition()
    for name, member, unit in SEGMENTS:
        dimensions = {**OPERATING, SEGMENT: member}
        if period == FY2023_10K:
            dimensions = {**unit, **dimensions}
        put(result, "category", name, find(filing, request, concept, dimensions))
    if period <= LAST_SPLIT:
        put(
            result,
            "category",
            OTHER,
            find(filing, request, concept, {CONSOLIDATION: CORPORATE}),
            find(filing, request, concept, {**CONTENT, CONSOLIDATION: CORPORATE}),
        )
        put(
            result,
            "reconciling",
            ELIMINATIONS,
            find(filing, request, concept, {**CONTENT, CONSOLIDATION: "us-gaap:IntersegmentEliminationMember"}),
            find(filing, request, concept, {BUSINESS_UNIT: "cmcsa:InterBusinessUnitEliminationsMember", CONSOLIDATION: "us-gaap:IntersegmentEliminationMember"}),
        )
    else:
        put(result, "category", OTHER, find(filing, request, REVENUE, {CONSOLIDATION: CORPORATE}))
        put(result, "reconciling", ELIMINATIONS, find(filing, request, REVENUE, {CONSOLIDATION: "srt:ConsolidationEliminationsMember"}))
    put(result, "total", TOTAL, find(filing, request, concept))
    return result
