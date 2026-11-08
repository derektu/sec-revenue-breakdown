"""CSCO：依申報列示產品與服務別，FY2024 起為五類；舊結構另列 Other Products 調節項。"""

from sec_revenue.parser_utils import Missing, find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "CSCO"
VIEW = "product"
TOTAL = "Total revenue"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
PRODUCT = "srt:ProductOrServiceAxis"
PRODUCTS = (
    ("Networking", ("csco:NetworkingMember", "csco:NetworkingRevenueMember")),
    ("Services", ("us-gaap:ServiceMember",)),
    ("Security", ("csco:SecurityMember", "csco:SecurityRevenueMember")),
    ("Collaboration", ("csco:CollaborationMember",)),
    ("Observability", ("csco:ObservabilityMember", "csco:ObservabilityRevenueMember")),
)
OLD_PRODUCTS = (
    ("Secure, Agile Networks", "csco:SecureAgileNetworksMember"),
    ("Internet for the Future", "csco:InternetForTheFutureMember"),
    ("Collaboration", "csco:CollaborationMember"),
    ("End-to-End Security", "csco:EndToEndSecurityMember"),
    ("Optimized Application Experiences", "csco:OptimizedApplicationExperiencesMember"),
    ("Services", "us-gaap:ServiceMember"),
)
OTHER = "Other Products"
# FY2024 Q1 10-Q（0000858877-23-000031，期末 2023-10-28）自該季起日採五類。
FIRST_FIVE = "2023-07-30"
# 同份 10-Q 起將 End-to-End Security 改稱 Security；FY2023、FY2022 同值證據見 parser.md。
FORMER_NAMES = {"Security": ("End-to-End Security",)}


def categories(day):
    if day >= FIRST_FIVE:
        return [name for name, _ in PRODUCTS]
    return [name for name, _ in OLD_PRODUCTS] + [OTHER]


def compose(filing, request):
    networking = one_of(
        filing, request, *((REVENUE, {PRODUCT: member}) for member in PRODUCTS[0][1])
    )
    result = Composition()
    if isinstance(networking, Missing):
        for name, member in OLD_PRODUCTS:
            put(result, "category", name, find(filing, request, REVENUE, {PRODUCT: member}))
        put(result, "reconciling", OTHER, find(filing, request, REVENUE, {PRODUCT: "csco:OtherProductsMember"}))
    else:
        for name, members in PRODUCTS:
            put(result, "category", name, one_of(
                filing, request, *((REVENUE, {PRODUCT: member}) for member in members)
            ))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
