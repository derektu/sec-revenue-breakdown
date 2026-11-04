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

    earnings_exhibits = {
        "0000018230-26-000052": {
            "reportDate": "2026-09-30",
            "primaryDocument": "ex991toformcat3q2026earnin.htm",
        }
    }

    def extract_document(self, filing, documents):
        if filing["form"] != "8-K":
            return super().extract_document(filing, documents)
        from .cat_tables import RevenueTables
        from .table_support import HtmlTableAdapter

        raw, receipt = documents["primary"]
        tables = HtmlTableAdapter().nonempty(
            raw,
            [
                "Sales and Revenues by Segment",
                "Sales and Revenues by Geographic Region",
            ],
        )
        for table in tables:
            boundary = next(
                (
                    i
                    for i, row in enumerate(table["rows"])
                    if row[0] == "Third Quarter 2025"
                ),
                None,
            )
            if boundary is not None:
                table["rows"] = table["rows"][:boundary]
        parsed = RevenueTables(self.repository, self.output).parse_snapshot(
            {
                "source_url": receipt["source_url"],
                "format": "SEC_DOM_nonempty_cell_text",
                "tables": tables,
            },
            receipt["sha256"],
        )
        for fact in parsed["facts"]:
            fact.update(source_format="original_html", source_cik=filing["cik"])
        return {
            "filing": filing,
            "facts": parsed["facts"],
            "table_selected": parsed["selected"],
        }

    def parse_downloaded(self, records, periods):
        rows = super().parse_downloaded(records, periods)
        for record in records:
            if record["filing"]["reportDate"] not in periods or not record.get(
                "table_selected"
            ):
                continue
            period = record["filing"]["reportDate"]
            rows = [row for row in rows if row["period_end"] != period]
            outputs = {
                label: {
                    "status": value["status"],
                    "value_usd": value["value"],
                    "SEC_operands": value["facts"],
                    "weights": [1] * len(value["facts"]),
                    "rule_id": "cat-2026q3-sec-exhibit-corporate-bridge",
                }
                for label, value in record["table_selected"].items()
            }
            rows.append(
                {
                    "ticker": self.ticker,
                    "period_end": period,
                    "period_kind": "Q",
                    "basis": "reported",
                    "outputs": outputs,
                }
            )
        return rows
