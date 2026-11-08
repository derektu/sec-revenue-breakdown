"""INTC：抵銷前業務分部營收，另列 Intersegment eliminations 調節項。

us-gaap:StatementBusinessSegmentsAxis 的成員是運算、晶圓代工等業務別，不是地區。
"""

from sec_revenue.parser_utils import Missing, find, put
from sec_revenue.revenue.contract import Composition

TICKER = "INTC"
VIEW = "business_segment"
TOTAL = "Total net revenue"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
LEGACY_OPERATING = {"srt:ConsolidatedEntitiesAxis": "us-gaap:OperatingSegmentsMember"}
CCG = ("Client Computing Group", "intc:ClientComputingGroupMember")
CCPG = ("Client Computing and Physical AI Group", "intc:ClientComputingAndPhysicalAIGroupMember")
FOUNDRY = ("Intel Foundry", "intc:IntelFoundryMember")
DCAI = ("Data Center and AI", "intc:DatacenterAndAIMember")
OTHER = ("All Other", "us-gaap:AllOtherSegmentsMember")
NEX = ("Network and Edge", "intc:NetworkAndEdgeMember")
LEGACY_SEGMENTS = (
    ("Client Computing", CCG[1]),
    DCAI,
    NEX,
    ("Mobileye", "intc:MobileyeSegmentMember"),
    ("Intel Foundry Services", "intc:IntelFoundryServicesMember"),
    OTHER,
)
ELIMINATIONS = "Intersegment eliminations"
# 2024 Q1 10-Q：0000050863-24-000076，期末 2024-03-30；新模型從該季起日開始。
INTERNAL_FOUNDRY_START = "2023-12-31"
# 2025 Q1 10-Q：0000050863-25-000074，期末 2025-03-29；NEX 併入 CCG、DCAI。
NEX_INTEGRATION_START = "2024-12-29"
# 2026 Q2 10-Q：0000050863-26-000157，期末 2026-06-27；CCG 純改名，見 parser.md。
CCPG_START = "2026-03-29"
FORMER_NAMES = {"Client Computing and Physical AI Group": ("Client Computing Group",)}


def categories(day):
    if day < INTERNAL_FOUNDRY_START:
        return [name for name, _ in LEGACY_SEGMENTS]
    client = CCPG if day >= CCPG_START else CCG
    segments = (client, FOUNDRY, DCAI, OTHER)
    if day < NEX_INTEGRATION_START:
        segments += (NEX,)
    return [name for name, _ in segments] + [ELIMINATIONS]


def compose(filing, request):
    result = Composition()
    foundry = find(filing, request, REVENUE, {**OPERATING, SEGMENT: FOUNDRY[1]})
    if isinstance(foundry, Missing):
        # FY2023 的原申報仍是 IFS、獨立 Mobileye 與剩餘 Other；不用新模型改寫。
        for name, member in LEGACY_SEGMENTS:
            put(result, "category", name, find(filing, request, REVENUE, {**LEGACY_OPERATING, SEGMENT: member}))
    else:
        client = CCPG
        client_term = find(filing, request, REVENUE, {**OPERATING, SEGMENT: client[1]})
        if isinstance(client_term, Missing):
            client = CCG
            client_term = find(filing, request, REVENUE, {**OPERATING, SEGMENT: client[1]})
        put(result, "category", client[0], client_term)
        put(result, "category", FOUNDRY[0], foundry)
        put(result, "category", DCAI[0], find(filing, request, REVENUE, {**OPERATING, SEGMENT: DCAI[1]}))
        # 2024 Q1–Q3：AllOtherSegmentsMember 只代表剩餘 Other，優先取申報明列的合計。
        other = find(filing, request, REVENUE, {**OPERATING, SEGMENT: "intc:AlteraMobileyeAndOtherMember"})
        if isinstance(other, Missing):
            other = find(filing, request, REVENUE, {**OPERATING, SEGMENT: OTHER[1]})
        put(result, "category", OTHER[0], other)
        nex = find(filing, request, REVENUE, {**OPERATING, SEGMENT: NEX[1]})
        if not isinstance(nex, Missing):
            put(result, "category", NEX[0], nex)
        put(result, "reconciling", ELIMINATIONS, find(filing, request, REVENUE, {CONSOLIDATION: "us-gaap:IntersegmentEliminationMember"}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
