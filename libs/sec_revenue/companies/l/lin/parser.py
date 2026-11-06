"""LIN：Industrial Gases（三個地區分部加總）、Engineering、Other。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員有工業氣體業務依地區劃分的三個報告分部，以及業務別的 Engineering、Other；
三個地區分部只以加總成 Industrial Gases 出現。
"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "LIN"
VIEW = "business_segment"
TOTAL = "Total"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
OPERATING = {"srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}
INDUSTRIAL_GASES = ("lin:AmericasSegmentMember", "lin:EMEASegmentMember", "lin:APACSegmentMember")
SEGMENTS = (
    ("Engineering", "lin:EngineeringSegmentMember"),
    ("Other", "us-gaap:CorporateAndOtherMember"),
)


def categories(day):
    return ["Industrial Gases"] + [name for name, _ in SEGMENTS]


def _segment(filing, request, member):
    return find(filing, request, REVENUE, {**OPERATING, SEGMENT: member})


def compose(filing, request):
    result = Composition()
    # 工業氣體業務依地區分成三個報告分部；觀點不做地區拆分，三個 fact 相加成一類。
    put(result, "category", "Industrial Gases", *(_segment(filing, request, m) for m in INDUSTRIAL_GASES))
    for name, member in SEGMENTS:
        put(result, "category", name, _segment(filing, request, member))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
