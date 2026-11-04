"""CMCSA 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from .base import IssuerParser


class CMCSAParser(IssuerParser):
    ticker = "CMCSA"
    rules = {
        "reported": {
            "Connectivity and Platforms": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cmcsa:ResidentialConnectivityAndPlatformsSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cmcsa:BusinessServicesConnectivitySegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                    ]
                ],
                "role": "scope_candidate",
            },
            "Content and Experiences": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cmcsa:MediaSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cmcsa:StudiosSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cmcsa:ThemeParksSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                    ]
                ],
                "role": "scope_candidate",
            },
        },
        "segments": {
            "Business Services Connectivity": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cmcsa:BusinessServicesConnectivitySegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "Residential Connectivity & Platforms": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cmcsa:ResidentialConnectivityAndPlatformsSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "主題公園": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cmcsa:ThemeParksSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "其他收入": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
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
            "媒體": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cmcsa:MediaSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "抵銷": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "srt:ConsolidationEliminationsMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "演播室": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cmcsa:StudiosSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
        },
    }
    aliases = []

    def parse(self, records):
        """業務群淨額不可直接以分部毛額相加；年度與比較 YTD 採真正 HTML。"""
        from .cmcsa_tables import RevenueTables
        import json

        reader = RevenueTables(self.repository, self.output)
        facts = []
        for entry in reader.manifest(
            "research/sec-dom-sources-20261104/CMCSA-manifest.json"
        )["files"]:
            raw = reader.read(entry, self.ticker, "dom_snapshot")
            facts.extend(
                reader.parse_snapshot(json.loads(raw), entry["sha256"])["facts"]
            )
        for entry in reader.manifest("research/shared-raw-semantics/manifest.json")[
            "filings"
        ]:
            if entry["ticker"] != self.ticker:
                continue
            # 此 manifest 的 sha256 指向解壓 bytes，另有 gzip_sha256。
            source = dict(entry, source_url=entry["url"], raw_sha256=entry["sha256"])
            import hashlib

            source["sha256"] = hashlib.sha256(
                (self.repository / entry["path"]).read_bytes()
            ).hexdigest()
            raw = reader.read(source, self.ticker, "original_html")
            for (kind, year, label), value in reader.parse_groups(
                raw, entry["form"], 2025
            ).items():
                month = 12 if kind == "FY" else 9
                facts.append(
                    {
                        "kind": kind,
                        "year": year,
                        "month": month,
                        "label": label,
                        "concept": "sec-table:NetBusinessGroupRevenue",
                        "dimensions": {
                            "reported_business_group": label,
                            "basis": "reported_net_group_total",
                        },
                        "value": value,
                        "unit": "iso4217:USD",
                        "decimals": "-6",
                        "startdate": f'{year}-{7 if kind=="Q" else 1:02d}-01',
                        "enddate": f"{year}-{month:02d}-{31 if month==12 else 30}",
                        "source_url": entry["url"],
                        "source_report_date": entry["reportDate"],
                        "accession": entry["accessionNumber"],
                        "source_artifact_sha256": entry["sha256"],
                        "source_format": "SEC_HTML_from_verified_gzip",
                    }
                )
        rows = reader.observations(
            facts,
            self.ticker,
            "reported",
            {k: k for k in reader.LABELS},
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
            original_only=True,
        )
        self.source_receipts = reader.receipts
        return rows

    def extract_document(self, filing, documents):
        """從當次下載的 reported 淨業務群表萃取，不把分部相加冒充淨額。"""
        from .cmcsa_tables import RevenueTables

        reader = RevenueTables(self.repository, self.output)
        raw, receipt = documents["primary"]
        report_year = int(filing["reportDate"][:4])
        report_month = int(filing["reportDate"][5:7])
        facts = []
        for (kind, year, label), value in reader.parse_groups(
            raw, filing["form"], report_year, report_month
        ).items():
            month = 12 if kind == "FY" else report_month
            import calendar

            end = f"{year}-{month:02d}-{calendar.monthrange(year,month)[1]}"
            start = f'{year}-{month-2 if kind=="Q" else 1:02d}-01'
            facts.append(
                {
                    "kind": kind,
                    "label": label,
                    "value": value,
                    "concept": "sec-table:NetBusinessGroupRevenue",
                    "dimensions": {
                        "reported_business_group": label,
                        "basis": "reported_net_group_total",
                    },
                    "unit": "iso4217:USD",
                    "decimals": "-6",
                    "startdate": start,
                    "enddate": end,
                    "source_url": receipt["source_url"],
                    "source_cik": filing["cik"],
                    "source_report_date": filing["reportDate"],
                    "source_artifact_sha256": receipt["sha256"],
                    "source_format": "original_html",
                    "accession": filing["accessionNumber"],
                }
            )
        return {"filing": filing, "facts": facts}

    def parse_downloaded(self, records, periods):
        from .cmcsa_tables import RevenueTables

        reader = RevenueTables(self.repository, self.output)
        return reader.observations(
            [f for r in records for f in r["facts"]],
            self.ticker,
            "reported",
            {k: k for k in reader.LABELS},
            periods,
        )
