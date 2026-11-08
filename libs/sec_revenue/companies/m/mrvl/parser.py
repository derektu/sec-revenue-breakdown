"""MRVL：終端市場別營收，依原申報由五類轉為 Data center、Communications and other。說明見 parser.md。"""

from sec_revenue.parser_utils import Missing, find, put
from sec_revenue.revenue.contract import Composition

TICKER = "MRVL"
VIEW = "product"
TOTAL = "Net revenue"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
PRODUCT = "srt:ProductOrServiceAxis"
FIVE_MARKETS = (
    ("Data center", "mrvl:DataCenterMember"),
    ("Enterprise networking", "mrvl:EnterpriseNetworkingMember"),
    ("Carrier infrastructure", "mrvl:CarrierInfrastructureMember"),
    ("Automotive/industrial", "mrvl:AutomotiveAndIndustrialMember"),
    ("Consumer", "mrvl:ConsumerMember"),
)
TWO_MARKETS = (
    ("Data center", "mrvl:DataCenterMember"),
    ("Communications and other", "mrvl:CommunicationsAndOtherMember"),
)
# FY2026 10-K（0001835632-26-000011，期末 2026-01-31）自 Q4 起合併四個非資料中心市場。
TWO_MARKETS_START = "2025-11-02"


def categories(day):
    markets = FIVE_MARKETS if day < TWO_MARKETS_START else TWO_MARKETS
    return [name for name, _ in markets]


def compose(filing, request):
    other = find(filing, request, REVENUE, {PRODUCT: "mrvl:CommunicationsAndOtherMember"})
    markets = FIVE_MARKETS if isinstance(other, Missing) else TWO_MARKETS
    result = Composition()
    for name, member in markets:
        put(result, "category", name, find(filing, request, REVENUE, {PRODUCT: member}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
