"""AAPL：產品別營收（iPhone、Mac、iPad、Wearables, Home and Accessories、Services）。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, fact

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
PRODUCT = "srt:ProductOrServiceAxis"

SPEC = CompanySpec(
    ticker="AAPL",
    view="product",
    categories=(
        Category("iPhone", fact(REVENUE, {PRODUCT: "aapl:IPhoneMember"})),
        Category("Mac", fact(REVENUE, {PRODUCT: "aapl:MacMember"})),
        Category("iPad", fact(REVENUE, {PRODUCT: "aapl:IPadMember"})),
        Category(
            "Wearables, Home and Accessories",
            fact(REVENUE, {PRODUCT: "aapl:WearablesHomeandAccessoriesMember"}),
        ),
        Category("Services", fact(REVENUE, {PRODUCT: "us-gaap:ServiceMember"})),
    ),
    total=Category("Total net sales", fact(REVENUE)),
)
