"""AVGO：業務分部營收（Semiconductor solutions、Infrastructure software）。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是半導體與基礎設施軟體業務，不是地區。
"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "AVGO"
VIEW = "business_segment"
TOTAL = "Total net revenue"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
SEGMENTS = (
    ("Semiconductor solutions", "avgo:SemiconductorSolutionsMember"),
    ("Infrastructure software", "avgo:InfrastructureSoftwareMember"),
)


def categories(day):
    return [name for name, _ in SEGMENTS]


def compose(filing, request):
    result = Composition()
    for name, member in SEGMENTS:
        put(result, "category", name, find(filing, request, REVENUE, {SEGMENT: member}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
