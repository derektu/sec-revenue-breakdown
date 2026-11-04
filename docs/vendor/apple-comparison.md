# Apple local reference comparison

Executed 2026-11-04 using the user's existing Edge pages. Research-only DOM
observations, their normalized values and the detailed comparison remain below
Git-ignored `data/vendor/local/apple-20261104/`. No original third-party data is
published or committed. The repository contains the reusable offline comparison
script and this findings summary.

## Observed result

| Check | Observed result |
| --- | --- |
| Stock Analysis quarterly product/service observations | 8 quarters, 40 values |
| Stock Analysis values equal to saved SEC candidates | 40/40 |
| Stock Analysis five-category sums equal to saved SEC consolidated totals | 8/8 |
| Futu observations within the same target period range | 5 quarters, 25 values |
| Futu values equal to Stock Analysis and saved SEC candidates | 25/25 |
| Futu displayed percentages consistent with saved SEC totals | 25/25 within 0.005 percentage points |
| Futu target quarters absent from the visible selector | FY2026 Q4, FY2026 Q2, FY2025 Q4 |
| Native CSV file format/content verified | No |

The target display dates are 2024-12-31 through 2026-09-30. Stock Analysis uses
calendar-end display labels, while Apple SEC quarter ends fall on fiscal dates
a few days earlier. Futu uses Apple fiscal labels. The comparison uses an explicit
reviewed Apple period mapping, not a join on equal date strings. FY entries are
excluded from quarterly comparisons; missing Futu quarters are not filled in.

The source of Stock Analysis values is the rendered chart's accessibility labels,
which expose full-dollar amounts. Its History table abbreviates billions. The
source of Futu values is the rendered Business DOM after the selected quarter's
revenue values refresh. Chinese 億 is normalized as 100,000,000 USD. Futu changes
row order by period, so categories are mapped by their reviewed labels rather
than row position. The Region section is outside this product/service comparison.

SEC evidence is the recovered `AAPL.json` from the frozen 2026-11-03 candidate
audit. Five exact product/service members under the disclosed axis are selected;
the Products subtotal is excluded. Q4 values in that evidence are annual-minus-
nine-month derivations with saved operands. This comparison does not independently
certify those operands against recasts or reparse the eight raw filings. Matching
values do not establish cross-company accuracy or full disclosure recall.

## Reproduce offline

From the repository root, with the private local captures and recovered archive:

```sh
data/vendor/local/.venv/bin/python scripts/compare_apple_reference.py \
  --capture-dir data/vendor/local/apple-20261104 \
  --sec-evidence data/vendor/local/research-imports/eight_quarter_reproducible_results/sec_revenue_experiment/eight_quarter_eval/outputs/AAPL.json
```

The script makes no network requests. It validates issuer, schemas, currency,
quarter labels and five-category coverage, and rejects missing/conflicting SEC
values. `comparison.json` is written inside `--capture-dir`; it refuses to overwrite
an existing result. Reproducing after the first run requires choosing a new local
capture directory containing the two input captures. Input SHA-256 values, raw
values, fiscal mappings and per-observation outcomes stay in that ignored result.

A local negative control changes one captured Stock Analysis value by one USD.
It reduces the equal-value count by one and the matching-quarter-sum count by
one. A mixed FY label is rejected. These controls check that disagreement and
non-quarterly periods are detected, rather than forcing a successful comparison.

## Native export status and next step

The earlier single Download to CSV action has no confirmed completed artifact.
The exact pending download permission was checked again before this work; no
affirmative reaction was available. No duplicate download was triggered. DOM
observations are labelled as DOM captures, not native vendor CSV exports.

To finish the native-export test, resolve the existing Stock Analysis download
permission, confirm whether a file was produced, and only then decide whether
one retry is necessary. The tool restriction on `edge://downloads/all` remains
in force. No alternative route to the blocked page was used. No login change,
credential extraction or hidden vendor endpoint was required for the DOM sample.

## Batch readiness

The Apple-only offline comparison is reusable, with explicit issuer-specific
period and category mappings. It is not a 30-company scraper. Expanding to other
issuers requires checking their actual categories, units, period definitions,
source availability and applicable access conditions. The current 30-company
coverage roster remains a plan; Apple is the sole vendor comparison performed.
