# GuaranteeRelease — Document-First Case Pipeline Status

Date: 2026-08-29

## Implemented pipeline

`NATIVE TEXT / TEXT-NATIVE PDF OR PAGE-TEXT DOCUMENTS`
→ `SOURCE + NORMALIZED SHA-256`
→ `EXACT CONSERVATIVE EXTRACTION`
→ `DOCUMENT VERSION / DUPLICATE CONTROL`
→ `FACT PROVENANCE`
→ `PENDING REVIEW`
→ `APPROVED FACTS ONLY`
→ `IDENTITY / CONFLICT GATES`
→ `ENGINE_V4`
→ `REPRODUCIBLE CALCULATION`
→ `DOSSIER JSON + MARKDOWN`
→ `RECOMMENDED NEXT ACTION`
→ `TENANT-SAFE CASE API / AUDIT`

## Executed local tests

- engine v4 outcome integrity: `PASS 17/17`
- primary document pipeline: `PASS 33/33`
- adversarial document suite: `PASS 28/28`
- independent 7-case document corpus: `PASS 50/50`
- verified-reduction / outcome separation: `PASS 15/15`
- native PDF/text adapter: `PASS 10/10`
- case CLI workflow: `PASS 8/8`
- tenant-safe persistent case server: `PASS 54/54`
- case-server verified outcome flow: `PASS 14/14`

Total executed assertions in the local case-pipeline stack: `PASS 229/229`.

## Material false-positive controls exercised

- wrong project → `UNKNOWN` and reviewer approval refused;
- wrong contract → approval refused;
- conflicting active amount → `UNKNOWN`;
- conflicting amendments without supersession → `UNKNOWN`;
- malformed/OCR-like amount → missing/UNKNOWN rather than guessed;
- vague discretionary wording → no right;
- expiry alone → `RELEASE_MAY_BE_DUE` with zero release value;
- valid defect → correct zero;
- pending facts → zero supported value;
- duplicate document content → deduplicated;
- invalid supersession graph → rejected;
- candidate reduction ≠ verified reduction;
- cancellation and collateral release remain distinct;
- potential release remains distinct from verified release;
- verified reduction/release/collateral dimensions are not summed;
- impossible current > original → `UNKNOWN`.

## Current truthful status

`PRODUCT_TRUTH = DOCUMENT_CASE_PIPELINE_BUILT_AND_SYNTHETICALLY_TESTED`.

This is **not `CASE_READY`**, **not `PILOT_READY`**, and not market/commercial validation. Text-native PDFs can be extracted with source-byte provenance. Image-only PDFs fail closed and still require an OCR/manual-review lane. Representative external customer documents and measured real-world extraction accuracy remain unproven.
