#!/usr/bin/env python3
"""可選 Playwright 實測：正常 UI、三十家公司、期別／basis、錯誤 HTTP。"""

import argparse
import json
import shutil
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError


class ViewerUiCheck:
    def run(self):
        cli = argparse.ArgumentParser(description=__doc__)
        cli.add_argument("--url", default="http://127.0.0.1:8765")
        cli.add_argument("--out", type=Path, default=Path("data/engine-ui"))
        cli.add_argument(
            "--tickers", nargs="+", help="只驗證已萃取的 ticker；省略為全部支援 ticker"
        )
        cli.add_argument(
            "--expected-periods",
            type=int,
            help="可選固定期數；一般操作允許任意日期範圍",
        )
        args = cli.parse_args()
        args.out.mkdir(parents=True, exist_ok=True)
        from playwright.sync_api import sync_playwright, expect

        errors = []
        supported = json.load(urlopen(args.url + "/api/tickers"))
        tickers = [t.upper() for t in args.tickers] if args.tickers else supported
        self.assert_true(
            bool(tickers) and set(tickers).issubset(supported),
            "unsupported ticker selection",
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, executable_path=shutil.which("chromium")
            )
            page = browser.new_page(viewport={"width": 1280, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(args.url)
            for ticker in tickers:
                page.locator("#ticker").fill(ticker)
                page.locator("button").click()
                expect(page.locator("#context")).to_contain_text(ticker + " ·")
                expect(page.locator("#rows tr").first).to_be_visible()
                count = page.locator("#period option").count()
                self.assert_true(
                    (
                        count == args.expected_periods
                        if args.expected_periods
                        else count > 0
                    ),
                    ticker + " periods",
                )
            selected = "CVX" if "CVX" in tickers else tickers[0]
            page.locator("#ticker").fill(selected)
            page.locator("button").click()
            expect(page.locator("#context")).to_contain_text(selected + " ·")
            basis_options = page.locator("#basis option").evaluate_all(
                "(nodes)=>nodes.map(n=>n.value)"
            )
            if selected == "CVX":
                expect(page.locator("#basis")).to_have_value("net")
            if len(basis_options) > 1:
                alternate = "gross" if selected == "CVX" else basis_options[-1]
                page.locator("#basis").select_option(alternate)
                expect(page.locator("#context")).to_contain_text(alternate)
            oldest = page.locator("#period option").last.get_attribute("value")
            page.locator("#period").select_option(oldest)
            expect(page.locator("#context")).to_contain_text(oldest)
            page.locator("#rows details").first.locator("summary").click()
            expect(page.locator("#rows pre").first).to_be_visible()
            page.screenshot(
                path=str(
                    args.out
                    / ("viewer-cvx.png" if selected == "CVX" else "viewer-workflow.png")
                ),
                full_page=True,
            )
            for query, status in [
                ("ticker=NOPE", 400),
                ("ticker=../AAPL", 400),
                ("ticker=AAPL&period=1900-01-01", 404),
                ("ticker=AAPL&basis=invalid", 404),
            ]:
                response = page.request.get(args.url + "/api/revenue?" + query)
                self.assert_true(response.status == status, query)
            page.locator("#ticker").fill("INVALID")
            page.locator("button").click()
            expect(page.locator("#error")).not_to_be_empty()
            self.assert_true(
                page.locator("#rows tr").count() == 0, "invalid UI must clear old data"
            )
            browser.close()
        self.assert_true(not errors, str(errors))
        report = {
            "tickers": len(tickers),
            "ui_period_basis_switch": True,
            "evidence_details": True,
            "invalid_http_and_ui": True,
            "page_errors": errors,
        }
        (args.out / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))

    def assert_true(self, condition, message):
        if not condition:
            raise AssertionError(message)


if __name__ == "__main__":
    ViewerUiCheck().run()
