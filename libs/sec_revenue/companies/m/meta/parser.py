"""META：營運分部（Family of Apps、Reality Labs）。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（社群應用、AR／VR 硬體與軟體），不是地區。
"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "META"
VIEW = "business_segment"
TOTAL = "Revenue"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
SEGMENTS = (
    ("Family of Apps", "meta:FamilyOfAppsMember"),
    ("Reality Labs", "meta:RealityLabsMember"),
)


def categories(day):
    return [name for name, _ in SEGMENTS]


def compose(filing, request):
    result = Composition()
    for name, member in SEGMENTS:
        put(result, "category", name, find(filing, request, REVENUE, {SEGMENT: member}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
