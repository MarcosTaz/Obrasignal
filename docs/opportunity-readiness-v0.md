# Opportunity Readiness / Bid Readiness v0

## Purpose

Opportunity Readiness answers a narrow operational question: **does this account currently have enough verified information to proceed with bid preparation for this opportunity?**

It does not make the commercial BID / NO-BID decision. It exposes blockers, warnings, unknowns, verified-ready checks and deterministic next verification steps.

## Non-goals

V0 does not implement Opportunity Unlock, automatic submission, document generation, partner search, insurance/bond sourcing, crew hiring, portfolio optimisation, SHADOW, COMMAND, or automated external action.

## Repository state used by v0

At implementation time, `main` contains canonical opportunity/lifecycle data, tenant-scoped company profiles, `economic_fit.py`, and `signal_store.py`.

`signal_store.py` is the canonical durable envelope for normalized signals. The legacy `tenders` table remains the actionable-TENDER compatibility projection. Readiness therefore uses `tenders` plus lifecycle state for the current opportunity identity/status/deadline and may enrich that read model from the matching canonical `signal_records.normalized_json` TENDER snapshot by `(source, external_id)`.

A parallel Opportunity Requirements v0 capability exists in PR #152 with public `build_checklist(...)` and `assess_checklist(...)` contracts, but it is not integrated into `main`. Readiness includes a soft public-contract adapter for that capability and does not read any Requirements private storage.

The Signal enrichment path copies only an explicit allowlist of structured Requirements context (for example certifications, turnover, insurance, equipment and document requirements, plus currency/jurisdiction). A Signal snapshot cannot overwrite canonical source identity, external identity, deadline or lifecycle state.

Current connector coverage of those structured requirement fields is not assumed. If the matching Signal snapshot does not contain supported structured Requirements context, eligibility remains `UNKNOWN`.

## Readiness model

`evaluate_readiness(account_id, opportunity, company_state, requirements=..., economic_fit_result=..., clock=...)` returns an on-demand assessment containing:

- `opportunity_id`
- `account_id`
- `overall_status`
- `dimensions`
- `blocking_items`
- `warning_items`
- `unknown_items`
- `ready_items`
- `generated_at`
- `assessment_version`
- `policy_version`
- `evidence_refs`
- `data_completeness_percent`
- `next_checks`

V0 is computed on demand and deliberately creates no readiness persistence/cache/source-of-truth.

## Status semantics

### Item / dimension status

- `READY`: the check is positively supported by current input.
- `BLOCKED`: a known condition prevents readiness.
- `WARNING`: known risk/attention item that does not itself block readiness.
- `UNKNOWN`: required evidence is missing, unavailable, incomplete or unparsable.
- `NOT_APPLICABLE`: reserved for dimensions with no applicable checks.

### Overall status policy

Policy version: `opportunity-readiness-policy.v0`.

1. One or more blockers => `NOT_READY`.
2. No blockers but one or more critical unknowns => `UNKNOWN`.
3. No blockers/critical unknowns but warnings or non-critical unknowns => `CONDITIONALLY_READY`.
4. Otherwise => `READY`.

This ordering is intentional. Unknown critical data can never silently become `READY`, and missing data is never converted into a false blocker.

## Dimensions in v0

V0 evaluates only dimensions for which current repository contracts can provide meaningful evidence:

- `OPPORTUNITY_STATUS`: explicit lifecycle/actionability.
- `DEADLINE`: official submission deadline existence, parseability, expiry and <=48-hour warning.
- `ELIGIBILITY`: optional Requirements public contract; unavailable or incomplete mandatory-requirements coverage remains critical `UNKNOWN`.
- `FINANCIAL`: reuses the existing `economic_fit.py` result or its public evaluator; no duplicate economic engine.
- `SOURCE_COMPLETENESS`: source + external opportunity identity completeness.

Capacity, documents, mobilisation, location-specific capacity and commercial-fit dimensions are not shown as green merely because data is absent.

## Blockers vs warnings vs unknowns

Known non-actionable lifecycle states (`CLOSED`, `CANCELLED`, `AWARDED`, `EXPIRED`, `COMPLETED`) and an official deadline that has passed **or is exactly due at evaluation time** are deterministic blockers.

Actionability is normalized explicitly so repository/SQLite values `0` and `1` retain their intended boolean meaning. This prevents a known `is_actionable=0` record from falling through to `UNKNOWN` merely because SQLite returned an integer rather than Python `False`.

A mandatory requirement explicitly reported as `NOT_MET` is a blocker. An optional requirement reported as `NOT_MET` is a warning.

Requirement priority is conservative: only an explicit `mandatory=False` makes a supplied readiness requirement non-mandatory. Missing/unknown priority remains critical rather than being coerced to optional.

Missing or invalid deadline, unavailable Requirements, incomplete Requirements coverage, unknown mandatory requirement status and unavailable economic data are unknowns. Only critical unknowns prevent absolute readiness.

A valid deadline within 48 hours is a warning, not an automatic blocker.

## Evidence and provenance

Each readiness item can preserve `source_ref` and `evidence_ref`. The assessment also emits de-duplicated `evidence_refs`. V0 does not implement an Evidence Graph; it only preserves references supplied by existing or future public contracts.

The current source reference is generated from canonical `source:external_id` when both values are available.

The Requirements adapter preserves the first public evidence reference as `source_ref#locator` when both fields are supplied by the Requirements contract.

## Economic fit boundary

When no explicit `economic_fit_result` is supplied, V0 calls the repository's existing `evaluate_economic_fit(...)`. It does not calculate a second economic score.

`UNFAVOURABLE` economic fit is surfaced as a warning because economic preference is not treated as a legal/technical submission blocker by readiness.

## Requirements compatibility

The domain-level optional `requirements` iterable accepts public requirement records with the following minimal fields:

- `name` or `code`
- `mandatory` boolean
- `status` (`MET`, `NOT_MET`, `UNKNOWN`, or compatible aliases)
- optional `source_ref`
- optional `evidence_ref`

`readiness_requirements_adapter.py` maps the public Opportunity Requirements v0 contract from PR #152 into this shape. The dependency is deliberately optional and imports only its public functions; there is no direct private-table coupling.

The adapter activates only when the enriched opportunity carries at least one explicit structured requirement field supported by Requirements v0. Free-form opportunity description text alone is **not** treated as a complete requirements inventory, and the adapter calls `build_checklist(..., include_text_rules=False)` to avoid promoting heuristic text extraction into readiness evidence.

Known Requirements blockers are still useful: a public `known_blocker=True` maps to mandatory `NOT_MET` and therefore makes readiness `NOT_READY`.

However, Requirements v0 currently makes no public guarantee that every mandatory requirement in the procurement documents has been discovered. Consequently, any partial Requirements result is accompanied by a synthetic critical `requirements_coverage_unverified` item. Verified extracted requirements may be shown, but they cannot by themselves produce full `READY`.

The adapter recognizes a future explicit public `coverage_complete=True` assertion on the checklist or assessment. Only such an explicit completeness contract removes that synthetic coverage unknown. Empty extraction without verified complete coverage is never interpreted as proof that the opportunity has no requirements.

If the Requirements module is absent or its public assessment fails, the adapter returns unavailable and Readiness degrades eligibility to `UNKNOWN`.

## Canonical Signal enrichment boundary

The authenticated endpoint calls the public `signal_store.get_signal_record(conn, source, external_id, "TENDER")` contract while the canonical database connection is open.

The normalized Signal snapshot is treated as optional rich context, not as a second lifecycle source. The endpoint copies only:

- the structured requirement fields recognized by `readiness_requirements_adapter.py`;
- `currency`;
- `jurisdiction`.

`currency` and `source_updated_at` may also be taken from the canonical Signal envelope when absent from the legacy projection.

The following remain authoritative from the current tender/lifecycle read model and cannot be replaced by `normalized_json`:

- `source`;
- `external_id`;
- submission `deadline`;
- `is_actionable`;
- `lifecycle_status` and lifecycle provenance.

Malformed Signal JSON, a missing Signal record, or Signal-store read failure contributes no optional enrichment and does not break the readiness endpoint.

## Tenant boundary

`account_id` is mandatory. If `company_state.account_id` is present and differs from the assessment account, `TenantBoundaryError` is raised.

The HTTP adapter never accepts account identity as an authorization input. `GET /api/v1/opportunities/{id}/readiness` derives the account from the existing trusted authentication provider, then loads the matching company profile server-side. A client-supplied `account_id` query parameter has no effect.

An authenticated identity object without a usable `account_id` is rejected with `401` rather than falling back to an unscoped/default tenant.

## Service / API contract

The domain service remains:

`evaluate_readiness(account_id, opportunity, company_state, optional_inputs) -> assessment`

The authenticated HTTP adapter is:

`GET /api/v1/opportunities/{id}/readiness`

The adapter:

1. obtains tenant identity from authentication;
2. loads the canonical tender projection plus current lifecycle state;
3. returns `404` when the opportunity does not exist;
4. looks up the matching canonical TENDER Signal and allowlist-enriches optional Requirements context;
5. loads the tenant-scoped company profile;
6. invokes the optional Requirements resolver through its public adapter;
7. calls the domain engine without duplicating readiness rules.

The route is installed idempotently at the production WSGI boundary. It introduces no client-controlled tenant selector, SQL interpolation or HTML rendering.

Requirements PR #152 is still a parallel branch, so the default Readiness branch does not claim that its module is available in `main`. When it is absent, or when normalized signals lack structured requirement fields, eligibility remains `UNKNOWN`.

## Opportunity-detail checklist

The mobile opportunity detail consumes the authenticated readiness endpoint through `api.readiness(id)` and renders a compact text/status checklist inside the existing explanation area.

The checklist exposes:

- the overall operational readiness label;
- known blockers;
- critical/non-critical unknowns;
- warnings;
- positively verified checks;
- up to four deterministic next verification steps.

The presentation deliberately does **not** render `data_completeness_percent`, a readiness gauge, probability of success, or bid-quality score. `UNKNOWN` is labelled **Por verificar** and is visually/semantically distinct from **Bloqueado**. The checklist also states that readiness is an operational state, not the BID / NO-BID decision.

Failure of the readiness endpoint is locally contained: the opportunity detail and commercial workflow remain usable, and the checklist offers a retry.

## Determinism and clock

Deadline rules use an injected `clock`. Same inputs + same clock + same policy version produce the same result.

The HTTP endpoint naturally uses evaluation time at request execution; domain tests use a fixed clock for replayable deadline semantics.

A deadline equal to the injected current instant is treated as due/expired, not open.

## Data completeness

`data_completeness_percent` measures the proportion of readiness items that are not `UNKNOWN`. It is explicitly **not** a readiness score and must never be presented as probability of success or bid quality. V0's mobile checklist intentionally does not display it.

## Error / graceful degradation

If the existing economic-fit subsystem cannot be imported/evaluated, the financial dimension becomes `UNKNOWN`; the assessment does not fabricate a pass.

If canonical Signal enrichment is unavailable or malformed, the endpoint continues without optional structured context.

If the tenant profile loader fails after authentication, the HTTP adapter preserves the authenticated tenant identity and falls back to an account-only company state. Economic/company-dependent checks therefore degrade conservatively rather than causing the whole readiness surface to fail.

If Requirements is unavailable or the optional resolver fails, eligibility becomes critical `UNKNOWN`; the rest of the assessment remains available.

If the mobile readiness request fails independently, the rest of opportunity detail remains usable and the checklist exposes a local retry.

Authentication failures do **not** degrade to anonymous behavior: they remain `401`.

## Tests

`tests/test_opportunity_readiness.py` covers:

- open opportunity with known data;
- expired deadline and exact-deadline boundary;
- explicitly closed opportunity;
- SQLite `0/1` actionability semantics;
- mandatory known blocker;
- mandatory requirement unknown / false-READY protection;
- unknown requirement priority remains critical;
- missing Requirements subsystem;
- missing economic/company data without false blocker;
- warning without blocker;
- optional unmet requirement;
- multiple blockers;
- deterministic assessment;
- evidence reference retention;
- cross-tenant company-state rejection;
- fixed-clock behavior;
- invalid deadline as UNKNOWN rather than blocker.

`tests/test_readiness_requirements_adapter.py` covers:

- free-form description alone does not activate structured Requirements;
- public Requirements assessment mapping and evidence retention;
- partial verified requirements cannot promote readiness to `READY`;
- known Requirements blockers still produce `NOT_READY`;
- NOT_EVALUATED maps to `UNKNOWN`;
- unknown priority remains mandatory/conservative;
- partial coverage produces `requirements_coverage_unverified`;
- a future explicit `coverage_complete=True` removes only that coverage unknown;
- Requirements subsystem failure degrades to unavailable.

`tests/test_readiness_api.py` additionally covers:

- authenticated tenant identity is authoritative;
- forged/query-string `account_id` cannot change assessment tenant;
- public requirements-resolver invocation and evidence propagation;
- canonical Signal structured context reaches the resolver;
- a malicious/stale Signal snapshot cannot overwrite canonical identity, deadline or lifecycle;
- Signal-store failure degrades locally;
- profile-loader failure degrades conservatively;
- requirements-resolver failure degrades to `UNKNOWN`;
- closed opportunity remains `NOT_READY` through HTTP;
- unknown opportunity returns `404`;
- missing/empty authenticated identity returns `401`;
- route installation is idempotent.

`tests/test_readiness_mobile_contract.py` protects the mobile presentation contract:

- readiness is a GET/read path;
- READY / CONDITIONALLY_READY / NOT_READY / UNKNOWN labels remain distinct;
- the UI explicitly states it is not BID / NO-BID;
- data completeness is not rendered as a score/gauge;
- readiness failure remains locally contained and retryable.

The existing Expo web-bundle smoke remains the compile/runtime integration gate for mobile changes.

## Limitations

V0 has no persistent readiness snapshot. The visual checklist is intentionally small and read-only; it does not mutate readiness, requirements, workflow or opportunity source data.

Opportunity Requirements v0 remains in parallel PR #152 at this point. Readiness has a tested soft adapter and a canonical Signal context path, but it does **not** claim Requirements is merged or universally populated by existing connectors.

Requirements v0 also does not yet publicly attest complete procurement-document coverage; partial extracted facts cannot remove the coverage unknown. This deliberately prevents false `READY` even when some individual requirements are positively verified.

Capacity, insurance, bonding, equipment, document readiness and mobilisation remain unavailable unless current/future canonical signals and public company-state contracts actually supply those facts.

## Future integrations

Potential consumers include Opportunity Requirements, Mobilize, Watchlist, Opportunity Compare, alerts and COMMAND. Integrations must consume published/public contracts only and remain optional so subsystem failure degrades to `UNKNOWN` instead of collapsing readiness.

The next material capability improvement is not another Readiness scoring layer. It is broader verified structured-requirement capture in canonical normalized signals plus an explicit Requirements completeness contract. Readiness can consume those through the boundaries already implemented.

## Rollback

The module creates no new migration or persisted readiness state. Reverting the branch commit removes the domain engine, optional Requirements adapter, authenticated route/wiring, mobile read-only checklist, tests and documentation. Existing canonical Signal storage remains untouched. No data rollback is required.

## Capability boundary

Prepared in parallel. This module does not modify the canonical Master Execution Queue, promote Dynamic Eligibility, promote COMMAND, perform automatic action, or claim production deployment merely because its isolated branch and CI are healthy.
