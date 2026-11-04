# SEC Revenue Breakdown

Cloud research workspace for SEC revenue composition across the S&P 500, 400
and 600, starting with a prior 30-company, eight-quarter experiment.

**Current status:** recovered SEC source, 12 original synthetic tests and the
30-company roster are integrated from `local/vendor-reference` at `4113daa`.
Cloud verification passed all 18 tests (12 recovered + 6 archive safety) and
matched all 10 recovered file hashes to the local recovery manifest. Original
archives, cached SEC HTML and saved candidate datasets remain outside this
cloud checkout; the local data-reproduction report is preserved separately.
No third-party reference comparison has been performed.

- [Cloud status, validation and blockers](docs/CLOUD_HANDOFF.md)
- [Research requirements, known issues and next steps](docs/RESEARCH_PLAN.md)
- [Archive identities and source registry](research/sources.json)
- [Recovered SEC source entry point](research/recovered-sec/HANDOFF.md)
- [Cloud integration review](docs/RECOVERED_INTEGRATION.md)
- [Cloud verification evidence](research/cloud-verification.json)

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
