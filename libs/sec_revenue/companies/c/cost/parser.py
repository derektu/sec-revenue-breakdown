"""COST：產品別營收（Foods and Sundries、Non-Foods、Warehouse Ancillary and Other Businesses、Fresh Foods 四類商品淨銷售額，加 Membership fees）。說明見 parser.md。"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "COST"
VIEW = "product"
TOTAL = "Total revenue"
# 季度是 12／12／12／16 週（53 週年度的 Q4 是 17 週），單季 84–119 天；10-Q 的累計欄是 24 週與 36 週；年度 52 或 53 週。
# 範圍取涵蓋這些長度的最窄範圍，理由見 parser.md 的「期別與推算」。
DURATION_DAYS = {
    "quarter": (84, 119),
    "six_months": (168, 168),
    "nine_months": (252, 252),
    "annual": (364, 371),
}

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
PRODUCT = "srt:ProductOrServiceAxis"
# 同一類商品在 10-K 與 10-Q 用不同成員（10-K `FoodandSundries`、`FreshFood`；10-Q `FoodsAndSundries`、`FreshFoods`），每種寫法都找。
CATEGORIES = (
    ("Foods and Sundries", ("cost:FoodsAndSundriesMember", "cost:FoodandSundriesMember")),
    ("Non-Foods", ("cost:NonFoodsMember",)),
    ("Warehouse Ancillary and Other Businesses", ("cost:OtherMember",)),
    ("Fresh Foods", ("cost:FreshFoodsMember", "cost:FreshFoodMember")),
    ("Membership fees", ("us-gaap:MembershipMember",)),
)


def categories(day):
    return [name for name, _ in CATEGORIES]


def compose(filing, request):
    result = Composition()
    for name, members in CATEGORIES:
        put(result, "category", name, one_of(filing, request, *((REVENUE, {PRODUCT: m}) for m in members)))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
