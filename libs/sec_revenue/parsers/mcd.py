"""MCD 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class MCDParser(IssuerParser):
    ticker = "MCD"
    rules = {
        "segments": {
            "United States (US)": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "mcd:USMarketMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "國際運營的市場": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "mcd:InternationalOperatedMarketsMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "國際開發許可市場和公司": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "mcd:InternationalDevelopmentalLicensedMarketsandCorporateMember"
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
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "mcd:USMarketMember"
            },
            "end": "2024-09-30",
            "id": "mcd-explicit-reported-row-scope",
            "original_dimensions": {
                "us-gaap:StatementBusinessSegmentsAxis": "mcd:U.S.MarketMember"
            },
            "start": "2024-09-30",
        }
    ]
