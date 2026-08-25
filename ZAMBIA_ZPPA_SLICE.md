# Zambia ZPPA OCDS public-works slice

## Scope

This implementation adds a bounded Zambia public-works tender slice from the Zambia Public Procurement Authority (ZPPA) OCDS dataset. It intentionally emits only active tenders whose native OCDS `tender.mainProcurementCategory` is `works` and whose tender deadline is still in the future.

## Source contract

- Publisher: Zambia Public Procurement Authority (ZPPA)
- Official source index: https://www.zppa.org.zm/record-packages
- Publication policy: https://www.zppa.org.zm/ocds-publication-policy
- Transport mirror: Open Contracting Partnership Data Registry, yearly `.jsonl.gz` compiled-release snapshot
- License: CC BY 4.0
- Stable identity: OCDS OCID (`ocds-23g63a...`)

ZPPA explicitly states that monthly record packages can be modified later as an existing contracting process advances. The connector therefore reprocesses the current-year snapshot instead of treating it as append-only; downstream stable OCID identity/deduplication provides idempotency.

## Safety and boundedness

The shared JSONL+gzip transport enforces compressed-size, uncompressed-size and record-count limits, rejects malformed gzip/JSON and treats an empty/invalid source as a failure rather than as zero opportunities.

## Coverage boundary

This is a **LIMITED HIGH-VALUE SLICE**, not a claim of complete Zambia procurement coverage. The OCP registry documents discrepancies between the OCDS dataset and the e-GP front-end. Awards/contracts/plans exist upstream but are not emitted by this implementation.

## Runtime

`zambia_zppa_runtime.py` uses the existing `incremental_runtime_plugin` contract. Runtime activation remains opt-in and must be composed behind the canonical source gate; source readiness must not be interpreted as automatic production enablement.

## Validation

Unit tests cover native works classification, active/future-deadline gating, stable OCID identity, repeat ingestion, compiled-release and wrapped-record shapes, invalid gzip/JSON, empty snapshots and bounded compressed size. A live transport attempt from the local execution environment was blocked by external DNS resolution; public source and current registry availability were independently verified through the web path.
