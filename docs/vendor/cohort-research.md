# Thirty-company vendor reference study

Executed locally on 2026-11-04 against the frozen 30-company roster and the
SEC candidate baseline in `research/sec-30-baseline-2026-11-04/`.
The complete roster is accounted for, including failed acquisition attempts.
This is a coverage study and numeric candidate diagnostic, not a certified
revenue-composition dataset or a cross-company accuracy score.

## Coverage actually observed

| Source | Issuers with captured values | Period observations | Numeric observations |
| --- | ---: | ---: | ---: |
| Stock Analysis Quarterly DOM, including the prior Apple capture | 22 | 176 | 728 |
| Futu supplementation: MCD, CVX, PGR | 3 | 19 | 90 |
| Prior Apple Futu sample, documented separately | 1 | 5 | 25 |

Apple overlaps the two sources. There are 25 distinct issuers with vendor
observations. Eight displayed vendor periods do not necessarily cover the SEC
baseline's latest eight fiscal periods: vendor lag and calendar labels must be
checked. No count in this table implies complete latest-eight-quarter coverage.

Stock Analysis captures cover AAPL, MSFT, NVDA, ORCL, GOOGL, META, DIS, CMCSA,
AMZN, TSLA, HD, COST, PG, KO, JNJ, UNH, LLY, JPM, BAC, CAT, UPS and LIN.
Its standard revenue-by-segment route returned 404 for MCD, WMT, PGR, XOM, CVX,
NEE and PLD. Each failed route was rechecked. BRK-B required symbol resolution:
the site's search returns BRK.B; its canonical company page did not expose a
Metrics navigation link. The failed dash-symbol route is not evidence that
Berkshire has no revenue disclosure.

Futu supplied seven target-range quarters for MCD, five for CVX and seven for PGR.
It shows Business “暫無內容” for WMT, XOM and NEE, and also for Berkshire after
resolving BRK.B through onsite search and following its financial navigation.
The PLD revenue and earnings routes returned 404. These five companies lack
vendor observations in this study; their revenue is not zero. Futu has only
been checked for Apple and these eight supplementation targets, not all 30.

The PGR revenue page was readable after following the site's earnings navigation;
its first direct-page snapshot lacked the Business section. Therefore missing
initial DOM content alone is not treated as proof that a source has no data.
Its Business list was expanded with the visible 查看全部 control before capture.

## Comparison and interpretation

The script `scripts/compare_vendor_cohort.py` compares locally captured values
against the actual saved SEC quarter facts. The source-specific diagnostics are
in [cohort-diagnostics.json](cohort-diagnostics.json). Its counts contain no
original vendor amounts, category rows, percentages or source tables.

Across Stock Analysis's 728 numeric observations, 642 have a numeric SEC
candidate within the captured precision, 68 lack such a candidate, and 18 lack
a usable period alignment. Across the three supplementary Futu samples, 51 of
90 observations have a numeric candidate and 39 do not. **These are candidate
search results, not accepted semantic matches or accuracy percentages.** A
coincidentally equal value can belong to the wrong concept, dimension or scope.

For each numeric hit, the private report retains all matching facts, concepts,
dimensions, units, periods, contexts, derivation and source references. Multiple
matches are not silently reduced to a preferred answer. A lexical member-name
hint is separately recorded and explicitly does not certify meaning. A missing
candidate can reflect parser coverage, hierarchy, annual/Q4 derivation, recasts,
period alignment or an actual disagreement; it is not automatically a vendor error.

Exact dates are distinguished from proposed nearby dates. A unique nearest SEC
endpoint within seven days is a nearby-date proposal; a shift of up to 45 days
is separately marked as a fiscal-label proposal. Neither proposal is a reviewed
calendar mapping. More distant or equally near endpoints cause abstention.
Oracle and Home Depot need fiscal-label review; two Costco observations cannot
be aligned by this rule. The script never moves a period to make values match.

## Verified failure modes and scoped arithmetic checks

- **Missing versus zero:** Microsoft's table can show a dash where its chart
  accessibility label exposes zero. The collector preserves the table's missing
  value. Across the captured Stock Analysis cohort, 112 such chart-zero labels
  were suppressed. They are empty category/period cells, not zero revenue and
  not necessarily missing quarters.
- **Category availability changes:** MSFT, ORCL, KO and CAT have changing active
  category sets within the eight displayed periods. The report flags these for
  definition/continuity review; names are not automatically stitched together.
- **Comcast aggregation:** Connectivity and Platforms is broader than one SEC
  segment. An explicitly scoped sum of Residential Connectivity and Platforms
  plus Business Services Connectivity, on the OperatingSegments basis, matches
  five of eight captured periods. Three differ and remain open. The latest
  captured period matches. The Content and Experiences category remains unresolved.
- **Chevron geography and gross/net scope:** Upstream and Downstream can be
  reconstructed from the US and Non-US dimensions of gross sales on the exact
  OperatingSegments basis. Eight of ten attempted category/period reconstructions
  match; two Q4 reconstructions lack unambiguous operands and abstain. Intersegment
  eliminations remain negative. These scoped sums are reported separately from
  single-fact numeric candidates.
- **Amazon advertising Q4:** The baseline's annual facts use
  `us-gaap:AdvertisingMember`, while the preceding nine-month facts use
  `amzn:AdvertisingServicesMember` in both reviewed years. The exact-member Q4
  derivation therefore abstains. The two absent Q4 advertising candidates are a
  demonstrated continuity gap, not evidence that advertising revenue is zero.
- **Insurance coverage:** PGR's visible categories include underwriting revenue,
  service revenue, investment income and securities gains/losses. The baseline's
  revenue/sales-name filter is not a complete insurer income extractor. Unmatched
  rows require concept/scope review, and overlapping realized/holding-gain labels
  must not be summed without checking their definition.

## Local evidence and reproduction

Original observations and detailed matches stay under ignored
`data/vendor/local/cohort-20261104/`. The JSON inputs preserve the visible category
labels, missing cells, signed amounts, capture times, source URLs and units.
Numeric chart labels are normalized to USD millions with an explicit scale;
when chart labels were unavailable, abbreviated table strings are retained.
P&G uses these rounded table strings, so half of their display step is used as
tolerance. Futu's trimmed trailing zeroes do not create a coarse tolerance:
億 uses a reviewed 0.01-億 display step, and 萬 uses a one-萬 step.
Downloaded-file precision remains unverified.

```sh
data/vendor/local/.venv/bin/python scripts/compare_vendor_cohort.py \
  --captures data/vendor/local/cohort-20261104 \
  --private-report data/vendor/local/cohort-20261104/private-report-new.json \
  --summary data/vendor/local/cohort-20261104/shareable-summary-new.json
```

The command makes no network requests, checks that all roster issuers are
accounted for and refuses to overwrite output files. The detailed output is
restricted to ignored `data/vendor/local/`; the shareable output uses a separate
schema containing only counters and statuses. Input hashes stay with the private
report. Twenty-four tests pass: 12 recovered SEC tests, six archive safety tests
and six vendor-diagnostic tests covering missing values, units, currency, period
abstention, FY rejection and aggregation scope.

## Remaining acquisition limits

The previous Apple CSV download permission still has no verifiable affirmative
reaction or completed file result. No duplicate download is triggered. All new
vendor observations are explicitly DOM captures, not native CSV exports. No
login changes, credential extraction, hidden endpoints, CAPTCHA handling or
access-limit bypasses were used. No original third-party observations are pushed
to the repository. The study uses the user's stated private research scope;
it does not establish a general vendor license for other uses.

Further work is to resolve the native-export outcome, review fiscal/date mappings,
add evidence-backed category hierarchies and investigate each unresolved comparison.
The five unavailable vendor cases require another permitted reference source or
explicitly supplied evidence. They must remain marked as gaps until acquired.
