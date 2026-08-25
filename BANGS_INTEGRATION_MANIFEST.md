# BANGS ENGINE v0 — Integration Manifest

MODULE: BANGS ENGINE v0

BRANCH: `bangs-field-intelligence-v0`

PR: pending at manifest creation; PR description must reference this manifest and must not merge automatically.

OWNED FILES:
- `bangs/__init__.py`
- `bangs/money.py`
- `bangs/units.py`
- `bangs/evidence.py`
- `bangs/contracts.py`
- `bangs/costs.py`
- `bangs/materials.py`
- `bangs/tenant.py`
- `bangs/providers/__init__.py`
- `bangs/providers/base.py`
- `bangs/providers/manual.py`
- `bangs/landed_cost.py`
- `bangs/equipment.py`
- `bangs/routes.py`
- `bangs/accommodation.py`
- `bangs/field_expenses.py`
- `bangs/mobilization.py`
- `bangs/financial.py`
- `bangs/true_cost.py`
- `bangs/scenarios.py`
- `bangs/comparator.py`
- `bangs/presentation.py`
- `tests/bangs/*`
- `BANGS_ENGINE.md`
- `BANGS_INTEGRATION_MANIFEST.md`

CANONICAL FILES TOUCHED:
- `capability_registry.py` — minimal additive registration only.

CANONICAL FILES NOT TOUCHED:
- `master_execution_queue.py`
- `cors_app.py`
- `source_registry.py`
- `preload.py`
- existing auth/runtime/database composition.

PUBLIC CONTRACTS:
- Money / safe compatible units (BANGS-owned, not promoted as global utilities)
- `MaterialRequirement`
- `MaterialPriceObservation`
- `SupplierCandidate`
- `CostAssessment`
- `LandedCostAssessment`
- `EquipmentAssessment`
- `RouteCostAssessment`
- `AccommodationAssessment`
- `MobilizationAssessment`
- `FinancialExposureAssessment`
- `TrueJobCostAssessment`
- `ComparisonResult`
- `ExecutiveBangResult`

PROVIDERS:
- provider-neutral contracts for material price, supplier, equipment, route, fuel, toll and accommodation discovery;
- `ManualObservationProvider` implemented for offline/manual structured observations;
- no live commercial provider claimed.

PRIVATE STATE:
- tenant-private quotes/company observations are explicitly scoped;
- BANGS-owned observation store rejects cross-tenant access and non-idempotent identity collisions;
- no private state is copied into Opportunity.

MIGRATIONS: NONE.

FEATURE FLAGS:
- `bangs_field_intelligence_v0` registered for experimental rollout; no runtime wiring is introduced by this branch.

DEPENDENCIES:
- Python standard library/domain contracts only for core calculation.
- Existing `capability_registry.py` only for lifecycle registration.

OPTIONAL DEPENDENCIES:
- future canonical Bid Economics through `FinancialExposureProvider`;
- future canonical provider implementations for supplier/material/equipment/route/fuel/toll/accommodation observations;
- future Company State/Requirements/MOBILIZE adapters.

UNMERGED BRANCH ASSUMPTIONS: NONE. No private implementation was copied from Bid Economics, MOBILIZE, Supply Edge, Crew Economics or other parallel branches.

CONFLICT RISKS:
- `capability_registry.py` is canonical and may receive concurrent additive entries. Integration resolution: retain all independent entries and the BANGS `EXPERIMENT` record; rerun registry validation/cycle tests.
- Future canonical Money/Unit contracts may supersede BANGS-owned contracts. Integration resolution: add adapter/migrate deliberately; do not silently alias incompatible semantics.
- Future Bid Economics/MOBILIZE public contracts may overlap composition responsibilities. Integration resolution: BANGS keeps field-cost inputs and delegates canonical margin/working-capital/mobilization policy rather than duplicating it.

MERGE ORDER:
1. Rebase/merge current `main` into this branch only if required by integration policy.
2. Resolve additive registry conflicts without dropping parallel capability entries.
3. Run exact-head repository quality workflow.
4. Merge BANGS only after review; no automatic merge.
5. Integrate API/persistence/providers in a later controlled operation.

TEST STATUS:
- Local isolated BANGS suite: 70/70 passed on the implementation/test tree before documentation/registry commits.
- Python package/tests compiled locally on that tree.
- Full repository/exact-head GitHub CI: must be reported from the PR head; local success is not a substitute.

LIVE VALIDATION:
- Core: deterministic manual/fixture provider path validated through tests.
- DGEG public fuel-price source investigated but deliberately not integrated due discovered reuse restriction for commercial use.
- European Commission Weekly Oil Bulletin identified as future candidate only; no live provider/parser claimed.

PRODUCTION STATUS: NOT PRODUCTION. Capability state is `EXPERIMENT`; no API/runtime is activated.

ROLLBACK:
- Before merge: close PR/delete branch; main is unchanged.
- After an eventual merge: revert the BANGS commits, including the additive registry entry. There are no migrations, external side effects, background workers or persisted BANGS schema to unwind.
- Feature flag/kill-switch semantics provide an additional rollout boundary once runtime integration exists.

SAFE INTEGRATION NOTES:
- Never derive tenant from API payload; use verified auth/account context.
- Do not persist private observations in shared/public storage.
- Do not add live fetches to calculation paths.
- HTTP providers must enforce allow-list, DNS/private-address checks, redirect revalidation, timeout and bounded results.
- Do not sum currencies without explicit FX evidence/provider.
- Do not promote observed list prices to quotes or observed accommodation rates to confirmed availability.
- Do not call known subtotal a total when material unknowns remain.
- Do not modify Master Queue/CURRENT_ITEM_ID as part of BANGS integration.
