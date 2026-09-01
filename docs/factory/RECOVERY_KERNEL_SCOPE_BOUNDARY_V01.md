# Recovery Assurance Kernel Scope Boundary v0.1

Status: INDEPENDENT_SCOPE_AUDIT / NON_RUNTIME / NO_MERGE_AUTHORIZATION

## Purpose

Prevent a valid shared recovery/economic-assurance primitive from being over-promoted into a broader semantic authority than its source proves.

Observed owner implementation:
- Factory Cloud PR #760
- branch `factory-cloud/shared-platform-portfolio-architecture`
- observed exact HEAD `02fdfc5422acd9b20b4f05ec511ef7f1cba1bf3a`
- exact-head Quality `33265278871`: SUCCESS

Additional current consumer evidence:
- Industrial Claims PR #785
- branch `apps/industrial-claims`
- observed exact HEAD `449e3e846d1ad7096b7cf6790ecc119299a35023`
- exact-head Quality `33270696084`: SUCCESS

## Boundary rule

A shared primitive may standardize **how evidence-backed recovery facts are represented and traced**.

It must not silently become the authority for:
- whether a contractual right exists;
- whether a legal/regulatory rule applies;
- whether two economically different claims overlap;
- whether a success fee is contractually billable;
- whether a deadline is legally tolled or extended;
- whether a recovery result is customer-realized cash without outcome evidence.

Those decisions remain in vertical/customer/legal source authority.

## Capability scope classifications

### `document_ingestion_contract`

Proven source:
- `EvidenceEnvelope` accepts evidence content/reference metadata and produces a deterministic content hash;
- shared persistence stores the evidence envelope/lineage;
- raw document acquisition and product intake policy are not centralized.

Industrial Claims proves the separation:
- it imposes its own maximum evidence size;
- missing/blank content becomes `REFERENCE_ONLY`;
- hashed content carries `raw_content_persisted=false` metadata;
- its own evidence sufficiency policy decides whether entitlement can become review-ready.

Independent disposition:

`SHARED_CORE_EVIDENCE_INGESTION_ENVELOPE`
+
`DOCUMENT_PIPELINE/POLICY AUTHORITY = CONSUMER OWNED`.

Do not infer malware scanning, OCR, document parsing, jurisdiction validation, customer authorization, retention policy or raw-document storage from the shared envelope contract.

### `obligation_entitlement_representation`

`EntitlementBasis` requires:
- entitlement id;
- tenant;
- domain;
- source evidence ids;
- rule reference;
- confidence in `{SUPPORTED, PARTIAL, UNRESOLVED}`;
- deterministic basis hash.

Only `SUPPORTED` returns `actionable=True`.

This is a useful evidence/rule/confidence **representation contract**. It does not evaluate the rule itself.

Aviation, ContractCredit and current Industrial Claims source supply their own domain/rule refs and their own evidence completeness/applicability logic.

Independent disposition:

`SHARED_VERIFIED_ENTITLEMENT_BASIS_REPRESENTATION`
+
`ENTITLEMENT DETERMINATION = VERTICAL OWNED`.

Safe:
`vertical evidence/rules -> EntitlementBasis`.

Unsafe:
`EntitlementBasis.actionable == universal proof that money is owed`.

### `duplicate_overlap_detection`

Current source creates a deterministic `RecoveryFingerprint` from:
- tenant id;
- vertical;
- contract ref;
- event ref;
- remedy type.

`duplicate_fingerprints()` counts repeated identical `(tenant_id, fingerprint)` pairs.
`RecoveryIndex` enforces tenant-scoped uniqueness for the same fingerprint.

This proves **exact duplicate detection**.

It does not prove semantic/economic overlap detection between different fingerprints. Examples not solved by exact fingerprint identity include:
- one cost appearing under two different remedy types;
- two contractual rights sharing the same economic loss base;
- different event ids referring to the same underlying event;
- one settlement satisfying multiple candidate entitlements;
- partial overlap between claim periods or invoice sets;
- cross-vertical double counting where fingerprints intentionally differ.

Factory Cloud's own capability inventory says a configurable overlap policy is still future proof before SHARED_CORE.

Independent disposition:

`SHARED_VERIFIED_EXACT_DUPLICATE_DETECTION`
/
`SEMANTIC_OVERLAP_DETECTION NOT PROVEN`.

No UI/report/release state should claim broad overlap protection from exact fingerprint uniqueness alone.

### `outcome_fee_lineage`

`AssuranceOperations.resolve()` creates an evidence-referenced recovery outcome only after an ACTIONED finding.
`record_fee()` requires a tenant-scoped `RECOVERED` outcome.
`FeeLineage` deterministically records:
- outcome id;
- recovered amount;
- fee rate;
- calculated fee amount;
- currency;
- lineage hash.

The mathematical lineage is valid and tests prove two verticals.

The kernel does not independently prove:
- the customer's signed fee agreement;
- the applicable fee tier;
- exclusions/caps/minimums;
- taxes;
- fee base definition;
- fee waiver/amendment;
- whether the specific recovered amount is in-scope for success fee under the customer agreement.

Independent disposition:

`SHARED_VERIFIED_FEE_CALCULATION_LINEAGE`
+
`FEE CONTRACTUAL ENTITLEMENT = CUSTOMER/VERTICAL OWNED`.

A reproducible fee calculation is not by itself an invoice right.

### `finding_review_workflow`

The shared finding states include `RECOVERED` and `CLOSED_NO_RECOVERY`.

That vocabulary is deliberately recovery/economic-assurance specific. It is appropriate for recovery verticals, but must not be reinterpreted as a universal workflow state machine for ObraSignal procurement, K3 prediction/calibration or Product Checker regulatory eligibility.

Independent disposition:

`SHARED_CORE_WITHIN_RECOVERY_ASSURANCE_FAMILY`
/
`NOT_GLOBAL_PRODUCT_WORKFLOW`.

### `deadline_notice_window`

The kernel proves evidence-linked date tracking and deterministic OPEN/DUE_TODAY/EXPIRED state relative to a supplied date.

It does not determine jurisdiction-specific legal computation, tolling, receipt methods, business-day calendars or contractual extensions unless the vertical explicitly supplies/validates them.

Independent disposition:

`SHARED_CORE_RECOVERY_NOTICE_RECORD`
/
`LEGAL DEADLINE AUTHORITY = VERTICAL OWNED`.

## Third-consumer proof from Industrial Claims

Industrial Claims current source uses the common kernel without collapsing its domain rules into it:
- `EvidenceEnvelope` for evidence lineage;
- `EntitlementBasis` with Industrial-owned `documented-commercial-basis-v2` rule ref;
- `RecoveryFingerprint` with Industrial claim family as remedy type;
- `CalculationRecord` with `industrial_net_potential_claim` formula;
- `DeadlineWindow` with Industrial deadline-evidence policy;
- `FindingRecord` with `industrial_recovery_candidate` type;
- shared tenant/audit/notification primitives;
- Industrial-specific reviewer independence, recovery cap, currency and verified-outcome controls remain in the vertical.

This is strong evidence that the safe architecture is:

`SHARED TRACEABILITY PRIMITIVES + VERTICAL ECONOMIC/CONTRACTUAL AUTHORITY`.

## Promotion-label rule

Every capability label should describe the strongest thing the source actually proves.

Preferred precise labels:
- `evidence_ingestion_envelope` rather than implying a full document pipeline;
- `entitlement_basis_representation` rather than entitlement determination;
- `exact_duplicate_fingerprint_detection` until overlap policy exists;
- `fee_calculation_lineage` rather than fee entitlement;
- `recovery_finding_workflow` rather than universal finding workflow.

This document does not require immediate renaming if compatibility depends on existing ids. It requires that product/UI/release claims preserve the narrower meaning until source and tests prove more.

## Owner routing

These scope findings were routed to Factory Cloud PR #760 in comment `5464470623`.

The most material implementation defect remains the separate live remote source-head revalidation gap tracked in comment `5464440957`.

## ACTIVE / NEXT / WAIT

ACTIVE: prevent capability-name inflation and re-audit owner changes at exact head.

NEXT: verify that UI/portfolio maturity output does not translate `SHARED_VERIFIED` exact-duplicate or fee-calculation primitives into broader customer claims; continue exact source/runtime reconciliation.

WAIT: no central legal authority, fee entitlement engine, shared customer data, auth/billing provider authority, merge or deploy is authorized by this scope audit.
