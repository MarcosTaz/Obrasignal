# DebitProof — Assisted Pilot Onboarding Runbook

## Gate 0 — Qualification
Confirm without leading the buyer:
- recurring warranty/quality/customer debits exist;
- there is a pre-acceptance or post-debit review process worth testing;
- materiality is sufficient for a bounded diagnostic;
- an operational owner exists across Warranty/Quality/Finance/Purchasing;
- the current incumbent process does not already solve contract versioning, evidence, duplicate/credit checks and deadline control adequately.

If the incumbent fully solves the problem, record `INCUMBENT_SOLVED` and do not force a pilot.

## Gate 1 — Scope
Create a tenant-scoped pilot intake record and define:
- maximum cases and documents;
- currencies;
- historical period / live monitoring window;
- included customers/OEMs/programs;
- explicit exclusions from scope.

## Gate 2 — Acceptance and data authorization
Record acceptance evidence for the exact terms/privacy versions. Authorize only required data classes. Credentials, secrets, payment-card data, health data and government IDs are prohibited.

## Gate 3 — Intake
Create a source register with file name/ID, source hash, received date, tenant and reviewer. Prefer pseudonymized identifiers. Do not infer missing mappings.

## Gate 4 — Document truth
For each material agreement/CSR/warranty/amendment:
1. ingest source or reviewed extracted text;
2. extract clause candidates only;
3. human-review every material clause;
4. compile only explicit approved rules;
5. retain clause/source/dossier hashes;
6. fail closed on conflict or missing material clause.

## Gate 5 — Debit analysis
For every debit:
- map tenant/customer/part/program/asset;
- select one applicable approved contract version;
- verify evidence hash/reviewer lineage;
- assess warranty/cost eligibility;
- assess root cause/responsibility;
- check exclusion facts;
- detect exact/potential duplicates separately;
- reconcile prior credits and prior payments separately;
- evaluate notice deadline conservatively;
- output SUPPORTED / PARTIALLY_SUPPORTED / DISPUTABLE / UNKNOWN / RESOLVED.

`UNKNOWN` exposes no supported/disputable money.

## Gate 6 — QA and dossier
A human reviewer verifies every actionable case before customer delivery. A dispute package remains `DRAFT_REVIEW_REQUIRED`; DebitProof does not autonomously submit disputes to an OEM/customer.

## Gate 7 — Save / return / outcome
Save the dossier in the client-held workspace format, verify its integrity, return the bundle, and record outcome only from evidence. A credit approved, credit received and cash received are distinct states.

## Gate 8 — Commercial truth
Billing sandbox may test quote → acceptance evidence → invoice draft → payment-evidence review, but it recognizes zero real revenue. Real payment/revenue is recorded only from independently verifiable external evidence.

## Gate 9 — Support / incidents
Route analysis questions through the support workflow. P0 security/data-integrity incidents isolate the affected process and require resolution evidence before closure.

## Completion record per pilot
Record: scope, source hashes, case counts, UNKNOWN count, actionable cases, verified outcomes, manual minutes, support minutes, cost-to-serve evidence basis, customer feedback, payment truth, repeat-cycle truth, incidents and deletion/return evidence.
