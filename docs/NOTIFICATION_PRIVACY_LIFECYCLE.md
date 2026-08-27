# Notification Delivery privacy lifecycle owner contract

Owner: Notification Delivery / #263. Scope: `push_devices` and `push_deliveries` only.

This contract does **not** invent legal retention periods, does not change Expo/FCM/APNs delivery truth, and does not own Auth/provider revocation, device-local cache cleanup, Billing, or Privacy orchestration.

## Dataset semantics

### `push_devices`

- tenant path: direct `push_devices.account_id`;
- export: `INCLUDE_SANITIZED`;
- exported fields: internal device row id, `installation_id`, platform, created/updated timestamps, bounded last error, revoked timestamp, and booleans saying whether a provider token / tap binding existed;
- excluded raw fields: `account_id`, `expo_push_token`, `binding_id`;
- deletion: `DELETE`;
- active-account retention: retain active rows and revoked/dead-token tombstones while the account exists because the stable device row is part of the current delivery dedupe/token-rotation contract;
- time/legal retention: **no duration asserted by this owner**;
- deletion-state registration: blocked at `/api/v1/push/devices`; deleted/deleting accounts cannot create or rebind a device association.

### `push_deliveries`

- tenant path must agree on both sides: `event_id -> opportunity_events.account_id` and `push_device_id -> push_devices.account_id`;
- orphan or cross-account chains are contract errors and fail closed;
- export: `INCLUDE_SANITIZED`;
- exported fields: row/event/device ids, attempt/submission/retry timestamps, bounded errors, attempt count, receipt status/check timestamps, terminal failure timestamp, plus a boolean saying whether a provider ticket existed;
- excluded raw fields: `ticket_id`, historical `expo_push_token`;
- deletion: `DELETE`;
- active-account retention: retain ledger rows while the account exists so retries, receipts, dedupe and historical token rotation remain truthful;
- time/legal retention: **no duration asserted by this owner**.

## Cleanup ordering

Privacy must set the account to `deletion_pending` before calling the owner cleanup seam and must execute the following in the same destructive transaction:

1. validate the complete `push_deliveries` event/device tenant chain;
2. delete the account's `push_deliveries` rows;
3. delete the account's `push_devices` rows, including revoked/dead-token tombstones;
4. Privacy owner then deletes canonical `opportunity_events` and its other private dependants;
5. Privacy proves its own account-level postconditions and moves the minimal account tombstone to `deleted_pending_revocation`.

`delete_notification_account_data()` deliberately does not commit, does not delete `opportunity_events`, and does not mutate provider state.

## Late provider receipt after deletion

A late Expo receipt has no surviving `push_deliveries` row to update. Local state must not be recreated from a receipt. `provider_accepted` remains only provider acceptance and never becomes device/user delivery.

## Retry after deletion

No retry is permitted. Pending/retry ledger rows are deleted before device rows. Subsequent retry scans find no account delivery/device pair and must not call the provider.

## Dead-token / tombstone behavior

For an active account, `DeviceNotRegistered` or explicit unregister tombstones the usable provider token and preserves the stable device row for dedupe/token-rotation correctness. On account deletion, that tombstone is deleted; it is not retained as a private device association.

## Token rotation / rebind after deletion

Deletion-state identities are blocked from `/api/v1/push/devices`. A deleted account cannot rotate a token, re-enable an installation, or rebind a physical device to itself. Auth/session revocation remains a separate Privacy/Auth boundary; this owner guard is defense in depth and does not claim provider-session completion.

## Orphan prevention

Cleanup fails closed if any relevant delivery is orphaned or connects an event from one account to a device owned by another account. Delivery rows are deleted before device rows. The cleanup postcondition also rejects remaining global orphan/cross-account delivery chains.

## Critical post-condition

After Notification cleanup plus Privacy's canonical `opportunity_events` deletion/ordinary-API lifecycle guard:

- zero `push_devices` rows belong to the deleted account;
- zero `push_deliveries` rows remain transitively associated with it;
- zero pending retry/provider receipt state can recreate local notification ownership;
- no push registration/rebind is accepted for a deletion-state account;
- no raw provider token, opaque tap binding, dead-token tombstone, or delivery ledger remains as an account-private association;
- stale physical tray content may exist only outside server ownership until Mobile/Auth cleanup completes, and it cannot legitimately regain current account tap/API authority through the composed Privacy lifecycle guard.

## Reopen conditions

Reopen this owner contract on any material change to push table schema, account status semantics, device identity/dedupe strategy, receipt/retry semantics, tap binding semantics, Privacy deletion ordering, or provider token handling.
