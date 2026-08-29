# GuaranteeRelease — Evidence Retention & Lineage Policy

Date: 2026-08-29
Status: CONTROLLED PILOT POLICY

## Principle

The application may classify only what can be tied to retained, reviewable evidence. A database row, operator statement, expiry date, project milestone or `sourceRef` is not self-verifying evidence.

## v5 lineage retained per evidence object

- evidence id and type;
- `sourceRef` and observed-at timestamp;
- project id and contract id;
- typed payload;
- review status;
- submission timestamp, role and `principalId`;
- review timestamp, role, `principalId` and review note.

Audit events preserve acting principal and state transition.

## Source retention

`sourceRef` is only a locator. The underlying source must remain available to reviewer/customer for the pilot decision and audit period. Prefer immutable or version-preserving customer repositories. If a source can be silently overwritten and no durable version can be recovered, it must not be promoted to durable verified truth.

The v5 prototype does **not** ingest source document bytes or cryptographically hash the external document content. This remains an explicit production-hardening requirement, not a hidden capability.

## Supersession

Never overwrite an approved evidence object to represent a newer document. Retain the old object/audit history, submit the newer source as a new object, review independently, and fail closed whenever governing-source identity is unresolved.

## Baseline lineage

`INSTRUMENT_TERMS` is the reviewed baseline for instrument type, currency, original amount, current amount and expiry when present. Any record change that no longer matches the latest approved baseline invalidates baseline verification and returns assessment to `UNKNOWN` until a fresh matching baseline is approved.

## Outcome separation

Retain distinct evidence for contractual release condition, release event, bank cancellation, surety cancellation and collateral release. Never infer one from another. Bank cancellation alone is not evidence that cash collateral, bank limit or bonding capacity was restored.

## Retention/deletion duration

No fixed statutory or customer retention duration is asserted. Duration depends on customer contract, jurisdiction, accounting/audit requirements, dispute exposure and agreed data-processing terms. During a controlled pilot, do not silently delete approved evidence or its audit history.

A production retention/deletion schedule must be agreed before real production use and must satisfy legal/customer deletion duties without falsifying historical audit events.

## Portfolio boundary

Evidence/customer data is not automatically transferred to ObraSignal or sister Factories. Referral is not data-sharing authorization. Any transfer requires explicit authorization and its own tenant/security boundary.

## Production hardening still required

Before claiming production-grade evidence lineage, add or verify immutable/versioned document storage or connector semantics; source-content digest where possible; explicit supersession/current-governing-document model; encryption-at-rest/key controls for real documents; customer/jurisdiction retention rules; and restore drills that include source availability, not only JSON metadata.
