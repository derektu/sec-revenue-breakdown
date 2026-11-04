"""CVX 獨立完整 scope 規則；精確配對而非模糊名稱。"""

from sec_revenue.parsers.base import IssuerParser


class CVXParser(IssuerParser):
    ticker = "CVX"
    rules = {
        "gross": {
            "上游": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "srt:StatementGeographicalAxis": "country:US",
                                "us-gaap:StatementBusinessSegmentsAxis": "cvx:UpstreamSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cvx:UpstreamSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                    ]
                ],
                "role": "scope_candidate",
            },
            "下游": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "srt:StatementGeographicalAxis": "country:US",
                                "us-gaap:StatementBusinessSegmentsAxis": "cvx:DownstreamSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cvx:DownstreamSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        },
                    ]
                ],
                "role": "scope_candidate",
            },
            "所有其他": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
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
            "部門間收入抵銷": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:ConsolidationItemsAxis": "us-gaap:IntersegmentEliminationMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
        },
        "net": {
            "all_other_net": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:AllOtherSegmentsMember"
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "consolidated_sales": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {},
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "total_not_component",
            },
            "downstream_international": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cvx:DownstreamSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "downstream_us": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:StatementGeographicalAxis": "country:US",
                                "us-gaap:StatementBusinessSegmentsAxis": "cvx:DownstreamSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "upstream_international": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                                "us-gaap:StatementBusinessSegmentsAxis": "cvx:UpstreamSegmentMember",
                            },
                            "unit": "iso4217:USD",
                            "weight": 1,
                        }
                    ]
                ],
                "role": "scope_candidate",
            },
            "upstream_us": {
                "alternatives": [
                    [
                        {
                            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                            "dimensions": {
                                "srt:StatementGeographicalAxis": "country:US",
                                "us-gaap:StatementBusinessSegmentsAxis": "cvx:UpstreamSegmentMember",
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
    aliases = [
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:StatementGeographicalAxis": "country:US",
                "us-gaap:StatementBusinessSegmentsAxis": "cvx:UpstreamSegmentMember",
            },
            "end": "2024-09-30",
            "id": "cvx-2024-gross-sales-reported-rows",
            "original_dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:ProductOrServiceAxis": "us-gaap:OilAndGasMember",
                "srt:StatementGeographicalAxis": "country:US",
                "us-gaap:StatementBusinessSegmentsAxis": "cvx:UpstreamMember",
            },
            "start": "2024-09-30",
        },
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "cvx:UpstreamSegmentMember",
            },
            "end": "2024-09-30",
            "id": "cvx-2024-gross-sales-reported-rows",
            "original_dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:ProductOrServiceAxis": "us-gaap:OilAndGasMember",
                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "cvx:UpstreamMember",
            },
            "start": "2024-09-30",
        },
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:StatementGeographicalAxis": "country:US",
                "us-gaap:StatementBusinessSegmentsAxis": "cvx:DownstreamSegmentMember",
            },
            "end": "2024-09-30",
            "id": "cvx-2024-gross-sales-reported-rows",
            "original_dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:ProductOrServiceAxis": "us-gaap:OilAndGasMember",
                "srt:StatementGeographicalAxis": "country:US",
                "us-gaap:StatementBusinessSegmentsAxis": "cvx:DownstreamMember",
            },
            "start": "2024-09-30",
        },
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "cvx:DownstreamSegmentMember",
            },
            "end": "2024-09-30",
            "id": "cvx-2024-gross-sales-reported-rows",
            "original_dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "srt:ProductOrServiceAxis": "us-gaap:OilAndGasMember",
                "srt:StatementGeographicalAxis": "us-gaap:NonUsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "cvx:DownstreamMember",
            },
            "start": "2024-09-30",
        },
        {
            "concept": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember",
                "us-gaap:StatementBusinessSegmentsAxis": "us-gaap:AllOtherSegmentsMember",
            },
            "end": "2024-09-30",
            "id": "cvx-2024-gross-sales-reported-rows",
            "original_dimensions": {
                "srt:ConsolidationItemsAxis": "us-gaap:CorporateNonSegmentMember",
                "srt:ProductOrServiceAxis": "us-gaap:OilAndGasMember",
            },
            "start": "2024-09-30",
        },
    ]

    def normalize(self, record):
        """舊 2024 Q3 表的兩地區全球抵銷合計，不重複計分部內抵銷。"""
        record = super().normalize(record)
        if record["filing"]["reportDate"] != "2024-09-30":
            return record
        from sec_revenue.engines import QuarterEngine

        for start in ("2024-01-01", "2024-07-01"):
            found = []
            for geo in ("country:US", "us-gaap:NonUsMember"):
                scope = {
                    "srt:ConsolidationItemsAxis": "srt:GeographyEliminationsMember",
                    "srt:StatementGeographicalAxis": geo,
                    "srt:ProductOrServiceAxis": "us-gaap:OilAndGasMember",
                }
                candidates = [
                    f
                    for f in record["facts"]
                    if f["concept"]
                    == "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
                    and f["dimensions"] == scope
                    and f.get("startdate") == start
                    and f.get("enddate") == "2024-09-30"
                ]
                unique, bad = QuarterEngine().dedupe(candidates)
                if len(unique) == 1 and not bad:
                    found.extend(unique)
            if len(found) == 2:
                record["facts"].append(
                    dict(
                        found[0],
                        dimensions={
                            "srt:ConsolidationItemsAxis": "us-gaap:IntersegmentEliminationMember"
                        },
                        value=sum(f["value"] for f in found),
                        aggregation_evidence=found,
                        normalization_rule_id="cvx-2024-global-geographical-eliminations",
                    )
                )
        # 舊表尚未列兩地區 net tags，gross 加負抵銷才是對外收入。
        # 僅限這份舊申報；每個運算元保留原始 scope，不能將缺欄當零。
        concept = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
        segment_axis = "us-gaap:StatementBusinessSegmentsAxis"
        consolidation = "srt:ConsolidationItemsAxis"
        product = "srt:ProductOrServiceAxis"
        geography = "srt:StatementGeographicalAxis"
        originals = list(record["facts"])
        for start in ("2024-01-01", "2024-07-01"):
            for member in ("Upstream", "Downstream"):
                for geo in ("country:US", "us-gaap:NonUsMember"):
                    operands = []
                    for item in (
                        "us-gaap:OperatingSegmentsMember",
                        "us-gaap:IntersegmentEliminationMember",
                    ):
                        dims = {
                            segment_axis: "cvx:" + member + "Member",
                            geography: geo,
                            consolidation: item,
                            product: "us-gaap:OilAndGasMember",
                        }
                        found = [
                            f
                            for f in originals
                            if f["concept"] == concept
                            and f.get("original_dimensions", f["dimensions"]) == dims
                            and f.get("startdate") == start
                            and f.get("enddate") == "2024-09-30"
                        ]
                        unique, bad = QuarterEngine().dedupe(found)
                        if len(unique) == 1 and not bad:
                            operands.extend(unique)
                    if len(operands) == 2:
                        record["facts"].append(
                            dict(
                                operands[0],
                                dimensions={
                                    segment_axis: "cvx:" + member + "SegmentMember",
                                    geography: geo,
                                },
                                value=sum(f["value"] for f in operands),
                                aggregation_evidence=operands,
                                normalization_rule_id="cvx-2024-net-gross-plus-intersegment",
                            )
                        )
            found = [
                f
                for f in originals
                if f["concept"] == concept
                and f["dimensions"]
                == {
                    consolidation: "cvx:CorporateAndEliminationsMember",
                    product: "us-gaap:OilAndGasMember",
                }
                and f.get("startdate") == start
                and f.get("enddate") == "2024-09-30"
            ]
            unique, bad = QuarterEngine().dedupe(found)
            if len(unique) == 1 and not bad:
                record["facts"].append(
                    dict(
                        unique[0],
                        original_dimensions=unique[0]["dimensions"],
                        dimensions={segment_axis: "us-gaap:AllOtherSegmentsMember"},
                        normalization_rule_id="cvx-2024-reported-corporate-net",
                    )
                )
        return record

    def parse(self, records):
        """net 為主系列；合併總額不符時拒絕整期 net，gross 不受影響。"""
        rows = super().parse(records)
        for row in rows:
            if row["basis"] != "net":
                continue
            outputs = row["outputs"]
            if (
                any(o["status"] != "observed" for o in outputs.values())
                or sum(
                    v["value_usd"]
                    for k, v in outputs.items()
                    if k != "consolidated_sales"
                )
                != outputs["consolidated_sales"]["value_usd"]
            ):
                for value in outputs.values():
                    value.update(status="net_reconciliation_incomplete", value_usd=None)
        return rows

    def parse_downloaded(self, records, periods):
        from sec_revenue.engines import RevenueReconciliation

        rows = super().parse_downloaded(records, periods)
        engine = RevenueReconciliation()
        for row in rows:
            if row["basis"] != "net":
                continue
            check = engine.check(
                row["outputs"],
                {
                    key: -1 if key == "consolidated_sales" else 1
                    for key in row["outputs"]
                },
            )
            row["reconciliation_checks"] = [check]
            if check["status"] != "verified":
                engine.reject(row["outputs"], "net_reconciliation_failed")
        return rows
