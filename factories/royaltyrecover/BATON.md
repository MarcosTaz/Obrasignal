# RoyaltyRecover BATON

BATON_READY: true
BATON_CAPTURE_DATE: 2026-08-29

## MISSION
Build RoyaltyRecover into a real evidence-first contractual royalty/revenue-share recovery company and operational web application that can ingest, reconstruct, reconcile, evidence, review, route and verify incremental recoveries without invented entitlements or unsupported calculations.

## VERSION / HEAD
CURRENT_SOURCE_HEAD: `82bf8a171cee480a88718c17e3b9b7a4e97fb578`
BASE_MAIN: `66d43f6fd51cf9cea08016dad335aaa04b711a24`
ENGINE_VERSION: `0.2.0`

## BRANCH
`royaltyrecover/company-web-app`

## PR
No PR on the active source branch. Validation-only PR #814 exists on `validation/royaltyrecover-company-web-app-20260829-v1`; it is draft, unmerged and must not be treated as the active source branch. No automatic merge.

## DONE
- Evidence-first royalty engine, recoverability scan, service pipeline and synthetic portfolio.
- Tenant-scoped repository for organizations, licensors, licensees, agreements, versions and evidence.
- Contract/rule review gates and persisted calculation/finding workflow.
- Human review workflow and formal-audit handoff boundary.
- Outcome/recovered-amount persistence with evidence requirements.
- Authz roles and organization-bound credentials.
- Operator web application, readiness, backup/restore and container workflow.
- Normalized sales import core and HTTP API with provenance.
- Cross-tenant import/read tests.
- Identified current CI regression at source head `09f96c144c2b99951a4f51e2dd64b432bcf54932`.
- Repaired duplicate-import HTTP semantics: `ConflictError` subclasses `ValueError`, so the import endpoint now re-raises it to the canonical 409 handler instead of incorrectly returning 400. Repair commit: `82bf8a171cee480a88718c17e3b9b7a4e97fb578`.

## IN_PROGRESS
- Verify CI for `82bf8a171cee480a88718c17e3b9b7a4e97fb578`.
- Harden normalized import tenant identity and dataset uniqueness.
- Complete canonical document pipeline: INGEST -> EXTRACT -> NORMALIZE -> IDENTIFY RIGHT -> CALCULATE -> DOSSIER.
- Expand adversarial false-recovery coverage.
- Gate product toward CASE_READY before any PILOT_READY claim.

## ACTIVE
Current-head CI verification. If red, repair the failing regression first. If green, immediately fix normalized sales uniqueness so identical external dataset IDs/row keys can safely exist under different agreements/tenants without collision.

## NEXT
1. Verify RoyaltyRecover Quality run for current source head.
2. Repair any failing CI before feature work.
3. Change sales-record uniqueness from global `(source_dataset_id, source_row_key)` to agreement-scoped identity and add regression coverage for same external dataset/row identifiers across tenants.
4. Add explicit migration handling for existing SQLite files rather than silently assuming CREATE TABLE updates constraints.
5. Continue document/evidence ingestion and clause extraction boundary.
6. Continue false-positive/adversarial case coverage.
7. Update operator workflow for import -> review -> reconciliation -> dossier.
8. Continue commercial differentiation and partner economics in parallel.

## WAIT
- Real customer contracts/statements and real recovery proof.
- Jurisdiction-specific qualified legal/accounting review where required.
- Irreversible customer/production actions.

## BLOCKERS
No blocker to continued safe technical/research work. External dependencies do not stop independent execution.

## OWNER_ONLY_DEPENDENCIES
Real contracting, signatures, customer authorization, production credentials, regulated/professional representation and irreversible external actions when reached.

## CASE_TRUTH
Synthetic and repository-backed cases exist. No real customer case has yet produced verified recovered money. Synthetic evidence is implementation proof only.

## CONTRACT_TRUTH
Contract/rule data must remain source-linked and reviewed. No audit right, rate, deduction permission, product scope, territory, FX rate, deadline consequence or recoverability may be inferred from market norms.

## PRODUCT_TRUTH
Functional isolated prototype with persistence, authz, import, review, outcomes and operator UI. Not yet CASE_READY for arbitrary real royalty contracts and not PILOT_READY for unattended production use.

## CUSTOMER_TRUTH
Real customers: 0 verified in this Factory. Real paid pilots: 0 verified. Real recoveries: 0 verified.

## BUSINESS_TRUTH
Problem/materiality validated; differentiation remains provisional. TTO/technology licensing remains a candidate beachhead, not market validation.

## REVENUE_TRUTH
Verified RoyaltyRecover revenue: 0.

## EVIDENCE
Persisted forensic validation, competitor teardown, wedge decision, legal/professional boundary, ICP evidence, commercial offer, procurement evidence and deterministic synthetic tests.

## DECISIONS
- Zero false recovery is P0.
- Bilateral truth and UNKNOWN/NEEDS_REVIEW states are mandatory.
- No formal audit/legal claim representation by software alone.
- No auto-merge.
- No status promotion from synthetic evidence.

## TEST_STATE
Prior source runs were green before normalized import composition. Run #99 at `09f96c...` failed in the RoyaltyRecover tests step. Current repair head `82bf8a...` has CI running at baton capture; not yet verified green.

## CI_STATE
IN_PROGRESS for `82bf8a171cee480a88718c17e3b9b7a4e97fb578` at capture.

## REGRESSIONS
Known regression under repair: duplicate normalized-import conflict was converted to HTTP 400 because `ConflictError` is a `ValueError`; code repaired, CI pending.

## SECURITY_STATE
Tenant-scoped repository/authz present. Current schema still has a material hardening gap: sales row uniqueness is global by external dataset/row key rather than agreement-scoped. This can cause cross-tenant denial/collision and must be repaired before CASE_READY.

## MODIFIED_FILES
- `factories/royaltyrecover/import_api.py`
- `factories/royaltyrecover/BATON.md`

## UNRESOLVED_ASSUMPTIONS
- Real contract extraction coverage.
- Real customer data completeness.
- Beachhead procurement speed and WTP.
- Partner economics.
- Success-fee legality/practicality by jurisdiction.
- Production storage/auth/deployment operating model.

## NEXT_TESTS
- Current-head RoyaltyRecover Quality.
- Cross-tenant same dataset-id/same row-key acceptance after uniqueness repair.
- Same-agreement duplicate rejection remains 409.
- Migration test for existing pre-fix SQLite schema.

## RESUME_AT
Verify current-head CI. If green, implement agreement-scoped sales-record uniqueness plus migration/regression tests. If red, inspect failing step and repair before continuing.

## COMPLETION_GATES
CONTRACT, REPORTING, CALCULATIONS, RECONCILIATION, EVIDENCE, FALSE_POSITIVE_CONTROL, DOSSIER, PRODUCT, SECURITY, BILLING, SUPPORT, OPERATIONS, PILOT, CUSTOMER_VALUE, COMMERCIAL, RETENTION, ECONOMICS, QUALITY. PROJECT COMPLETE only when applicable gates are actually satisfied with real evidence where required.
