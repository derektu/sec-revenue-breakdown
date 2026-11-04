"""三十家公司明確候選範圍；命名對照可重用，不等同已人工認證的完整揭露。"""
from historical_rule_experiments import definitions, MAPPINGS
from review_vendor_evidence import reviewed_selector

R = 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'
S = 'us-gaap:StatementBusinessSegmentsAxis'
C = 'srt:ConsolidationItemsAxis'
P = 'srt:ProductOrServiceAxis'
G = 'srt:StatementGeographicalAxis'
OP = 'us-gaap:OperatingSegmentsMember'


def leaf(concept, dimensions, weight=1):
    return {'concept': concept, 'dimensions': dimensions, 'unit': 'iso4217:USD', 'weight': weight}


def rule(*alternatives, role='scope_candidate'):
    return {'alternatives': [[x] if isinstance(x, dict) else x for x in alternatives], 'role': role}


def segment(concept, member, operating=True):
    return leaf(concept, {S: member, **({C: OP} if operating else {})})


def catalog():
    out = {ticker: {'stockanalysis': {}, 'futu': {}} for ticker in (
        'AAPL MSFT NVDA ORCL GOOGL META DIS CMCSA AMZN TSLA HD MCD WMT COST PG KO JNJ UNH LLY JPM BAC BRK-B PGR XOM CVX CAT UPS NEE LIN PLD'.split())}
    for ticker in MAPPINGS:
        rules = definitions(ticker)
        leaves = {s['id'].split(':', 1)[1]: leaf(s['concept'], s['dimensions'])
                  for s in rules['selectors'] if s['period_kind'] == 'Q'}
        for source, mapping in MAPPINGS[ticker].items():
            for label, key in mapping.items():
                terms = [leaves[k] for k in rules['aggregates'][key]] if key in rules['aggregates'] else [leaves[key]]
                out[ticker][source][label] = rule(terms)
    def products(ticker, concept, members):
        out[ticker]['stockanalysis'].update({label: rule(leaf(concept, {P: member})) for label, member in members.items()})
    def segments(ticker, concept, members, operating=True):
        out[ticker]['stockanalysis'].update({label: rule(segment(concept, member, operating)) for label, member in members.items()})
    products('AAPL', R, {'iPhone': 'aapl:IPhoneMember', 'Services': 'us-gaap:ServiceMember', 'Mac': 'aapl:MacMember',
        'Wearables, Home and Accessories': 'aapl:WearablesHomeandAccessoriesMember', 'iPad': 'aapl:IPadMember'})
    segments('MSFT', R, {label: 'msft:' + member for label, member in {
        'Agents and Infra': 'AgentsAndInfraMember', 'Devices and Consumer': 'DevicesAndConsumerMember',
        'Intelligent Cloud': 'IntelligentCloudMember', 'More Personal Computing': 'MorePersonalComputingMember',
        'Productivity and Business Processes': 'ProductivityAndBusinessProcessesMember'}.items()}, False)
    out['MSFT']['stockanalysis']['Corporate and Other'] = rule(leaf(R, {C: 'us-gaap:CorporateNonSegmentMember'}), role='definition_pending')
    orcl = {'Cloud': [('orcl:CloudRevenues', {}), (R, {P: 'orcl:CloudRevenuesMember'})],
        'Software': [('orcl:SoftwareRevenues', {}), (R, {P: 'orcl:SoftwareRevenuesMember'})],
        'Services': [('orcl:SalesRevenueServicesNet1', {}), (R, {S: 'orcl:ServicesBusinessMember', C: OP})],
        'Hardware': [('orcl:HardwareRevenues', {}), (R, {S: 'orcl:HardwareBusinessMember', C: OP})],
        'Cloud License and On-Premise License': [('orcl:CloudLicenseAndOnPremiseLicenseRevenue', {})],
        'Cloud Services and License Support': [('orcl:CloudServicesAndLicenseSupportRevenue', {}), (R, {P: 'orcl:CloudServicesAndLicenseSupportMember'})]}
    out['ORCL']['stockanalysis'] = {label: rule(*(leaf(concept, dims) for concept, dims in choices)) for label, choices in orcl.items()}
    for label, member in {'Google Search & Other': 'GoogleSearchOtherMember',
        'Google Subscriptions, Platforms & Devices': 'SubscriptionsPlatformsAndDevicesRevenueMember',
        'YouTube Ads': 'YouTubeAdvertisingRevenueMember', 'Google Network': 'GoogleNetworkMember'}.items():
        out['GOOGL']['stockanalysis'][label] = rule(leaf(R, {S: 'goog:GoogleServicesMember', P: 'goog:' + member}))
    out['GOOGL']['stockanalysis'].update({'Google Cloud': rule(segment(R, 'goog:GoogleCloudMember', False)),
        'Other Bets': rule(segment(R, 'us-gaap:AllOtherSegmentsMember', False)),
        'Hedging Gains': rule(leaf('us-gaap:RevenueNotFromContractWithCustomer', {}))})
    out['META']['stockanalysis'] = {
        'Advertising': rule(leaf(R, {S: 'meta:FamilyOfAppsMember', P: 'us-gaap:AdvertisingMember'})),
        'Payments and Other': rule(leaf(R, {S: 'meta:FamilyOfAppsMember', P: 'us-gaap:ServiceOtherMember'})),
        'Reality Labs': rule(segment(R, 'meta:RealityLabsMember', False))}
    segments('DIS', 'us-gaap:Revenues', {'Entertainment': 'dis:EntertainmentSegmentMember',
        'Parks and Experiences': 'dis:ExperiencesSegmentMember', 'Sports': 'dis:SportsSegmentMember'}, False)
    products('AMZN', R, {label: 'amzn:' + member for label, member in {
        'Online Stores': 'OnlineStoresMember', 'Third Party Seller Services': 'ThirdPartySellerServicesMember',
        'AWS': 'AmazonWebServicesMember', 'Advertising': 'AdvertisingServicesMember', 'Subscription': 'SubscriptionServicesMember',
        'Physical Stores': 'PhysicalStoresMember', 'Other': 'OtherServicesMember'}.items()})
    for label, member in {'Hardlines': 'MajorProductLineHardlinesMember', 'Building Materials': 'MajorProductLineBuildingMaterialsMember',
                          'Decor': 'MajorProductLineDcorMember'}.items():
        out['HD']['stockanalysis'][label] = rule(leaf(R, {P: 'hd:' + member, S: 'hd:PrimarySegmentMember', C: OP}),
            leaf(R, {P: 'hd:' + member, S: 'hd:PrimarySegmentMember'}),
            leaf(R, {P: 'hd:' + member, S: 'us-gaap:ReportableSegmentAggregationBeforeOtherOperatingSegmentMember'}))
    out['HD']['stockanalysis']['Other'] = rule(segment(R, 'us-gaap:AllOtherSegmentsMember', False), role='definition_pending')
    out['MCD']['futu'] = {label: rule(segment('us-gaap:Revenues', 'mcd:' + member, False)) for label, member in {
        '國際運營的市場': 'InternationalOperatedMarketsMember', 'United States (US)': 'USMarketMember',
        '國際開發許可市場和公司': 'InternationalDevelopmentalLicensedMarketsandCorporateMember'}.items()}
    for ticker, labels in {'WMT': ['Walmart United States (U.S.)', '沃爾瑪國際', "Sam's Club United States (U.S.)"],
        'NEE': ['Florida Power & Light Company (FPL)', 'NextEra Energy Resources (NEER)', '公司和其他'],
        'BRK-B': ['保險', '製造業', 'Pilot', 'McLane', '服務和零售', 'Berkshire Hathaway Energy (BHE)',
                  'Burlington Northern Santa Fe, LLC (BNSF)', '公司、抵銷和其他']}.items():
        for label in labels:
            concept, scopes = reviewed_selector(ticker, label)
            out[ticker]['futu'][label] = rule(*(leaf(concept, dims) for dims in scopes))
    products('COST', R, {'Net Sales': 'us-gaap:ProductMember', 'Membership Fees': 'us-gaap:MembershipMember'})
    segments('PG', 'us-gaap:Revenues', {label: 'pg:' + member for label, member in {
        'Fabric and Homecare': 'FabricHomeCareSegmentMember', 'Baby, Feminine, and Familycare': 'BabyFeminineFamilyCareSegmentMember',
        'Beauty': 'BeautySegmentMember', 'Healthcare': 'HealthCareSegmentMember', 'Grooming': 'GroomingSegmentMember'}.items()})
    out['PG']['stockanalysis']['Corporate'] = rule(leaf('us-gaap:Revenues', {C: 'us-gaap:CorporateNonSegmentMember'}))
    for label, member in {'North America': 'NorthAmericaSegmentMember', 'Europe, Middle East, and Africa': 'EuropeMiddleEastAfricaMember',
        'Latin America': 'LatinAmericaSegmentMember', 'Asia Pacific': 'A.PacificMember', 'Bottling Investments': 'BottlingInvestmentsMember',
        'Global Ventures': 'GlobalVenturesMember'}.items():
        out['KO']['stockanalysis'][label] = rule(segment('us-gaap:Revenues', 'ko:' + member),
            segment('ko:RevenueForReportableSegments', 'ko:' + member, False),
            segment('ko:RevenueForReportableSegments', 'ko:' + member),
            segment('us-gaap:Revenues', 'ko:' + member, False))
    out['KO']['stockanalysis'].update({'Corporate': rule(leaf('us-gaap:Revenues', {C: 'us-gaap:CorporateNonSegmentMember'}),
        leaf('ko:RevenueForReportableSegments', {C: 'us-gaap:CorporateNonSegmentMember'})),
        'Eliminations': rule(leaf('us-gaap:Revenues', {C: 'srt:ConsolidationEliminationsMember'}),
                             leaf('ko:IntersegmentRevenue', {C: 'srt:ConsolidationEliminationsMember'}),
                             leaf('ko:RevenueForReportableSegments', {C: 'srt:ConsolidationEliminationsMember'}))})
    for label, member in {'Pharmaceutical': 'InnovativeMedicineMember', 'Medtech': 'MedTechMember'}.items():
        out['JNJ']['stockanalysis'][label] = rule(segment(R, 'jnj:' + member, False), segment(R, 'jnj:' + member))
    out['UNH']['stockanalysis'] = {'UnitedHealthcare': rule(segment('us-gaap:Revenues', 'unh:UnitedhealthcareMember')),
        'Optum': rule(segment('us-gaap:Revenues', 'unh:TotalOptumMember', False)),
        'Eliminations': rule(leaf('us-gaap:Revenues', {C: 'us-gaap:CorporateNonSegmentMember'}),
            leaf('us-gaap:Revenues', {C: 'us-gaap:CorporateNonSegmentMember', 'srt:MajorCustomersAxis': 'unh:IntersegmentMember'}), role='definition_pending')}
    products('LLY', 'us-gaap:Revenues', {'Cardiometabolic': 'lly:CardiometabolicHealthMember', 'Oncology': 'lly:OncologyMember',
        'Immunology': 'lly:ImmunologyMember', 'Neuroscience': 'lly:NeuroscienceMember', 'Other': 'us-gaap:ProductAndServiceOtherMember'})
    segments('JPM', 'us-gaap:RevenuesNetOfInterestExpense', {label: 'jpm:' + member for label, member in {
        'Commercial and Investment Bank': 'CommercialAndInvestmentBankMember', 'Consumer and Community Banking': 'ConsumerCommunityBankingMember',
        'Wealth Management': 'AssetandWealthManagementSegmentMember'}.items()})
    out['JPM']['stockanalysis']['Corporate'] = rule(leaf('us-gaap:RevenuesNetOfInterestExpense', {C: 'us-gaap:CorporateNonSegmentMember'}))
    segments('BAC', 'bac:RevenuesNetOfInterestExpenseFullTaxEquivalentBasis', {label: 'bac:' + member for label, member in {
        'Consumer Banking': 'ConsumerBankingSegmentMember', 'Global Wealth and Investment Management': 'GlobalWealthAndInvestmentManagementSegmentMember',
        'Global Banking': 'GlobalBankingSegmentMember', 'Global Markets': 'GlobalMarketsSegmentMember'}.items()})
    out['BAC']['stockanalysis']['Other'] = rule(leaf('bac:RevenuesNetOfInterestExpenseFullTaxEquivalentBasis', {C: 'bac:CorporateReconcilingItemsAndEliminationsMember'}))
    for label, member in {'個人保險': 'PersonalLinesSegmentMember', '商業保險': 'CommercialLinesSegmentMember', '其他': 'OtherIndemnitySegmentMember'}.items():
        out['PGR']['futu'][label] = rule(leaf('pgr:PremiumsEarnedFeesAndOtherRevenue', {P: 'pgr:UnderwritingOperationsMember', S: 'pgr:' + member, C: OP}))
    out['PGR']['futu'].update({'Service revenues': rule(leaf('pgr:NonInsuranceServiceRevenues', {})),
        'Net realized gains (losses) on security sales': rule(leaf('pgr:DebtAndEquitySecuritiesRealizedGainsLossesOnSecuritySales', {}), role='overlap_review_required')})
    for label, member in {'上游': 'UpstreamMember', '能源產品': 'EnergyProductsMember', '化工產品': 'ChemicalProductsMember', '特種產品': 'SpecialtyProductsMember'}.items():
        out['XOM']['futu'][label] = rule([leaf('us-gaap:Revenues', {S: 'xom:' + member, G: geo, P: 'xom:SalesAndOtherOperatingRevenueMember'}) for geo in ('country:US', 'us-gaap:NonUsMember')], role='gross_sales_scope_candidate')
    out['XOM']['futu']['分部間收入'] = rule(leaf('us-gaap:Revenues', {C: 'us-gaap:IntersegmentEliminationMember'}), role='definition_pending')
    for label, member in {'上游': 'UpstreamSegmentMember', '下游': 'DownstreamSegmentMember'}.items():
        out['CVX']['futu'][label] = rule([leaf(R, {S: 'cvx:' + member, G: geo, C: OP}) for geo in ('country:US', 'us-gaap:NonUsMember')])
    out['CVX']['futu'].update({'所有其他': rule(segment(R, 'us-gaap:AllOtherSegmentsMember')),
        '部門間收入抵銷': rule(leaf(R, {C: 'us-gaap:IntersegmentEliminationMember'}))})
    segments('CAT', 'us-gaap:Revenues', {label: 'cat:' + member for label, member in {
        'Power & Energy': 'PowerEnergyMember', 'Construction': 'ConstructionIndustriesMember',
        'Resource': 'ResourceIndustriesMember', 'Energy and Transportation': 'EnergyandTransportationMember'}.items()})
    out['CAT']['stockanalysis'].update({'Financial Products': rule(segment('us-gaap:Revenues', 'cat:FinancialProductsSegmentMember'),
        leaf('us-gaap:Revenues', {S: 'cat:FinancialProductsSegmentMember', C: 'cat:OperatingSegmentsExcludingIntersegmentEliminationMember'})),
        'Other': rule(segment('us-gaap:Revenues', 'us-gaap:AllOtherSegmentsMember')),
        'Eliminations': rule(leaf('us-gaap:Revenues', {C: 'cat:EliminationsAndReconcilingItemsMember'}))})
    out['UPS']['stockanalysis'] = {
        'Domestic Package': rule(leaf(R, {S: 'ups:USDomesticPackageMember', G: 'country:US'}), segment(R, 'ups:U.S.DomesticPackageSegmentMember')),
        'International Package': rule(leaf(R, {S: 'ups:InternationalPackageMember', G: 'us-gaap:NonUsMember'}), segment(R, 'ups:InternationalSegmentMember')),
        'Supply Chain and Freight': rule(segment(R, 'ups:SupplyChainSolutionsMember', False), segment(R, 'ups:SupplyChainSolutionsMember'), role='definition_pending')}
    out['PLD']['issuer_ir'] = {'Rental': rule(leaf('pld:RentalRevenue', {})),
        'Strategic capital': rule(leaf('pld:ManagementFeesRevenue', {}), leaf('pld:ManagementFeesRevenue1', {})),
        'Development management and other': rule(leaf('pld:OtherRealEstateRevenue', {}), leaf('pld:OtherRealEstateRevenue1', {})),
        'Total revenues': rule(leaf('us-gaap:Revenues', {}), role='total_not_component')}
    return out
