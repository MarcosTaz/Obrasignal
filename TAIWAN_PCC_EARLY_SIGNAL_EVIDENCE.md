# Taiwan PCC Bounded Construction Signal Slice — Evidence and Gate Status

**Date:** 2026-08-25  
**Branch:** `feature/tw-pcc-early-signal-v0`  
**Status:** IMPLEMENTED + LIVE TESTED / NOT CANONICALLY INTEGRATED / NOT PRODUCTION

## Executive result

The APAC cell produced a real implementation win for Taiwan using two official Public Construction Commission (PCC) open-data sources. This is deliberately a bounded high-value construction/public-works slice, not a claim of full Taiwan procurement coverage.

The implemented path is:

`official PCC XML -> bounded HTTP fetch -> XML parse -> native identity -> conservative construction filter -> canonical ObraSignal Signal -> signal_store persistence -> idempotent reingestion`

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

## Final live validation

GitHub Actions executed the connector and construction filter against the official PCC endpoints on 2026-08-25.

Final verified construction run:

- raw public-viewing plans normalized: **124**;
- raw supplier-level contracts normalized: **226**;
- construction/public-works plans accepted: **39**;
- construction/public-works contracts accepted: **16**;
- accepted via publisher-native procurement nature: **16**;
- accepted via conservative title fallback: **39**;
- construction Signals persisted: **55**;
- identity collisions: **0**;
- second ingestion retained exactly **55** canonical rows;
- result: `lossless=1 idempotent=1`.

An earlier live run also proved all 350 raw normalized records could be persisted losslessly. The product runtime now deliberately stages only the records that pass the construction/public-works selector.

## Construction filtering

Filtering is implemented in code, not inferred later in presentation.

1. When PCC provides publisher-native procurement nature, that value has precedence.
2. Native categories containing works/construction terms are accepted with basis `publisher_procurement_nature`.
3. A populated native category that is not construction does **not** fall through to keyword matching.
4. Only when publisher category is absent is a conservative native-title fallback allowed.
5. The fallback uses infrastructure/works terms such as roads, bridges, tunnels, drainage, sewerage, rehabilitation and new-build works.
6. Adjacent-service exclusions explicitly reject consulting, insurance, software/information-system and research false positives.
7. The filter basis is retained on each accepted Signal as `construction_filter_basis`.

Tests cover publisher-taxonomy precedence and false-positive fallback cases.

## Identity and lineage

- Every accepted row requires the publisher-native tender/case number.
- `source_reference` and `lineage_key` preserve that case number without transliteration.
- `PROCUREMENT_PLAN` external identity is `procurement_plan:<case_number>`.
- Dataset 7264 is supplier-level. `CONTRACT` external identity is `contract:<case_number>:<vendor_code>`.
- A contract row without native vendor code is rejected rather than collapsed or assigned a synthetic identity.
- Multiple supplier contracts therefore remain distinct while sharing the procurement lineage key.

A live smoke initially failed because its assertion still expected the older case-only contract identity. The connector's vendor-scoped identity was correct; the stale smoke assertion was corrected and the live run passed.

## Runtime semantics

`taiwan_pcc_runtime.py` exposes live-validated sources `(7260, 7264)` through the repository's generic `install_incremental_source` contract and applies the construction selector before staging.

The sources are complete/current snapshots rather than a proven publisher delta stream:

- re-fetch the full bounded snapshot;
- preserve stable canonical identity;
- rely on idempotent upsert;
- do not infer cancellation from disappearance;
- do not advance an invented publisher cursor;
- fail closed if a non-empty live snapshot unexpectedly yields zero defensible construction signals.

The runtime helper is implemented and tested, but this parallel branch does **not** modify canonical `preload.py`, `source_registry.py`, `CURRENT_ITEM_ID`, or the Master Execution Queue. Activation therefore remains an explicit integration decision and is not falsely presented as production.

## Failure semantics and security

- HTTP failures propagate and cannot become successful zero-result observations.
- empty payload fails closed;
- malformed XML fails closed;
- XML without recognizable procurement rows fails closed;
- rows lacking stable publisher identity are rejected;
- supplier-level contracts without native vendor identity are rejected;
- non-empty snapshots yielding zero defensible construction output fail closed at runtime;
- source URLs are fixed official contracts, not user-controlled input.

No CAPTCHA, login, private API, paid-access or anti-bot bypass is used.

## Tests

Unit/integration coverage includes:

- native Chinese identity preservation;
- ROC-year scheduled-target normalization;
- cross-stage lineage;
- supplier-level contract identity;
- rejection of missing case/vendor identity;
- construction taxonomy precedence;
- conservative title fallback and false-positive exclusions;
- canonical signal-store idempotency/update semantics;
- bounded timeout;
- HTTP error propagation;
- empty/malformed/unrecognized XML;
- two-source runtime composition;
- runtime construction filtering/fail-closed behavior;
- generic incremental-runtime installation contract;
- live official source -> construction filter -> canonical persistence smoke.

The repository `ObraSignal Quality` workflow is required to pass on the final PR head in addition to the dedicated Taiwan live smoke.

## Known limitations

- This is not full Taiwan tender coverage.
- 6574 and 7261 remain unimplemented until their raw machine contracts are verified.
- Canonical source-registry/preload activation is intentionally not included in this parallel branch.
- No foreign-contractor eligibility engine is included.
- No LLM translation is used by the connector.

## Classification

**Taiwan — LIMITED HIGH-VALUE CONSTRUCTION SLICE / IMPLEMENTED + TESTED + LIVE TESTED.**

**NOT CANONICALLY INTEGRATED. NOT PRODUCTION.**

## Rollback

Remove the Taiwan connector/runtime/tests/live workflow/evidence files. No migration, canonical queue change or production deployment is part of this PR.
