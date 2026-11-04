"""既有原始 facts 的受限範圍接合；保留完整維度及每個運算元。"""
import calendar
import copy
import datetime as dt
from decimal import Decimal

from cohort_rule_catalog import R, S, C, P, OP, G
from historical_rule_experiments import fact_error

EVIDENCE = {
    'HD': 'https://www.sec.gov/Archives/edgar/data/354950/000035495025000085/hd-20250202.htm',
    'LLY': 'https://www.sec.gov/Archives/edgar/data/59478/000005947826000013/lly-20251231.htm',
    'KO': 'https://www.sec.gov/Archives/edgar/data/21344/000162828026067844/ko-20261002.htm',
    'COST': 'https://www.sec.gov/Archives/edgar/data/909832/000090983226000093/cost-20260830.htm',
    'UPS': 'https://www.sec.gov/Archives/edgar/data/1090727/000162828026008432/ups-20251231.htm',
    'MCD': 'https://www.sec.gov/Archives/edgar/data/63908/000006390825000012/mcd-20241231.htm',
    'CAT': 'https://www.sec.gov/Archives/edgar/data/18230/000001823026000008/cat-20251231.htm',
}
PRODUCTS = {'Cardiometabolic': 'lly:CardiometabolicHealthMember', 'Oncology': 'lly:OncologyMember',
    'Immunology': 'lly:ImmunologyMember', 'Neuroscience': 'lly:NeuroscienceMember', 'Other': 'us-gaap:ProductAndServiceOtherMember'}
KO_MEMBERS = {'North America': 'ko:NorthAmericaSegmentMember', 'Europe, Middle East, and Africa': 'ko:EuropeMiddleEastAfricaMember',
    'Latin America': 'ko:LatinAmericaSegmentMember', 'Asia Pacific': 'ko:A.PacificMember',
    'Bottling Investments': 'ko:BottlingInvestmentsMember', 'Global Ventures': 'ko:GlobalVenturesMember'}


def normalize_record(ticker, record):
    result = copy.deepcopy(record)
    for f in result['facts']:
        dims = f['dimensions']; new = None
        end = f.get('enddate', '')
        if ticker == 'HD' and f['concept'] == R and '2024-07-28' <= end <= '2026-08-02':
            member = dims.get(P)
            if member in ['hd:MajorProductLineHardlinesMember', 'hd:MajorProductLineBuildingMaterialsMember', 'hd:MajorProductLineDcorMember']:
                if dims in [{P: member, S: 'hd:PrimarySegmentMember'},
                             {P: member, S: 'us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember'}]:
                    new = {P: member, S: 'hd:PrimarySegmentMember', C: OP}
            if dims == {S: 'hd:OtherSegmentMember'}:
                new = {S: 'us-gaap:AllOtherSegmentsMember'}
        if ticker == 'LLY' and f['concept'] == 'us-gaap:Revenues' and end >= '2024-09-30':
            if dims in [{P: 'lly:OtherProductTotalMember'},
                {P: 'lly:OtherProductTotalMember', G: 'country:US'}, {P: 'lly:OtherProductTotalMember', G: 'us-gaap:NonUsMember'}]:
                new = {**dims, P: 'us-gaap:ProductAndServiceOtherMember'}
        if ticker == 'KO' and f['concept'] == 'us-gaap:Revenues' and '2024-09-27' <= end <= '2026-10-02':
            member = dims.get(S)
            if dims == {S: member} and member in set(KO_MEMBERS.values()) | {'ko:PacificMember'}:
                new = {S: 'ko:A.PacificMember' if member == 'ko:PacificMember' else member, C: OP}
            elif dims == {S: 'us-gaap:CorporateMember'}:
                new = {C: 'us-gaap:CorporateNonSegmentMember'}
            elif dims == {S: 'ko:EliminationsMember'}:
                new = {C: 'srt:ConsolidationEliminationsMember'}
        if ticker == 'UPS' and f['concept'] == R and '2024-09-30' <= end <= '2026-06-30':
            if dims == {S: 'ups:USDomesticPackageMember', G: 'country:US'}:
                new = {S: 'ups:U.S.DomesticPackageSegmentMember', C: OP}
            elif dims == {S: 'ups:InternationalPackageMember', G: 'us-gaap:NonUsMember'}:
                new = {S: 'ups:InternationalSegmentMember', C: OP}
            elif dims == {S: 'ups:SupplyChainSolutionsMember', C: OP}:
                new = {S: 'ups:SupplyChainSolutionsMember'}
        if (ticker == 'MCD' and result['filing']['reportDate'] == '2024-09-30' and end == '2024-09-30'
            and f['concept'] == 'us-gaap:Revenues' and dims == {S: 'mcd:U.S.MarketMember'}):
            new = {S: 'mcd:USMarketMember'}
        if ticker == 'CAT' and f['concept'] == 'us-gaap:Revenues' and '2024-09-30' <= end <= '2026-06-30':
            if dims == {S: 'cat:EnergyandTransportationMember', C: OP}:
                new = {S: 'cat:PowerEnergyMember', C: OP}
            elif dims == {C: 'cat:CorporateReconcilingItemsAndEliminationsMember'}:
                new = {C: 'cat:EliminationsAndReconcilingItemsMember'}
        if new is not None:
            f.update(original_dimensions=copy.deepcopy(dims), dimensions=new,
                normalization_rule_id=ticker.lower() + '-explicit-reported-row-scope', normalization_source=EVIDENCE[ticker])
    if ticker == 'LLY':
        result['facts'].extend(global_product_facts(result['facts']))
    if ticker == 'UPS':
        result['facts'].extend(ups_nonreportable_total(result['facts']))
    return result


def ups_nonreportable_total(facts):
    groups = {}
    members = ['ups:ForwardingMember', 'ups:LogisticMember', 'us-gaap:ProductAndServiceOtherMember']
    for f in facts:
        dims = f['dimensions']; product = dims.get(P)
        if f['concept'] == R and f.get('unit') == 'iso4217:USD' and product in members and dims == {S: 'ups:SupplyChainSolutionsMember', P: product}:
            groups.setdefault((f.get('startdate'), f.get('enddate')), {}).setdefault(product, []).append(f)
    out = []
    for (start, end), products in groups.items():
        if any(f['concept'] == R and f['dimensions'] == {S: 'ups:SupplyChainSolutionsMember'}
            and f.get('startdate') == start and f.get('enddate') == end for f in facts):
            continue
        if set(products) != set(members) or any(len({f['value'] for f in fs}) != 1 for fs in products.values()):
            continue
        operands = [products[m][0] for m in members]
        f = copy.deepcopy(operands[0]); f.update(dimensions={S: 'ups:SupplyChainSolutionsMember'},
            value=sum(f['value'] for f in operands), aggregation_evidence=operands,
            normalization_rule_id='ups-nonreportable-scs-products', normalization_source=EVIDENCE['UPS'])
        out.append(f)
    return out


def global_product_facts(facts):
    """只在全球產品列不存在時合計美國及非美國；不覆蓋較精確的直接全球列。"""
    result = []
    for member in PRODUCTS.values():
        periods = {}
        for f in facts:
            if f['concept'] != 'us-gaap:Revenues' or f.get('unit') != 'iso4217:USD':
                continue
            dims = f['dimensions']; geo = dims.get(G)
            if dims == {P: member, G: geo} and geo in ('country:US', 'us-gaap:NonUsMember'):
                key = (f.get('startdate'), f.get('enddate'), f['unit'])
                periods.setdefault(key, {}).setdefault(geo, []).append(f)
        for (start, end, unit), by_geo in periods.items():
            if any(f['concept'] == 'us-gaap:Revenues' and f['dimensions'] == {P: member}
                and (f.get('startdate'), f.get('enddate'), f.get('unit')) == (start, end, unit) for f in facts):
                continue
            if set(by_geo) != {'country:US', 'us-gaap:NonUsMember'} or any(len({f['value'] for f in fs}) != 1 for fs in by_geo.values()):
                continue
            operands = [by_geo[g][0] for g in ['country:US', 'us-gaap:NonUsMember']]
            if not all(isinstance(f['value'], int) for f in operands):
                continue
            fact = copy.deepcopy(operands[0])
            fact.update(dimensions={P: member}, value=sum(f['value'] for f in operands),
                aggregation_evidence=operands, context_id='aggregate:' + str(operands[0].get('context_id')),
                normalization_rule_id='lly-us-plus-non-us-product', normalization_source=EVIDENCE['LLY'])
            result.append(fact)
    return result


def reported_error(fact):
    if fact.get('derivation') == 'annual_minus_nine_months':
        operands = [fact['annual_evidence'], fact['nine_month_evidence']]
    elif fact.get('aggregation_evidence'):
        operands = fact['aggregation_evidence']
    else:
        return fact_error(fact)
    errors = [reported_error(f) for f in operands]
    return None if any(e is None for e in errors) else sum(errors, Decimal(0))


def retail_label(ticker, display, actual):
    if ticker not in ('HD', 'COST'):
        return False
    d = dt.date.fromisoformat(actual)
    if d.weekday() != 6 or not '2024-09-01' <= actual <= '2026-08-30':
        return False
    if ticker == 'HD':
        q = {1: 4, 2: 4, 4: 1, 5: 1, 7: 2, 8: 2, 10: 3, 11: 3}.get(d.month)
        year = d.year - 1 if d.month in (1, 2) else d.year
    else:
        q = {2: 1, 5: 2, 8: 3, 9: 3, 11: 4}.get(d.month)
        year = d.year
    if not q:
        return False
    expected = dt.date(year, q * 3, calendar.monthrange(year, q * 3)[1])
    return dt.datetime.strptime(display, '%b %d, %Y').date() == expected


def coke_label(display, actual):
    d = dt.date.fromisoformat(actual)
    label = dt.datetime.strptime(display, '%b %d, %Y').date()
    return ('2024-09-27' <= actual <= '2026-10-02' and label.month in (3, 6, 9, 12)
        and label.day == calendar.monthrange(label.year, label.month)[1]
        and (label == d or d.weekday() == 4 and abs((label - d).days) <= 7))
