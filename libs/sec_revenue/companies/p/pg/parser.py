"""PG：五個營運分部（Fabric & Home Care、Baby, Feminine & Family Care、Beauty、Health Care、Grooming）與 Corporate。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（織物與居家清潔、嬰兒／女性／家庭用紙、美容、保健、刮鬍），不是地區。
"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "PG"
VIEW = "business_segment"
TOTAL = "Total Company"

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
OPERATING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember"}
# 分部表的同一列在不同申報用不同成員，FY2025 Q2 10-Q（期末 2024-12-31）起另帶 OperatingSegmentsMember；
# 每份申報都找每一種寫法。
SEGMENTS = (
    (
        "Fabric & Home Care",
        ("pg:FabricHomeCareSegmentMember", "pg:FabricandHomeCareMember", "pg:FabricHomeCareMember"),
    ),
    (
        "Baby, Feminine & Family Care",
        (
            "pg:BabyFeminineFamilyCareSegmentMember",
            "pg:BabyFeminineandFamilyCareSegmentMember",
            "pg:BabyFeminineFamilyCareMember",
        ),
    ),
    ("Beauty", ("pg:BeautySegmentMember",)),
    ("Health Care", ("pg:HealthCareSegmentMember", "pg:HealthCareSegMember")),
    ("Grooming", ("pg:GroomingSegmentMember", "pg:GroomingMember")),
)
CORPORATE = "Corporate"


def categories(day):
    return [name for name, _ in SEGMENTS] + [CORPORATE]


def compose(filing, request):
    result = Composition()
    for name, members in SEGMENTS:
        variants = []
        for member in members:
            variants += [(REVENUE, {**OPERATING, SEGMENT: member}), (REVENUE, {SEGMENT: member})]
        put(result, "category", name, one_of(filing, request, *variants))
    put(
        result,
        "category",
        CORPORATE,
        one_of(
            filing,
            request,
            (REVENUE, {CONSOLIDATION: "us-gaap:CorporateNonSegmentMember"}),
            (REVENUE, {SEGMENT: "us-gaap:CorporateMember"}),
        ),
    )
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
