"""JPM 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from sec_revenue.parsers.base import IssuerParser


class JPMParser(IssuerParser):
    ticker = "JPM"
    rules = {
        "reported": {
            "Commercial and Investment Bank": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenuesNetOfInterestExpense",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "jpm:CommercialAndInvestmentBankMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Consumer and Community Banking": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenuesNetOfInterestExpense",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "jpm:ConsumerCommunityBankingMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Corporate": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenuesNetOfInterestExpense",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:CorporateNonSegmentMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Wealth Management": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenuesNetOfInterestExpense",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "jpm:AssetandWealthManagementSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
        }
    }
    aliases = [
        {
            "concept": "us-gaap:RevenuesNetOfInterestExpense",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "jpm:CommercialAndInvestmentBankMember",
            },
            "id": "jpm-2024q3-cib-reorganization-member",
            "original_dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "jpm:CorporateAndInvestmentBankMember",
            },
            "report_dates": ["2024-09-30"],
        },
        {
            "concept": "us-gaap:RevenuesNetOfInterestExpense",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "jpm:CommercialAndInvestmentBankMember",
            },
            "id": "jpm-2024q3-cib-reorganization-member",
            "original_dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "jpm:CorporateAndInvestmentBankMember",
            },
            "report_dates": ["2024-09-30"],
        },
    ]
