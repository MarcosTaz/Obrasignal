# ObraSignal Customer Account & Privacy Lifecycle

Baseline reconstructed from canonical `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`.

This document is a product-truth and ownership contract. It does **not** claim GDPR, statutory retention, tax/accounting, consumer-law or other legal compliance.

## ACTIVE — canonical account-owned data map

| Data | Persistence owner | Tenant boundary | Export v1 | Product DB deletion | Notes |
|---|---|---|---|---|---|
| `accounts` | `account_registry` + `evaluation_policy` | `account_id` PK | yes | scrub to minimal anti-resurrection tombstone | Billing/Auth remain external owners |
| `company_profiles` | `company_profile` | `account_id` PK | yes, JSON parsed fail-closed | delete tenant row | historical profile-file cleanup remains owner boundary |
| `opportunity_decisions` | `decision_log` | `account_id` | yes | delete tenant rows | shared tender remains |
| `opportunity_events` | `notification_events` | `account_id` | yes | delete tenant rows | shared tender remains |
| `opportunity_workflow` | `opportunity_workflow` | `account_id` + opportunity identity | yes | delete tenant rows | shared opportunity remains |
| `evaluation_events` | `evaluation_policy` | `account_id` | yes, JSON parsed fail-closed | delete tenant rows | Evaluation/Billing policy remains external owner |

The executable inventory discovers every SQLite table carrying `account_id`. If a future account-scoped table appears without being classified above, export and deletion fail closed. This is deliberate integration pressure: new tenant-private owners must supply an export/deletion contract before account control can still claim completeness.

`accounts` deletion is currently a **minimal tombstone**, not physical row removal. Removing the row while a still-valid Auth identity or late Billing webhook exists would allow `ensure_account()` to recreate the customer. The tombstone therefore remains until external identity/session revocation and billing reconciliation have a proven integration contract.

## Data that is not private-account deletion scope

`tenders`, source-normalized Signal records, source metadata, source health/cursors and opportunity lifecycle are shared/public procurement truth. Tenant exit must not delete them.

`billing_webhook_events` is currently an account-independent dedupe table (`event_id`, `received_at`) with no safe `account_id` attribution. This lifecycle does not guess an owner relationship or delete arbitrary webhook rows. If Billing later adds attributable customer payload/history, it must register that data with this lifecycle.

## NEXT — tenant isolation

Export and deletion derive tenant authority only from server-side authenticated identity at HTTP boundaries. The export/delete functions use exact `account_id=?` predicates, and deletion tests preserve another tenant's profile, decisions, events, workflow and evaluation events while deleting the requesting tenant's rows.

A future tenant-private table causes fail-closed `account_data_contract_unproven` until explicitly integrated.

## NEXT — session / device revocation

Canonical Auth remains Supabase/provider-owned. `sessionCoordinator.js` does not persist a second access token. Password recovery and provider identity/session revocation are Auth ownership and must be consumed as public contracts rather than reimplemented here.

Mobile private cache isolation/cleanup is owned by #291 / PR #322. Its candidate scopes Profile/Radar/Saved cache by authenticated local identity and purges previous-tenant private namespaces on identity change/sign-out. Physical-device proof remains external to this server cell.

Notification account/device token registration and revoke/rotate semantics are not canonical on current main. They remain Notification Delivery ownership (#57/#263/current equivalent). Account deletion cannot be called completed until that owner exposes and proves a revocation contract if device tokens exist.

## NEXT — export truth

`GET /api/v1/account/export` exports **current canonical server-owned account data only**:

- account/billing/evaluation projection held in `accounts`;
- Company Profile;
- decision history;
- opportunity event history;
- workflow state/notes;
- evaluation event history.

It explicitly does not claim to include:

- identity-provider account/session data;
- Billing provider source records;
- device-local private cache;
- shared public procurement datasets.

Corrupt persisted JSON or an unregistered account-scoped owner fails closed; it is never silently omitted from an export called complete within the declared scope.

## NEXT — deletion semantics

`POST /api/v1/account/deletion` requires the authenticated account plus literal destructive confirmation `DELETE_MY_OBRASIGNAL_DATA`. No client-supplied tenant selector is accepted.

The local transaction deletes the requesting tenant from all five dependent private tables and scrubs Billing/Evaluation projection fields in `accounts`. It verifies zero dependent rows before commit and preserves shared public procurement rows.

The result is intentionally `PENDING`, not `COMPLETED`, with `deleted_pending_revocation` retained in the account row. Current pending boundaries are:

1. Auth provider identity/session revocation;
2. #291 device-local private cache purge/physical-device proof;
3. historical Company Profile file retention/cleanup review by the profile/persistence owner;
4. Billing provider reconciliation / late-event behavior.

A cleanup exception rolls back the destructive transaction and leaves `deletion_failed`, never success. A newly discovered account-owned table also produces `deletion_failed` until its owner is integrated.

Ordinary `/api/v1/*` customer routes are blocked for deletion lifecycle states. Account deletion/status endpoints remain available so the lifecycle can be inspected/retried.

## RETENTION / ORPHAN BEHAVIOR

No guessed automatic retention duration is introduced here. The minimum anti-resurrection account tombstone is retained while external revocation is unproven. This is a product-safety choice, not a legal-retention claim.

Deletion postconditions scan every registered dependent private owner for orphan rows. Unknown future tenant-private owners prevent deletion rather than becoming silent orphans.

## PENDING CANDIDATES / integration obligations

- Q090 Company State (`company_state_snapshots`) is not canonical on current main. PR #223 and current Integration Lab all-up evidence show it as tenant-private. If/when integrated, it must be added to export/deletion through its public owner contract before this lifecycle can pass its executable inventory.
- Watchlist and Pursuit Workspace are also non-canonical current candidates per Data Reliability #238. Any tenant-private persistence added by them inherits the same integration obligation.
- Data Reliability #238 owns storage/migration/backup correctness; this cell does not create a second migration engine or storage truth.

## Golden / Integration Lab handoff

Golden issue #292 / PR #212 acceptance requires:

- authenticated export with no cross-tenant private state;
- explicit destructive deletion confirmation;
- no shared-public-data destruction;
- proven postconditions;
- completed/pending/failed distinction.

This branch implements and tests those server-side truths while intentionally keeping overall deletion `PENDING` at external-owner boundaries. Password recovery remains Auth ownership. Integration Lab must combine this candidate with current Auth, Billing, #291 and persistence candidates and rerun the same fail-closed account-data inventory before any assembly claim.

No merge, deployment, production mutation, secret/config change or destructive production action is authorized by this branch.
