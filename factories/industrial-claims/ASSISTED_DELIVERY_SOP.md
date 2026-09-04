# CAUSLEDGER — ASSISTED DELIVERY SOP

## Objective
Complete a safe customer case before full automation exists. Manual steps are allowed when bounded, recorded and independently reviewable.

## Stage 0 — Qualification
Accept a case for rapid scan only when there is a plausible customer-caused commercial event and at least one identifiable contract/PO/change source plus a cost source. If there is only an unsupported cost complaint, do not create a recovery expectation.

## Stage 1 — Secure intake
Request only the minimum document sample needed for the first pass:
- contract/PO/commercial terms relevant to the event;
- customer change/order/release/cancellation/correspondence;
- cost ledger/invoice/time/tooling/freight evidence;
- prior credit/payment/settlement evidence;
- notice/deadline correspondence if available.

Before real customer data is accepted into any runtime, the target environment must have verified tenant binding, authorization and approved data handling. Until then, use a controlled authorized channel outside the unprovisioned product runtime and record only permitted metadata/hashes in the product.

## Stage 2 — Rapid scan
Human analyst answers:
1. What changed?
2. Who caused/directed it?
3. What commercial document could make the customer responsible?
4. What incremental cost is evidenced?
5. What has already been recovered/credited/mitigated?
6. Is notice/deadline known?
7. What evidence would falsify the candidate?

Output: NO CLAIM / NEEDS DOCUMENTS / CANDIDATE FOR FORENSIC AUDIT.

## Stage 3 — Forensic reconstruction
Build an evidence-indexed case in CausLedger. Preserve UNKNOWN states. Reconcile gross cost to mitigation and prior recovery. Never use a success-oriented estimate unsupported by sources.

## Stage 4 — Human causation/responsibility review
A human reviewer explicitly tests:
- direct customer causation vs supplier/internal causes;
- contractual/documentary responsibility basis;
- prerequisites, caps, exclusions and notice;
- duplicate/prior recovery;
- calculation support;
- contrary evidence.

The creator cannot self-approve the same finding.

## Stage 5 — Dossier production
Produce the audit-grade dossier defined in `DOSSIER_STANDARD.md`. The dossier must expose evidence gaps and attack paths, not hide them.

## Stage 6 — Customer review / external action
No external claim is sent automatically. The customer reviews the dossier and decides whether to negotiate, notify, claim, seek legal review or close. External action requires explicit authority and an approved channel.

## Stage 7 — Outcome tracking
Record only a documented final cumulative outcome with settlement/payment/credit/closure evidence. Do not treat an installment as a final outcome. Do not record recovered value above reviewed net potential.

## Stage 8 — Commercial close
Record:
- audit fee invoiced/paid;
- success fee if contractually agreed and triggered by documented recovery;
- delivery hours;
- external specialist cost;
- customer acquisition cost where measurable;
- gross margin on the case.

No revenue or recovery is counted without evidence.

## Stage 9 — Learning / automation
For every manual step, log:
- frequency;
- minutes/hours;
- error risk;
- evidence sensitivity;
- whether deterministic automation is possible;
- whether human judgment must remain.

Automation priority = repeated + costly + safe to automate + commercially material.

## Service-level operating targets for early assisted delivery
These are operating targets, not promises:
- acknowledge qualified document receipt within 1 business day;
- rapid-scan disposition within 2 business days after a complete sample;
- dossier plan/missing-evidence list immediately after scan;
- forensic dossier target within 5 business days for a bounded single-case sample once required evidence is available;
- material correction creates a new revision and fresh independent review.

## Incident handling
Stop external use of a case immediately if tenant identity, evidence lineage, calculation, revision currentness or raw-document handling is suspect. Preserve evidence, isolate the case, repair or recreate the affected revision, and disclose material impact before resuming external action.
