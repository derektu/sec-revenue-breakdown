"""UPS 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class UPSParser(IssuerParser):
    ticker = "UPS"
    rules = {
        "reported": {
            "Domestic Package": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:StatementGeographicalAxis": "country:US",
                                "us-gaap:StatementBusinessSegmentsAxis": "ups:USDomesticPackageMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "ups:U.S.DomesticPackageSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "International Package": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "ups:InternationalPackageMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "ups:InternationalSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "scope_candidate",
            },
            "Supply Chain and Freight": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "ups:SupplyChainSolutionsMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "ups:SupplyChainSolutionsMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ],
                ],
                "role": "definition_pending",
            },
        }
    }
    aliases = [
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "ups:U.S.DomesticPackageSegmentMember",
            },
            "end": "2026-06-30",
            "id": "ups-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:StatementGeographicalAxis": "country:US",
                "us-gaap:StatementBusinessSegmentsAxis": "ups:USDomesticPackageMember",
            },
            "start": "2024-09-30",
        },
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "ups:InternationalSegmentMember",
            },
            "end": "2026-06-30",
            "id": "ups-explicit-reported-row-scope",
            "original_dimensions": {
                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "ups:InternationalPackageMember",
            },
            "start": "2024-09-30",
        },
    ]

    def normalize(self, record):
        """SCS 未列合計時須有三個非重疊產品運算元才可合計。"""
        record = super().normalize(record)
        from sec_revenue.engines import QuarterEngine

        engine = QuarterEngine()
        groups = {}
        segment = {
            "us-gaap:StatementBusinessSegmentsAxis": "ups:SupplyChainSolutionsMember"
        }
        members = [
            "ups:ForwardingMember",
            "ups:LogisticMember",
            "us-gaap:ProductAndServiceOtherMember",
        ]
        for f in record["facts"]:
            product = f["dimensions"].get("srt:ProductOrServiceAxis")
            if (
                f["concept"]
                == "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
                and product in members
                and f["dimensions"] == {**segment, "srt:ProductOrServiceAxis": product}
            ):
                groups.setdefault((f["startdate"], f["enddate"]), []).append(f)
        for (start, end), found in groups.items():
            if any(
                f["dimensions"] == segment
                and f.get("startdate") == start
                and f.get("enddate") == end
                for f in record["facts"]
            ):
                continue
            unique, bad = engine.dedupe(found)
            if len(unique) == 3 and not bad:
                record["facts"].append(
                    dict(
                        unique[0],
                        dimensions=segment,
                        value=sum(f["value"] for f in unique),
                        aggregation_evidence=unique,
                        normalization_rule_id="ups-nonreportable-scs-products",
                    )
                )
        return record

    def pool(self, records, index, engine):
        if records[index]["filing"]["reportDate"] != "2024-12-31":
            return super().pool(records, index, engine)
        prior = [
            f
            for r in records
            if r["filing"]["reportDate"] == "2025-09-30"
            for f in r["facts"]
            if f.get("startdate") == "2024-01-01" and f.get("enddate") == "2024-09-30"
        ]
        return engine.quarter(records[index]["facts"], "2024-12-31", prior)

    def parse(self, records):
        import json, hashlib
        from .ups_tables import RevenueTables

        rows = super().parse(records)
        reader = RevenueTables(self.repository, self.output)
        manifest = reader.manifest(
            "research/refactor-baseline-sec-20261104/source-snapshots/manifest.json"
        )
        entry = manifest["files"][0]
        entry = dict(
            entry,
            source_url=reader.UPS_URL,
            path="research/refactor-baseline-sec-20261104/source-snapshots/"
            + entry["path"],
            reportDate="2026-09-30",
            raw_sha256=entry["decompressed_sha256"],
        )
        raw = reader.read(entry, self.ticker, "web_text")
        parsed = reader.parse_ups_sec_page(raw.decode())
        outputs = {}
        for label, value in parsed.items():
            fact = {
                "concept": "sec-table:SegmentRevenue",
                "dimensions": {"reported_segment": label},
                "unit": "iso4217:USD",
                "value": value["value_usd"],
                "decimals": "-6",
                "startdate": "2026-07-01",
                "enddate": "2026-09-30",
                "source_url": reader.UPS_URL,
                "accession": "0001628280-26-067381",
                "source_line": value["line"],
                "source_artifact_sha256": hashlib.sha256(raw).hexdigest(),
                "source_format": "SEC_page_text_returned_by_web_tool",
            }
            outputs[label] = {
                "status": "observed",
                "value_usd": fact["value"],
                "SEC_operands": [fact],
                "weights": [1],
            }
        rows.append(
            {
                "ticker": self.ticker,
                "period_end": "2026-09-30",
                "period_kind": "Q",
                "basis": "reported",
                "outputs": outputs,
            }
        )
        self.source_receipts = reader.receipts
        return rows

    def download_dependencies(self, filing, filings):
        dependencies = super().download_dependencies(filing, filings)
        if filing["reportDate"] == "2024-12-31":
            dependencies.extend(
                f
                for f in filings
                if f["reportDate"] == "2025-09-30" and f["form"] == "10-Q"
            )
        return dependencies

    earnings_exhibits = {
        "0001628280-26-067381": {
            "reportDate": "2026-09-30",
            "primaryDocument": "exhibit991-earningspressre.htm",
        }
    }

    def extract_document(self, filing, documents):
        if filing["form"] != "8-K":
            return super().extract_document(filing, documents)
        from .ups_tables import RevenueTables

        raw, receipt = documents["primary"]
        facts = RevenueTables(self.repository, self.output).parse_earnings_html(
            raw, receipt["source_url"], receipt["sha256"]
        )
        for fact in facts:
            fact["source_cik"] = filing["cik"]
        return {
            "filing": filing,
            "facts": facts,
            "table_selected": {
                fact["dimensions"]["reported_segment"]: {
                    "status": "observed",
                    "value_usd": fact["value"],
                    "SEC_operands": [fact],
                    "weights": [1],
                    "rule_id": "ups-2026q3-sec-exhibit-direct",
                }
                for fact in facts
            },
        }

    def parse_downloaded(self, records, periods):
        rows = super().parse_downloaded(records, periods)
        for record in records:
            period = record["filing"]["reportDate"]
            if period not in periods or not record.get("table_selected"):
                continue
            rows = [row for row in rows if row["period_end"] != period]
            rows.append(
                {
                    "ticker": self.ticker,
                    "period_end": period,
                    "period_kind": "Q",
                    "basis": "reported",
                    "outputs": record["table_selected"],
                }
            )
        return rows
