# CERTACTUM — DISCOVERY & INTAKE PACK

## 20-minute discovery objective
Determine whether one historical customer/OEM-caused engineering/change/NRE case is suitable for a bounded evidence-first recovery scan. Do not sell a recovery number before evidence exists.

## Phase A — metadata-only triage (safe before confidential intake)
Until the real-document activation gate is genuinely GREEN, discovery must use only non-confidential metadata and buyer-described facts. Do not request or accept contracts, POs, ECNs, drawings, ledgers, invoices or other confidential source documents through ordinary email or an unverified runtime.

Allowed triage fields:
- supplier industry and approximate size band;
- customer/OEM type or anonymized identifier;
- program/change type;
- approximate date range;
- approximate gross-cost band;
- whether a PO/contract/change document exists: YES / NO / UNKNOWN;
- whether an engineering/NRE cost source exists: YES / NO / UNKNOWN;
- whether any claim was submitted: YES / NO / UNKNOWN;
- whether any value was approved/credited/paid: YES / NO / UNKNOWN;
- whether notice/deadline rules may exist: YES / NO / UNKNOWN;
- internal owner role;
- desired outcome from a review.

Phase A may qualify an opportunity. It may not manufacture evidence support, legal entitlement or a precise recoverable amount.

## Discovery questions
1. What customer/OEM/program created the change or disruption? An anonymized label is sufficient at triage.
2. What changed: drawing, scope, validation, timing, volume, launch requirement, tooling or another customer instruction?
3. Is the change documented and which function holds the source?
4. Which incremental costs arose only because of that change?
5. How are those costs tracked and who owns recovery internally?
6. Is there contract/PO/change-order language that may support or limit responsibility?
7. Was any amount already claimed, approved, credited, paid, reused or mitigated?
8. Could a notice/deadline rule apply?
9. What evidence or fact could weaken or defeat the recovery hypothesis?
10. What would make a scan useful even if the conclusion is NO CLAIM?

## Qualification result
Choose one:
- `NO_FIT`: no customer/event/cost chain, economics too small, or mechanism outside the Factory;
- `NEEDS_PREQUALIFICATION`: problem plausible but economic owner, evidence existence or process is unclear;
- `METADATA_QUALIFIED`: buyer confirms a bounded case and the required evidence categories appear to exist, but confidential intake is not yet authorized;
- `RAPID_SCAN_CANDIDATE`: secure documentary intake is authorized and minimum evidence can be supplied;
- `SPECIALIST_REVIEW_FIRST`: legal/regulatory/technical interpretation is the primary blocker.

## Metadata qualification score
Score only observable buyer answers. Do not infer missing evidence.

- +2 customer/OEM-driven change/event is clearly identifiable;
- +2 incremental cost source is known to exist;
- +2 commercial basis/PO/change documentation is known to exist;
- +1 prior claim/approval/payment state can be reconstructed;
- +1 notice/deadline process is known or can be checked;
- +1 named internal economic owner exists;
- +1 approximate exposure comfortably exceeds the likely audit fee.

Interpretation:
- `0–3`: weak fit / discovery only;
- `4–6`: prequalification;
- `7–10`: strong metadata-qualified opportunity.

The score is a routing aid, not a recoverability score.

## Minimum document sample for NRE/change-cost rapid scan
Request this only after secure intake is permitted:
1. relevant PO / contract / commercial terms or bounded excerpt;
2. customer ECN/change order/instruction/release/cancellation evidence;
3. engineering/NRE cost source: time ledger, invoice, subcontractor charge, validation invoice or equivalent;
4. prior credit/payment/settlement evidence or confirmation that reconciliation is pending;
5. notice/deadline correspondence if applicable.

Do not request an entire ERP export, mailbox or contract library for the first scan.

## Data-handling gate before real documents
Before receiving non-public customer documents into Certactum:
- verified production authentication is active;
- authorized sender and tenant/case are bound;
- permitted document set and purpose are recorded;
- secure transfer channel is verified;
- immutable/WORM storage provider is declared and operationally verified for the intended use;
- trusted timestamp provider is declared and operationally verified for the intended use;
- tenant/case separation is confirmed;
- credentials, secrets and unrelated personal data are excluded;
- retention/deletion handling is explicit;
- legal/NDA/DPA requirements are addressed when materially required;
- the automated readiness output has `real_evidence_intake_enabled=true`.

If any required control is false/unknown, remain in Phase A metadata-only triage.

## Preferred early transfer pattern after the gate is GREEN
1. prospect confirms willingness to share a bounded sample;
2. create a prospect-specific authorized secure channel;
3. receive only the agreed sample;
4. preserve immutable original + source/custody metadata;
5. perform controlled human review;
6. reconcile documented cost → mitigation → evidence-supported → claimed → approved → settled;
7. generate the Certactum Supplier Recovery Dossier;
8. deliver through an agreed secure channel;
9. do not reuse data for another prospect/case.

## Rapid scan checklist
- [ ] customer/program/event identified
- [ ] contract/PO/change source identified
- [ ] event chronology plausible
- [ ] causation tested against supplier/internal causes
- [ ] customer responsibility basis located or marked unresolved
- [ ] documented cost source reconciled
- [ ] mitigation checked
- [ ] evidence-supported amount explicitly distinguished from unsupported exposure
- [ ] claimed amount reconciled
- [ ] approved amount reconciled
- [ ] settled/credited/paid amount reconciled
- [ ] currency explicit
- [ ] notice/deadline known or marked unknown
- [ ] contrary evidence recorded
- [ ] duplicate exposure checked
- [ ] next missing document named
- [ ] disposition chosen without inflation

## Rapid scan output
One page maximum for the first commercial decision:
- case hypothesis;
- evidence present;
- evidence missing;
- net documented exposure;
- evidence-supported amount only when actually supported;
- supported-unclaimed / claimed-unapproved / approved-unsettled split;
- causation/responsibility state;
- notice/deadline risk;
- disposition: NO CLAIM / NEEDS REVIEW / FORENSIC AUDIT CANDIDATE;
- fixed-scope proposal if deeper work is justified.

## Paid-audit conversion trigger
Offer a paid audit only if the scan shows enough economic materiality and documentary support that a professional dossier could create decision value. A large gross-cost number without responsibility/causation evidence is not a conversion trigger.
