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

The MVP reads the current calendar-year registry snapshot. Because ZPPA keeps a process in the package associated with its first release and later updates that package as the process evolves, a procurement first published in an earlier year can remain active without appearing in the current-year snapshot. Those carry-over processes are deliberately outside this first slice rather than being silently claimed as covered.

## Runtime

`zambia_zppa_runtime.py` uses the existing `incremental_runtime_plugin` contract. Runtime activation remains opt-in and must be composed behind the canonical source gate; source readiness must not be interpreted as automatic production enablement. `ZM_ZPPA` is deliberately not assigned to the canonical Wave 1 queue.

## Validation

Unit tests cover native works classification, active/future-deadline gating, stable OCID identity, repeat ingestion, compiled-release and wrapped-record shapes, invalid gzip/JSON, empty snapshots and bounded compressed size.

The local execution environment could not resolve external DNS, so live validation was repeated deliberately on a GitHub Actions runner with the live-test skip temporarily removed. Run `32799913676` downloaded and parsed the real 2026 registry snapshot and completed the full Python suite successfully: **683 passed, 2 skipped**. The live test is opt-in again in the final branch (`OBRASIGNAL_LIVE_SOURCE_TESTS=1`) so ordinary CI does not become dependent on an external network/source.
