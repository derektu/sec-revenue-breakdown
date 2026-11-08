"""MU：依原申報列示業務分部，All Other 列分類，新結構另列 Unallocated 調節項。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別，不是地區。說明見 parser.md。
"""

from sec_revenue.parser_utils import Missing, find, put
from sec_revenue.revenue.contract import Composition

TICKER = "MU"
VIEW = "business_segment"
TOTAL = "Total revenue"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
ORIGINAL_SEGMENTS = (
    ("CNBU", "mu:CNBUMember"),
    ("MBU", "mu:MBUMember"),
    ("EBU", "mu:EBUMember"),
    ("SBU", "mu:SBUMember"),
    ("All Other", "us-gaap:AllOtherSegmentsMember"),
)
NEW_SEGMENTS = (
    ("CMBU", "mu:CMBUMember"),
    ("CDBU", "mu:CDBUMember"),
    ("MCBU", "mu:MCBUMember"),
    ("AEBU", "mu:AEBUMember"),
    ("All Other", "us-gaap:AllOtherSegmentsMember"),
)
# FY2025 10-K（0000723125-25-000028，期末 2025-08-28）說明重組於 Q4 生效。
# 最後一份舊結構主申報 FY2025 Q3 期末為 2025-05-29，故從隔日起切換。
FIRST_NEW_SEGMENTS = "2025-05-30"


def categories(day):
    segments = NEW_SEGMENTS if day >= FIRST_NEW_SEGMENTS else ORIGINAL_SEGMENTS
    return [name for name, _ in segments] + (["Unallocated"] if day >= FIRST_NEW_SEGMENTS else [])


def compose(filing, request):
    first_new = find(filing, request, REVENUE, {**OPERATING, SEGMENT: NEW_SEGMENTS[0][1]})
    new_structure = not isinstance(first_new, Missing)
    segments = NEW_SEGMENTS if new_structure else ORIGINAL_SEGMENTS
    dimensions = OPERATING if new_structure else {}
    result = Composition()
    for name, member in segments:
        put(result, "category", name, find(filing, request, REVENUE, {**dimensions, SEGMENT: member}))
    if new_structure:
        put(result, "reconciling", "Unallocated", find(filing, request, REVENUE, {CONSOLIDATION: "us-gaap:CorporateNonSegmentMember"}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
