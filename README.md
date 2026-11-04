# SEC Revenue Breakdown

Cloud research workspace for SEC revenue composition across the S&P 500, 400
and 600, starting with a prior 30-company, eight-quarter experiment.

**Current status:** the full 30-company SEC candidate baseline was executed in
cloud on 2026-11-04. Both SEC hosts are reachable. All 234 available quarters
were processed with zero download errors; six requested quarters are missing
because ExxonMobil's successor CIK has only two reporting endpoints. All 18
tests passed, source snapshot hashes were verified, and all 234 quarters replayed
offline. Public SEC-derived results and provenance are committed; large raw HTML
caches remain ignored.

Separately, the local Apple DOM comparison reports 40 Stock Analysis values
across eight quarters and 25 Futu values across five quarters matching saved SEC
evidence. Those vendor captures remain on the Mac in ignored paths; native CSV
export and broader vendor accuracy remain unverified. The generic cloud baseline
does not use vendor inputs.

- [Executed 30-company cloud baseline and reproduction](docs/SEC_30_BASELINE.md)
- [Per-company results](research/sec-30-baseline-2026-11-04/company_summary.csv)
- [All 240 requested quarter slots](research/sec-30-baseline-2026-11-04/quarter_summary.csv)

- [Cloud status, validation and blockers](docs/CLOUD_HANDOFF.md)
- [Research requirements, known issues and next steps](docs/RESEARCH_PLAN.md)
- [Archive identities and source registry](research/sources.json)
- [Recovered SEC source entry point](research/recovered-sec/HANDOFF.md)
- [Cloud integration review](docs/RECOVERED_INTEGRATION.md)
- [Cloud verification evidence](research/cloud-verification.json)
- [Local Apple reference comparison and limitations](docs/vendor/apple-comparison.md)

For all cloud source-integrity checks and synthetic tests, use Python 3.12 with
the recovered `lxml==6.1.1` dependency:

```sh
python3 scripts/verify_recovered.py
```

Python 3.11+ is sufficient for the staging tool alone and its tests; no packages or
network access are required:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/stage_archive.py /path/to/eight_quarter_reproducible_results.zip
python3 scripts/stage_archive.py /path/to/eight_quarter_reproducible_results.zip --extract
```

The first archive command audits only. `--extract` writes a fresh directory in
ignored `data/staging/`; it never executes imported code or updates git. Inspect
the staged files before promoting public SEC evidence and reviewed code into
tracked research folders. Restricted vendor data, browser state, credentials,
large caches and original archive staging are excluded from git.
