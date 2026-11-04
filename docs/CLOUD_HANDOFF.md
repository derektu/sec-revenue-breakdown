# Cloud continuation — 2026-11-04 UTC

## Repository and environment

- Remote: `https://github.com/derektu/sec-revenue-breakdown.git`.
- GitHub connector confirmed `visibility: private`, default branch `main`, and
  current account pull/push permissions. Visibility was not changed.
- Fetched remote HEAD at `2be07eaceee665ad04c0b2486fbdc19f00c0b9b6`.
  It contained only `README.md`. The environment initially had an unborn `work`
  branch, no commits checked out, and a fetch refspec for HEAD only.
- Created `research/cloud-baseline` from the fetched remote HEAD. Existing main
  and user work were preserved. No applicable `.agents/skills` or `AGENTS.md`
  files were present in this checkout or the workspace instruction directory.
- Cloud is running independently of the Mac. No browser session, credential or
  vendor dataset was transferred from the Mac.

## Archive retrieval blocker

Library resolved all three files with names, IDs and byte sizes recorded in
`research/sources.json`. This verifies metadata availability, **not local file
readability or archive contents**. No archive has been downloaded or extracted.

The current Library skill's three Python companion helpers were fetched into a
new private scratch directory outside the repo. The complete unchanged structured
search result, explicit selection `000001002`, and relative destination were
passed to the prescribed download helper. It exited with:

```
library download request failed: hosted apps tools/list request failed: network
```

This is a runtime transfer failure; its exact host/root cause is not exposed by
the helper. It was not an approval rejection. No raw signed-URL transfer,
alternate download implementation or credential workaround was attempted.
Repair the supported hosted-app transfer connectivity, then resume the Library
skill download workflow. Helper inputs and scripts remain in
`/workspace/scratch/sec-library-*` for this run only; fetch current helpers again
in a new run. These scratch paths are not portable deliverables.

## Network limits

The enforced cloud policy allows the package-manager preset and GitHub git
operations. `www.sec.gov`, `data.sec.gov` and `api.github.com` are absent from
the allowlist. `gh repo view` failed with `Forbidden`; repository visibility
was instead confirmed through the available authorized GitHub connector.
Do not infer missing git authentication from that API-domain restriction.
Do not edit the network-policy snapshot or bypass its proxy.

## What is ready

The repo now records the research scope, provenance requirements, source archive
identities, known baseline limitations and concrete resume steps. The standard
library archive tool audits hashes and sizes, rejects dangerous paths, links,
cache/credential entries and known credential signatures, validates ZIP CRCs,
and stages only into ignored `data/staging/` without overwriting prior work.
It does not establish that arbitrary text is credential-free or redistributable;
manual file/content review is required before tracked promotion.

The included tests cover import safety, not SEC extraction correctness. Original
experiment code, datasets, original tests, exact cohort, periods and source
filing URLs remain unavailable until archive retrieval succeeds. The prior
234/240 and 138-quarter figures have not been reproduced. There is no claim of
Stock Analysis/Futu comparison or vendor validation.

## Validation

Run from the repo root:

```sh
python3 -m unittest discover -s tests -v
python3 -m json.tool research/sources.json > /dev/null
git diff --check
```

Executed in this cloud environment on 2026-11-04: all six tests passed (0.007s),
the source registry parsed successfully, and `git diff --check` passed. These
checks cover the new staging foundation only. Resume details are in
`docs/RESEARCH_PLAN.md`; no always-on local computer is required for those steps.
