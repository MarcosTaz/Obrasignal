# Engineering Change Recoverability Assurance

Independent recoverability assurance for engineering changes:

`engineering change -> exact revision delta -> linked evidence -> causal cost -> mitigation/prior payment -> contractual basis -> notice/deadline -> recoverability -> commercial action package`

## Truth rules

- A detected change is not a cost.
- A cost is not entitlement.
- Entitlement is not recoverability.
- Recoverability is not payment.
- A boolean saying “evidence supported” is not evidence.
- Unknown remains unknown.
- Correct EUR 0 is a successful output.
- Mixed currency, unverified revision/baseline, missing linked cost/causality evidence, ambiguous contract basis and unresolved notice conditions fail closed.

## Verified code boundary

The assisted product now has a production-grade application boundary in code:

- deterministic recoverability engine and 26-company independent oracle matrix;
- tenant-scoped signed bearer principals with bounded lifetime, role and JTI;
- authenticated real-record analysis and persistence; synthetic demo remains public;
- explicit cross-tenant rejection;
- append-only SQLite case/analysis version history with concurrent-write protection;
- HMAC-SHA256 tamper-evident audit chain;
- OWNER-only operational purge while retaining the minimal audit ledger;
- retention purge for stale operational records;
- AES-256-GCM encrypted backup/restore with wrong-key failure and integrity validation;
- fail-closed `/readyz` requiring independent auth, audit and backup secrets in `ECE_ENV=production`;
- bounded HTTP request bodies and security response headers;
- no customer-file upload endpoint exists, so malware/file scanning is not an exposed surface in this slice;
- commercial action package with input SHA-256 audit fingerprint.

## Tests

```bash
python -W error::ResourceWarning -m unittest -v
```

Verified production-boundary suite: **45 tests passing**, plus an isolated production HTTP smoke gate that proves readiness, unauthenticated rejection, cross-tenant rejection, payload-size rejection, OWNER purge and security headers.

The GitHub workflow `Engineering Change Production Boundary` protects both the production-boundary branch and the canonical Factory branch.

## Production configuration

Production startup fails closed unless all required secrets are present:

```bash
export ECE_ENV=production
export ECE_AUTH_SECRET='replace-with-at-least-32-random-bytes'
export ECE_AUDIT_SECRET='different-at-least-32-random-bytes'
export ECE_BACKUP_SECRET='different-at-least-32-random-bytes'
export ECE_DB_PATH='/secure/persistent/ece.db'
export ECE_MAX_BODY_BYTES='1048576'
python app.py
```

`GET /readyz` must return `ready: true` before receiving real records.

## Current maturity truth

- T0 thesis: **NARROW / SURVIVED**
- Assisted product: **PILOT CAPABLE**
- Code production boundary: **CLOSED / VERIFIED**
- Hosted production deployment for confidential customer data: **NOT YET VERIFIED**
- Real customer data: **NONE**
- Commercial proof: **NONE**
- Market exposure: **NOT YET**

A green code boundary is not commercial validation and is not evidence of recovered cash. Do not label this Factory `PILOT_VALIDATED`, `MARKET_VALIDATED` or `COMMERCIAL_READY` until real external evidence exists.
