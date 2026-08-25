# ObraSignal Recovery Runbook

Baseline for this runbook: `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`. Current production architecture is SQLite on persistent Render storage. This runbook does not authorize or automate production mutation.

## Objectives and assumptions

Repository defaults encode an initial operating contract of **RPO <= 24h**, **RTO <= 4h**, and **30-day backup retention**. These are explicit assumptions, not provider guarantees. A production owner may choose stricter targets, but must not silently weaken them.

Every recoverable backup must exist outside the failure domain of the active Render disk. A copy on the same disk is only a logical-recovery convenience. Off-disk storage must provide encryption at rest, access control, retention/lifecycle policy, and enough durability to meet the declared RPO.

## Artifact contract

Use `storage_recovery.create_backup_artifact()` or the CLI `python storage_recovery.py artifact SOURCE DIRECTORY --label LABEL --source-revision SHA` against an explicit source path. The helper never selects production implicitly.

Each artifact is named deterministically from label + UTC timestamp + schema fingerprint prefix and has a sibling versioned manifest containing artifact SHA-256, full schema fingerprint, source revision when supplied, RPO/RTO/retention metadata, and explicit `off_disk_required=true` / `encrypted_at_rest_required=true` expectations.

Do not upload an artifact off-disk unless `verify_backup_artifact()` succeeds. The uploader/provider integration is deliberately separate from the database helper and must treat the database artifact and manifest as one retention unit.

## Scheduled backup procedure

1. Resolve the intended database path explicitly from deployment configuration; never infer it from this runbook.
2. Create the verified artifact in disposable staging storage.
3. Verify artifact + manifest locally.
4. Upload both files to a provider outside the Render disk failure domain using provider-native encryption at rest and least-privilege credentials.
5. Verify provider-side object existence/checksum where the provider supports it.
6. Apply retention >= the declared manifest retention period. Deletion before retention expiry requires a separately authorized retention/privacy decision.
7. Record only artifact identifier, timestamp, checksum/fingerprint and status. Do not log customer rows, JSON payloads, tokens or secrets.

The repository does not contain provider credentials and does not perform step 4 automatically. That is the intentional external boundary.

## Restore drill

A restore drill must use disposable paths only:

1. Download one off-disk artifact + its exact manifest to disposable storage.
2. Run `verify_backup_artifact()`.
3. Run `verified_restore_drill()` into a **new** destination. Existing destinations are rejected.
4. Run application schema contract verification against the restored DB; for runtime owners also ensure Signal/source-metadata/lifecycle tables before `verify_database(..., include_runtime=True)`.
5. Exercise bounded synthetic/read-only acceptance appropriate to the recovered revision.
6. Destroy only the disposable drill copy when the drill is complete. Do not delete the retained backup artifact merely because a drill passed.

A successful copy is not enough: checksum, SQLite `integrity_check`, schema fingerprint and application storage contract must all pass.

## Corruption / suspected silent-state incident

If corruption is suspected, stop writes before any production recovery action. Preserve the suspect file as evidence. Never run guessed cleanup, `DROP`, `DELETE`, VACUUM-based salvage or cursor reset as a first response.

Create/read a verified backup artifact only if SQLite can produce a consistent backup. If `integrity_check` or application JSON/schema contracts fail, mark the state as suspect and select the newest earlier off-disk artifact that passes verification. Corrupt durable Company Profile state must remain an explicit error; it must not be converted to defaults or a legacy file.

## Candidate selection for production recovery

For each candidate artifact, verify: checksum, artifact format version, SQLite integrity, schema fingerprint, source revision compatibility, and application storage contract. Prefer the newest artifact that satisfies those checks and the incident's consistency requirements. Never choose a candidate solely because its timestamp is newest.

## Production cutover guard

`production_cutover_guard()` is validation-only. It requires explicit operator acknowledgement and returns `cutover_performed=false`; it does not rename, replace, unlink or swap the production database.

A real production cutover is therefore a separate, explicitly authorized operator/deployment action. Before any cutover:

- quiesce all application/worker writes;
- preserve the current authoritative database as a rollback artifact without modifying it;
- restore the selected backup to a new candidate path;
- verify checksum/integrity/schema/application contracts;
- verify expected build/schema compatibility;
- obtain explicit production mutation authorization;
- only then perform the provider/filesystem-specific atomic switch procedure.

This lab does not perform that switch.

## Failed restore / rollback

A failed repository restore removes only the newly created disposable destination. Existing authoritative files are never overwritten by `restore_database()`.

If a future authorized production cutover fails after the switch, rollback means re-quiesce writes and atomically return to the preserved pre-cutover authoritative artifact/path. Do not try to 'reverse' a bad restore by deleting rows from the restored database. Preserve both failed candidate and pre-cutover artifact until incident closure and retention review.

## Migration failure during deploy

Production startup migrations run behind `storage_migration_lock`. If an owner migration fails after earlier owners committed, treat the DB as partially migrated but data-preserving. Do not execute destructive down migrations. Keep the application from serving incompatible code, repair the migration/code, then rerun the additive migration graph. Application contract verification must pass before declaring recovery.

## Cursor / source-state recovery

Never reset or advance source cursors by guess. A cursor is valid only if the durable source state it represents is present. If an incident reveals cursor/state disagreement, preserve both values, determine the last transactionally proven state, and replay from the source according to that connector's contract. Duplicate-safe identity/UPSERT semantics should absorb replay; deletion to 'make replay clean' is forbidden without explicit data ownership proof.

## Required periodic evidence

At least one recurring operational drill should prove an off-disk artifact can be downloaded, verified and restored to a disposable database within the declared RTO. Repository tests prove the mechanics synthetically; they do not prove provider credentials, network access, retention policy, storage-class durability or production cutover permissions.
