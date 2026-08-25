# CanadaBuys connector evidence — 2026-08-25

## Scope
Q040_CANADA_BUYS. Federal-first official CanadaBuys tender-notice open data.

## Live transport validation
Official files were fetched successfully from a GitHub Actions runner after the interactive browser/container could not consume the octet-stream CSV directly. That limitation was a tool/transport issue, not source unavailability.

- New Tender Notices: HTTP 200, `application/octet-stream`, 212,519 bytes, ETag present, Last-Modified `Mon, 24 Aug 2026 22:15:16 GMT`.
- Open Tender Notices: HTTP 200, `application/octet-stream`, 6,910,833 bytes, ETag present, Last-Modified `Mon, 24 Aug 2026 10:20:16 GMT`.
- Data dictionary XML: HTTP 200, UTF-8 XML, 60,478 bytes.

Both tender CSV files had the same 67 publisher columns.

## Publisher-native construction admission
`procurementCategory-categorieApprovisionnement = *CNST` means construction. The connector therefore admits construction strictly by CNST, not by title/description keywords.

## Identity and amendments
CanadaBuys documents `solicitationNumber-numeroSollicitation` as the identifier used to relate tender notices and award/history data. It is the durable ObraSignal external identity.

`referenceNumber-numeroReference` is preserved as source evidence but is not durable identity.

`amendmentNumber-numeroModification` and `amendmentDate-dateModification` describe versions/amendments of the same solicitation; amendments must not create a new canonical opportunity identity.

## Lifecycle
Publisher tender status semantics are Open / Expired / Cancelled.

Open Tender Notices is the authoritative daily snapshot of notices open for bidding and contains current amendment state. New Tender Notices is the intraday freshness feed. Missing rows in a later Open snapshot are not automatically labelled Cancelled unless the publisher provides that evidence; elapsed deadlines can safely close a known tender as non-actionable.

## Time semantics
The data dictionary explicitly states that `tenderClosingDate-appelOffresDateCloture` is expressed at fixed UTC-05:00, including dates when Eastern local civil time observes daylight saving time. The connector therefore uses a fixed -05:00 offset, not `America/Toronto` DST conversion.

## Value/currency
Tender-notice CSV has no tender value/currency field. Connector emits empty value/currency rather than inventing an estimate.

## Incremental strategy
HTTP conditional validators (ETag/Last-Modified) prevent re-downloading unchanged New/Open files. New provides low-latency discovery; Open provides active-state reconciliation. Cursor advancement remains fail-closed when schema/identity/closing-time invariants fail.

## Legal/reuse
Dataset is official Government of Canada open data. Production registry must remain separately gated from mere connector existence; runtime activation occurs only after exact-head CI and live production-path validation.