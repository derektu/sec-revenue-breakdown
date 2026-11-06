"""HD：商品類別（Hardlines、Building Materials、Décor）與 Other。說明見 parser.md。"""

from sec_revenue.revenue.spec import Category, CompanySpec, define, effective, fact, one_of

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
PRODUCT = "srt:ProductOrServiceAxis"
OPERATING = {"srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}
# 定義以申報期末日切換，相鄰的生效期間首尾相接：
# - FY2024 Q1（期末 2024-04-28）以前只有單一分部，商品類別 fact 不帶分部軸。
# - FY2024 Q2 起分成 Primary 與 Other 兩個分部，商品類別只拆 Primary，成員是 hd:PrimarySegmentMember
#   （帶或不帶 ConsolidationItemsAxis）。
# - FY2024 10-K（期末 2025-02-02）以報告分部合計成員標示 Primary。這個成員只在 Primary 是唯一報告分部時等於 Primary，
#   所以只用於這一期。
SINGLE_SEGMENT = (None, "2024-04-28")
TWO_SEGMENTS = ("2024-04-29", "2025-02-01")
FY2024_10K = ("2025-02-02", "2025-02-02")
PRIMARY_FROM = "2025-02-03"


def line(*members: str):
    """`members` 是商品類別成員的各種寫法（只有單一分部期間的 Décor 有兩種）。"""
    single = [fact(REVENUE, {PRODUCT: m}) for m in members]
    member = members[0]
    primary = one_of(
        fact(REVENUE, {**OPERATING, PRODUCT: member, SEGMENT: "hd:PrimarySegmentMember"}),
        fact(REVENUE, {PRODUCT: member, SEGMENT: "hd:PrimarySegmentMember"}),
    )
    return (
        define(single[0] if len(single) == 1 else one_of(*single), effective(*SINGLE_SEGMENT)),
        define(primary, effective(*TWO_SEGMENTS)),
        define(fact(REVENUE, {PRODUCT: member, SEGMENT: "us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember"}), effective(*FY2024_10K)),
        define(primary, effective(PRIMARY_FROM, None)),
    )


SPEC = CompanySpec(
    ticker="HD",
    view="product",
    categories=(
        Category("Hardlines", *line("hd:MajorProductLineHardlinesMember")),
        Category("Building Materials", *line("hd:MajorProductLineBuildingMaterialsMember")),
        # FY2023 10-K 的 Décor 成員是 hd:MajorProductLineDecorMember，其他申報是 hd:MajorProductLineDcorMember。
        Category("Décor", *line("hd:MajorProductLineDcorMember", "hd:MajorProductLineDecorMember")),
        # FY2024 Q3 10-Q 以前用 hd:OtherSegmentMember；之後的申報用 us-gaap:AllOtherSegmentsMember。
        Category(
            "Other",
            define(
                one_of(fact(REVENUE, {SEGMENT: "us-gaap:AllOtherSegmentsMember"}), fact(REVENUE, {SEGMENT: "hd:OtherSegmentMember"})),
                effective(TWO_SEGMENTS[0], None),
            ),
        ),
    ),
    total=Category("Net sales", fact(REVENUE)),
)
