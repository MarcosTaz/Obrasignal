# SUPPLIER RECOVERY — FACTORY STATE

## Canonical identity
**Product/company: SUPPLIER RECOVERY.**

Supplier Recovery is a distinct project/company and must remain separate from **CERTACTUM**, **VARACTUM**, ContractCredit and every other Factory. `Industrial Supplier Claims & Margin Recovery` was the descriptive Factory title; `CausLedger` was a retired working name that may remain only in legacy internal schema lineage where technically required.

No Supplier Recovery custom domain or business mailbox has been selected. Never reuse another project's domain, mailbox, Vercel project, repository, environment variables or production runtime.

## Mission and hard scope
Supplier Recovery reconstructs **supplier-side customer/OEM-caused engineering/change cost and NRE recovery** from evidence to economic outcome.

Core chain:

`CUSTOMER/PO → CHANGE/EVENT → CAUSATION → INCREMENTAL COST → MITIGATION → COMMERCIAL BASIS → EVIDENCE → HUMAN REVIEW → EVIDENCE-SUPPORTED AMOUNT → CLAIMED → APPROVED → SETTLED → DOSSIER/PROOF`

Cost is not money owed. Evidence support is not legal entitlement. Claim, approval and settlement are separate truth states.

Direct adjacencies are allowed only when bound to the same customer/program/change mechanism: change-driven premium freight/expedite, tooling/dedicated investment, rework/production disruption, contractually supported volume shortfall and clearly supported material/cost adjustments. Warranty supplier recovery, procurement-side vendor recovery, generic rebates/pricing, M&A/debt/utility recovery and unrelated claims software remain outside this Factory.

## Durable product truth
Implemented capabilities include:
- tenant/auth separation and cross-tenant denial controls;
- authorization-scoped evidence capture;
- immutable-original/WORM abstractions and exact-version readback;
- source-authenticity state separated from recoverability;
- independent reviewer-before-action workflow;
- revision/supersession integrity;
- deadline/notice truth;
- duplicate recovery fingerprints;
- backup/restore with integrity/tamper rejection;
- deterministic recovery reconciliation hash;
- append-only reconciliation persistence with actor/evidence binding;
- explicit reversal reasons for economic decreases;
- current-finding-only recovery workflow;
- Supplier Recovery Dossier v2;
- current-revision/latest-reconciliation portfolio roll-up;
- duplicate-finding, cross-tenant and cross-currency aggregation rejection;
- metadata-only 0–10 qualification that routes fit but never scores recoverability;
- customer-safe metadata triage brief;
- REAL-vs-TEST commercial proof ledger;
- synthetic/adversarial NRE and true-null tests.

## Economic truth model
The recovery ledger is fail-closed and monotonic:

`NET DOCUMENTED EXPOSURE >= EVIDENCE-SUPPORTED >= CLAIMED >= APPROVED >= SETTLED`

It separately exposes:
- `unsupported_exposure`;
- `supported_unclaimed`;
- `claimed_unapproved`;
- `approved_unsettled`;
- `supported_unsettled`.

Impossible economic chains fail closed instead of being silently reshaped.

## Identity correction — completed
The prior attempt to label this Factory as Certactum was identified as a cross-project identity collision and reversed.

Hard automated boundary now protects Supplier Recovery-specific product/commercial surfaces against:
- Certactum / `certactum.com` / Certactum mailbox reuse;
- Varactum identity reuse;
- retired CausLedger customer-facing reuse;
- cross-project Vercel/runtime reuse.

PR `#947` is **CLOSED / NOT MERGED** and preserved only as historical identity-collision lineage.

## Repository truth — 2026-09-04
Repository: `MarcosTaz/Obrasignal`.

### Canonical product promotion
PR `#948` — **MERGED**.
- exact tested head: `c1c1c1c5355462360b0f3d7128e171b54993727c`;
- `ObraSignal Quality` run `#5272`: Python SUCCESS + Mobile SUCCESS;
- Python result: **1480 passed, 2 skipped, 2 warnings**;
- squash merge on main: `9391b40725bf31a5d9129244760bcd14febe0356`.

### Isolated deployment package
PR `#949` — **MERGED**.
- exact tested head: `dc323138138ca359068611a166c5ff255afab959`;
- `ObraSignal Quality` run `#5274`: Python SUCCESS + Mobile SUCCESS;
- squash merge on main: `f3fbbc6e5fe3823a138915febf945c0ebd9a5315`.

Deployment package now contains:
- static Supplier Recovery public surface;
- `vercel.json` with defensive CSP/security headers;
- `robots.txt` blocking indexing while release gate is pending;
- explicit isolated deployment contract;
- automated tests preventing cross-project runtime/domain/secrets reuse.

### Current work branch
`Supplier-recovery/gtm-cohort-1` is the current working branch from main `f3fbbc6e5fe3823a138915febf945c0ebd9a5315`.

## Own-surface truth
Connected Vercel account was inventoried on 2026-09-04.

Truth:
- plan is Hobby;
- no existing Vercel project belongs to Supplier Recovery;
- existing projects belong to Certactum, ContractCredit and other products and must not be reused;
- the connected Vercel tool currently exposes project listing/inspection/deployment access but not creation of a new isolated project from the remote monorepo;
- therefore **no Supplier Recovery external deployment has been claimed or performed**;
- the repository package is technically ready for an isolated import using root directory `vertical_apps/industrial_claims/public_site`;
- no custom domain is selected or purchased.

The default generated `*.vercel.app` hostname should be retained if/when an isolated project can be created, until the user explicitly selects a paid/custom domain.

## Production/data boundary
Commercial presentation and **metadata-only triage** may proceed on Supplier Recovery's own isolated surface when deployed.

Do **not** accept real confidential customer documents until Supplier Recovery has its own verified production identity/access/storage/data-handling controls and the real-evidence activation gate is genuinely GREEN. Do not route confidential evidence through ordinary email.

No production WORM/TSA/HSM certification, court acceptance, guaranteed recovery, legal entitlement or real-customer validation may be inferred from internal tests or provider names.

## Commercial truth
Real commercial validation remains separate:
- real paid Supplier Recovery customer: not proven;
- real paid recovery audit: not proven;
- independently verified customer recovery: not proven;
- repeat monitoring revenue: not proven;
- outbound sent: not proven / currently false in cohort state;
- buyer interest: not proven;
- customer leakage: not proven;
- recoverable amount: not proven.

Any technical/test payment from another product/environment is excluded from Supplier Recovery commercial proof.

Pricing in `COMMERCIAL_OPERATING_MODEL.md` remains hypothesis-only until costly buyer behavior validates it.

## GTM cohort 1 — current evidence
`GTM_COHORT_1.json` now records four evidence-grounded named C-level buyer hypotheses using public sources observed on 2026-09-04:
- TMG Automotive — Isabel Furtado — CEO;
- Simoldes Plastics — Hugo Garcia de Carvalho — Chief Operating Officer, Simoldes Plastic Division;
- FEHST Componentes — Alexandre Ferreira — CEO;
- HFA, S.A. — Sérgio Paulo Coelho — CEO.

These are **buyer-role research targets only**. The file explicitly records:
- `outbound_sent=false`;
- `buyer_interest_proven=false`;
- `customer_leakage_proven=false`;
- `recoverable_value_proven=false`;
- `paid_customer_proven=false`;
- `confidential_documents_requested=false`;
- `enrichment_credits_used=false`;
- `outbound_authorized=false` per target.

No email or phone was guessed. A public HFA association listing for a commercial representative named Sérgio Coelho is recorded only as a company contact source and explicitly **not assumed to be the same individual as the CEO without confirmation**.

Apollo people search was attempted without enrichment and rejected because the connected Apollo plan does not include that API. No enrichment credits were consumed.

## Offer now
1. Metadata-only Recovery Triage.
2. Rapid Recovery Scan once secure documentary intake is allowed.
3. Forensic Recovery Audit producing Supplier Recovery dossier + evidence index + recovery reconciliation.
4. Customer-authorized Recovery Support with independently verified baseline/outcome.
5. Continuous Leakage Monitoring only after repeated real patterns justify it.

## ACTIVE
`GTM_COHORT_1_TRUTH → EXACT_HEAD_VALIDATION → CONTACT_ROUTE_VERIFICATION → AUTHORIZED_OUTBOUND → QUALIFIED_BUYER`

## NEXT
1. Exact-head CI for the machine-readable GTM cohort + market-truth tests.
2. Merge only if exact-head GREEN.
3. Verify safe public contact routes for the four named buyer targets without paid enrichment or guessed addresses.
4. Expand toward 10 named buyer targets only where current role evidence is sufficiently strong; unresolved roles remain account-only.
5. Keep outbound unsent until a valid sender identity/authority is available; do not substitute another project's mailbox.
6. Create/import the isolated Supplier Recovery Vercel project when the connected tooling supports it; never reuse an existing project.
7. Once a valid Supplier Recovery sender/surface exists, run metadata-only outbound experiment and record REAL proof events separately from test activity.
8. Seek a bounded paid diagnostic without accepting confidential documents through an unsafe channel.
9. Configure/verify Supplier Recovery production identity + WORM + trusted timestamp + data-handling controls before real-document intake.
10. Drive first paid case to independently documented recovery or defensible true-null outcome.

## COMPLETION GATES
Supplier Recovery is not commercially complete until all are true:
- current exact-head tests are GREEN;
- cross-project identity boundary remains clean;
- no P0/P1 truth/security regression;
- canonical dossier and recovery reconciliation are end-to-end persisted/auditable;
- Supplier Recovery has its own safe production documentary-intake path;
- fresh-account customer-zero journey is verified;
- deliberate price/plan is tested with a real buyer;
- at least one paid diagnostic/audit or equivalent costly commercial commitment exists;
- at least one real case reaches independently documented recovery or defensible true-null outcome;
- customer payment truth is recorded without counting synthetic/test payments;
- repeatable delivery workflow and handoff are documented.

## RESUME_AT
`VERIFY_GTM_COHORT_HEAD → MERGE → VERIFY_CONTACT_ROUTES → 10_NAMED_BUYERS → OWN_VERCEL_PROJECT → AUTHORIZED_METADATA_OUTBOUND → QUALIFIED_BUYER → PAID_DIAGNOSTIC → SECURE_INTAKE → VERIFIED_OUTCOME`
