# Cloud continuation — 2026-11-04 UTC

## Completed SEC continuation

The subsequently republished environment correctly allows `data.sec.gov` and
`www.sec.gov`; both returned HTTP 200. The full fixed 30-company cohort was
executed as of 2026-11-04 on `research/sec-30-baseline`, based on `3eaba53`.
See [SEC_30_BASELINE.md](SEC_30_BASELINE.md) for results and reproduction.
There were 234 processed quarters, six successor-issuer history gaps, zero
download errors, and successful offline replay of every processed quarter.
Original archives and vendor reference imports remain separate unresolved work.
The historical sections below describe earlier environments and blockers, not
the currently verified SEC network policy.

## Current status after recovered-source integration

Integrated the reviewed `local/vendor-reference` branch at `4113daa`, preserving
its Git history, original source bytes and local recovery evidence. The only
merge conflict was `.gitignore`; both sets of exclusions were retained.
Cloud checks verified 10 manifest file hashes, the 30-company roster and all
18 synthetic/safety tests. See `docs/RECOVERED_INTEGRATION.md` and the executable
`scripts/verify_recovered.py` for the current continuation path.

The earlier records below describe the initial environment checks and failed
Library transfer attempts. Source retrieval is now resolved through the explicit
Git handoff; original archives, source snapshots and saved 234-quarter datasets
remain unavailable here. Source-only recovery does not establish cloud data
reproduction or vendor agreement. Network settings have not been changed.

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

### Bounded follow-up retry

On 2026-11-04, fetched all three helper companions again from the current
Library skill into a new private directory after removing the previous copies.
Reused the complete original structured search result and explicit selection.
Ran the supported download command once with a 45-second maximum. It exited
with code 1 immediately and the same error:

```
library download request failed: hosted apps tools/list request failed: network
```

Confirmed zero ZIP files in the designated destination. No contents, archive
hashes, original tests or baseline results could be verified. No additional
transfer route was attempted. No approval was denied and no write outcome is
uncertain. The error does not identify a blocked destination; adding SEC domains
must not be presented as a fix for this separate Library transfer failure.

The smallest supported escalation is to contact OpenAI Support through the
[Help Center chat bubble](https://help.openai.com/en/articles/6614161-how-can-i-contact-support)
with the cloud task ID `01a1a415-f259-76fd-b5e3-3d4c196f70f4`, date, this exact
error and the fact that search resolves all three archives while the download
fails at hosted-app tool discovery. No passwords, tokens, browser state or
unredacted network logs are needed for that initial report. User action is
pending; this task has not contacted support. We cannot identify a narrower
self-service Library network fix from the available evidence.

## Network limits

The enforced cloud policy allows the package-manager preset and GitHub git
operations. `www.sec.gov`, `data.sec.gov` and `api.github.com` are absent from
the allowlist. `gh repo view` failed with `Forbidden`; repository visibility
was instead confirmed through the available authorized GitHub connector.
Do not infer missing git authentication from that API-domain restriction.
Do not edit the network-policy snapshot or bypass its proxy.

### User-reviewed SEC access setup

Verified against the current official
[Cloud environments documentation](https://developers.openai.com/codex/environments/cloud-environments)
on 2026-11-04:

1. Open **Settings > Codex Cloud > Environments**. On
   **sec-revenue-breakdown**, select **… > Edit**.
2. In **Public internet access**, keep full internet access disabled. Under
   **Additional allowed domains**, add `www.sec.gov` and `data.sec.gov` as
   separate hosts; retain the existing package-manager setting.
3. Save, test those services in setup, and select **Republish** after reviewing
   the configuration. Start a **new task** using the updated environment and
   the `research/cloud-baseline` branch. Existing tasks retain their state.

If workspace policy prevents the change, ask the workspace administrator to
review it. This task made no network configuration changes. After publication,
check current enforced policy and test SEC access with an identifying User-Agent;
an allowed domain alone does not establish successful SEC access. Library transfer
connectivity must be repaired and verified separately.

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

Follow-up verification on 2026-11-04: all six tests passed again (0.009s), source
JSON and `git diff --check` passed. These were rerun after the unsuccessful
download retry to confirm the unaffected work remains usable.
