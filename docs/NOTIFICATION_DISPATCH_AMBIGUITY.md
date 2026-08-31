# Notification dispatch ambiguity

Status: owner candidate only; not canonical; do not merge without integration authorization.

## Problem

A provider POST is an external irreversible side effect. If the process dies after the request may have crossed that boundary but before the local `push_deliveries` ticket/attempt update commits, the database alone cannot prove whether Expo accepted the request. Automatically replaying the same `(event_id, push_device_id)` can therefore create an ObraSignal-caused duplicate.

## Candidate invariant

Before the provider call, persist and commit a dispatch-intent marker in the existing `push_deliveries` row. Normal responses continue through the existing Notification owner ledger path. If the marker survives a process restart, classify the pair as `ambiguous_provider_state`, terminalize automatic replay, and keep Radar as the authoritative customer surface.

This is intentionally an at-most-once local replay choice at the crash boundary. A crash before the provider call and a crash after provider acceptance are observationally identical without provider idempotency, so the system must not claim to know which occurred.

## Preserved semantics

- `MAX_PUSH_ATTEMPTS=8` remains the upper bound.
- Normal accepted tickets retain `submitted_at` + provider ticket truth.
- Explicit handled transport failures retain the existing bounded retry path in this candidate.
- `provider_accepted` remains provider acceptance, not device/user delivery.
- Event/device tenant scope, stable device identity, token rotation and Privacy lifecycle remain unchanged.

## Remaining limitation

This candidate closes the proven accepted-response/local-ledger crash reproducer. It does not claim that every network exception is unambiguous: a transport timeout can itself occur after a remote side effect. That broader policy remains explicit follow-up rather than being silently declared solved.
