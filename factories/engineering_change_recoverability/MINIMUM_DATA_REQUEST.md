# Minimum Data Request — Assisted Engineering Change Recoverability Pilot

Principle: start with exports/documents. No production write access, no passwords, no ERP/PLM migration and no broad connector project are required for the first pilot.

## Required minimum dataset

For 25–50 engineering changes across 1–2 programs:

### Change identity
- change / ECN / ECR / ECO ID;
- customer;
- program;
- part / assembly;
- revision before and after;
- request / received / effective dates;
- change description.

### Technical evidence
- customer change notice/request;
- old and new drawing/specification or other revision proof;
- BOM/affected-item evidence where relevant;
- PPAP/revalidation/test requirement changes where relevant.

### Economic evidence
Per cost line where applicable:
- tooling / fixture / gauge quotes or invoices;
- material/WIP/finished-goods obsolete inventory;
- rework/scrap records;
- engineering/quality/validation hours;
- supplier cancellation/MOQ charges;
- special freight;
- capacity or dedicated-investment impact.

### Mitigation and prior recovery
- material reuse / resale / rework;
- supplier credits/cancellations;
- prior customer credits/payments;
- other third-party recovery.

Zero balances must be reconciled, not assumed.

### Commercial basis
- governing PO / MSA / nomination / program agreement / amendment;
- change procedure or customer-specific requirements;
- relevant notice, prior-approval, waiver and submission requirements.

### Commercial workflow
- quotation/change request submitted;
- customer response/approval;
- customer PO or price update;
- invoice / debit-credit note;
- AR/payment evidence;
- commercial open-item tracker or bump/price-history tracker if used.

## Preferred format

- CSV/XLSX export for the change register and commercial tracker;
- PDF/email/document export for evidence;
- no live-system credentials for T2 pilot.

Customer/part identifiers may be pseudonymized for an initial diagnostic provided the same stable identifiers are preserved across all source files.

## Minimum acceptance gate

Do not start a paid recovery pilot unless the sample contains:
- at least 20 materially reviewable changes, OR fewer changes with clearly material economics;
- exact revision identity for most sampled changes;
- at least one governing commercial document;
- enough cost evidence to distinguish estimate from verified cost;
- enough downstream commercial evidence to distinguish quoted, approved, invoiced and paid states.

If these are absent, run only a data-readiness diagnostic and do not imply recoverability can be quantified.
