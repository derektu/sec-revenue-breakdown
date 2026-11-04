"""META 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from sec_revenue.parsers.base import IssuerParser


class METAParser(IssuerParser):
    ticker = "META"
    rules = {
        "reported": {
            "Advertising": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "us-gaap:AdvertisingMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "meta:FamilyOfAppsMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Payments and Other": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "us-gaap:ServiceOtherMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "meta:FamilyOfAppsMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Reality Labs": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "meta:RealityLabsMember"
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
    aliases = []
