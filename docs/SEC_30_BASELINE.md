# Executed cloud SEC candidate baseline — 2026-11-04

The fixed 30-company roster was rerun from original SEC submissions and inline
XBRL filings, using the unchanged recovered parser and quarter audit at `3eaba53`.
The cutoff is **2026-11-04**, inclusive by SEC filing date. Each issuer selects its
latest eight unique 10-Q/10-K report dates; a ninth filing supports annual-minus-
nine-month Q4 arithmetic. Fiscal quarter ends differ. This is a generic XBRL
candidate and arithmetic baseline, with no Stock Analysis or Futu inputs.

The working checkout was initially an unborn `work` branch without user files or
changes. The requested remote branch was fetched, then a separate
`research/sec-30-baseline` branch was created. No main checkout or main push was
performed. No applicable AGENTS.md or `.agents/skills` was present.

## Results

| Observed quantity | Count |
| --- | ---: |
| Companies attempted | 30 |
| Requested quarter slots | 240 |
| Selected and processed quarters | 234 |
| Missing issuer-history slots | 6 |
| Original filing HTML snapshots | 263 |
| All source snapshots, including submissions JSON | 309 |
| Source bytes (ignored raw cache) | 890,476,285 |
| Download/discovery errors | 0 |
| Numeric parse exceptions | 5 |
| Conflicting duplicate groups rejected | 2 |
| Quarter candidate facts | 9,000 |
| Annual-minus-nine-month derived candidate facts | 1,732 |
| Single-axis candidate groups | 524 |
| Groups matching at least one candidate total | 258 |
| Quarters with at least one such match, any axis class | 138 |
| By source heuristic groups | 290 |
| By source heuristic groups matching a candidate total | 148 |
| Quarters with at least one By source heuristic match | 114 |

The 29 issuers other than XOM have all eight endpoints. XOM uses successor CIK
2115436 and has only 2026-06-30 and 2026-09-30. Legacy CIK 34088 is deliberately
not joined. Six missing slots have explicit status and blank dates, rather than
invented historical quarters. A successor/legacy continuity decision is needed
to obtain 240 actual endpoints under a revised identity policy.

“By source” here includes only axes whose name heuristic yields product/service
or operating segment, excluding axes classified as geography by name. It is a
candidate subset, not a semantic mapping to a vendor's categories. Apple’s
operating segments can be geographic despite their axis name. A successful sum
does not establish hierarchy, accounting scope, completeness, or accuracy.
The 138-quarter figure includes geography and unclassified axes; it must not be
presented as 138 successful By source extractions.

## Retained evidence

Results are under [`research/sec-30-baseline-2026-11-04`](../research/sec-30-baseline-2026-11-04):

- `company_summary.csv`: every issuer, processing state, counts and history gap.
- `quarter_summary.csv`: all 240 requested slots; report/filing dates, observed
  candidate start dates, accession, source URL/SHA-256, parse-error count in the
  current filing, rejected duplicate count, Q4 derivation and group counts.
- `TICKER.json.gz`: complete public SEC-derived results, including original raw
  candidate facts per filing, parse errors, all selected quarter facts, exact
  annual/nine-month Q4 operands and citations, candidate totals and comparisons.
  Use Python `gzip.open(path, 'rt')` then `json.load(...)` to inspect.
- `quarter_candidates.csv.gz`: 9,000 candidate observations with period, unit,
  dimensions, evidence and Q4 operands. This is not a clean composition dataset.
- `manifest.json`: URLs, accessions, report/filing dates for HTML, sizes and SHA-256
  for all 309 sources. Paths refer to the ignored recovered audit cache.
- `exceptions.json`: five numeric parse errors plus the two rejected conflicting
  duplicate groups. Supporting ninth filings are included in parse-error counts.
- `summary.json`, `verification.json`: aggregate/per-issuer metrics, artifact and
  executable-source hashes, and completed replay/source-check counts.

The whole derived package is about 2.6 MiB compressed. Large HTML/submissions
caches, original archives, secrets, browser state and vendor data are excluded
from Git. Source manifests permit fresh retrieval and byte-identity checks;
SEC can revise a served document, in which case a hash mismatch must be reviewed.

[`sec-30-network-check.json`](../research/sec-30-network-check.json) records HTTP
200 from both SEC hosts with the enforced corrected policy. The inherited HTTPS
proxy and CA trust were used with TLS verification enabled. The User-Agent
identifies Derek's research project and genuine public GitHub contact profile;
no invented email is used. Only one downloader process ran, with two workers and
a shared 0.22-second minimum interval between request starts (under five/second),
three attempts maximum and backoff. There were no download failures.

## Reproduce

Use Python 3.12 and `lxml==6.1.1`. Preserve the environment's proxy/CA settings.
Set `SEC_USER_AGENT` to a genuine identifying operator/project contact. Do not
use the recovered runner's placeholder default. Start only one downloader process.

```sh
python3 -m pip install -r research/recovered-sec/requirements.txt
export SEC_USER_AGENT='Your actual operator/project identity and contact'
python3 research/recovered-sec/eight_quarter_eval/run.py --workers 2 --as-of 2026-11-04
python3 research/recovered-sec/eight_quarter_eval/summarize.py
python3 scripts/package_sec_baseline.py export research/new-sec-baseline-run
python3 scripts/package_sec_baseline.py verify research/new-sec-baseline-run
```

The runner reuses existing raw downloads and rewrites generated ignored outputs.
Use a fresh checkout for independent retrieval. The exporter requires a new
destination and refuses to overwrite an existing result directory. It verifies
all source sizes/hashes and recomputes every processed quarter before packaging.
No network or raw HTML cache is needed to verify the committed package:

```sh
python3 scripts/verify_recovered.py
python3 scripts/package_sec_baseline.py verify research/sec-30-baseline-2026-11-04
git diff --check
```

Executed checks: all 18 synthetic/safety tests passed; 10 recovered source hashes
matched their recovery manifest; all 309 downloaded source sizes/hashes matched;
all 234 quarter results were recomputed from preserved candidate facts and
matched, including exact Q4 operands and all group checks. All 36 packaged data
artifacts passed SHA-256 verification. Replay tests arithmetic determinism from
saved parser output; it is not an independent standards-aware re-extraction.
The separate [`sec-30-tests.json`](../research/sec-30-tests.json) records only
source/synthetic tests, so its historical baseline-recomputation flags remain
false; the new package verification records the executed data replay.

## Exceptions and limits

Lilly's FY2024 supporting filing has two revenue strings rendered as `no`, which
the parser does not transform. Prologis has two sales-agent-count strings rendered
as `twenty`; Tesla has an empty available-for-sale-securities fact. The latter
three also demonstrate the broad revenue/sales regex's false positives. No zero
is invented. Berkshire's 2024 and 2025 year ends each contain one conflicting
duplicate group, rejected by the audit; original alternatives remain in raw facts.

The preserved baseline uses exact concept/unit/member/start-date matching for
Q4 and refuses renamed members; it does not certify recast consistency across
filings. Parent/child subtotals can overlap, and multi-axis compositions such as
P&G's are preserved in candidates but excluded from single-axis group checks.
Bank/insurance consolidated totals are not fully covered by the concept whitelist.
Entity scope, amendments, all XBRL transformations/continuations, taxonomy labels
and linkbase hierarchy remain unresolved. See the recovered
[method and limitations](../research/recovered-sec/eight_quarter_eval/README.md).

SEC access is resolved. Outstanding work is semantic/standards-aware validation,
any explicitly approved successor continuity mapping, and importing authorized
Stock Analysis/Futu references for a broader cohort comparison. The separate
[local Apple DOM comparison](vendor/apple-comparison.md), merged through PR #3,
reports 40 Stock Analysis values and 25 Futu values matching saved SEC evidence.
Its raw inputs remain on the Mac and were not used or revalidated by this cloud
baseline. Native CSV export and cross-company vendor accuracy remain unverified.
No accuracy or vendor-agreement percentage is claimed for this baseline.
