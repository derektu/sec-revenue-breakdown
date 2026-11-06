"""LLY：治療領域產品別營收，五類為 Diabetes and obesity／Cardiometabolic Health、Oncology、Immunology、Neuroscience、Other。說明見 parser.md。"""

from sec_revenue.parser_utils import Missing, find, one_of, put
from sec_revenue.revenue.contract import Composition

TICKER = "LLY"
VIEW = "product"
TOTAL = "Revenue"

REVENUE = "us-gaap:Revenues"
PRODUCT = "srt:ProductOrServiceAxis"
GEOGRAPHY = "srt:StatementGeographicalAxis"
REGIONS = ("country:US", "us-gaap:NonUsMember")
# 2024 Q2 10-Q（0000059478-24-000187，期末 2024-06-30）首次列 Cardiometabolic Health。
RENAMED_FROM = "2024-04-01"
PRODUCTS = (
    ("Oncology", ("lly:OncologyMember",)),
    ("Immunology", ("lly:ImmunologyMember",)),
    ("Neuroscience", ("lly:NeuroscienceMember",)),
    ("Other", ("lly:OtherProductTotalMember", "us-gaap:ProductAndServiceOtherMember")),
)


def categories(day):
    first = "Diabetes and obesity" if day < RENAMED_FROM else "Cardiometabolic Health"
    return [first] + [name for name, _ in PRODUCTS]


def _revenue_terms(filing, request, members):
    direct = one_of(filing, request, *((REVENUE, {PRODUCT: member}) for member in members))
    if not isinstance(direct, Missing):
        return (direct,)
    return tuple(
        one_of(filing, request, *((REVENUE, {PRODUCT: member, GEOGRAPHY: region}) for member in members))
        for region in REGIONS
    )


def compose(filing, request):
    result = Composition()
    first = _revenue_terms(filing, request, ("lly:CardiometabolicHealthMember",))
    if any(isinstance(term, Missing) for term in first):
        name = "Diabetes and obesity"
        first = _revenue_terms(filing, request, ("lly:DiabetesAndObesityMember",))
    else:
        name = "Cardiometabolic Health"
    put(result, "category", name, *first)
    for name, members in PRODUCTS:
        put(result, "category", name, *_revenue_terms(filing, request, members))
    put(result, "total", TOTAL, find(filing, request, REVENUE))
    return result
