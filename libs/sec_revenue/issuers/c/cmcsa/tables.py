"""公司表格解析器；由已核對規則移植，維持表頭、期間與對帳拒絕條件。"""

import re
import hashlib
from decimal import Decimal
from datetime import date
from lxml import html
from sec_revenue.parsers.table_support import TableSourceReader


class RevenueTables(TableSourceReader):
    LABELS = {
        "Connectivity and Platforms": "Total Connectivity & Platforms revenue",
        "Content and Experiences": "Total Content & Experiences revenue",
    }
    MONTHS = {3: ("March 31", "Q"), 6: ("June 30", "YTD6"), 9: ("September 30", "YTD9")}

    def parse_snapshot(self, snapshot, artifact_sha256):
        url = snapshot["source_url"]
        if (
            not self.sec_url(url)
            or "/data/1166691/" not in url
            or snapshot.get("format") != "SEC_DOM_sparse_cell_spans"
        ):
            raise ValueError("Unreviewed Comcast SEC source")
        date = re.search("/cmcsa-(20\\d\\d)(03|06|09)(31|30)\\.htm$", url)
        if not date:
            raise ValueError("Unreviewed Comcast report date")
        year, month, day = map(int, date.groups())
        if day != (31 if month == 3 else 30):
            raise ValueError("Wrong report end date")
        results = {}
        rejected_currency_tables = []
        for table in snapshot["tables"]:
            rows = table["rows"]
            header_rows = [cells for index, cells in rows if index < 3]
            header = (
                " ".join((text for cells in header_rows for _, _, text in cells))
                .lower()
                .replace(" ", "")
            )
            if "asreported" in header or "effectsofforeigncurrency" in header:
                rejected_currency_tables.append(table["index"])
                continue
            target_rows = {
                label: [
                    (index, cells)
                    for index, cells in rows
                    if cells and cells[0][2].casefold() == reported.casefold()
                ]
                for label, reported in self.LABELS.items()
            }
            if not any(target_rows.values()):
                continue
            if (
                "inmillions" not in header
                or "threemonthsended" + self.MONTHS[month][0].replace(" ", "").lower()
                not in header
            ):
                raise ValueError("Missing reported revenue units or quarter header")
            kinds = ["Q"] if month == 3 else ["Q", self.MONTHS[month][1]]
            if (
                month != 3
                and ("six" if month == 6 else "nine")
                + "monthsended"
                + self.MONTHS[month][0].replace(" ", "").lower()
                not in header
            ):
                raise ValueError("Missing reviewed YTD header")
            years = [
                r
                for r in header_rows
                if any((text == str(year) for _, _, text in r))
                and any((text == str(year - 1) for _, _, text in r))
            ]
            if len(years) != 1:
                raise ValueError("Missing unique year-column row")
            columns = [
                (start, span, int(text))
                for start, span, text in years[0]
                if re.fullmatch("20\\d\\d", text)
            ]
            if [y for _, _, y in columns] != [year, year - 1] * len(kinds):
                raise ValueError("Wrong year-column sequence")
            for label, hits in target_rows.items():
                if not hits:
                    continue
                if len(hits) != 1:
                    raise ValueError("Duplicate business-group subtotal")
                row_index, cells = hits[0]
                for number, (start, span, period_year) in enumerate(columns):
                    values = [
                        text
                        for col, _, text in cells
                        if start <= col < start + span
                        and re.fullmatch("\\d[\\d,]*", text)
                    ]
                    if len(values) != 1:
                        raise ValueError(
                            "Ambiguous net business-group value under year header"
                        )
                    kind = kinds[number // 2]
                    key = (kind, period_year, label)
                    if key in results:
                        raise ValueError("Duplicate reported business-group period")
                    accession = url.split("/")[-2]
                    results[key] = {
                        "kind": kind,
                        "year": period_year,
                        "month": month,
                        "label": label,
                        "concept": "sec-table:NetBusinessGroupRevenue",
                        "dimensions": {
                            "reported_business_group": label,
                            "basis": "reported_net_group_total",
                        },
                        "value": int(values[0].replace(",", "")) * 1000000,
                        "raw": values[0],
                        "unit": "iso4217:USD",
                        "decimals": "-6",
                        "startdate": f"{period_year}-{(month - 2 if kind == 'Q' else 1):02d}-01",
                        "enddate": f"{period_year}-{month:02d}-{day}",
                        "source_url": url,
                        "accession": accession[:10]
                        + "-"
                        + accession[10:12]
                        + "-"
                        + accession[12:],
                        "source_report_date": f"{year}-{month:02d}-{day}",
                        "source_format": snapshot["format"],
                        "source_table_index": table["index"],
                        "source_row_index": row_index,
                        "source_year_column": [start, span],
                        "source_artifact_sha256": artifact_sha256,
                    }
        if len(results) != 2 * 2 * (1 if month == 3 else 2):
            raise ValueError("Incomplete business groups or fiscal periods")
        return {
            "facts": list(results.values()),
            "rejected_constant_currency_tables": rejected_currency_tables,
        }

    def cells(self, row):
        result = []
        start = 0
        for cell in row.xpath("./td|./th"):
            span = int(cell.get("colspan", "1"))
            text = " ".join(" ".join(cell.itertext()).split())
            result.append((start, span, text))
            start += span
        return result

    def parse_groups(self, body, form, report_year, report_month=9):
        result = {}
        for table in html.fromstring(body).xpath("//table"):
            rows = [self.cells(r) for r in table.xpath("./tr|./tbody/tr")]
            head = (
                " ".join((text for row in rows[:6] for _, _, text in row))
                .lower()
                .replace(" ", "")
            )
            if (
                "inmillions" not in head
                or "asreported" in head
                or "effectsofforeigncurrency" in head
            ):
                continue
            if form == "10-Q" and (
                not (
                    "threemonthsended" in head
                    and (
                        report_month == 3
                        or (
                            "sixmonthsended" if report_month == 6 else "ninemonthsended"
                        )
                        in head
                    )
                )
            ):
                continue
            if form == "10-K" and "yearendeddecember31" not in head:
                continue
            headers = [
                r
                for r in rows[:6]
                if any((t == str(report_year) for _, _, t in r))
                and any((t == str(report_year - 1) for _, _, t in r))
            ]
            if len(headers) != 1:
                continue
            for label, reported in self.LABELS.items():
                hits = [r for r in rows if r and r[0][2].lower() == reported.lower()]
                if len(hits) != 1:
                    continue
                for year in [report_year, report_year - 1]:
                    columns = [
                        (c, span) for c, span, text in headers[0] if text == str(year)
                    ]
                    kinds = (
                        (
                            ["Q"]
                            + ([] if report_month == 3 else ["YTD" + str(report_month)])
                        )
                        if form == "10-Q"
                        else ["FY"]
                    )
                    if len(columns) != len(kinds):
                        raise ValueError("Unexpected business-group period columns")
                    for kind, (start, span) in zip(kinds, columns):
                        values = [
                            text
                            for col, _, text in hits[0]
                            if start <= col < start + span
                            and re.fullmatch("-?\\d[\\d,]*", text)
                        ]
                        if len(values) != 1:
                            raise ValueError("Ambiguous business-group value")
                        key = (kind, year, label)
                        value = int(values[0].replace(",", "")) * 1000000
                        if key in result and result[key] != value:
                            raise ValueError("Conflicting direct business-group tables")
                        result[key] = value
        if len(result) != (4 if form == "10-K" or report_month == 3 else 8):
            raise ValueError("Incomplete business groups or periods")
        return result
