"""PLD：營運分部（不動產、Strategic Capital）。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（不動產營運、Strategic Capital），不是地區。
"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "PLD"
VIEW = "business_segment"
TOTAL = "Total revenues"

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
OPERATING = {"srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}
SEGMENTS = (
    ("Real estate segment", "pld:RealEstateOperationsSegmentMember"),
    ("Strategic capital segment", "pld:StrategicCapitalSegmentMember"),
)


def categories(day):
    return [name for name, _ in SEGMENTS]


def compose(filing, request):
    result = Composition()
    for name, member in SEGMENTS:
        put(result, "category", name, find(filing, request, REVENUE, {**OPERATING, SEGMENT: member}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
