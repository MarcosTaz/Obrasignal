# Taiwan PCC Limited High-Value Slice

This branch implements a bounded Taiwan PCC source slice instead of waiting for perfect national coverage.

## Source 7260 — Public viewing

- Signal: `PROCUREMENT_PLAN`.
- Value: pre-tender public-viewing intelligence.
- Coverage: rolling/current PCC public-viewing snapshot; not full Taiwan procurement.
- Identity: native tender/case number.
- Construction hook: publisher procurement nature when supplied, with live construction-relevance assertion.

## Source 7264 — Large procurement suppliers in performance

- Signal: `CONTRACT`.
- Value: supplier/value/performance intelligence on large procurements under execution.
- Identity: native tender/case number + native vendor code.
- Lineage: tender/case number remains the common procurement lineage key.

## Shared runtime semantics

Both sources are fetched from fixed official PCC XML endpoints. The runtime re-fetches complete snapshots, relies on canonical idempotent persistence, preserves any existing watermark, and never interprets disappearance as cancellation because no publisher delta/cancellation contract has been proven.

## Live proof — 2026-08-25

The final live validation fetched **124** pre-tender plan records and **226** supplier-level contract records. After correcting contract identity to include publisher vendor code, all **350** normalized records persisted losslessly and a repeated ingestion remained exactly **350** rows.

Rights: official PCC/Taiwan open-data catalogue, free, Open Government Data License v1.0.

Status: **IMPLEMENTED + LIVE TESTED / NOT INTEGRATED / NOT PRODUCTION**.
