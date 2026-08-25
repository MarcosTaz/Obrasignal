# Taiwan PCC Early-Signal Connector — Evidence and Gate Status

**Date:** 2026-08-25  
**Branch:** `feature/tw-pcc-early-signal-v0`  
**Status:** PREPARED / NOT PRODUCTION ENABLED

## Why this exists

The APAC audit found Taiwan to have the best bounded early-signal engineering case in the queue. The Public Construction Commission (PCC) publishes multiple official procurement datasets daily under Taiwan's Open Government Data License v1.0, including activity before the tender notice exists.

This implementation deliberately does **not** claim Taiwan market support or full national tender coverage.

## Official datasets in bounded v0 scope

| Dataset | ID | Signal | Catalogue freshness | Rights | Raw endpoint status |
| --- | ---: | --- | --- | --- | --- |
| Procurement notice | 6574 | `PROCUREMENT_PLAN` | daily | Open Government Data License v1.0 / free | **UNVERIFIED IN THIS ENVIRONMENT** |
| Public viewing announcement | 7260 | `PROCUREMENT_PLAN` | daily | Open Government Data License v1.0 / free | endpoint discovered; payload fetch unavailable in this environment |
| Public Recruitment Announcement | 7261 | `MARKET_DIALOGUE` | daily | Open Government Data License v1.0 / free | **UNVERIFIED IN THIS ENVIRONMENT** |
| Large procurement suppliers during performance | 7264 | `CONTRACT` | daily | Open Government Data License v1.0 / free | endpoint discovered; payload fetch unavailable in this environment |

Official catalogue pages establish native fields such as tender/case number, title, buyer/agency, tendering method, scheduled tender month, public-viewing/public-recruitment dates and contract-performance supplier/value dates.

## Identity and lineage decision

- Preserve the publisher tender/case number without transliteration.
- `source_reference` and `lineage_key` use the native case number.
- `external_id` is stage-scoped (`<signal_type>:<case_number>`) so plan/dialogue/contract observations do not overwrite each other.
- Same-stage repeated snapshots upsert idempotently through the canonical `signal_store` key `(source, signal_type, external_id)`.
- Updates are updates, not new procurement identities.

## Construction filtering

PCC publishes procurement-nature / target-classification data, including an official procurement target classification dataset with Chinese and English names. The prepared normalizer preserves publisher-native procurement nature as `TW_PCC_PROCUREMENT_NATURE`. No keyword-only construction rule is hard-coded here because the exact production payload and code contract still require live validation.

## Access and rights

**Catalogue-level rights: GREEN.** The bounded source pages state free access and Open Government Data License v1.0.

**Production machine contract: GATED.** A catalogue download link is not sufficient production proof. The `web.pcc.gov.tw` download endpoints for datasets 7260/7264 could be resolved, but payload retrieval failed from the available environment. Dataset 6574/7261 concrete raw endpoints were not captured, so the connector refuses to run the complete source set.

No CAPTCHA, login, private API, rate-limit bypass or anti-bot circumvention is used.

## Implementation

`taiwan_pcc.py` provides:

- source-specific bounded dataset contracts;
- namespace-tolerant XML parsing;
- Chinese/English field alias normalization while preserving native values;
- ROC-year scheduled-month normalization;
- stable signal-stage identity;
- lineage key preservation;
- fail-closed malformed/empty/unrecognizable XML handling;
- fail-closed production gate when any raw URL remains unverified.

`test_taiwan_pcc.py` covers:

- native identity preservation;
- plan → market-dialogue lineage compatibility;
- no cross-stage identity collision;
- canonical signal-store idempotency/update semantics;
- malformed/unrecognized XML failure;
- missing-live-contract fail-closed behavior;
- explicit production gate reasons.

## Not implemented

- runtime registration/enabling;
- source-registry promotion;
- live ingestion schedule;
- full national live-tender coverage;
- foreign-contractor eligibility engine;
- LLM translation in the core connector.

## Production promotion gate

Promotion requires all of the following:

1. capture exact raw download URL for datasets 6574 and 7261;
2. successfully fetch representative live payloads for all bounded datasets;
3. reconcile exact XML element names against the prepared aliases and commit regression fixtures derived from the real schema (without storing sensitive/non-public data);
4. prove same case number continuity across at least two lifecycle stages where naturally present;
5. verify snapshot disappearance semantics do not imply cancellation;
6. confirm construction classification values/codes from real payloads;
7. add source-registry metadata as `ready` only after machine access is verified;
8. add runtime wiring only after the above gates and live smoke pass.

Until then: **PREPARED != IMPLEMENTED MARKET SUPPORT != PRODUCTION.**

## Rollback

Code-only: remove `taiwan_pcc.py`, `test_taiwan_pcc.py` and this evidence document. No schema, runtime, credentials, canonical queue or market-state changes are included.
