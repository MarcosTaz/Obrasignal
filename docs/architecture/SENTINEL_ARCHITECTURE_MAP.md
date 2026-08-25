# ObraSignal System Architecture Map — Sentinel snapshot

**Snapshot baseline:** `main@fce51d5b5524e09691f9187f7619ea0166217487`  
**Captured:** 2026-08-25  
**Authority:** derived inspection aid only. Canonical runtime modules, registries, queue and ADRs remain the sources of truth.

## Epistemic status

- Repository structure and configuration below: **FACT** for the baseline SHA.
- Production deployment/runtime claims: only where explicitly stated as repository-declared; this document does not promote them to `PRODUCTION_VALIDATED`.
- Open-PR topology is volatile and must be reconstructed before integration.

## Canonical control plane

| Concern | Canonical owner / contract | Role |
| --- | --- | --- |
| Master execution priority | `master_execution_queue.py` | Sole canonical execution queue and `CURRENT_ITEM_ID`. |
| Capability lifecycle | `capability_registry.py` | Capability state, health, contracts, dependencies and rollout metadata. |
| Source identity / source gates | `source_registry.py` | Stable source identity, access/reuse/readiness metadata and production gates. |
| Market scope | `market_scope_registry.py` | Canonical market-scope declarations. |
| Architecture policy | `docs/adr/0001-modular-monolith-capability-contracts.md` | Modular-monolith and contract-boundary decision. |

The current queue baseline has exactly one active item: `Q080_EVIDENCE_GRAPH_V1`. Queue advancement is not owned by feature branches or this Sentinel.

## Runtime composition

Repository-declared production path:

`Render web service`
→ `gunicorn cors_app:APP`
→ `cors_app` imports `api.APP`
→ `api.APP` is the same Flask application object exported from the legacy application/preload path
→ source/runtime installers and protected product routes compose onto that application.

There is one production Flask constructor in `app.py` on the inspected baseline. `api.py` and `cors_app.py` compose the same application; their coexistence is not evidence of a second runtime.

## Persistence boundary

Repository-declared persistence is one SQLite database selected through `OBRASIGNAL_DB`; Render configuration mounts the persistent database under `/var/data` for the single web instance.

Schema evolution is currently repository-native additive bootstrap/`ensure_*` logic rather than a separate migration directory. This makes idempotent startup and table ownership important architectural invariants. Capability sidecar tables must not become competing canonical Opportunity/Signal stores.

Key ownership:

- legacy actionable TENDER compatibility projection: `tenders` table owned through `app.py` ingestion/read compatibility;
- canonical normalized cross-lifecycle Signal envelope: `signal_store.py`;
- source-native current opportunity lifecycle: `opportunity_lifecycle.py`;
- account decision history: `decision_log.py` / existing `opportunity_decisions` contract;
- source health/cursor/runtime metadata: source runtime/support modules.

## Source ingestion path

Canonical shape:

`official publisher/source`
→ source-specific connector/normalizer
→ source runtime / incremental runtime plugin
→ `source_runtime.run_source_sync`
→ staged transaction
→ canonical Signal persistence + source metadata/lifecycle + cursor
→ legacy TENDER projection only where the signal type is TENDER
→ product read models.

Source-runtime persistence is transaction-scoped: source records, Signal events, lifecycle observations and cursor changes commit together or roll back together. Non-TENDER Signals must not be projected as legacy tenders.

## Auth and tenant boundary

`auth_context.py` is the public request-identity boundary. In provider mode it accepts a Bearer token only through the configured production JWT verifier and derives `RequestIdentity.account_id` from verified identity. API request setup attaches that server-derived identity and account bootstrap is performed for that account.

Tenant-private consumers must therefore accept account identity from the trusted request context or an already-trusted internal contract, never from arbitrary `payload.account_id`, query parameters or tenant headers as authority.

`auth_context_jwt.py` owns provider/JWKS signature and claim verification. Provider/JWKS failure is distinct from token invalidity and remains fail-closed.

## Opportunity / lifecycle boundary

Canonical Opportunity-facing product identity currently bridges two repository generations:

- strategic normalized data flows through canonical Signal records keyed by publisher/source-native identity;
- current customer opportunity API/read surfaces still project TENDER-compatible rows through `tenders.id` plus `(source, external_id)`.

`opportunity_lifecycle.py` owns source-native actionability/lifecycle state; current commercial read models must combine that with authoritative deadline evidence rather than creating an independent UI truth. Historical detail remains readable even when no longer actionable.

## Product API and UI boundary

- Product HTTP API: `api.py` blueprint on the shared Flask `APP`.
- Additional modular product routes are installed at `cors_app.py` only when their owning module is actually integrated.
- Legacy web/detail/radar composition uses server-side read models; HTML rendering remains presentation, not canonical business logic.
- Mobile lives under `mobile/` and consumes authenticated backend contracts. It must not manufacture lifecycle, eligibility, money, evidence or decision truth independently.

## Decision / Evidence boundary

Current main owns existing decision persistence/presentation. Q080 Evidence remains an `EXPERIMENT` capability on main. Parallel Evidence work is not canonical until integrated.

Evidence-related parallel order at this snapshot:

`#147 Evidence foundation`
→ `#194 Evidence production-decision lineage integration`

Both remain separate from main. Integration must preserve the already-merged Auth/runtime tree rather than replacing canonical files wholesale.

## Parallel PR architecture graph — material subset

This list is an integration map, not merge authorization.

- `#147` → Evidence Graph domain foundation; dependency for `#194`.
- `#194` → Evidence product/runtime integration; depends on `#147`.
- `#150` → Watchlist; additive account→Opportunity relationship/runtime/UI.
- `#152` → Requirements public contract.
- `#153` → Readiness; optional public-contract consumption of Requirements.
- `#209` → **temporary Integration Lab** cumulative Auth + Evidence + Watchlist + Requirements + Readiness validation; explicitly DO NOT MERGE.
- `#151` → Compare; currently has adversarial monetary blockers captured by temporary PRs `#201/#202`.
- `#211` → bounded Auth/JWKS production diagnostics; no production mutation by Sentinel.
- `#214` → Sentinel repair for expired-opportunity actionability truth drift; separate repair branch, NO MERGE.

At Sentinel-pass start the repository had 59 open PRs. Do not infer ownership from raw changed-file overlap because temporary integration branches deliberately contain common history and already-absorbed commits.

## Canonical architecture direction

The inspected repository is consistent with this target when changes preserve:

`small modular-monolith core`
→ `explicit public/domain contracts`
→ `replaceable adapters/providers`
→ `single canonical data/identity owners`
→ `feature-gated optional capability composition`
→ `failure isolation`
→ `tenant-safe product surfaces`.

A green PR or a conflict-free Git merge is not sufficient evidence of architectural safety. Exact combined trees must be retested whenever multiple PRs touch composition roots, registries, auth, migrations/persistence, mobile contracts or shared canonical files.
