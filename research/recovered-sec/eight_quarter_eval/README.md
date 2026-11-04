# Latest eight-quarter SEC revenue candidate experiment

This is an executed, reproducible **uncurated deterministic candidate audit**, not a production extractor and not an accuracy benchmark. The fixed 30-company roster is in `roster.json`. Each issuer uses its latest eight report dates in 10-Q/10-K filings available by **2026-11-03**. Fiscal quarter ends differ by issuer. SEC's ticker directory is saved as `company_tickers.json`.

## Run

Python 3.12 and `lxml` (the dependency used by the parent experiment):

    SEC_USER_AGENT='Your Organization your-real-contact@example.com' python run.py --workers 4
    python summarize.py
    python -m unittest -v test_run.py

Use a genuine operator contact for new downloads. Requests are paced per process, with three attempts and backoff. Run one downloader process at a time in production. Cached source snapshots are reused. Default as-of date is frozen, not automatically today's date. `--as-of YYYY-MM-DD` and `--tickers AAPL,MSFT` are supported. The first exploratory run additionally downloaded INTC; `summarize.py` excludes it because it is not in the frozen 30-company roster.

## Actual method

1. Download SEC submissions JSON and select latest 9 unique 10-Q/10-K report dates. The ninth filing supports Q4 reconstruction for the eighth reporting endpoint. No predecessor CIK is silently joined. XOM's new successor CIK is deliberately flagged.
2. Download original inline-XBRL HTML. Preserve URL, accession, filing date, bytes, SHA-256 and full source.
3. Use the prior pilot's broad revenue/sales concept parser. Preserve raw text, unit, decimals, scale, context, dimensions, fact ID, source table/row and source line. This also catches false positives; **raw candidates are not validated revenue observations**.
4. For each report date, use duration 70–126 days for directly reported quarter facts. Never treat a nine-month fact as Q3 just because its end date matches. For annual filings, derive Q4 only when annual and nine-month facts share exact concept, unit, dimension signature and start date, and the resulting quarter duration fits. Preserve both operands and citations. No fuzzy member mapping is applied.
5. Collapse equal duplicates; reject conflicting values for an identical concept/unit/dimension/period key. Keep separate multi-dimensional contexts instead of flattening them into a one-axis composition.
6. Group single-axis facts by concept, axis and exact quarter period. Compare sums to same-concept undimensioned revenue candidates, or other whitelisted undimensioned revenue concepts if none exists. Preserve every candidate total and each comparison rather than silently choosing a potentially partial total. A rounding tolerance is used for reported values. Cross-concept matches are only candidates and can be coincidental.
7. Classify axes by a visible, deliberately simple name heuristic; preserve original axes and members. **This is not a resolved parent-child accounting hierarchy.** Products subtotals and detailed products can overlap. Such groups should fail, not be advertised as accurate. Presentation/calculation/definition linkbases, recasts and narrative table interpretation remain future work.

## Artifacts

- `data/TICKER/*.html`: exact raw SEC snapshots; `submissions.json`: discovery response.
- `outputs/TICKER.json`: raw candidate facts from every filing plus eight-quarter candidates, original operands for Q4, reconciliation groups and exceptions.
- `outputs/manifest.json`: provenance manifest for frozen 30-company roster.
- `outputs/company_summary.csv`: per-company coverage and failure metrics.
- `outputs/quarter_summary.csv`: one row per available issuer fiscal-quarter endpoint.
- `outputs/quarter_candidates.csv`: candidate values plus citations and Q4 operand provenance. **Not a clean composition dataset.**
- `outputs/summary.json`: aggregate metrics and per-company results.
- `tests.log`, `run.log`, `run_rest.log`: execution evidence.

## Interpret coverage honestly

"Processed" means downloaded and parsed, not correct. "Has a dimensional group" means at least two candidates under a single axis, not that this axis is a valid complete revenue composition. "Reconciled" means a sum is consistent with at least one candidate total, not semantic correctness, source-disclosure completeness or independent ground truth. A company can have 8/8 reconciled geography groups while its product composition still fails.

No TradingView reference was obtained or compared. No accuracy, recall, TradingView agreement, model cost, model latency or cross-source equivalence is claimed. No LLM was invoked by this harness. This experiment isolates the deterministic extraction and period/hierarchy difficulties.

## Known limitations and honest abstention

- The parser is not a standards-complete iXBRL processor. It does not resolve transformations, continuations, all nil semantics, entity identifiers, hidden facts or taxonomy linkbases. Missing/unsupported numeric strings are errors, not silently guessed.
- Taxonomy/member renames prevent annual-minus-nine-month matching. Exact-name continuity can also hide a business-definition change; no semantic continuity guarantee is made.
- Q4 derivation across separately filed reports may mix original and recast bases. Operands remain visible for review, but no automatic recast certification is attempted. Derived rounding tolerances are not a full XBRL precision-interval engine.
- Common US-GAAP consolidated revenue tags do not cover every banking, insurance, REIT or utility presentation. Lack of a whitelisted candidate total is a coverage gap, not zero revenue.
- Undimensioned does not by itself prove consolidated entity scope. Multiple issuing entities and investee facts require additional scope checks.
- The submissions selector starts with `filings.recent` and retrieves archived submissions when fewer than nine report dates are available. A genuinely new issuer can still have insufficient history.
- A dimension can contain parents, leaves and totals. Source table/row and member evidence are preserved, but hierarchy resolution remains an explicitly unimplemented stage.

Nine synthetic regression tests exercise duration selection, Q4 arithmetic, exact-member abstention, conflicting duplicate rejection, equal-duplicate collapse, double-counting rejection, multi-axis preservation and direct-Q4 preference, and a 16-week retail quarter. They test code behavior, not the correctness of every filing extraction.

## Concrete observed failure cases

- Apple Q3 FY2026: the same ProductOrServiceAxis contains Products 78,678 million, Services 30,739 million, and four individual product categories totaling 78,678 million. Adding all six gives a false double count. The correct consolidated candidate is 109,417 million. The evidence is the original fact rows in the AAPL JSON, not a fabricated hierarchy edge.
- P&G: segment revenue uses both StatementBusinessSegmentsAxis and ConsolidationItemsAxis. A single-axis-only extractor misses the composition even though the facts were retrieved. The baseline exposes this limitation rather than treating it as no disclosure.
- Costco: fiscal Q4 is 16 weeks, so a calendar-quarter-like upper bound of 110 days incorrectly excludes it. The final guard supports 70–126 days and includes a dedicated regression test.
- JPMorgan/Bank of America: recent submissions can contain fewer than eight quarters because of their frequent filings; archived submissions are needed.
- ExxonMobil: ticker-directory CIK 2115436 is a successor with shorter history. Bridging to legacy CIK 34088 is a separate identity/continuity decision, not an automatic ticker-name join.

Original 10-Q/10-K submissions are used; 10-Q/A and 10-K/A amendments are not independently resolved. This is an additional limitation for restatement-sensitive use.

Observed numeric parser exceptions include two Lilly `us-gaap:Revenues` facts whose rendered text is “no” (FY2024), two Prologis sales-agent counts rendered as “twenty,” and an empty Tesla available-for-sale-securities fact. These are retained as parse errors. The Lilly revenue-word transform is a genuine parser-support gap; no zero is invented.
