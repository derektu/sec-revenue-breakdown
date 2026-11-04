"""BAC 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from sec_revenue.parsers.base import IssuerParser


class BACParser(IssuerParser):
    ticker = "BAC"
    rules = {
        "reported": {
            "Consumer Banking": {
                "alternatives": [
                    [
                        {
                            "concept": "bac:RevenuesNetOfInterestExpenseFullTaxEquivalentBasis",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "bac:ConsumerBankingSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Global Banking": {
                "alternatives": [
                    [
                        {
                            "concept": "bac:RevenuesNetOfInterestExpenseFullTaxEquivalentBasis",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "bac:GlobalBankingSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Global Markets": {
                "alternatives": [
                    [
                        {
                            "concept": "bac:RevenuesNetOfInterestExpenseFullTaxEquivalentBasis",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "bac:GlobalMarketsSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Global Wealth and Investment Management": {
                "alternatives": [
                    [
                        {
                            "concept": "bac:RevenuesNetOfInterestExpenseFullTaxEquivalentBasis",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "bac:GlobalWealthAndInvestmentManagementSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Other": {
                "alternatives": [
                    [
                        {
                            "concept": "bac:RevenuesNetOfInterestExpenseFullTaxEquivalentBasis",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "bac:CorporateReconcilingItemsAndEliminationsMember"
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

    def pool(self, records, index, engine):
        """FY2025 追溯改會計方法，使用最早後續申報的新基礎 YTD9。"""
        record = records[index]
        if record["filing"]["reportDate"] != "2025-12-31":
            return super().pool(records, index, engine)
        later = [
            r
            for r in records
            if r["filing"]["reportDate"] > "2025-12-31"
            and any(
                f.get("startdate") == "2025-01-01" and f.get("enddate") == "2025-09-30"
                for f in r["facts"]
            )
        ]
        if not later:
            return [], []
        source = min(later, key=lambda r: r["filing"]["filingDate"])
        prior = [
            f
            for f in source["facts"]
            if f.get("startdate") == "2025-01-01" and f.get("enddate") == "2025-09-30"
        ]
        facts, conflicts = engine.quarter(record["facts"], "2025-12-31", prior)
        for fact in facts:
            fact.update(
                revision_rule_id="bac-fy2025-retrospective-tax-equity-accounting",
                comparative_filing_date=source["filing"]["filingDate"],
            )
        return facts, conflicts

    def download_dependencies(self, filing, filings):
        dependencies = super().download_dependencies(filing, filings)
        if filing["reportDate"] == "2025-12-31":
            later = [
                f
                for f in filings
                if f["reportDate"] > "2025-12-31"
                and f["reportDate"].endswith("-09-30")
                and f["cik"] == filing["cik"]
            ]
            if later:
                dependencies.append(min(later, key=lambda f: f["filingDate"]))
        return dependencies
