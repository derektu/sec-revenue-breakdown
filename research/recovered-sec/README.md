# SEC revenue composition feasibility experiment

Executed on 2026-11-03, Python 3.12.14. This is an actual raw-filing download and code execution experiment, not a literature review. It is a **deterministic extraction baseline with curated selection**, not a completed automated LLM benchmark. Historical 2024 filings were deliberately chosen as a small reproducible pilot, not as the latest financial information.

## Observed result

- Three raw SEC HTML filings successfully downloaded directly using Python urllib. Exact URLs, byte lengths and SHA-256 hashes are in `data/manifest.json`.
- Apple FY2024 10-K: 1,503,892 bytes. Amazon FY2024 10-K: 1,922,467 bytes. Amazon Q3 2024 10-Q: 1,385,053 bytes.
- Broad revenue/sales concept retrieval returned 91, 91 and 94 candidates respectively, with no numeric parse errors on these candidates. This is not a precision metric: the broad regex deliberately also catches false positives such as available-for-sale securities.
- After selecting the exact consolidated revenue concept, exact contexts and curated dimension memberships, 124 component-period observations were retained.
- All 26 product/service, operating-segment and geographic group-period sums matched their corresponding consolidated revenue exactly. The 10-Ks include three comparative annual periods each; the 10-Q includes current/prior quarter and current/prior YTD periods. Geography is not populated in this 10-Q extraction. Missing groups are not counted as successes.
- Three unit tests passed, covering scale/sign/context retention, duplicate collapse and conflicting-duplicate rejection. Negative controls confirmed duplicated components and quarter-plus-YTD mixing do not reconcile to quarterly revenue.

## Concrete findings from the data

Values below are USD millions, not investment guidance.

1. Apple FY2024 product/service: iPhone 201,183; Mac 29,984; iPad 26,694; Wearables/Home/Accessories 37,005; Services 96,169. Sum 391,035. The separate Products subtotal of 294,866 must NOT be added to those five components.
2. Amazon FY2024 product/service: Online stores 247,029; Physical stores 21,215; Third-party seller services 156,146; Advertising services 56,214; Subscription services 44,374; AWS 107,556; Other 5,425. Sum 637,959.
3. Amazon FY2024 operating segments: North America 387,497; International 142,906; AWS 107,556. Sum 637,959. These are a different decomposition of the same total. AWS appears in both presentations and must not be counted twice.
4. Amazon Q3 2024 quarterly revenue totals 158,877, while nine-month YTD totals 450,167. Both have the same period end, so selecting by end date alone is wrong.
5. Amazon advertising uses `amzn:AdvertisingServicesMember` in the Q3 filing, but `us-gaap:AdvertisingMember` in the annual filing. A name-only or fixed company-specific-member mapping can miss continuity even for the same company and fiscal year.
6. Apple operating segments are named geographically, but its separate geographical disclosure uses different country groups. Classification must preserve the disclosed axis and definition, not guess from the label alone.
7. Amazon Q3 also includes a `us-gaap:Revenues` fact for a nonconsolidated equity-method investee. A revenue-looking tag is insufficient to establish the reporting entity and scope.

## Reproduce

From this directory, install dependencies from `requirements.txt` in an appropriate Python environment if needed. Then run:

```
python download.py
python extract.py
python validate.py
python -m unittest -v test_extract.py
```

Existing local downloads are reused; delete only the files you intentionally want to fetch again. Before deploying download.py, replace its placeholder User-Agent contact with the operator's real authorized contact and implement SEC-compliant rate limits/backoff. No account credentials are used. This pilot made only a few sequential requests and did not require an install.

## Artifacts and provenance

- `data/*.html`: complete immutable source snapshots from SEC.
- `data/manifest.json`: URL, byte length and SHA-256.
- `outputs/*_facts.json`: candidate facts with original concept, dimensions, unit, raw text, scale, decimals, context ID, inline fact ID, source line, table index and source row text.
- `outputs/normalized.json`: selected normalized rows and revenue shares. The row explicitly records that selection used curated exclusions.
- `outputs/validation.json`: complete reconciliation results.
- `outputs/extraction.log`, `validation.log`, `test.log`: actual run results.

The manifest joins outputs by filename/filing identity. `source_line` can be coarse because SEC HTML is minified; context IDs, fact IDs, table index, row text and the original snapshot give better location evidence.

## What has and has not been demonstrated

Demonstrated: this cloud runtime can fetch real SEC filings, write/run Python, retain dimensional contexts and provenance, separate annual/quarter/YTD periods, and reconcile selected groups.

NOT demonstrated: cross-company production recall/precision, automated semantic grouping, longitudinal mapping accuracy, model API throughput/cost/latency, OCR, or any superiority of an agent framework. No external LLM API was invoked and no API credentials were requested. The analyst selected exclusions in validate.py after examining these filings. Those exclusions are not a general solution.

The parser is a small lxml baseline, NOT a standards-complete iXBRL processor. It does not resolve calculation/presentation/definition linkbases, taxonomy labels, continuation chains, all transformation formats, nil semantics, entity-scope variants or precision intervals. Unsupported numeric strings are reported rather than interpreted. It preserves decimals but does exact arithmetic instead of rounding-tolerance-aware validation. A successful reconciliation does not establish that every disclosure was captured or the selected grouping was conceptually correct.

## Recommended next experiment

Benchmark a hybrid pipeline before choosing an agent framework:

1. Freeze a varied corpus, for example 20-30 companies across software, retail, industrials, financials and healthcare, at least two years and one 10-Q each. Include restructurings, recasts and acquisitions.
2. Establish annotated ground truth for explicit revenue categories, scope, definitions, totals, periods and source locations. Hold out companies/years from rule creation.
3. Compare a standards-aware XBRL baseline, an HTML-table/text model extraction baseline, and a hybrid: deterministic values/context plus model-based table selection, classification and member mapping. Require cited evidence and explicit abstention.
4. Keep `product_service`, `operating_segment`, `geography` and `other` separate. Include parent-child relations, accounting basis, effective date, restatement flag and source. Do not synthesize undisclosed segment-by-product matrices.
5. Measure field accuracy, disclosure recall, evidence validity, abstention/review rate, total reconciliation, deduplication, period selection, model cost and latency on the held-out set. Report errors individually, not only aggregate sum checks.
6. Use narrative footnotes to distinguish reported revenue from bookings, GMV, ARR, intersegment sales and investee revenue. Net/gross recognition matters especially for marketplaces; sums alone cannot validate it.

A cloud coding agent is feasible for this work. The critical research question is extraction coverage and semantic correctness on a diverse held-out corpus, not whether the agent can execute Python or fetch these three files.
