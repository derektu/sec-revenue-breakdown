"""AMZN：產品與服務別營收（Online stores、Physical stores、Third-party seller services、Advertising、Subscription、AWS、Other）。說明見 parser.md。"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "AMZN"
VIEW = "product"
TOTAL = "Consolidated"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
PRODUCT = "srt:ProductOrServiceAxis"
ADVERTISING = "Advertising services"
LINES = (
    ("Online stores", "amzn:OnlineStoresMember"),
    ("Physical stores", "amzn:PhysicalStoresMember"),
    ("Third-party seller services", "amzn:ThirdPartySellerServicesMember"),
    (ADVERTISING, None),
    ("Subscription services", "amzn:SubscriptionServicesMember"),
    ("AWS", "amzn:AmazonWebServicesMember"),
    ("Other", "amzn:OtherServicesMember"),
)


def categories(day):
    return [name for name, _ in LINES]


def compose(filing, request):
    result = Composition()
    for name, member in LINES:
        if name == ADVERTISING:
            # 10-Q 標 amzn:AdvertisingServicesMember，10-K 標 us-gaap:AdvertisingMember。
            term = one_of(
                filing,
                request,
                (REVENUE, {PRODUCT: "amzn:AdvertisingServicesMember"}),
                (REVENUE, {PRODUCT: "us-gaap:AdvertisingMember"}),
            )
        else:
            term = find(filing, request, REVENUE, {PRODUCT: member})
        put(result, "category", name, term)
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
