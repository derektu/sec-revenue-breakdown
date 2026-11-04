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
        args = cli.parse_args()
        args.out.mkdir(parents=True, exist_ok=True)
        from playwright.sync_api import sync_playwright, expect

        errors = []
        tickers = json.load(urlopen(args.url + "/api/tickers"))
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
                self.assert_true(
                    page.locator("#period option").count() == 8, ticker + " periods"
                )
            page.locator("#ticker").fill("CVX")
            page.locator("button").click()
            expect(page.locator("#context")).to_contain_text("CVX ·")
            expect(page.locator("#basis")).to_have_value("net")
            page.locator("#basis").select_option("gross")
            expect(page.locator("#context")).to_contain_text("gross")
            oldest = page.locator("#period option").last.get_attribute("value")
            page.locator("#period").select_option(oldest)
            expect(page.locator("#context")).to_contain_text(oldest)
            page.locator("#rows details").first.locator("summary").click()
            expect(page.locator("#rows pre").first).to_be_visible()
            page.screenshot(path=str(args.out / "viewer-cvx.png"), full_page=True)
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
