"""MCD：營收類型（Franchised restaurants、Company-owned and operated restaurants、Other revenues）。說明見 parser.md。"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "MCD"
VIEW = "product"
TOTAL = "Total revenues"

FRANCHISED = "Franchised restaurants"
COMPANY_OPERATED = "Company-owned and operated restaurants"
OTHER = "Other revenues"


def categories(day):
    return [FRANCHISED, COMPANY_OPERATED, OTHER]


def compose(filing, request):
    result = Composition()
    put(result, "category", FRANCHISED, find(filing, request, "mcd:Revenuesfromfranchisedrestaurants"))
    # 直營餐廳營收在申報之間來回使用兩個公司自訂 concept。
    put(
        result,
        "category",
        COMPANY_OPERATED,
        one_of(filing, request, ("mcd:SalesbyCompanyoperatedrestaurants", None), ("mcd:SalesByCompanyOwnedAndOperatedRestaurants", None)),
    )
    put(result, "category", OTHER, find(filing, request, "mcd:OtherRevenues"))
    put(result, "total", TOTAL, find(filing, request, "us-gaap:Revenues"))
    return result
