# SEC revenue composition research

The target universe is US companies in the S&P 500, 400 and 600. The first
evaluation is the existing 30-company, cross-industry baseline, using the most
recent eight fiscal quarters *at that baseline's recorded collection date*.
The collection date and company list have not yet been recovered from the ZIP.
Do not treat those results as the latest eight quarters as of today, or infer
index membership from company size. After import, preserve the baseline unchanged
and record an explicit as-of date for a separate refresh.

## Evidence and output contract

Use original SEC XBRL/iXBRL facts and filing evidence. For every observation,
retain company identity (CIK and historical identity), accession, filing URL,
filing date, raw concept QName, original labels/definition references, context
ID, original period start/end, unit, decimals/scale, original value, and the
complete axis/member mapping. Preserve multiple facts and restatement provenance;
never silently replace conflicting observations. Keep the source filing hash
and retrieval timestamp where available. Store any normalized labels separately.

Keep each disclosure family separate (product/service, segment, geography,
customer or other). A business segment is not automatically a product/source.
Do not sum different axes or flatten multi-axis cells into one list. Preserve
company definitions and distinguish external sales, intersegment sales, subtotals
and eliminations. If the evidence does not support a single By source partition,
report the ambiguity and retain the candidate partitions for review.

Quarter values must retain their derivation: directly disclosed quarter versus
YTD subtraction versus annual-minus-nine-month calculation. Derivations require
compatible entities, concepts, complete dimensions, units, accounting basis and
period boundaries; retain the input facts and method. Missing data is not zero.

Arithmetic checks compare one coherent candidate partition to a compatible
consolidated revenue fact, recording both values, difference, tolerance, units
and candidate identity. Passing is arithmetic consistency only. It does not
prove semantic correctness, complete disclosure, or agreement with a vendor.

## Reported baseline and open issues

The delegation reports 234 of 240 company-quarters processed, and 138 quarters
with at least one candidate partition arithmetically matching total revenue.
These numbers are **prior reported results, not locally verified**. Do not call
them accuracy or disclosure coverage. Recover the exact tolerance, counting
method and denominators from the source code before reproducing them.

- XOM: resolve historical company identity/CIK linkage before filling missing quarters.
- Intel: inspect subtotals and elimination items before interpreting candidate sums.
- PG and COST: inspect multi-axis observations; do not add across axes.
- Verify the exact 30-company list, sectors, eight fiscal periods and six missing
  company-quarters from imported evidence rather than guessing them.

Stock Analysis and Futu user-authorized data are future reference sources.
Neither has been imported or compared. TradingView annual data is secondary and
cannot validate quarterly detail. Restricted vendor bytes and authenticated
browser state stay out of git even though the repository is private.

## Resume sequence

1. Restore supported Library transfer connectivity and obtain the three exact
   registered archives using the current Library skill. Preserve Library identity
   and current versions; do not substitute files from another executor's paths.
2. Audit the archives with `scripts/stage_archive.py`, stage each separately,
   review every file, and promote only code, documentation and public SEC-derived
   research data. A clean automated audit does not establish data ownership.
   Never run imported code before inspecting it and its dependencies.
3. Treat the eight-quarter archive as the baseline; retain the older experiment
   and filing review separately. Compare overlapping files by SHA-256 before
   consolidating them; do not overwrite one version with another.
4. Record archive hashes, per-file hashes, exact original paths and promotion
   decisions. Recover and run the original meaningful tests, pin dependencies,
   and document the original entrypoints and offline/online commands.
5. Recompute baseline counts offline where evidence permits. Reconcile the
   234/240 and 138 counts and document any differences with original output.
6. Request the cloud environment's supported network configuration workflow to
   allow `www.sec.gov` and `data.sec.gov` before an online refresh. Use SEC's
   current access policy and a real configured identifying User-Agent. No SEC
   requests or access-policy validation have been performed in this task.
7. Review the recovered cohort with the user before extending across the full
   S&P 1500 universe. Record dated membership and identity mapping sources.
