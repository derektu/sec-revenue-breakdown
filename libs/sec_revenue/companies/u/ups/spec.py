"""UPS：營運分部（U.S. Domestic Package、International Package）與 Supply Chain Solutions／Other revenues。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, define, effective, fact, one_of

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
OPERATING = {"srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}
CORPORATE = "srt:ConsolidationItemsAxis"
# 定義以申報期末日切換，相鄰的生效期間首尾相接：
# - 2025 年起包裹分部改以 OperatingSegmentsMember 搭配新成員標記；Supply Chain Solutions 不再是報告分部，
#   分部表的營收調節列為 Other revenues，分界在財年起點。
# - 更早的申報用舊成員：2023 年度 10-K 的包裹分部帶 OperatingSegmentsMember，其餘申報只帶分部軸。
FY2023_10K = ("2023-10-01", "2023-12-31")
OLD_MEMBERS = ("2024-01-01", "2024-12-31")
NEW_MEMBERS_FROM = "2025-01-01"


def package(old: str, new: str):
    return (
        define(fact(REVENUE, {SEGMENT: old}), effective(None, "2023-09-30")),
        define(fact(REVENUE, {**OPERATING, SEGMENT: old}), effective(*FY2023_10K)),
        define(fact(REVENUE, {SEGMENT: old}), effective(*OLD_MEMBERS)),
        define(fact(REVENUE, {**OPERATING, SEGMENT: new}), effective(NEW_MEMBERS_FROM, None)),
    )


SPEC = CompanySpec(
    ticker="UPS",
    view="business_segment",
    categories=(
        Category("U.S. Domestic Package", *package("ups:USDomesticPackageMember", "ups:U.S.DomesticPackageSegmentMember")),
        Category("International Package", *package("ups:InternationalPackageMember", "ups:InternationalSegmentMember")),
        Category(
            "Supply Chain Solutions",
            define(fact(REVENUE, {SEGMENT: "ups:SupplyChainSolutionsMember"}), effective(None, OLD_MEMBERS[1])),
        ),
        # 2025 年各 10-Q 以兩種寫法標示同一個數字，FY2025 10-K 起只有 CorporateNonSegmentMember。
        Category(
            "Other revenues",
            define(
                one_of(
                    fact(REVENUE, {CORPORATE: "us-gaap:CorporateNonSegmentMember"}),
                    fact(REVENUE, {SEGMENT: "ups:SupplyChainSolutionsMember"}),
                ),
                effective(NEW_MEMBERS_FROM, None),
            ),
        ),
    ),
    total=Category("Consolidated revenue", fact(REVENUE)),
)
