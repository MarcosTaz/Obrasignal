# VINDORUM — RECOVERY DOSSIER STANDARD

## Purpose
The VINDORUM Recovery Dossier must let a finance, commercial or independent reviewer understand what happened, what is documented, what remains uncertain, how the economics were reconstructed and what bounded action is justified next.

The dossier is evidence-linked decision support. It does not establish legal entitlement merely because cost or documentary support exists.

## Mandatory structure

### 1. Executive case sheet
- case/finding ID and revision;
- tenant/customer/program references;
- claim family and current workflow state;
- net documented exposure and currency;
- evidence-supported / claimed / approved / settled amounts;
- confidence and unresolved evidence;
- notice/deadline state;
- bounded next action;
- explicit statement that candidate value is not automatically money owed.

### 2. Documentary index
For every source:
- source reference and type;
- content hash/provenance state;
- relevant date;
- proposition supported;
- raw-document storage state.

### 3. Commercial basis
Record only what evidence supports:
- PO/contract/change reference;
- customer instruction/event reference;
- responsibility/reimbursement language identified by the system/customer;
- limitations, exclusions, caps, prerequisites and notice requirements;
- unresolved interpretation requiring customer or independent specialist review.

### 4. Event chronology
Dated sequence:
`customer instruction/change → supplier response → incremental work/cost → notice/communication → prior recovery/credit/payment`.

### 5. Causation assessment
Separate:
- observed event;
- proposed causal link;
- supporting evidence;
- competing/supplier-controlled causes;
- state: `SUPPORTED / PARTIAL / UNRESOLVED`.

### 6. Customer-responsibility basis
Never infer responsibility from cost alone. Record source references, required conditions, contrary evidence and state:
`SUPPORTED FOR COMMERCIAL REVIEW / PARTIAL / UNRESOLVED`.

This is not a legal conclusion.

### 7. Economic reconciliation
For each economic component expose source, mitigation and prior recovery, then reconcile:
`documented cost → mitigation → net documented exposure → evidence-supported → claimed → approved → settled`.

Required invariant:
`net documented exposure >= evidence-supported >= claimed >= approved >= settled`.

Also expose:
- unsupported exposure;
- supported-unclaimed;
- claimed-unapproved;
- approved-unsettled;
- supported-unsettled.

### 8. Duplicate / prior-recovery check
State whether the same exposure is already represented by another case, credit note, payment, settlement or recovery. UNKNOWN is valid; omission is not.

### 9. Notice / deadline
Record evidence state, due date when supported, timing state (`OPEN / DUE_TODAY / EXPIRED / UNKNOWN`) and method/recipient when known. Expiry never automatically means non-recoverability.

### 10. Evidence gaps and attack list
List missing evidence, disputed assumptions, competing explanations, duplicated costs, unsupported allocations, unclear responsibility and deadline uncertainty.

### 11. Customer confirmation
Persist which extracted facts the customer confirmed, corrected or left unresolved, with actor, revision and timestamp/provenance.

### 12. Disposition
Allowed dispositions:
- `NO CLAIM / INSUFFICIENT EVIDENCE`;
- `NEEDS EVIDENCE`;
- `DOCUMENTED CANDIDATE FOR CUSTOMER/INDEPENDENT REVIEW`;
- `CUSTOMER-CONFIRMED WORKFLOW CANDIDATE`;
- `DOCUMENTED FINAL OUTCOME`.

Do not label value as recoverable, owed or overcharged unless that conclusion has been independently established under applicable authority.

### 13. Next action
Exactly one bounded next action, such as requesting a missing source, reconciling prior credits, obtaining independent interpretation, preparing a customer-authorized communication or closing for insufficient evidence.

## Automated release gate
A dossier may be released to its authorized customer workspace only when:
- tenant/case identity is correct;
- revision is current;
- evidence lineage is intact;
- raw evidence is not embedded in an unauthorized output;
- calculations reproduce;
- prior recovery is recorded;
- missing/contrary evidence is visible;
- deadline truth is visible;
- customer confirmation state is explicit;
- external-action authority remains separate.

A failed gate blocks release rather than creating an operator task on the normal path.
