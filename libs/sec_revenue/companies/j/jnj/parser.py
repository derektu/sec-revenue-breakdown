"""JNJ：Innovative Medicine、MedTech 業務分部營收；分部軸成員是業務別，不是地區。說明見 parser.md。"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "JNJ"
VIEW = "business_segment"
TOTAL = "Sales to customers"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
SEGMENTS = (
    ("Innovative Medicine", "jnj:InnovativeMedicineMember"),
    ("MedTech", "jnj:MedTechMember"),
)


def categories(day):
    return [name for name, _ in SEGMENTS]


def compose(filing, request):
    result = Composition()
    for name, member in SEGMENTS:
        put(result, "category", name, find(filing, request, REVENUE, {SEGMENT: member}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
