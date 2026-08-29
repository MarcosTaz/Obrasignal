# Portfolio Maturity & Promotion Truth Audit v0.2

Status: INDEPENDENT_GOVERNANCE_AUDIT / NON_RUNTIME / EVIDENCE_INTEGRITY_OVERRIDE_ACTIVE / NO_MERGE_AUTHORIZATION

## Scope

Audit Factory Cloud PR #760 planning/maturity metadata, scheduling priority and portfolio-to-application promotion so planning state cannot silently become repository, runtime, customer or business authority.

Observed owner:
- PR #760
- branch `factory-cloud/shared-platform-portfolio-architecture`
- observed exact HEAD `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`
- exact-head Quality `33265278871`: SUCCESS

Related Control Tower owner:
- PR #722
- branch `factory-cloud/global-control-tower-routing`
- observed HEAD `cfaca761dfb816ac36ac98627671e9e6502b3090`

## 1. Planning metadata remains non-authoritative — PASS

Factory Cloud portfolio metadata explicitly denies repository-write, production-write, cross-app-data and merge authority. Maturity is planning classification, not company completion.

Disposition: `PASS_PLANNING_ONLY`.

## 2. Switchboard registration != application source registration — PASS

A Factory can exist in `factories.json`/portfolio without being a source-registered application. `promotion_queue.py` independently checks `apps.json`; missing application source becomes:

`PROMOTION_BLOCKED / canonical_application_source_truth_required`.

Product Market Access / Legal Product Checker therefore remains a research/business Factory visible to the portfolio but not an application with canonical source/runtime authority.

Disposition: `PASS_FAIL_CLOSED_APPLICATION_PROMOTION`.

## 3. Priority does not grant execution capability — PASS

`portfolio_priority.py` orders eligible work:

`safety > pilot blocker > evidence integrity > commercial leverage > shared leverage > base priority`.

It does not grant adapters, source authority, repository mutation or runtime provisioning.

Invariant:

`PRIORITY SELECTS WHAT TO ATTEMPT; IT DOES NOT CREATE AUTHORITY.`

## 4. G3 semantic contract — amended by evidence-integrity red team

Factory Cloud names G3 `pilot_capable` and `PilotReadinessEvidence.ready` checks source registration, exact SHA, technical test categories, assisted API, pricing/exit-criteria presence and runtime provisioning.

The previous audit accepted that as a credible engineering readiness contract for beginning an assisted pilot while explicitly distinguishing it from pilot validation.

A later source audit proved an additional material gap for Aviation and ContractCredit:
- canonical `/analyze` paths do not accept the actual contract/clause/remedy evidence required to prove entitlement;
- evidence content is synthesized internally from references/economic inputs;
- entitlement basis is marked `SUPPORTED` from hardcoded rule refs;
- current outcome path can create `RECOVERED` from a symbolic evidence reference and unconstrained caller-supplied amount/currency after approval/action;
- the shared path does not prove full review/action/resolve audit lineage.

Therefore the G3 readiness function is **not sufficient by itself** for a real-customer `PILOT_CAPABLE` claim for these two verticals.

Current independent interpretation:

`PilotReadinessEvidence.ready == TECHNICAL/ENGINEERING ASSISTED READINESS ONLY`.

For Aviation and ContractCredit, real-customer pilot capability additionally requires:
1. evidence intake sufficient to support executed contract/remedy basis;
2. missing/reference-only evidence fails closed;
3. reviewed entitlement/applicability truth remains vertical-owned;
4. reviewed economic amount + currency lineage;
5. verified outcome evidence before `RECOVERED`;
6. actor-aware transition audit;
7. exact-head adversarial tests proving these controls.

Until those exist:

`ENGINEERING_ASSISTED / SYNTHETIC_FLOW_GREEN`
+
`REAL_CUSTOMER_PILOT_CAPABILITY BLOCKED`.

This is stricter than the earlier wording and is authoritative for the Side Factory audit.

Critical evidence/repair contract:
`RECOVERY_ENTITLEMENT_OUTCOME_INTEGRITY_AUDIT_V01.md`
and PR #760 comment `5464535076`.

## 5. G3 still does not mean validated business outcome

Even after the above evidence-integrity repair, G3 can mean only **capable of safely beginning an assisted real pilot**.

Current Aviation and ContractCredit pilot contracts still mark pricing `HYPOTHESIS` and require real-case exit evidence including:
- real contract/evidence loaded with permission;
- human review;
- outcome/no-recovery record;
- delivery cost measured;
- pricing validated or revised.

Therefore G3 never means:
- `PILOT_VALIDATED`;
- `MARKET_VALIDATED`;
- `FIRST_PAID_OUTCOME`;
- `COMMERCIAL_READY`;
- `PRICING_VALIDATED`.

Existing non-escalation comment: PR #760 `5464503964`.

## 6. Canonical global command D — PASS with composition constraint

Factory Cloud `factories.json` on the shared-platform branch already records `factory-cloud.signal = D`; `factory_switchboard.py` derives the signal from that registry.

The legacy static UI inherited by PR #760 still contains historical `Ω`/clipboard behavior, but PR #760 does not own that file.

Control Tower PR #722 owns the newer UI/router and already provides:
- `D = Factory Cloud / orquestração global`;
- API `/v1/dispatch` for `LIGAR TODAS`;
- deterministic internal routes rather than manual chat URLs;
- API execution-state rendering.

Composition invariant:

`DO NOT INTEGRATE #760 IN A WAY THAT REGRESSES #722 TO Ω OR CLIPBOARD-ONLY LIGAR TODAS.`

## 7. Capability maturity != Factory maturity — PASS with two material exceptions

Separate state machines remain structurally correct.

Known independent exceptions:

### Source verification

`source_truth_verification=SHARED_VERIFIED` is too strong for the real persistent worker path until live remote-head verification is mandatory before execution.

Safe independent state:
`VERIFIER_LIBRARY_PROVEN / RUNTIME_INTEGRATION_PARTIAL`.

### Audit/recovery lifecycle

`audit_decision_lineage=SHARED_CORE` is safe only if interpreted as the reusable audit-event primitive/storage contract. It is too strong if interpreted as complete review -> action -> recovered-outcome audit on current Aviation/ContractCredit canonical paths.

Safe independent state:
`AUDIT_PRIMITIVE_PROVEN / FULL RECOVERY LIFECYCLE AUDIT PARTIAL`.

## 8. Portfolio/UI must preserve layer-qualified truth

Any internal or future customer-facing surface must not flatten:
- exact duplicate fingerprints into broad semantic overlap protection;
- fee calculation lineage into contractual fee entitlement;
- entitlement-basis representation into entitlement determination;
- technical G3 readiness into real-customer pilot capability;
- `RECOVERED` into verified recovery when outcome evidence/reconciliation is incomplete;
- planning `registered` into application source authority;
- priority into execution capability.

The examined Switchboard does not currently expose those assurance capability names as customer claims, so no separate UI mutation is required from this Side Factory.

## ACTIVE / NEXT / WAIT

ACTIVE: enforce evidence-integrity override on Aviation/ContractCredit maturity while tracking owner repair; keep planning, source registration, runtime readiness, real-pilot capability and pilot validation as distinct states.

NEXT: re-audit PR #760 after owner changes; only restore real-customer pilot-capable classification from exact-head evidence that satisfies the entitlement/outcome repair contract and runtime gates.

WAIT: no maturity/priority/planning state grants merge, deploy, production write, cross-app data, billing/provider authority, real-customer pilot capability or pilot validation by itself.
