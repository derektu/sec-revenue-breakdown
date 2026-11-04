# Apple live-browser acquisition check

Checked on 2026-11-04 in the user's existing Edge tabs. This check uses rendered
page DOM and native controls. It makes no hidden API requests, exports no browser
credentials, changes no login state, and uploads no vendor data.

## Stock Analysis

Page: <https://stockanalysis.com/stocks/aapl/metrics/revenue-by-segment/>.
The live page is already on Quarterly and has a readable History table: Date,
iPhone, Services, Mac, Wearables/Home/Accessories and iPad. The accessible chart
also exposes full-dollar values, while the History table abbreviates billions.
The latest eight displayed period dates span 2024-12-31 to 2026-09-30. The live
chart/table exposes 48 periods, rather than the public page's shorter history.

Opening the native Download menu reveals Excel, CSV and Google Sheets. The
single Apple Download to CSV action was triggered once. The automation's download
completion event timed out; no file path or completed artifact was returned.
The room contains an unresolved permission prompt:

    Allow download from https://stockanalysis.com/stocks/aapl/metrics/revenue-by-segment/?

Consequently file bytes, actual CSV schema, downloaded precision and row count
remain unverified. Do not classify the result as a successful download or retry
the action without resolving its permission and checking the outcome.

An attempted inspection of `edge://downloads/all` was rejected because the
browser tool permits only HTTP/HTTPS URLs. This is a tool policy restriction,
not a Stock Analysis 403 or a vendor login failure. No alternative route to that
blocked browser page was attempted after the rejection. Native Edge access also
produced permission prompts; native control is unnecessary for reading the two
webpage DOMs.

## Futu

Page: <https://www.futunn.com/hk/stock/AAPL-US/financials-revenue>.
The existing rendered page is readable. Its Business section exposes period,
currency (USD), category, revenue and proportion as DOM text. The five categories
correspond to Apple's product/service categories. The separate Region section
has its own independent annual period selector; do not join it to Business
using the selected business quarter.

The Business selector initially shows fiscal 2026/Q3. Its visible options include
2026/Q3, 2026/Q1, 2025/FY, 2025/Q3, 2025/Q2, 2025/Q1, 2024/FY, 2024/Q4,
2024/Q3 and older periods. There are gaps among recent quarter options, including
2026/Q2 and 2025/Q4. An FY entry must not be treated as a single quarter.
The fiscal labels also differ from Stock Analysis's display dates.

Selecting 2025/Q3 updates the selected label before revenue values finish
refreshing. A subsequent DOM observation confirms that the revenue values changed.
A collector must wait for the values belonging to the selected period, rather
than capture the first snapshot after clicking. The period is restored to the
initial 2026/Q3 after the check. Continuous latest-eight-quarter coverage has not
been established.

The earlier public retrieval's 403 applies only to that retrieval. It provides
no evidence that this existing live tab cannot be read. No Futu export control
has been established; the site's header Download link is an app download link.

## Scope of terms concerns

Stock Analysis terms: <https://stockanalysis.com/terms-of-use/>, updated
2026-10-29. The Automated access section restricts bots, scripts, scrapers,
browser automation and bulk downloading. It includes the exception beginning
“This does not apply to search engines, AI agents” for robots-compliant crawlers.
The separate Your account section states:
“You may not let other people, machines or systems access your account.”
These are separate clauses; the crawler exception does not clearly authorize
authenticated account automation. A user manually operating the native export,
an agent performing a single explicitly requested native click, and a 30-company
batch scraper are distinct operations. The mere existence of a Download control
does not settle the terms for the latter two, nor do those clauses establish that
a user may never manually export data. Do not turn a terms interpretation into a
claim of technical inability.

Futu agreement: <https://www.futunn.com/about/services?lang=zh-hk>, updated
2024-08-13. Section III(3)(6) concerns using non-authorized third-party
software/plugins to log in to or use its services; III(3)(4) concerns copying or
changing runtime/client-server data and unauthorized tool integration. Section V
and the appendix concern use and redistribution of market data. These clauses
do not constitute evidence that DOM text is technically inaccessible. This task
establishes live DOM readability and one historical-period interaction, not a
general license to batch-copy or redistribute the data.

The immediate operational blocker for the CSV test is the pending download
permission. No new login, password, account setting or vendor authorization
change was requested by either page during this check.
