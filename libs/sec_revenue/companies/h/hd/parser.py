"""HD：商品類別（Hardlines、Building Materials、Décor）與 Other。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是業務別（Primary 與 Other 分部），不是地區。
"""

from sec_revenue.parser_utils import find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "HD"
VIEW = "product"
TOTAL = "Net sales"

REVENUE = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
PRODUCT = "srt:ProductOrServiceAxis"
OPERATING = {"srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}
PRIMARY = {SEGMENT: "hd:PrimarySegmentMember"}
# FY2024 10-K 以報告分部合計成員標示 Primary；這個成員只在 Primary 是唯一報告分部時等於 Primary，所以只用於這一份申報。
AGGREGATION = {SEGMENT: "us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember"}
# 商品類別成員的各種寫法；只有 FY2023 10-K 的 Décor 是 hd:MajorProductLineDecorMember，其他申報是第一種寫法。
LINES = (
    ("Hardlines", ("hd:MajorProductLineHardlinesMember",)),
    ("Building Materials", ("hd:MajorProductLineBuildingMaterialsMember",)),
    ("Décor", ("hd:MajorProductLineDcorMember", "hd:MajorProductLineDecorMember")),
)
OTHER = "Other"
# 期末 2024-04-28 的 FY2024 Q1 10-Q 是最後一份只有單一分部的申報：商品類別 fact 不帶分部軸，沒有 Other。
LAST_SINGLE_SEGMENT = "2024-04-28"
FY2024_10K = "2025-02-02"


def categories(day):
    names = [name for name, _ in LINES]
    return names + [OTHER] if day > LAST_SINGLE_SEGMENT else names


def compose(filing, request):
    period = filing.report_date
    result = Composition()
    for name, members in LINES:
        if period <= LAST_SINGLE_SEGMENT:
            variants = [(REVENUE, {PRODUCT: m}) for m in members]
            term = find(filing, request, *variants[0]) if len(variants) == 1 else one_of(filing, request, *variants)
        elif period == FY2024_10K:
            term = find(filing, request, REVENUE, {PRODUCT: members[0], **AGGREGATION})
        else:
            # Primary 的商品類別 fact 在部分申報另帶 ConsolidationItemsAxis。
            term = one_of(
                filing,
                request,
                (REVENUE, {**OPERATING, PRODUCT: members[0], **PRIMARY}),
                (REVENUE, {PRODUCT: members[0], **PRIMARY}),
            )
        put(result, "category", name, term)
    if period > LAST_SINGLE_SEGMENT:
        # FY2024 Q3 10-Q 以前用 hd:OtherSegmentMember，之後的申報用 us-gaap:AllOtherSegmentsMember。
        put(
            result,
            "category",
            OTHER,
            one_of(filing, request, (REVENUE, {SEGMENT: "us-gaap:AllOtherSegmentsMember"}), (REVENUE, {SEGMENT: "hd:OtherSegmentMember"})),
        )
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
