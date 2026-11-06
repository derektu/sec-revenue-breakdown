"""KO：營運類型（Concentrate operations、Finished product operations）。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, define, effective, fact

REVENUE = "us-gaap:Revenues"
PRODUCT = "srt:ProductOrServiceAxis"
# FY2023 10-K（期末 2023-12-31）以公司自訂 concept 標示兩類營收；其前後的申報都用 us-gaap:Revenues × ProductOrServiceAxis。
# 定義以申報期末日切換，相鄰的生效期間首尾相接。
FY2023_10K = ("2023-09-30", "2023-12-31")


def operations(member: str, custom_concept: str):
    return (
        define(fact(REVENUE, {PRODUCT: member}), effective(None, "2023-09-29")),
        define(fact(custom_concept), effective(*FY2023_10K)),
        define(fact(REVENUE, {PRODUCT: member}), effective("2024-01-01", None)),
    )


SPEC = CompanySpec(
    ticker="KO",
    view="product",
    categories=(
        Category(
            "Concentrate operations",
            *operations("ko:ConcentrateOperationsMember", "ko:Netoperatingrevenuesrelatedtoconcentrateoperations"),
        ),
        Category(
            "Finished product operations",
            *operations("ko:FinishedProductOperationsMember", "ko:Netoperatingrevenuesrelatedtofinishedproductoperations"),
        ),
    ),
    total=Category("Net operating revenues", fact(REVENUE)),
)
