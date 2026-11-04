# Recovered SEC experiments

This source-only package contains the deterministic SEC pilot and eight-quarter
candidate audit recovered from three research archives on 2026-11-04. All three
archives passed ZIP CRC checks. Archive checksums, sizes and source-file mappings
are in `../../docs/vendor/recovery-manifest.json`.

The import uses its own directory and has no code dependency on the cloud baseline.
`extract.py` is byte-identical in the two archives that include it. The import
preserves its source, the curated `validate.py`, both test suites, the 30-company
roster and the candidate-audit runner/summarizer. `verify_local.py` is an offline
verification entry point. One trailing space in the archived runner is normalized;
the manifest records both source and imported hashes. No external third-party
repository code is vendored.

The third archive, `sec-filing-review.zip`, contains a review and scripts dependent
on a separate external repository at a pinned commit. Its contents remain in the
ignored local import directory; none of that external dependency was fetched or run.
Historical outputs, full filing snapshots, execution logs, environment exports and
the pilot downloader with a placeholder contact are excluded from this source package.

## Run offline verification

From the repository root, using Python 3.12 with `lxml==6.1.1`:

```sh
data/vendor/local/.venv/bin/python research/recovered-sec/verify_local.py \
  --imports data/vendor/local/research-imports \
  --results data/vendor/local/verification
```

The command requires the three original archives and their extracted directories.
It verifies archive hashes and the three raw pilot filing hashes, runs 3 pilot and
9 audit tests, reparses the three cached pilot HTML snapshots, runs curated pilot
reconciliation, and recomputes saved quarter candidates/groups from saved raw facts.
It writes disposable data/outputs beneath this package and logs under `--results`.
Those paths are Git-ignored. The command makes no network requests.

Observed local verification: 12 tests pass; 26/26 curated group reconciliation
checks pass; all 234 processed quarters across the 30-company roster reproduce the
stored quarter facts, totals, groups and conflicting-duplicate counts. This is
reproducibility of the saved experiment. It does not measure disclosure recall,
semantic accuracy or agreement with Stock Analysis/Futu.

The eight-quarter ZIP contains saved raw candidate facts and outputs, but omits
its `data/` source-HTML cache. Therefore this check does not reparse 30 companies'
raw HTML or independently validate those source snapshots. The pilot's three
raw HTML files are present in its separate ZIP and have been reparsed locally.

## Network runner constraints

The archived `eight_quarter_eval/run.py` retains its original behavior, including
a placeholder default User-Agent. It is research code, not an approved production
downloader. Supply a genuine authorized `SEC_USER_AGENT` before any network run,
review SEC access rules, and run one downloader process at a time. This task did
not execute its network path. A network run writes its own ignored cache/outputs.

The original READMEs retain historical findings and limitations. In particular,
reconciled totals do not prove correct composition; taxonomy hierarchy, entity
scope, recasts, amendments and cross-source semantic mapping require further work.
The cloud task should reconcile this recovered package with its existing baseline
before adopting any module. It should preserve provenance and avoid treating saved
candidate outputs as clean revenue-reference data.
