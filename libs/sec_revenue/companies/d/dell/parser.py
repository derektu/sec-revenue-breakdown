"""DELL：ISG、CSG 與各期原申報的其他業務分類；無調節項。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別，不是地區。
"""

from sec_revenue.parser_utils import Missing, find, put
from sec_revenue.revenue.contract import Composition

TICKER = "DELL"
VIEW = "business_segment"
TOTAL = "Total consolidated net revenue"

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
CORPORATE = {CONSOLIDATION: "us-gaap:CorporateNonSegmentMember"}
OTHER_BUSINESSES = {**OPERATING, SEGMENT: "us-gaap:AllOtherSegmentsMember"}
SEGMENTS = (
    ("Infrastructure Solutions Group", "dell:InfrastructureSolutionsGroupMember"),
    ("Client Solutions Group", "dell:ClientSolutionsMember"),
)
# FY2025 10-K（0001571996-25-000034，期末 2025-01-31）首採合併分類；Q4 起日為 2024-11-02。
CORPORATE_AND_OTHER_START = "2024-11-02"


def categories(day):
    names = [name for name, _ in SEGMENTS]
    if day < CORPORATE_AND_OTHER_START:
        return names + ["Unallocated transactions", "Other businesses"]
    return names + ["Corporate and other"]


def compose(filing, request):
    result = Composition()
    for name, member in SEGMENTS:
        put(result, "category", name, find(filing, request, REVENUE, {**OPERATING, SEGMENT: member}))
    other = find(filing, request, REVENUE, OTHER_BUSINESSES)
    if isinstance(other, Missing):
        put(result, "category", "Corporate and other", find(filing, request, REVENUE, CORPORATE))
    else:
        put(result, "category", "Unallocated transactions", find(filing, request, REVENUE, CORPORATE))
        put(result, "category", "Other businesses", other)
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
