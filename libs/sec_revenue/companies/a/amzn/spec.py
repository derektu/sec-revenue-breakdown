"""AMZN：產品與服務別營收（Online stores、Physical stores、Third-party seller services、Advertising、Subscription、AWS、Other）。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, fact, one_of

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
PRODUCT = "srt:ProductOrServiceAxis"


def line(member: str):
    return fact(REVENUE, {PRODUCT: member})


SPEC = CompanySpec(
    ticker="AMZN",
    view="product",
    categories=(
        Category("Online stores", line("amzn:OnlineStoresMember")),
        Category("Physical stores", line("amzn:PhysicalStoresMember")),
        Category("Third-party seller services", line("amzn:ThirdPartySellerServicesMember")),
        # 10-K 標 us-gaap:AdvertisingMember，10-Q 標 amzn:AdvertisingServicesMember。
        Category("Advertising services", one_of(line("amzn:AdvertisingServicesMember"), line("us-gaap:AdvertisingMember"))),
        Category("Subscription services", line("amzn:SubscriptionServicesMember")),
        Category("AWS", line("amzn:AmazonWebServicesMember")),
        Category("Other", line("amzn:OtherServicesMember")),
    ),
    total=Category("Consolidated", fact(REVENUE)),
)
