# GuaranteeRelease — Persistent API Verification

Date: 2026-08-29
Branch: `factory/guaranteerelease`

## Executed result

The minimal persistent prototype API was executed locally against an isolated temporary datastore.

```text
PASS 12/12 backend assertions
```

Verified behavior includes:

1. unauthenticated instrument access returns `401`;
2. tenant A can create an instrument;
3. creation runs the canonical `engine_v2` assessment;
4. internal `tenantId` is not exposed in the public instrument object;
5. tenant B cannot read tenant A's instrument by id;
6. tenant B's list cannot see tenant A instruments;
7. `tenantId` cannot be patched by the client;
8. issuer cancellation changes state to `BANK_CANCELLED` without fabricating collateral release;
9. independently verified collateral release changes state to `VERIFIED_RELEASE` and records the separate collateral amount;
10. tenant A receives the expected audit history;
11. tenant B cannot read tenant A audit history;
12. instrument + audit history persist to disk with tenant ownership intact.

## Prototype architecture

- Node built-in HTTP server; no external package dependency.
- API-key-to-tenant mapping supplied by `GR_API_KEYS_JSON` environment configuration.
- Server-side tenant binding; client payload cannot choose or modify tenant ownership.
- Atomic file replacement for the prototype datastore.
- Serialized write chain to avoid same-process write races.
- Audit events on create/reassessment.
- Assessment delegated to `engine_v2.mjs`.

## Safety boundary

This is a controlled prototype, not production infrastructure.

It does **not** yet claim:

- production-grade identity/authentication;
- encrypted database/storage service;
- multi-process transaction safety;
- backup/restore verification;
- rate limiting / abuse protection;
- customer secrets management;
- bank/surety connectivity;
- legal authority to send release actions;
- browser E2E verification.

These absences remain explicit and must not be inferred as complete from the passing local API tests.
