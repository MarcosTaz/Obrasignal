# GuaranteeRelease — Canonical Case Data Model v1

## Document

- `documentId`
- `type`
- `sourceName`
- `sha256`
- `sourceSha256` when native source bytes are available
- `pages[] { pageNumber, text }`
- `supersedes[]`
- `metadata`

## ExtractedFact

- `factId`
- `kind`
- `value`
- `confidence` (`EXACT` in v1)
- `provenance.documentId`
- `provenance.documentSha256`
- `provenance.sourceSha256`
- `provenance.documentType`
- `provenance.pageNumber`
- `provenance.lineNumber`
- `provenance.quote`
- `reviewStatus` (`PENDING | APPROVED | REJECTED` after review)

No extracted fact is assessment truth before explicit review.

## Core fact kinds

Identity / baseline:
- `PROJECT_ID`
- `CONTRACT_ID`
- `INSTRUMENT_ID`
- `INSTRUMENT_TYPE`
- `ORIGINAL_AMOUNT`
- `CURRENT_AMOUNT`
- `EXPIRY_DATE`
- `AUTO_EXTENSION`

Rights / triggers:
- `REDUCTION_RULE`
- `RELEASE_CONDITION`
- `REPAYMENT`
- `MILESTONE`
- `BLOCKER`

Verified outcomes:
- `REDUCTION_CONFIRMATION`
- `CANCELLATION`
- `CANCELLED_AMOUNT`
- `COLLATERAL_RELEASED`

## CaseAssessment

- `caseId`
- `asOf`
- resolved identity
- engine assessment state
- potential/verified amounts
- reproducible `calculations[]`
- unresolved issues
- pending fact ids
- provenance index
- approved fact set

## Calculation

Every positive amount persists:
- kind;
- currency;
- formula;
- named inputs;
- result;
- rounding rule;
- confidence.

No hidden arithmetic is allowed.

## Dossier

- executive summary;
- instrument/project/contract identity;
- state and confidence;
- economic values kept separate;
- calculation recipe;
- evidence with document/page/line/hash/quote;
- unresolved/missing evidence;
- recommended next action;
- explicit truth/authorization boundary.

## State discipline

`PENDING extraction` != approved fact.

`EXPIRED` != cancelled.

`REDUCTION_EVIDENCE_SUPPORTED` != `REDUCED`.

`RELEASE_EVIDENCE_SUPPORTED` != verified release.

`BANK_CANCELLED` != collateral released.

`POTENTIAL VALUE` != cash/capacity actually recovered.
