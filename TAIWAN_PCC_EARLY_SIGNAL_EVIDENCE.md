# Taiwan PCC Bounded Signal Slice — Evidence and Gate Status

**Date:** 2026-08-25  
**Branch:** `feature/tw-pcc-early-signal-v0`  
**Status:** IMPLEMENTED + LIVE TESTED / NOT INTEGRATED / NOT PRODUCTION

## Executive result

The APAC cell produced a real implementation win for Taiwan using two official Public Construction Commission (PCC) open-data sources. This is deliberately a bounded high-value slice, not a claim of full Taiwan procurement coverage.

The implemented source path is:

`official PCC XML -> HTTP fetch -> XML parse -> native identity -> canonical ObraSignal Signal -> signal_store persistence -> idempotent reingestion`

## Implemented official sources

| Dataset | ID | Signal | Freshness | Rights | Machine contract |
| --- | ---: | --- | --- | --- | --- |
| Public viewing announcement | 7260 | `PROCUREMENT_PLAN` | daily catalogue / rolling snapshot | Open Government Data License v1.0 / free | **LIVE VERIFIED** |
| Large procurement suppliers during performance | 7264 | `CONTRACT` | daily catalogue / snapshot | Open Government Data License v1.0 / free | **LIVE VERIFIED** |

Still outside the implemented slice:

| Dataset | ID | Signal | State |
| --- | ---: | --- | --- |
| Procurement notice | 6574 | `PROCUREMENT_PLAN` | raw URL not yet verified |
| Public Recruitment Announcement | 7261 | `MARKET_DIALOGUE` | raw URL not yet verified |

The first slice does not depend on 6574/7261.

## Live validation

GitHub Actions executed the connector against the official PCC endpoints on 2026-08-25.

Final verified run after identity corrections:

- public-viewing plans fetched/normalized: **124**;
- contract-performance supplier records fetched/normalized: **226**;
- canonical Signals persisted: **350**;
- normalized identity collisions: **0**;
- second ingestion retained exactly **350** canonical rows;
- result: `lossless=1 idempotent=1`.

The live smoke also requires construction-relevant publisher classification/title evidence on dataset 7260 and supplier/value evidence on dataset 7264.

## Identity and lineage

- Every accepted row requires the publisher-native tender/case number.
- `source_reference` and `lineage_key` preserve that case number without transliteration.
- `PROCUREMENT_PLAN` external identity is `procurement_plan:<case_number>`.
- Dataset 7264 is supplier-level. `CONTRACT` external identity is `contract:<case_number>:<vendor_code>`.
- A contract row without native vendor code is rejected rather than collapsed or assigned a synthetic identity.
- Multiple supplier contracts therefore remain distinct while sharing the procurement lineage key.

This contract was corrected after the first 7264 live run exposed supplier-row collisions under case-only identity.

## Construction relevance

The connector preserves publisher-native procurement nature as `TW_PCC_PROCUREMENT_NATURE` when present. The live smoke additionally requires at least one publisher classification or construction-relevant native title in the current 7260 snapshot. Core identity does not depend on translation or LLM output.

## Runtime semantics

`taiwan_pcc_runtime.py` exposes the live-validated tuple `(7260, 7264)` through the repository's generic `install_incremental_source` contract.

The two sources are complete/current snapshots rather than a proven publisher delta stream:

- re-fetch the full bounded snapshot;
- preserve stable canonical identity;
- rely on idempotent upsert;
- do not infer cancellation from disappearance;
- do not advance an invented publisher cursor.

The runtime helper is implemented and unit tested, but this branch does **not** modify canonical `preload.py`, `source_registry.py`, `CURRENT_ITEM_ID`, or the Master Execution Queue. Activation therefore remains an explicit later integration decision.

## Failure semantics

- HTTP failures propagate and cannot become successful zero-result observations.
- empty payload fails closed;
- malformed XML fails closed;
- XML without recognizable procurement rows fails closed;
- rows lacking stable publisher identity are rejected;
- source URLs are fixed source contracts, not user-controlled input.

No CAPTCHA, login, private API, paid-access or anti-bot bypass is used.

## Tests

Unit/integration coverage includes:

- Chinese/native identity preservation;
- ROC-year scheduled-target normalization;
- cross-stage lineage;
- supplier-level contract identity;
- rejection of missing case/vendor identity;
- canonical signal-store idempotency and update semantics;
- bounded timeout;
- HTTP error propagation;
- empty/malformed/unrecognized XML;
- two-source runtime composition;
- generic incremental-runtime installation contract;
- live source -> canonical persistence smoke.

The repository `ObraSignal Quality` workflow is required to pass on the final PR head in addition to the live smoke.

## Known limitations

- This is not full Taiwan tender coverage.
- 6574 and 7261 remain unimplemented until their raw machine contracts are verified.
- No automatic source-registry/preload activation is included in this parallel branch.
- No foreign-contractor eligibility engine is included.
- No LLM translation is used by the connector.

## Classification

**Taiwan — LIMITED HIGH-VALUE SLICE / IMPLEMENTED + LIVE TESTED.**

**NOT INTEGRATED. NOT PRODUCTION.**

## Rollback

Remove the Taiwan connector/runtime/tests/live workflow/evidence files. No migration, canonical queue change or production deployment is part of this PR.
