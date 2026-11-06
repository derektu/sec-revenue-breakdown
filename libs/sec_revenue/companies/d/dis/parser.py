"""DIS：業務分部營收總額，含分部間交易；Eliminations 為調節項。說明見 parser.md。

us-gaap:StatementBusinessSegmentsAxis 的成員是娛樂、體驗與體育等業務別，不是地區。
"""

from sec_revenue.parser_utils import Missing, find, put
from sec_revenue.revenue.contract import Composition

TICKER = "DIS"
VIEW = "business_segment"
TOTAL = "Revenues"

REVENUE = "us-gaap:Revenues"
SEGMENT = "us-gaap:StatementBusinessSegmentsAxis"
SEGMENTS = (
    ("Entertainment", "dis:EntertainmentSegmentMember"),
    ("Experiences", "dis:ExperiencesSegmentMember"),
    ("Sports", "dis:SportsSegmentMember"),
)
OLD_SEGMENTS = (
    ("Disney Media and Entertainment Distribution", "dis:DisneyMediaAndEntertainmentDistributionMember"),
    ("Disney Parks, Experiences and Products", "dis:DisneyParksExperiencesAndProductsMember"),
)
ELIMINATIONS = "Eliminations"
# FY2023 10-K（0001744489-23-000216，期末 2023-09-30）首採三分部；Q4 起日為 2023-07-02。
THREE_SEGMENTS_START = "2023-07-02"


def categories(day):
    if day < THREE_SEGMENTS_START:
        return [name for name, _ in OLD_SEGMENTS]
    return [name for name, _ in SEGMENTS] + [ELIMINATIONS]


def compose(filing, request):
    old_structure = not isinstance(find(filing, request, REVENUE, {SEGMENT: OLD_SEGMENTS[0][1]}), Missing)
    result = Composition()
    for name, member in OLD_SEGMENTS if old_structure else SEGMENTS:
        put(result, "category", name, find(filing, request, REVENUE, {SEGMENT: member}))
    if not old_structure:
        put(result, "reconciling", ELIMINATIONS, find(filing, request, REVENUE, {SEGMENT: "dis:SegmentEliminationsMember"}))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
