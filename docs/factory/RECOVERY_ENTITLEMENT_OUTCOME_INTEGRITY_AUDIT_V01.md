# Recovery Entitlement & Outcome Integrity Audit v0.1

Status: CRITICAL_INDEPENDENT_SAFETY_AUDIT / NON_RUNTIME / OWNER_REPAIR_REQUIRED / NO_MERGE_AUTHORIZATION

## Executive finding

Current canonical Aviation Lease Entitlement Recovery and ContractCredit application branches can produce a `SUPPORTED` entitlement / `READY_FOR_REVIEW` finding without receiving the real contractual clause/remedy evidence, and can later mark a finding `RECOVERED` from a symbolic evidence reference plus a caller-supplied amount.

This violates the intended evidence-first boundaries and is a material blocker to treating those paths as real-customer pilot-capable.

Classification:

`ZERO-INVENTED-ENTITLEMENT GAP`
+
`ZERO-FALSE-RECOVERY GAP`
+
`FULL OUTCOME AUDIT LINEAGE NOT PROVEN`.

The implementation remains useful as synthetic/engineering scaffolding. It must not be promoted into evidence-complete customer truth until repaired.

## Canonical source evidence

### Aviation

- repository: `MarcosTaz/Obrasignal`
- canonical branch: `apps/aviation-lease-entitlement-recovery`
- exact observed HEAD: `0d1759832a06b3177b67b35a4c53ee0c69db459e`
- Factory Cloud registry records the same exact head and prior GREEN Quality evidence.

### ContractCredit

- repository: `MarcosTaz/Obrasignal`
- canonical branch: `apps/contractcredit`
- exact observed HEAD: `0d1759832a06b3177b67b35a4c53ee0c69db459e`
- Factory Cloud registry records the same exact head and prior GREEN Quality evidence.

No separate open PR was found with either canonical app branch as head. The executable shared/platform owner is therefore Factory Cloud PR #760.

## Finding A — contractual entitlement evidence is synthesized from references

Factory Cloud `vertical_consumers.py` currently constructs evidence content internally rather than receiving documentary source content.

### Aviation

The consumer creates:
- lease contract evidence from `lease:{contract_ref}`;
- maintenance event evidence from `maintenance:{event_ref}:{eligible_cost}`;
- entitlement basis with hardcoded `rule_ref = lease-maintenance-reserve-term`;
- confidence `SUPPORTED`.

The calculation then produces unreimbursed balance from caller-provided eligible cost and reimbursed amount. A positive amount can make the finding `READY_FOR_REVIEW`.

This is not evidence that:
- the executed lease contains the claimed maintenance-reserve reimbursement right;
- the clause applies to the event;
- the eligible cost definition is satisfied;
- notice/claim conditions are satisfied;
- the reimbursable maximum is the supplied arithmetic balance.

### ContractCredit

The consumer creates:
- service-contract evidence from `service-contract:{contract_ref}`;
- incident evidence from `incident:{incident_ref}:{monthly_fee}:{credit_rate}`;
- entitlement basis with hardcoded `rule_ref = service-level-credit-term`;
- confidence `SUPPORTED`.

The supplied monthly fee and credit rate then determine a potential credit. A positive amount can make the finding `READY_FOR_REVIEW`.

This is not evidence that:
- the executed contract contains that SLA/remedy;
- the incident breached the relevant service level;
- exclusions/cure/measurement rules do not apply;
- the supplied rate is the contractual rate;
- notice conditions are satisfied.

## Finding B — canonical web intake cannot provide the missing proof

Current canonical `/analyze` surfaces accept only references/economic parameters.

Aviation accepts:
- `contract_ref`;
- `event_ref`;
- `eligible_cost`;
- `reimbursed_amount`;
- `notice_due`.

ContractCredit accepts:
- `contract_ref`;
- `incident_ref`;
- `monthly_fee`;
- `credit_rate`;
- `notice_due`.

Neither current path accepts documentary contract/clause content or independently verified contractual rule evidence.

Therefore the missing evidence is not merely a test omission; the current application contract has no route to supply it.

## Finding C — generic RECOVERED outcome is under-evidenced

The shared `AssuranceOperations` implementation currently used by both canonical branches:

- requires only finding state `ACTIONED`;
- accepts any decimal recovered amount that is not negative;
- accepts any non-empty currency string;
- accepts any non-empty `evidence_ref` string;
- does not require or persist verified outcome evidence content;
- does not validate that the evidence reference exists in tenant-scoped evidence storage;
- does not reconcile recovered amount to the reviewed calculation/potential;
- does not reconcile currency to the reviewed calculation currency;
- review transition is not appended to the audit stream;
- action transition has no actor and no audit event;
- resolve transition has no actor and no audit event.

A positive caller-supplied amount therefore produces `RECOVERED` even when the recovery proof and economic reconciliation are not independently established by the shared path.

## Finding D — fee lineage can inherit a weak outcome

`record_fee()` correctly requires an outcome whose state is `RECOVERED`, and `FeeLineage` correctly computes the arithmetic fee from recovered amount × rate.

However, if `RECOVERED` itself was created from a symbolic evidence reference and unconstrained caller-supplied amount, fee lineage can be mathematically reproducible while resting on an under-evidenced recovery outcome.

Therefore:

`FEE CALCULATION LINEAGE != FEE ENTITLEMENT`

and additionally:

`FEE CALCULATION LINEAGE IS ONLY AS SOUND AS THE RECOVERED OUTCOME IT REFERENCES`.

## Stronger pattern already proven in Industrial Claims

Do not create a second architecture.

Current Industrial Claims canonical source:
- branch `apps/industrial-claims`;
- exact observed HEAD `449e3e846d1ad7096b7cf6790ecc119299a35023`;
- exact-head Quality run `33270696084`: SUCCESS.

It already demonstrates the required safety direction.

### Evidence completeness

Industrial Claims accepts real commercial/event/cost evidence content.

Missing/blank content becomes `REFERENCE_ONLY` and contributes to missing-evidence state. Entitlement confidence becomes `SUPPORTED` only when required evidence is complete; otherwise it remains partial and the finding is not review-ready.

### Reviewed economic maximum

Before recording recovery, Industrial Claims reloads the persisted reviewed calculation and obtains:
- reviewed maximum amount;
- reviewed currency.

It rejects:
- recovered amount above reviewed net potential;
- recovery currency different from reviewed currency.

An amount above the reviewed maximum requires amendment and re-review rather than silently redefining the finding.

### Verified outcome evidence

Industrial Claims requires actual outcome evidence content, creates an `EvidenceEnvelope`, persists it, and only then resolves the finding.

The evidence persist and resolution can occur within one transaction.

### Transition audit

The newer `factory_cloud/assurance_ops.py` present on the Industrial Claims branch adds:
- reviewer/reason audit for review;
- optional actor-aware audit for action;
- optional actor-aware audit for resolve;
- transaction-capable resolve;
- finite-decimal validation;
- stronger one-fee-per-outcome integrity.

This code is a compatibility/reuse candidate for the canonical shared owner. Industrial-specific economic rules must remain vertical-owned.

## Required repair boundary

### Shared operations owner

Factory Cloud should reconcile the neutral improvements already proven on the Industrial branch:

1. actor-aware review/action/resolve audit events;
2. transaction-capable outcome recording;
3. finite numeric validation;
4. ability to require an existing/persisted tenant-scoped outcome evidence envelope before `RECOVERED`;
5. immutable outcome lineage;
6. no success-fee lineage before evidence-backed recovery;
7. compatibility tests for Aviation, ContractCredit and Industrial Claims.

The shared layer should not choose each vertical's economic maximum or entitlement rule.

### Aviation vertical

Require evidence sufficient to support the executed lease right and event applicability before `SUPPORTED`/`READY_FOR_REVIEW`.

At minimum:
- executed lease/clause evidence content or another explicit verified source;
- maintenance-event/cost evidence;
- rule/applicability policy owned by Aviation;
- evidence completeness state;
- reviewed recoverable amount + currency lineage;
- verified outcome evidence before `RECOVERED`.

Reference-only contract identifiers must fail closed to unresolved evidence.

### ContractCredit vertical

Require evidence sufficient to support the executed SLA/remedy and incident breach before `SUPPORTED`/`READY_FOR_REVIEW`.

At minimum:
- contract/SLA/remedy evidence;
- incident/performance evidence;
- vertical-owned applicability/exclusion logic;
- contractual credit rate derived from/verifiable against source, not trusted merely because supplied by caller;
- reviewed credit amount + currency lineage;
- verified credit/payment/outcome evidence before `RECOVERED`.

Reference-only contract identifiers or caller-supplied remedy rates must not prove contractual entitlement.

## Mandatory regression proofs

A repaired exact head should prove at least:

1. ref-only Aviation contract cannot become `READY_FOR_REVIEW`;
2. ref-only ContractCredit MSA/SLA cannot become `READY_FOR_REVIEW`;
3. missing clause/remedy evidence cannot create `SUPPORTED` entitlement;
4. arbitrary caller-supplied contractual rate does not prove ContractCredit remedy;
5. recovered amount above reviewed maximum fails closed;
6. recovery currency mismatch fails closed;
7. symbolic outcome `evidence_ref` without verified/persisted content cannot create `RECOVERED`;
8. review/action/resolve transitions create actor-aware immutable audit lineage;
9. fee cannot be created from a non-evidence-backed outcome;
10. Industrial Claims remains GREEN and its domain-specific claim rules remain outside shared core;
11. cross-tenant composition remains rejected;
12. replay/idempotency behavior remains deterministic.

## Maturity consequence

Until this is repaired and exact-head verified:

### Aviation

Current safe classification:

`ENGINEERING_ASSISTED / SYNTHETIC_CONTRACT_FLOW_GREEN / REAL_CUSTOMER_EVIDENCE_INTEGRITY_BLOCKED`.

Do not claim real-customer `PILOT_CAPABLE` solely from the current G3 technical readiness function.

### ContractCredit

Current safe classification:

`ENGINEERING_ASSISTED / SYNTHETIC_CONTRACT_FLOW_GREEN / REAL_CUSTOMER_EVIDENCE_INTEGRITY_BLOCKED`.

Do not claim real-customer `PILOT_CAPABLE` solely from the current G3 technical readiness function.

### Shared audit lineage

`audit_decision_lineage=SHARED_CORE` is too broad if interpreted as the entire recovery lifecycle.

Current evidence supports:
- case-creation audit primitive and durable audit storage;
- deterministic audit event hashing;
- tenant isolation.

It does not support a complete review -> action -> outcome chain on the current Aviation/ContractCredit canonical shared source.

Independent disposition:

`SHARED AUDIT PRIMITIVE PROVEN / FULL RECOVERY LIFECYCLE AUDIT PARTIAL`.

## Owner routing

Critical repair contract routed to Factory Cloud PR #760 comment:
`5464535076`.

The Side Factory must track the exact owner head and re-audit the repair; it must not create a competing runtime implementation.

## ACTIVE / NEXT / WAIT

ACTIVE: treat Aviation/ContractCredit evidence integrity as a critical maturity blocker; track owner reconciliation of the stronger Industrial Claims outcome/audit pattern into Factory Cloud and re-test exact heads.

NEXT: update prior capability/maturity audits so they no longer overstate full audit lineage or real-customer pilot capability; recheck PR #760 for owner changes; verify current Side Factory exact-head CI.

WAIT: real-customer pilot-capable classification for Aviation/ContractCredit, success-fee reliance, shared source-verifier promotion, supervised runtime proof, K3 source resolution, Product Checker application source, merge, deploy, production data/secrets/auth/billing/database authority remain outside proven safe state.
