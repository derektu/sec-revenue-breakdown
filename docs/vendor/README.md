# Local vendor references and cloud handoff

The local task owns `docs/vendor/`, ignored `data/vendor/local/`, and the isolated
`research/recovered-sec/` experiment import. The cloud task owns the SEC baseline
on `research/cloud-baseline`. The shared GitHub repository is
`https://github.com/derektu/sec-revenue-breakdown`.

The local branch is `local/vendor-reference`, based on initial main commit
`2be07ea`. The cloud branch was observed at
`923303d69379fab6856089c9ba185b5aa49533e6` on 2026-11-04. It is not checked out or
modified by this task. The source-only handoff uses the separate
`local/vendor-reference` branch; cloud integration requires an explicit review
and selection of files from that branch.

## Files and responsibilities

| Location | Contents | Git handling |
| --- | --- | --- |
| `docs/vendor/` | Coverage, acquisition constraints, provenance and handoff | Reviewable source documents |
| `research/recovered-sec/` | Selected SEC experiment source and synthetic tests | Reviewable source; separate from cloud baseline |
| `data/vendor/local/` | Research ZIPs, extracted originals, verification logs and venv | Entire directory ignored |
| `research/recovered-sec/data/` and `outputs/` | Disposable offline pilot snapshots and outputs | Ignored |

Original vendor downloads, screenshots containing vendor data, browser sessions,
cookies, passwords and tokens are not part of the Git handoff. A private repository
does not establish redistribution rights. No vendor data files have been downloaded
in this task. The ignored directory currently contains recovered SEC research
archives, not a vendor reference dataset.

## Apple acquisition status, 2026-11-04

Stock Analysis page:
<https://stockanalysis.com/stocks/aapl/metrics/revenue-by-segment/>.
The initial isolated-browser page displayed a Log In link. The default chart
explicitly described TTM. Selecting Quarterly displayed eight recent endpoints:
2026-09-30, 2026-06-30, 2026-03-31, 2025-12-31, 2025-09-30, 2025-06-30,
2025-03-31 and 2024-12-31. These are the vendor's display dates; verify actual
fiscal period boundaries against SEC filings rather than assuming calendar dates.

The five visible categories are iPhone, Services, Mac, Wearables/Home/Accessories,
and iPad. This is a product/service decomposition; the site's separate geography
page is a different decomposition. The display uses USD and abbreviated billions
(`B`); the exact downloaded precision and schema are unverified. The page identifies
TipRanks as the provider and shows a 2026-11-02 update date. No numeric vendor table
is saved in this handoff.

The Quarterly interaction also produced a logged-in notification, despite the
initial Log In link. This is not proof of subscription entitlement. No credentials
were entered, no account settings changed, and no subsequent download was attempted.
The download control's file formats and contents remain untested.

Stock Analysis terms, last updated 2026-10-29:
<https://stockanalysis.com/terms-of-use/>. The Automated access section limits
account/browser automation, with an exception for AI agents following robots.txt;
the Your account section separately disallows machine/system account access.
<https://stockanalysis.com/robots.txt> was checked. The AI crawler exception does
not establish permission to operate a paid personal account or build a competing
database. Written clarification is required before an authenticated batch workflow.
This is an acquisition constraint, not a claim about the user's intent.

Futu page already exists in the user's Edge session:
<https://www.futunn.com/hk/stock/AAPL-US/financials-revenue>.
The public web retrieval returned a 403/frequency-limit page. No retry, hidden API,
login alteration or bypass was attempted. Eight-quarter coverage, category mapping,
units and export format have not been independently verified in this task.

Futu's official agreement was rendered in Edge:
<https://www.futunn.com/about/services?lang=zh-hk>, updated 2024-08-13.
Section III(3) limits third-party tool access and copying/interception of system
data. Section V and the market-data appendix restrict redistribution. Applicability
and permission for revenue-table automation need clarification before collection.
The signed-in revenue page was left untouched.

## Acquisition and comparison workflow

1. Establish permission for the intended personal research, automated collection,
   offline processing and any transfer. Paid access alone does not establish these
   rights. Vendor permission or permitted manual exports are separate from GitHub
   access. Neither account needs to be reconfigured for the current offline work.
2. For an authorized manual export, the user selects Apple, Quarterly, By source /
   product-service, absolute values, and the latest eight disclosed periods. Save
   the unmodified file below `data/vendor/local/SOURCE/AAPL/DATE/`. Record the real
   format and SHA-256 after saving; CSV/XLSX support is not assumed.
3. Record source URL, UTC acquisition time, original filename, file format, SHA-256,
   display period, fiscal start/end, quarter/YTD/TTM basis, currency, unit multiplier,
   raw category, parent/subtotal structure, provider update date, source provider,
   export settings and the permission basis. Preserve blanks and unavailable values.
4. Keep the source file unchanged. Generate normalized rows only after validating
   schema and period basis. A suitable comparison key is issuer, source, fiscal
   start/end, period basis, breakdown axis and raw category. Retain original values,
   scaling, rounding and source reference. Do not map categories by name alone.
5. Compare Apple against the corresponding SEC product/service disclosure. Keep
   operating segments and geography separate; preserve products subtotals without
   adding them to child product values. Report missing quarters and differences,
   including vendor rounding and possible restatements.
6. Expand using the frozen 30-company roster at
   `research/recovered-sec/eight_quarter_eval/roster.json` only after the Apple file
   and rights check pass. `coverage.csv` tracks actual observations; planned issuers
   do not count as downloaded or covered. The roster spans technology, media,
   retail, consumer goods, healthcare, banks, insurance, energy, industrials,
   utilities, materials and real estate. It is a sampling plan, not verified vendor
   availability. Respect site limits and stop on authentication or access errors.

## Cloud and local coordination

Before combining branches, the cloud task checks these isolated paths against its
current tree and explicitly chooses which recovered modules to incorporate. It
must not merge duplicate pipelines blindly. `recovery-manifest.json` records archive
checksums and exact imported source hashes. The original experiment READMEs describe
their historical execution and include files intentionally excluded from this
source-only handoff; use `research/recovered-sec/HANDOFF.md` as the current entry point.

The local task does not write the cloud branch, and no active downloaders share a
cache. A future authorized publication should include only reviewed source and docs
from this branch. Git-ignored contents stay local until separately reviewed for
licensing and necessary disclosure. Cloud/local task conversations are not assumed
to share context automatically; this document and the recovery manifest provide an
explicit handoff.
