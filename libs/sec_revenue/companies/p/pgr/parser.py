"""PGR：業務分部營收（Personal Lines、Commercial Lines、Property、Other indemnity），加上分部以外的各項營收，依各期申報的分部表與營收調節表。

us-gaap:StatementBusinessSegmentsAxis 的成員是 Personal Lines、Commercial Lines、Property、Other indemnity 保險業務，不是地區。
說明見 parser.md。
"""

from sec_revenue.parser_utils import Missing, find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "PGR"
VIEW = "business_segment"
TOTAL = "Total revenues"
# 10-K 的財報（含分部表與營收調節表）在附件 EX-13，主文件只有 Schedule III；10-Q 沒有這類附件，只讀主文件。
ATTACHMENTS = ("EX-13",)

REVENUES = "us-gaap:Revenues"
SEGMENT_REVENUE = "pgr:PremiumsEarnedFeesAndOtherRevenue"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
CONSOLIDATION = "srt:ConsolidationItemsAxis"
PRODUCT = "srt:ProductOrServiceAxis"
UNDERWRITING = {CONSOLIDATION: "us-gaap:OperatingSegmentsMember", PRODUCT: "pgr:UnderwritingOperationsMember"}
RECONCILING = "us-gaap:MaterialReconcilingItemsMember"

PERSONAL = ("Personal Lines", ("pgr:PersonalLinesSegmentMember",))
COMMERCIAL = ("Commercial Lines", ("pgr:CommercialLinesSegmentMember",))
PROPERTY = ("Property", ("pgr:PropertySegmentMember",))
# 成員在不同申報寫成 OtherIndemnityMember 或 OtherIndemnitySegmentMember，每種寫法都找。
OTHER_INDEMNITY = ("Other indemnity", ("pgr:OtherIndemnityMember", "pgr:OtherIndemnitySegmentMember"))

# 分部營收是已賺保費（us-gaap:Revenues）的結構：Property 是獨立分部；手續費、服務業務、投資是分部以外的營收。
# 營收調節表成員：Investments 在 FY2023 10-K 寫成 InvestmentsMemberMember、2024 年各 10-Q 寫成 Investments1Member。
PREMIUM_SEGMENTS = (PERSONAL, COMMERCIAL, PROPERTY, OTHER_INDEMNITY)
PREMIUM_OTHERS = (
    ("Fees and other revenues", ("pgr:FeesAndOtherRevenuesMember",)),
    ("Service businesses", ("pgr:NonInsuranceServiceBusinessMember",)),
    ("Investments", ("pgr:InvestmentsMemberMember", "pgr:Investments1Member")),
)

# 分部營收是已賺保費加手續費（pgr:PremiumsEarnedFeesAndOtherRevenue）的結構：Property 併入 Personal Lines；
# 分部以外的營收是投資收益、證券已實現損益與服務營收，取不帶維度的合併 fact。
# 始於 FY2024 10-K（0000080661-25-000007，期末 2024-12-31）。
FEE_SEGMENTS = (PERSONAL, COMMERCIAL, OTHER_INDEMNITY)
FEE_OTHERS = (
    ("Investment income", "us-gaap:InterestAndDividendIncomeOperating"),
    ("Net realized gains (losses) on securities", "us-gaap:DebtAndEquitySecuritiesGainLoss"),
    ("Service revenues", "pgr:NonInsuranceServiceRevenues"),
)
# 新結構第一份主申報是 FY2024 10-K，取它涵蓋的 Q4 起日。
FEE_STRUCTURE_START = "2024-10-01"


def categories(day):
    if day >= FEE_STRUCTURE_START:
        return [name for name, _ in FEE_SEGMENTS] + [name for name, _ in FEE_OTHERS]
    return [name for name, _ in PREMIUM_SEGMENTS + PREMIUM_OTHERS]


def _segment(filing, request, concept, members):
    return one_of(filing, request, *((concept, {**UNDERWRITING, SEGMENT: m}) for m in members))


def compose(filing, request):
    result = Composition()
    fee_structure = not isinstance(_segment(filing, request, SEGMENT_REVENUE, PERSONAL[1]), Missing)
    if fee_structure:
        for name, members in FEE_SEGMENTS:
            put(result, "category", name, _segment(filing, request, SEGMENT_REVENUE, members))
        for name, concept in FEE_OTHERS:
            put(result, "category", name, find(filing, request, concept))
    else:
        for name, members in PREMIUM_SEGMENTS:
            put(result, "category", name, _segment(filing, request, REVENUES, members))
        for name, members in PREMIUM_OTHERS:
            put(result, "category", name, one_of(filing, request, *((REVENUES, {CONSOLIDATION: RECONCILING, PRODUCT: m}) for m in members)))
    put(result, "total", TOTAL, find(filing, request, REVENUES))
    return result
