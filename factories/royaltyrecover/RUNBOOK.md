# RoyaltyRecover — Assisted Pilot Operations Runbook

Date: 2026-08-29
Status: INTERNAL OPERATING RUNBOOK — NOT PRODUCTION CERTIFICATION

## Scope

This runbook operates the isolated RoyaltyRecover Flask application for an assisted pilot. It does not make RoyaltyRecover commercially validated, legally approved, or production-scalable.

The assisted-pilot deployment model is intentionally simple:
- one application instance at a time for SQLite-backed operation;
- persistent filesystem for the database and backups;
- Gunicorn WSGI runtime;
- HTTPS terminated by the hosting platform/reverse proxy;
- static API credentials supplied only through secret environment configuration;
- no raw agreement/evidence body persisted by the minimum text-ingestion endpoints;
- no automatic legal claim generation.

Do not deploy the persistent SQLite build to an ephemeral/serverless filesystem.

## Required environment

- `ROYALTYRECOVER_API_KEYS_JSON`
- `ROYALTYRECOVER_DB_PATH`
- `PORT` when the hosting platform does not inject it

Credential configuration for role-aware operation:

```json
{
  "keys": [
    {
      "key_id": "analyst-2026-01",
      "organization_id": "ORG-EXAMPLE",
      "secret": "GENERATED-OUTSIDE-SOURCE-CONTROL",
      "role": "ANALYST"
    },
    {
      "key_id": "reviewer-2026-01",
      "organization_id": "ORG-EXAMPLE",
      "secret": "GENERATED-OUTSIDE-SOURCE-CONTROL",
      "role": "REVIEWER"
    }
  ]
}
```

Rules:
- never commit secrets;
- every secret must be unique across all tenants and roles;
- legacy `{ORG: secret}` configuration grants ANALYST only;
- reviewer credentials must be separately provisioned;
- rotate a credential immediately after suspected disclosure.

## Start

From repository root:

```bash
gunicorn --chdir factories/royaltyrecover --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 120 application:app
```

Why one worker for the SQLite assisted build:
- reduces write-contention complexity;
- keeps the initial operating model easy to reason about;
- scale-out requires a managed multi-user database rather than multiplying SQLite writers.

## Pre-start checks

1. Database path points to a persistent volume.
2. Parent directory is writable by the application process and not public-web-readable.
3. Credential JSON parses successfully and contains unique secrets.
4. Current branch/commit is the approved pilot commit.
5. GitHub Actions `RoyaltyRecover Quality` is green for that exact commit.
6. A verified backup exists before deploying over an existing pilot database.
7. HTTPS is enforced by the platform/reverse proxy.
8. No debug server is exposed publicly.

## Health and readiness

Public health:

`GET /health`

Expected characteristics:
- non-sensitive;
- `ok=true`;
- `claim_generation=false`.

Protected operator dashboard:

`GET /app`

Without a valid key it must return 401 (or 503 if no credential registry is configured).

## Backup

Backups must be immutable-by-name and stored outside the live database path.

Example from `factories/royaltyrecover`:

```bash
python - <<'PY'
from datetime import datetime, timezone
from backup import backup_repository
from repository import RoyaltyRepository

source = '/persistent/royaltyrecover.db'
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
destination = f'/persistent/backups/royaltyrecover-{stamp}.db'
repo = RoyaltyRepository.file(source)
try:
    result = backup_repository(repo, destination)
    print(result)
finally:
    repo.close()
PY
```

Record the returned SHA-256 independently with the operational change record.

## Backup verification / restore drill

Never replace the live database merely to test a backup. Verify or restore to a separate path first.

```bash
python - <<'PY'
from backup import verify_backup
print(verify_backup('/persistent/backups/royaltyrecover-YYYYMMDDTHHMMSSZ.db'))
PY
```

For a restore drill:
1. copy/restore the backup to a separate test path;
2. start the app against that test path with test-only credentials;
3. verify health, tenant scope, register counts and audit history;
4. destroy the drill environment after verification.

## Change procedure

Before every assisted-pilot application update:
1. confirm exact branch/commit;
2. require green CI on exact commit;
3. take and verify backup;
4. record deployment actor and commit;
5. deploy;
6. run `/health` and authenticated `/app` smoke;
7. execute one tenant-scope negative smoke with a second test tenant where available;
8. if any gate fails, roll application version back; do not alter evidence/history to make the release appear green.

## Incident response

### Credential disclosure
- revoke/remove the credential from environment configuration;
- create a new unique secret;
- restart application with new configuration;
- review tenant-scoped audit events for unexpected access/activity;
- do not reuse the old secret.

### Suspected cross-tenant exposure
- stop external access to the affected instance;
- preserve database and logs;
- take an immutable verified backup;
- identify exact commit and request path;
- reproduce with synthetic tenants;
- classify as P0; no pilot continuation until fixed and CI/red-team tests pass.

### Database corruption / failed integrity check
- stop writes;
- preserve corrupted artifact separately;
- verify available backups by SHA-256 and SQLite integrity check;
- restore only from a verified backup;
- reconcile audit history and last known writes before resuming.

### Calculation dispute
- never overwrite historical calculation runs;
- preserve agreement-version SHA, rule/clause review history, evidence hashes, engine version and input hash;
- create a new calculation run after corrected evidence/rules;
- prior incompatible run should be treated as stale, not silently replaced.

## Data-handling rule

The minimum API hashes supplied agreement/evidence text for lineage and discards the raw body. For a real pilot, source originals must remain in the customer's approved document system or another separately approved secure store until a formal document-storage design is implemented.

Do not ask a client to upload confidential source documents to an unapproved environment merely because the API can accept text.

## Recovery truth rule

There are three distinct concepts and they must remain separate:

1. **Analytical candidate** — deterministic positive variance from reviewed rule + evidence.
2. **External outcome** — settlement/audit adjustment/no-adjustment supported by external evidence.
3. **Verified paid recovery** — recovery record explicitly verified against payment evidence.

Never present category 1 as category 3.

## Scale boundary

SQLite is an assisted-pilot storage choice, not the intended high-concurrency production architecture.

Migrate to a managed transactional database before:
- multiple horizontally scaled app instances;
- material concurrent write load;
- self-serve multi-customer production;
- contractual uptime/recovery commitments that the current deployment cannot meet.

## Release status vocabulary

Allowed internal labels must remain evidence-bound:
- `TECHNICALLY_GREEN` — exact CI commit passes.
- `ASSISTED_PILOT_CAPABLE` — technical/operational workflow can support a controlled pilot.
- `REAL_CLIENT_TESTED` — only after real customer data is processed with permission.
- `MARKET_VALIDATED` — only after required market proof gates are actually satisfied.
- `COMMERCIAL_READY` / `PRODUCTION_READY` — prohibited until their full real-world gates are satisfied.
