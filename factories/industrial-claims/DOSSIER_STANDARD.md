# CAUSLEDGER — AUDIT-GRADE DOSSIER STANDARD

## Purpose
The dossier is the initial product. It must let a finance/commercial/legal reviewer understand what happened, what is documented, what remains uncertain, how the amount was reconstructed and what action is justified next.

## Mandatory dossier structure

### 1. Executive case sheet
- case/finding ID and revision;
- customer and program references;
- claim family;
- current workflow state;
- net potential and currency;
- confidence / unresolved evidence;
- notice/deadline state and urgency;
- one-sentence next action;
- explicit statement that candidate value is not automatically money owed.

### 2. Documentary index
For each source:
- source reference;
- document type;
- content hash / provenance state;
- relevant date;
- what proposition the document is used to support;
- raw document storage status.

### 3. Contract / PO / change truth
State only what the documents support:
- commercial basis / PO / contract reference;
- change-order, release, customer instruction or other event reference;
- responsibility/reimbursement language located by the reviewer;
- limitations, exclusions, caps, prerequisites and notice requirements;
- unresolved interpretation requiring specialist/legal review.

### 4. Event chronology
A dated sequence of customer instruction/change/event → supplier response → incremental work/cost → notice/communication → any prior settlement/recovery.

### 5. Causation assessment
Separate:
- observed event;
- claimed causal link;
- evidence supporting the link;
- competing causes / supplier-controlled causes;
- reviewer conclusion: SUPPORTED / PARTIAL / UNRESOLVED.

### 6. Customer responsibility basis
Never infer responsibility from cost alone. Record:
- contractual/documentary basis;
- relevant source references;
- required conditions;
- contrary language/evidence;
- reviewer conclusion: SUPPORTED FOR COMMERCIAL REVIEW / PARTIAL / UNRESOLVED.

This is not a legal conclusion unless separately authorized and reviewed.

### 7. Cost reconstruction
For every economic component:
- gross cost;
- cost source;
- avoided cost;
- resale/reuse;
- third-party recovery;
- prior payment/credit;
- other mitigation;
- resulting net potential;
- currency;
- formula/version and reproducibility hash.

### 8. Prior recovery / duplicate check
Explicitly state whether the same economic exposure is already represented by another case, payment, credit note, settlement or recovery. UNKNOWN is acceptable; omission is not.

### 9. Notice / deadline
Record:
- documentary/declared deadline truth state;
- due date if supported for review;
- timing state (OPEN / DUE_TODAY / EXPIRED / UNKNOWN);
- required method/recipient if known;
- human exception/waiver review if expired;
- never equate expiry automatically with non-recoverability.

### 10. Evidence gaps and attack list
List missing documents, disputed assumptions, alternative explanations, duplicated costs, unsupported allocations, unclear responsibility, deadline uncertainty and any other reason the case may fail.

### 11. Confidence and disposition
Allowed dispositions:
- **NO CLAIM / INSUFFICIENT EVIDENCE**;
- **NEEDS REVIEW / DOCUMENT REQUEST**;
- **DOCUMENTED CANDIDATE FOR INDEPENDENT REVIEW**;
- **INTERNALLY APPROVED FOR WORKFLOW**;
- **ACTIONED INTERNALLY**;
- **DOCUMENTED FINAL OUTCOME**.

Do not label a dossier “recoverable”, “owed” or “overcharged” unless that conclusion is independently established under the applicable authority.

### 12. Next action
One bounded next action with owner and required evidence, for example:
- request signed change order and engineering time ledger;
- reconcile prior credit notes;
- obtain independent commercial/legal interpretation;
- prepare customer-authorized claim communication;
- close as insufficient evidence.

## Release gate
A dossier may leave internal review only when:
- tenant/case identity is correct;
- revision is current;
- raw evidence is not accidentally embedded in an unauthorized output;
- evidence lineage is intact;
- calculation reproduces;
- prior-recovery check is recorded;
- missing evidence and contrary evidence are visible;
- deadline truth is visible;
- human reviewer is identified;
- external/customer action authority is explicit.
