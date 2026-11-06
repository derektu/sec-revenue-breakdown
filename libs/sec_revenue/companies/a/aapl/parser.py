"""AAPL：產品別營收（iPhone、Mac、iPad、Wearables, Home and Accessories、Services）。說明見 parser.md。"""

from sec_revenue.parser_utils import find, put
from sec_revenue.revenue.contract import Composition

TICKER = "AAPL"
VIEW = "product"
TOTAL = "Total net sales"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
PRODUCT = "srt:ProductOrServiceAxis"
PRODUCTS = (
    ("iPhone", "aapl:IPhoneMember"),
    ("Mac", "aapl:MacMember"),
    ("iPad", "aapl:IPadMember"),
    ("Wearables, Home and Accessories", "aapl:WearablesHomeandAccessoriesMember"),
    ("Services", "us-gaap:ServiceMember"),
)


def categories(day):
    return [name for name, _ in PRODUCTS]


def compose(filing, request):
    result = Composition()
    for name, member in PRODUCTS:
        put(result, "category", name, find(filing, request, REVENUE, {PRODUCT: member}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
