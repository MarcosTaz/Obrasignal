# EarnedCash — Assisted Pilot Runbook v0

## Purpose

Run a Historical Closeout Cash Audit without pretending that the current product is autonomous debt collection, legal advice or a self-service finance platform.

## Pilot acceptance

A pilot can start only when the customer can provide a bounded historical population of completed or late-stage projects plus enough records to distinguish:

`CERTIFIED → INVOICED → DUE → PAID`

and, where relevant:

`RETENTION HELD → RELEASE CONDITION → RELEASE DUE → RELEASED → PAID`

`FINAL ACCOUNT POSITION → AGREED VALUE → INVOICED → DUE → PAID`

## Minimum customer inputs

For each pilot project request, where available:

- project/customer identifier;
- executed contract / order and material amendments;
- applications / valuations;
- payment certificates or equivalent certification;
- invoices and credit notes;
- bank/payment export or independently verifiable receipt evidence;
- retention schedule / retention ledger;
- practical/final completion evidence;
- defects/maintenance period status;
- closeout requirements and closeout evidence;
- final-account agreement evidence;
- deductions / set-offs and supporting notices;
- currency.

Missing evidence does not become an inferred fact. It becomes `UNKNOWN`, `REQUIRES_REVIEW` or a documented blocker.

## Intake boundary

Start with 2–5 years of completed / advanced projects, but cap the first controlled delivery to a dataset that can be manually audited end-to-end.

Never request production credentials when an export/document pack is sufficient.

Never ingest unrelated tenant/customer data into a shared reconciliation result.

Never aggregate currencies without an explicit reviewed FX model.

## Processing sequence

1. Create tenant-scoped company, customer, project and contract records.
2. Import project/payment records.
3. Validate record identity, project, tenant and currency scope.
4. Build documentary lineage.
5. Reconcile applications, certificates, invoices, payments, credits and deductions.
6. Evaluate retention independently from ordinary invoice balances.
7. Evaluate final account independently from contractor/customer positions.
8. Classify not-yet-due, disputed, blocked and unknown value separately.
9. Build recovery queue only from evidence-supported, presently actionable value.
10. Human reviewer verifies evidence lineage and blocker state.
11. Customer approves any external recovery action.
12. Track action; do not represent request/settlement as payment.
13. Verify received cash/credit from independently verified evidence.
14. Attribute the verified economic result before calculating any EarnedCash fee.
15. Preserve audit history.

## Human-review checklist

For every proposed queue item confirm:

- correct tenant;
- correct customer;
- correct project;
- correct contract/version;
- correct currency;
- amount is not double-counted elsewhere;
- certification evidence is present where certification is claimed;
- invoice evidence is present where invoicing is claimed;
- due status is evidence-supported;
- prior payments/credits/deductions are reconciled;
- retention release conditions are actually satisfied where retention is claimed;
- defects and closeout blockers are not silently ignored;
- final-account agreement exists where agreement is claimed;
- unresolved variation/time/LD entitlement is routed out of EarnedCash;
- no legal conclusion is generated beyond the evidence.

Any failed item returns the case to review rather than increasing recoverable value.

## Customer approval gate

EarnedCash may prepare an evidence package and recommended next action.

No debtor/customer contact is automatic in v0.

The customer must approve an external action before `ACTION_APPROVED` / `RECOVERY_REQUESTED` progression.

Jurisdiction-specific legal/regulatory review is required before EarnedCash itself performs regulated or legal collection activity.

## Cash truth

These are not equivalent:

- recovery candidate;
- recovery request sent;
- counterparty acknowledgement;
- settlement agreed;
- invoice issued;
- cash received;
- cash attributed to EarnedCash.

Only independently verified cash/credit with exact tenant/project/currency/amount matching can become `VERIFIED_CASH`.

A success fee is due only if the commercial agreement applies and attribution to the EarnedCash-assisted action is independently supported.

Correct verified recovery of `0` is a valid pilot outcome.

## Pilot output

Deliver:

- project-level reconciliation;
- evidence-supported recovery queue;
- explicit not-yet-due / disputed / blocked / unknown buckets;
- evidence lineage per queue item;
- recommended customer-approved action;
- audit history integrity status;
- verified cash/credit received after action, if any;
- fee calculation only from verified attributed result;
- unresolved issues and referral candidates.

## Referral boundaries

Route unresolved change/time/delay/LD entitlement to ScopeLedger.

Route high-value complex commercial disputes or multi-party claims to Industrial Claims.

Do not expand EarnedCash into generic ERP, accounting, lending, factoring, debt purchase or unbounded claims consultancy.

## Pilot metrics

Track separately:

- projects ingested;
- projects fully reconcilable;
- value classified `NOT_YET_DUE`;
- value classified `DISPUTED`;
- value classified `UNKNOWN`;
- evidence-supported queue value;
- queue value approved for action;
- verified cash/credit received;
- verified cash/credit attributed to EarnedCash;
- days from intake to first evidence-supported case;
- days from approved action to verified cash;
- delivery hours;
- gross margin;
- false-positive recovery cases;
- missed known oracle cases in synthetic validation.

## T1 gate

Do not label EarnedCash `T1 — PILOT CAPABLE` until all of the following are true:

- exact-head Python CI is green;
- persistent tenant isolation is verified;
- import/reconcile/queue/audit flow works end-to-end;
- action state transitions are evidence/customer-approval gated;
- cash verification cannot be self-attested by the client;
- at least one diversified synthetic end-to-end pilot completes with oracle agreement;
- zero-recovery pilot completes correctly;
- no known P0 remains;
- known P1s have either been repaired or explicitly bounded away from pilot use;
- backup/restore requirement for pilot persistence is defined and tested before real customer data is accepted.
