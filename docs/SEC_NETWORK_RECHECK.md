# SEC cloud network recheck — 2026-11-04 UTC

## Outcome

Started from `research/cloud-baseline` commit `528adb7` on a clean checkout.
Created the separate `research/cloud-sec-recheck` branch. No applicable AGENTS.md
or `.agents/skills` instructions were present. Main and the local vendor branch
were not modified. This record supersedes the earlier network observations in
`CLOUD_HANDOFF.md`; it does not rewrite their historical results.

The runtime reported current observations, an enforced restricted policy and
custom allowed hosts **`data.sec.org` and `www.sec.gov`**. The required API host
**`data.sec.gov` is absent**. This is a domain typo, not missing SEC credentials.
No secrets, runtime variables or outbound identities were configured.

Actual probes through the inherited HTTPS proxy, with CA verification enabled:

| Request | Observed result |
| --- | --- |
| `https://www.sec.gov/about/developer-resources` | HTTP 200; 68,453 bytes |
| `https://data.sec.gov/submissions/CIK0000320193.json` | Proxy tunnel 403 Forbidden (`URLError`) |
| Apple FY2024 10-K URL in the pilot manifest | HTTP 200; 1,503,895 bytes; parsed |

`research/cloud-sec-network-check.json` records the first two probes, timestamps
and hashes. Its `downloaded_filings: 0` describes those initial probes only; the
separate subsequent pilot manifest records one successful filing download.
The API denial was not retried. Latest user-message evidence was checked after
the denial and contained no correction to this network setting. No bypass or
alternate API hostname was attempted. This was a proxy policy denial, not an
automatic approval-review rejection and not an observed SEC rate-limit response.

## Bounded filing pilot actually performed

Downloaded the explicitly identified historical Apple filing:

`https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm`

The unchanged recovered parser produced **91 revenue/sales candidates, zero
numeric parse errors**. Saved facts include original concepts, dimensions,
periods, raw text, units, decimals/scale, context/fact IDs, row/table locations,
source URL and source hash. They remain broad candidates, not clean revenue
observations or a validated composition dataset. Parser scope, hierarchy,
transformations, nil values and continuation limitations still apply.

Tracked reusable artifacts:

- `scripts/sec_single_filing.py`: single explicit-URL fetch and parse entry point;
  requires an identifying User-Agent, makes no retries and refuses to overwrite
  an existing report directory.
- `research/cloud-sec-pilot-aapl-2024/manifest.json`: URL, retrieval timestamp,
  HTTP result, bytes, SHA-256 and exact parser hash.
- `research/cloud-sec-pilot-aapl-2024/candidates.json`: public SEC-derived
  candidates, not third-party subscription data.
- `research/cloud-sec-recheck-tests.json`: fresh offline source/test verification.
- `research/cloud-sec-cohort-status.json`: all 30 issuers explicitly not attempted
  in the latest-eight-quarter rerun because submissions discovery is blocked.

The full HTML remains in Git-ignored `data/cache/sec-single-filing/`; it is not
in the repository. The recorded filing is three bytes larger than the historical
pilot README's 1,503,892-byte snapshot, so this is a new fetch with its own hash,
not a claim of byte-identical recovery. Historical annual periods visible in
the new candidate output are FY2022, FY2023 and FY2024. No quarter derivation,
curated reconciliation or comparison with saved historical facts was performed.

To repeat the small pilot in cloud or local, from the repository root:

```sh
python3 -m pip install -r research/recovered-sec/requirements.txt
# Set SEC_USER_AGENT to your genuine operator identity and contact first.
python3 scripts/sec_single_filing.py \
  --url https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm \
  --report-dir research/a-new-pilot-directory
```

For these three bounded sequential probes the User-Agent identified Derek's
research project with the known public GitHub profile `https://github.com/derektu`.
No email address was invented. This identity was not reused for a bulk crawl.
The SEC's [developer rules](https://www.sec.gov/about/developer-resources) were
checked: identify automated access, fetch only needed content and remain below
10 requests/second across machines. These requests were sequential, with no
retry loop; the initial connectivity probes were paced at least one second apart.

## Full baseline still pending

Frozen reproducibility cutoff remains **2026-11-03**; this check occurred on
**2026-11-04 UTC**. No submissions JSON was obtained, no recent report endpoints
were selected, and **zero of 240 requested issuer-quarter slots were attempted**
in the full baseline. They are not 240 observed extraction failures. The one
historical Apple download is not counted toward that baseline.

The recovered period rules are unchanged: select up to nine unique 10-Q/10-K
report dates available by the cutoff, use the ninth to support Q4 operands,
retain direct 70–126-day quarters, and derive Q4 only for exact concept/unit/
dimension/start matches against nine-month facts. Recasts, amendment handling,
entity scope, hierarchy and XOM predecessor continuity remain unresolved.
The saved 234-quarter local experiment has not been reproduced here.
Stock Analysis, Futu and TradingView data were not obtained or compared. No
arithmetic consistency result or vendor accuracy rate is claimed.

Next supported step: replace `data.sec.org` with **`data.sec.gov`** in the cloud
environment's Additional allowed domains, retain `www.sec.gov`, save and
republish. Start a task with the updated environment and this branch, confirm
the effective enforced policy and probe the API once. Before a full run, provide
the genuine operator contact via `SEC_USER_AGENT` and use one downloader process.
The recovered downloader still retries arbitrary errors and has a placeholder
default; do not blindly launch its 30-company network path. Use a separately
versioned fetch wrapper that stops on access denial, limits rate and records
retrieval timestamps while preserving recovered source hashes.

All **18 existing tests passed**, including source-hash verification of the ten
recovered files and the frozen 30-company roster. These tests disable network
connections. The new single-filing command was exercised against the actual
Apple filing; JSON integrity, citation hashes and no-overwrite behavior were
also checked. No third-party paid data, secrets or large caches were committed.
