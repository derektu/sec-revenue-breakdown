# SEC Revenue Breakdown

Cloud research workspace for SEC revenue composition across the S&P 500, 400
and 600, starting with a prior 30-company, eight-quarter experiment.

**Current status:** the private repository is accessible from the cloud. Prior
research archives have been located in Library but their download is blocked
by the cloud transfer runtime. Original experiment code/data and results are
not yet imported or reverified. This branch supplies safe staging and explicit
continuation instructions; it is not a replacement SEC extraction baseline.

- [Cloud status, validation and blockers](docs/CLOUD_HANDOFF.md)
- [Research requirements, known issues and next steps](docs/RESEARCH_PLAN.md)
- [Archive identities and source registry](research/sources.json)

Python 3.11+ is sufficient for the staging tool and its tests; no packages or
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
