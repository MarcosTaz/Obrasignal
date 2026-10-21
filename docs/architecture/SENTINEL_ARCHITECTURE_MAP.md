# ObraSignal System Architecture Map — Sentinel snapshot

**Snapshot baseline:** `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`  
**Captured:** 2026-08-25  
**Authority:** derived inspection aid only; canonical queue, registries, runtime modules and ADRs remain authoritative.

## Current facts

- Master execution priority: `master_execution_queue.py`.
- Capability lifecycle: `capability_registry.py`.
- Source identity/gates: `source_registry.py`.
- Market scope: `market_scope_registry.py`.
- Production WSGI composition remains `gunicorn cors_app:APP` with one Flask constructor owned by `app.py`.
- Request identity remains server-derived through `auth_context.py` / `auth_context_jwt.py`.
- Production Auth and full authenticated E2E are validated on current canonical lineage; historical degraded claims are retired.
- Expired-opportunity actionability repair #214 is merged into current main; historical `CLOSED→ACTIONABLE` drift is retired on this baseline.
- #248 is the current tested Sentinel Security/Operability candidate; it is not canonical until separately integrated.
- `main` branch protection is still observably OFF at the visible GitHub boundary.

## Architecture fitness candidate

PR #216 provides a derived, repeatable audit only; it does not replace canonical state. Strict checks cover:

1. exactly one valid canonical Master Queue state;
2. capability registry validity;
3. non-empty unique stable `source_id` values;
4. duplicate literal registry keys before Python overwrite;
5. one production Flask constructor owned by `app.py`;
6. one repository-declared Gunicorn entrypoint targeting `cors_app:APP`.

Cross-PR semantic combination remains Integration Lab ownership. Product acceptance remains Golden Path ownership. Security/operability hardening remains Sentinel ownership. No architecture document authorizes queue/capability/source promotion or merge.
