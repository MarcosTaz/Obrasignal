# T1 — PILOT CAPABLE gate evidence — 2026-08-28

## Decision

**PROMOTED: T1 — PILOT CAPABLE (assisted local prototype).**

This promotion does not claim production readiness, real-customer validation, willingness to pay, legal entitlement, or money recovered. Assisted human review remains mandatory.

## End-to-end journey proven locally

`tenant/company -> customer -> program -> part -> baseline -> engineering change -> revision delta -> affected items -> evidenced cost -> causality -> mitigation -> prior payment -> entitlement basis -> notice/deadline -> missing evidence -> recoverability -> commercial package -> atomic save -> return -> history`

## Current test evidence

- 26 synthetic cases.
- Complete mandatory scenario-tag matrix from NO_COST_CHANGE through SUPERSEDED_CONTRACT and ZERO_RECOVERY.
- 38 unit/integration tests passing with ResourceWarning promoted to error.
- Independent expected oracle values are stored in fixtures; the application does not grade itself.
- HTTP E2E: valid signed tenant token returns a persisted recoverability package; missing auth returns 401; another tenant receives 404.
- Invalid input returns 400 with no partial case/analysis history.
- Append-only concurrent writes produce ordered versions without loss.
- Restart preserves history; backup/restore passes SQLite integrity checks.

## Fail-closed evidence rules proven

A positive recoverability classification requires evidence whose asserted content matches the case. Current assertions cover:

- change id;
- customer;
- program;
- part;
- baseline revision;
- changed revision;
- cost id / amount / currency;
- causal state and partial attribution when used;
- mitigation amount, including evidenced zero;
- prior payment amount, including evidenced zero;
- contract state;
- notice requirement and deadline;
- prior-approval requirement;
- notice proof for the exact change/date;
- approval proof when required.

Verified-but-superseded evidence is not accepted. Duplicate/missing evidence identifiers fail the case closed. Mixed currency fails closed until an evidenced FX normalization path exists.

## P0/P1 state at this gate

No **known applicable** P0/P1 remains in the isolated assisted T1 path after the current test battery. This statement is bounded to the tested prototype. Production identity provider integration, deployment hardening, enterprise connectors and real customer data are not claimed.

## Double-recovery controls

Commercial packages include:

- a stable `change_record_key` for versions of the same change id;
- a stable `technical_delta_key` for the same customer/program/part/revision transition;
- explicit duplicate-change and duplicate-cost-line handling;
- prior-payment reconciliation.

These keys surface collisions; they do not replace human review of genuinely distinct changes that happen to share a technical delta.

## Next terminal

**T2 — MARKET EXPOSED.** Optional product breadth is no longer the priority. Safe work now shifts to target-account qualification, trigger evidence, buyer mapping, pilot data request, market-facing offer and controlled outreach.
