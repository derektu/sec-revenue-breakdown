"""PGR 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class PGRParser(IssuerParser):
    ticker = "PGR"
    rules = {
        "segments": {
            "Net realized gains (losses) on security sales": {
                "alternatives": [
                    [
                        {
                            "concept": "pgr:DebtAndEquitySecuritiesRealizedGainsLossesOnSecuritySales",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "overlap_review_required",
            },
            "Service revenues": {
                "alternatives": [
                    [
                        {
                            "concept": "pgr:NonInsuranceServiceRevenues",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "個人保險": {
                "alternatives": [
                    [
                        {
                            "concept": "pgr:PremiumsEarnedFeesAndOtherRevenue",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "srt:ProductOrServiceAxis": "pgr:UnderwritingOperationsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "pgr:PersonalLinesSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "其他": {
                "alternatives": [
                    [
                        {
                            "concept": "pgr:PremiumsEarnedFeesAndOtherRevenue",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "srt:ProductOrServiceAxis": "pgr:UnderwritingOperationsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "pgr:OtherIndemnitySegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "商業保險": {
                "alternatives": [
                    [
                        {
                            "concept": "pgr:PremiumsEarnedFeesAndOtherRevenue",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "srt:ProductOrServiceAxis": "pgr:UnderwritingOperationsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "pgr:CommercialLinesSegmentMember",
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

    def parse(self, records):
        """合併損益及承保收入分開；總額不與其組成重複相加。"""
        from .pgr_tables import RevenueTables
        import hashlib

        reader = RevenueTables(self.repository, self.output)
        facts = []
        for entry in reader.manifest(
            "research/progressive-sec-html-20261104/manifest.json"
        )["files"]:
            raw = reader.read(entry, self.ticker, "original_html")
            facts.extend(reader.parse_html(raw, entry["source_url"]))
        labels = {
            label: label
            for label in reader.INCOME
            + ["個人保險", "商業保險", "其他", "Total underwriting revenue"]
        }
        rows = reader.observations(
            facts,
            self.ticker,
            "reported",
            labels,
            [
                "2024-12-31",
                "2025-03-31",
                "2025-06-30",
                "2025-09-30",
                "2025-12-31",
                "2026-03-31",
                "2026-06-30",
                "2026-09-30",
            ],
        )
        self.source_receipts = reader.receipts
        return rows
