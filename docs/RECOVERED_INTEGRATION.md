# Recovered SEC source integration — 2026-11-04

## Provenance and boundaries

Merged `local/vendor-reference` at `4113daa` into `research/cloud-baseline` after
reading `research/recovered-sec/HANDOFF.md` and inspecting the code and documents.
The source branch remains intact; main was not changed. Its only conflict was
an independently added `.gitignore`, resolved by retaining both exclusion lists.
The recovered modules remain isolated under `research/recovered-sec/`; there
was no competing SEC parser in the cloud branch to overwrite.

All 10 files listed in `docs/vendor/recovery-manifest.json` match their imported
SHA-256 hashes in this cloud checkout. The manifest distinguishes the original
archive hash from the imported runner's whitespace-normalized hash. Imported
code and historical READMEs were not edited. The handoff-only `verify_local.py`
is also retained as supplied. Original README commands mentioning `download.py`
refer to a deliberately excluded historical file; use HANDOFF.md and this review
for current entry points.

No archive, full filing snapshot, vendor export, browser profile, credential,
execution log, cache or external sec-filing-agent dependency is tracked in this
handoff. The local task's coverage and acquisition notes are historical local
observations, not checks performed by the cloud. Third-party collection or
comparison has not been performed here.

## Compatibility and code review

- Python 3.12.14 and `lxml==6.1.1` are available and match the recovered setup.
- Pilot tests import only the parser/curated validator; audit tests import the
  quarter/group logic without executing the guarded downloader entry point.
  Test processes explicitly reject socket connections during cloud verification.
- `run.py` uses a frozen as-of date, exact duration/dimension matching, candidate
  totals, conflict rejection and separate multi-axis facts. `summarize.py` runs
  at module scope and writes output: do not import it for discovery. Downloader
  execution has not been authorized by this integration or attempted.
- Recovered network code retains a placeholder default User-Agent, multiple
  workers and cached mutable file paths. Before any online use, require the
  genuine operator identity, current SEC access rules, approved domains and one
  downloader process. Review request-error handling and cache integrity first.
- The parser is a small candidate extractor: it does not retain entity identifiers
  or resolve taxonomy hierarchies, transformations, nil values and continuation
  chains comprehensively. It converts displayed dash strings to zero. Thus it
  does not yet meet the stricter research contract in RESEARCH_PLAN.md; preserve
  this behavior for historical reproducibility, and fix it in a separately
  versioned extraction stage with evidence before treating output as observations.
- Single-axis groups compare to candidate totals; fallback cross-concept matches
  and undimensioned scope are unvalidated. Q4 operands can span changed accounting
  bases. A successful synthetic test or candidate sum does not certify these cases.
- The frozen roster contains 30 issuers. Intel is an exploratory extra excluded
  by the recovered summarizer. XOM's predecessor link, PG's multi-axis disclosure,
  COST's periods, taxonomy changes, amendments and recasts remain review items.

## Cloud validation actually performed

Run `python3 scripts/verify_recovered.py` from the repository root. It checks the
pinned lxml version, hashes for 10 recovered files and 30 unique tickers with
positive integer CIKs; then runs the three test suites in separate processes.
All **18 tests passed**, without skipped tests or failures:

- 6 archive safety tests.
- 3 recovered pilot tests.
- 9 recovered quarter/candidate audit tests.

The generated report is `research/cloud-verification.json`. The script runs
without the archives and performs no filing download or original-data replay.
Use optional `--report NEW_PATH` to save a fresh report; it refuses to overwrite.
Paths/IDs and pinned imported file hashes should stay paired with the recovery
manifest. New algorithm changes must retain the original snapshot and identify
their changed provenance rather than rewriting that manifest as if unchanged.

## Data checks still pending in cloud

`docs/vendor/offline-verification.json` records the **local task's** 3 archive
hash checks, 3 pilot HTML checks, 26 reconciliations and 234-quarter recomputation.
Those input bytes are not in this checkout, so none of those data checks was
rerun in cloud. The eight-quarter archive also lacked its raw 30-company HTML
cache, so even local saved-fact reproduction was not a fresh HTML reparse.

Next, obtain the original archives/saved evidence through an authorized supported
transfer and run `research/recovered-sec/verify_local.py` with real cloud paths.
Do not reuse the Mac's ignored directory path as if shared. Recompute the 138
quarter arithmetic-match count and reconcile exact fiscal periods and missing
quarters. SEC online refresh still requires user-reviewed environment changes
and a new task; details are in CLOUD_HANDOFF.md. No vendor accuracy benchmark
can be reported until suitable reference evidence has been supplied and compared.
