# GuaranteeRelease — Document Support Matrix v1

Date: 2026-08-29

## Canonical input boundary

The v1 document pipeline consumes **already extracted text arranged by page**. Each document is hashed with SHA-256 and every extracted fact stores document id/hash/type/page/line/exact quote.

This is intentionally narrower than claiming native PDF/OCR support.

## Supported in v1

| Document class | Parser status | Extracted facts currently supported |
|---|---|---|
| SECURITY_INSTRUMENT | SUPPORTED_EXACT_TEXT | project, contract, instrument id/type, original/current amount, currency, expiry, auto-extension |
| CONTRACT | SUPPORTED_RULE_SUBSET | progressive advance-repayment reduction; milestone % reduction; release after practical completion/final certificate/final acceptance/defects-period end/original-instrument return |
| AMENDMENT | SUPPORTED_RULE_SUBSET | same rule subset as CONTRACT; explicit `supersedes` graph controls precedence |
| PAYMENT_CERTIFICATE | SUPPORTED_EXACT_TEXT | certified advance repaid-to-date |
| COMPLETION_CERTIFICATE | SUPPORTED_EXACT_TEXT | practical completion; final acceptance; defects-period end; original instrument returned |
| FINAL_CERTIFICATE | SUPPORTED_EXACT_TEXT | final certificate issued/not issued |
| DEFECT_NOTICE | SUPPORTED_EXACT_TEXT | valid open defect |
| BANK_CONFIRMATION | SUPPORTED_EXACT_TEXT | bank cancellation; cancelled amount |
| COLLATERAL_STATEMENT | SUPPORTED_EXACT_TEXT | collateral amount actually released |
| RELEASE_LETTER | PARTIAL | common structured lines can be extracted; no free-form legal-language interpretation |
| OTHER | SAFE_INGEST_ONLY | hashed/stored in extraction packet but creates no facts unless a supported exact pattern is present |

## Supported instrument labels

- ADVANCE_PAYMENT_GUARANTEE
- ADVANCE_PAYMENT_BOND
- PERFORMANCE_GUARANTEE
- PERFORMANCE_BOND
- RETENTION_GUARANTEE
- RETENTION_BOND
- WARRANTY_GUARANTEE
- WARRANTY_BOND
- DEFECT_GUARANTEE / DEFECTS_GUARANTEE
- BID_BOND
- STANDBY_LETTER_OF_CREDIT
- SECURITY_DEPOSIT
- CASH_RETENTION

## Explicitly unsupported / not claimed

- arbitrary native PDF semantic interpretation beyond text extraction;
- OCR of scans or photographs;
- handwriting;
- image-only signatures/stamps;
- complex tables without prior text normalization;
- arbitrary legal-language interpretation;
- inferred clause meaning from vague wording;
- automatic governing-law conclusions;
- beneficiary/bank authority inferred from correspondence tone;
- email-thread parsing;
- embedded spreadsheet formulas;
- multilingual extraction beyond the exact English patterns in v1;
- production document-storage connectors.

Text-native PDFs are accepted through the native adapter and retain source-byte SHA-256. Image-only PDFs fail closed as `OCR/review required`.

Unsupported input must remain `UNKNOWN / NEEDS_REVIEW`; it must not be converted into a release right.

## Duplicate and version handling

- duplicate `documentId`: rejected;
- identical active document content under different ids: one extraction is used and the duplicate group is recorded;
- explicit supersession: old document excluded from active extraction;
- missing supersession target: rejected;
- self-supersession: rejected;
- supersession cycle: rejected;
- conflicting active facts without valid supersession: fail closed to `UNKNOWN`.

## Promotion gate

Do not call document ingestion complete until representative external PDFs/scans can be converted to this page-text model with measured extraction accuracy and retained source-byte provenance.
