"""MCD：營收類型（Franchised restaurants、Company-owned and operated restaurants、Other revenues）。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, fact, one_of

SPEC = CompanySpec(
    ticker="MCD",
    view="product",
    categories=(
        Category("Franchised restaurants", fact("mcd:Revenuesfromfranchisedrestaurants")),
        # 直營餐廳營收在申報之間來回使用兩個公司自訂 concept。
        Category(
            "Company-owned and operated restaurants",
            one_of(fact("mcd:SalesbyCompanyoperatedrestaurants"), fact("mcd:SalesByCompanyOwnedAndOperatedRestaurants")),
        ),
        Category("Other revenues", fact("mcd:OtherRevenues")),
    ),
    total=Category("Total revenues", fact("us-gaap:Revenues")),
)
