# VINDORUM — ZERO-TOUCH OPERATING SOP

## Objective
The normal VINDORUM customer journey is self-service and requires no routine operator intervention from us.

Canonical path:
`metadata triage → account → case metadata → secure evidence intake → automated extraction → evidence gaps → customer confirmation → verified payment → reconciliation → dossier → claim workspace → portfolio monitoring`

Human involvement is an **exception path**, not the default delivery model. The product must fail closed when a decision cannot be made safely without specialist judgment.

## Stage 0 — Metadata qualification
The Free Exposure Check accepts non-confidential metadata only. It may classify fit; it may not claim recoverability, entitlement or a precise amount.

## Stage 1 — Secure intake gate
Confidential evidence remains blocked unless `real_evidence_intake_enabled=true` and production authentication, tenant/case binding, secure transfer, WORM storage, trusted timestamping, retention/deletion and required privacy/security controls are genuinely configured and tested.

If the gate is not green, VINDORUM stays metadata-only.

## Stage 2 — Automated extraction
The system extracts facts into explicit propositions with source references and confidence. Unknown, conflicting or missing facts stay UNKNOWN/UNSUPPORTED.

## Stage 3 — Customer confirmation
The customer confirms or corrects extracted facts and supplies missing evidence through the approved secure channel. Confirmation is recorded with revision and actor identity.

## Stage 4 — Economic reconciliation
VINDORUM reconstructs:
`documented cost → mitigation → net documented exposure → evidence-supported → claimed → approved → settled`

Required invariant:
`net documented exposure >= evidence-supported >= claimed >= approved >= settled`

Any impossible ledger fails closed.

## Stage 5 — Dossier
The product generates the VINDORUM Recovery Dossier with evidence index, chronology, causation state, commercial basis, reconciliation, contrary evidence, deadlines, gaps and next action.

Cost is not automatically money owed. Evidence support is not legal entitlement.

## Stage 6 — Claim workspace
The customer controls external action. VINDORUM may prepare a bounded communication only when the customer explicitly authorizes it and an approved channel exists. No external claim is silently sent.

## Stage 7 — Outcome tracking
Only evidenced cumulative outcomes move `claimed → approved → settled`. Installments are not treated as final settlement unless documented as such.

## Stage 8 — Portfolio monitoring
Current, non-superseded findings with latest verified reconciliations may be aggregated. Cross-currency aggregation requires an explicit FX evidence layer.

## Exception routing
VINDORUM routes to specialist/customer review only when deterministic processing cannot safely resolve:
- contradictory or ambiguous commercial language;
- legal/regulatory interpretation;
- disputed causation that cannot be grounded in evidence;
- expired/waived notice requiring judgment;
- evidence-integrity or security incident.

An exception must never be presented as normal operator work or as evidence that VINDORUM itself established legal entitlement.

## Incident rule
Stop external use of an affected case if tenant identity, evidence lineage, calculation, revision currentness or raw-document handling is suspect. Preserve evidence, isolate the case, create a corrected revision and disclose material impact before resuming external action.
