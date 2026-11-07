"""GOOGL：營收類型別（Google Services 的四項產品、Google Cloud、Other Bets、Hedging gains (losses)）。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（Google Services、Google Cloud、Other Bets），不是地區。
"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "GOOGL"
VIEW = "product"
TOTAL = "Total revenues"

CONTRACT = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
PRODUCT = "srt:ProductOrServiceAxis"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
SERVICES = "goog:GoogleServicesMember"
HEDGING = "Hedging gains (losses)"
# 依對照來源（Stock Analysis）的順序；Google Services 的產品帶產品軸與分部軸，Cloud 與 Other Bets 只帶分部軸。
LINES = (
    ("Google Search & other", {PRODUCT: "goog:GoogleSearchOtherMember", SEGMENT: SERVICES}),
    ("Google Cloud", {SEGMENT: "goog:GoogleCloudMember"}),
    ("Google subscriptions, platforms, and devices", {PRODUCT: "goog:SubscriptionsPlatformsAndDevicesRevenueMember", SEGMENT: SERVICES}),
    ("YouTube ads", {PRODUCT: "goog:YouTubeAdvertisingRevenueMember", SEGMENT: SERVICES}),
    ("Google Network", {PRODUCT: "goog:GoogleNetworkMember", SEGMENT: SERVICES}),
    ("Other Bets", {SEGMENT: "us-gaap:AllOtherSegmentsMember"}),
)


def categories(day):
    return [name for name, _ in LINES] + [HEDGING]


def compose(filing, request):
    result = Composition()
    for name, dimensions in LINES:
        put(result, "category", name, find(filing, request, CONTRACT, dimensions))
    # 到期末 2025-03-31 的 10-Q 為止，避險損益標 us-gaap:GainLossOnOilAndGasHedgingActivity、總營收標不帶維度的
    # RevenueFromContractWithCustomerExcludingAssessedTax；期末 2025-06-30 的 10-Q 起改標
    # us-gaap:RevenueNotFromContractWithCustomer 與 us-gaap:Revenues。每份申報只有其中一種寫法。
    put(
        result,
        "category",
        HEDGING,
        one_of(
            filing,
            request,
            ("us-gaap:RevenueNotFromContractWithCustomer", None),
            ("us-gaap:GainLossOnOilAndGasHedgingActivity", None),
        ),
    )
    put(result, "total", TOTAL, one_of(filing, request, ("us-gaap:Revenues", None), (CONTRACT, None)))
    return result
