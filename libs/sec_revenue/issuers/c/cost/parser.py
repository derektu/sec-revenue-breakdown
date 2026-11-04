"""COST 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from sec_revenue.parsers.base import IssuerParser


class COSTParser(IssuerParser):
    ticker = "COST"
    rules = {
        "reported": {
            "Membership Fees": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "us-gaap:MembershipMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Net Sales": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ProductOrServiceAxis": "us-gaap:ProductMember"
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
