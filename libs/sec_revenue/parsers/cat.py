"""CAT 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class CATParser(IssuerParser):
    ticker = "CAT"
    rules = {
        "reported": {
            "Construction": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cat:ConstructionIndustriesMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Eliminations": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "cat:EliminationsAndReconcilingItemsMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Energy and Transportation": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cat:PowerEnergyMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Financial Products": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cat:FinancialProductsSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "cat:OperatingSegmentsExcludingIntersegmentEliminationMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cat:FinancialProductsSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "Other": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:AllOtherSegmentsMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Power & Energy": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cat:PowerEnergyMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Resource": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:Revenues",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cat:ResourceIndustriesMember",
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
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "cat:PowerEnergyMember",
            },
            "end": "2025-09-30",
            "id": "cat-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "cat:EnergyandTransportationMember",
            },
            "start": "2024-09-30",
        },
        {
            "concept": "us-gaap:Revenues",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "cat:EliminationsAndReconcilingItemsMember"
            },
            "end": "2024-09-30",
            "id": "cat-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:ConsolidationItemsAxis": "cat:CorporateReconcilingItemsAndEliminationsMember"
            },
            "start": "2024-09-30",
        },
    ]

    def categories(self, period, basis):
        rules = dict(super().categories(period, basis))
        rules.pop(
            "Energy and Transportation" if period >= "2026-03-31" else "Power & Energy",
            None,
        )
        return rules

    def parse(self, records):
        from .cat_tables import RevenueTables
        import json

        rows = super().parse(records)
        reader = RevenueTables(self.repository, self.output)
        entry = reader.manifest("research/sec-dom-sources-20261104/CAT-manifest.json")
        entry = dict(entry, reportDate="2026-09-30")
        raw = reader.read(entry, self.ticker, "dom_snapshot")
        result = reader.parse_snapshot(json.loads(raw), entry["sha256"])
        outputs = {
            k: {
                "status": v["status"],
                "value_usd": v["value"],
                "SEC_operands": v["facts"],
                "weights": [1] * len(v["facts"]),
            }
            for k, v in result["selected"].items()
        }
        rows.append(
            {
                "ticker": self.ticker,
                "period_end": result["period_end"],
                "period_kind": "Q",
                "basis": "reported",
                "outputs": outputs,
            }
        )
        self.source_receipts = reader.receipts
        return rows
