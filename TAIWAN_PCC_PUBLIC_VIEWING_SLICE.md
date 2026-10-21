# Taiwan PCC Limited High-Value Construction Slice

This branch implements a bounded Taiwan PCC construction/public-works source slice instead of waiting for perfect national coverage.

## Source 7260 — Public viewing

- Signal: `PROCUREMENT_PLAN`.
- Value: pre-tender public-viewing intelligence.
- Coverage: rolling/current PCC public-viewing snapshot; not full Taiwan procurement.
- Identity: native tender/case number.
- Construction selection: publisher procurement nature has precedence; conservative native-title fallback is used only when category is absent.

## Source 7264 — Large procurement suppliers in performance

- Signal: `CONTRACT`.
- Value: supplier/value/performance intelligence on large procurements under execution.
- Identity: native tender/case number + native vendor code.
- Lineage: tender/case number remains the common procurement lineage key.
- Construction selection: same runtime filter as 7260.

## Shared runtime semantics

Both sources are fetched from fixed official PCC XML endpoints. The runtime re-fetches complete snapshots, applies the construction/public-works selector before staging, relies on canonical idempotent persistence, preserves any existing watermark, and never interprets disappearance as cancellation because no publisher delta/cancellation contract has been proven.

## Live proof — 2026-08-25

The final live validation fetched and normalized **124** pre-tender plan records and **226** supplier-level contract records. The product construction filter accepted **39** plans and **16** contracts: **55** construction/public-works Signals in total. Of those, **16** were accepted from publisher-native procurement nature and **39** via the conservative title fallback.

All **55** filtered Signals persisted losslessly with zero identity collisions, and repeated ingestion remained exactly **55** rows (`lossless=1 idempotent=1`). An earlier raw-normalization proof also persisted all 350 unfiltered records losslessly; those 350 are not the runtime product output.

Rights: official PCC/Taiwan open-data catalogue, free, Open Government Data License v1.0.

Status: **IMPLEMENTED + TESTED + LIVE TESTED / NOT CANONICALLY INTEGRATED / NOT PRODUCTION**.
