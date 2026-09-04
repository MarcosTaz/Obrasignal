# CERTACTUM — SUPPLIER RECOVERY FACTORY STATE

## Canonical identity
**Product/company: Certactum.**

`Industrial Supplier Claims & Margin Recovery` → `CausLedger` → **Certactum** is one continuous Factory lineage, not three companies. CausLedger is a retired working name and remains only where legacy identifiers/schemas must be preserved for compatibility or evidence lineage.

Canonical domain: `certactum.com` / `www.certactum.com`.
Canonical business mailbox: `marcos@certactum.com`.

## Mission and hard scope
Certactum reconstructs **supplier-side customer/OEM-caused engineering/change cost and NRE recovery** from evidence to economic outcome.

Core chain:

`CUSTOMER/PO → CHANGE/EVENT → CAUSATION → INCREMENTAL COST → MITIGATION → COMMERCIAL BASIS → EVIDENCE → HUMAN REVIEW → EVIDENCE-SUPPORTED AMOUNT → CLAIMED → APPROVED → SETTLED → DOSSIER/PROOF`

Cost is not money owed. Evidence support is not legal entitlement. Claim, approval and settlement are separate truth states.

Direct adjacencies are allowed only when bound to the same customer/program/change mechanism: change-driven premium freight/expedite, tooling/dedicated investment, rework/production disruption, contractually supported volume shortfall and clearly supported material/cost adjustments. Warranty supplier recovery, procurement-side vendor recovery, generic rebates/pricing, M&A/debt/utility recovery and unrelated claims software are outside this Factory.

## Current product truth
Existing durable capabilities include:
- tenant/auth separation and cross-tenant denial controls;
- secure authorization-scoped evidence capture;
- immutable-original/WORM abstractions and exact-version readback;
- source-authenticity state kept separate from recoverability;
- independent reviewer-before-action workflow;
- outcome evidence and recovery-state lineage;
- Proof Pack/offline verification and tamper checks;
- revision/supersession integrity;
- deadline/notice truth;
- duplicate recovery fingerprints;
- backup/restore with integrity/tamper rejection;
- public/help surfaces and multilingual help lineage;
- billing lifecycle logic;
- synthetic/adversarial NRE cases and customer-zero tests.

## Supplier Recovery Master delta — 2026-09-04
A clean continuation branch was created from current `main` because the legacy `apps/industrial-claims` branch had diverged materially and must not be merged wholesale.

New/continued work on `certactum/supplier-recovery-master`:
1. **Real-evidence activation gate hardened** — real documentary intake stays disabled unless database integrity, production authentication, declared WORM storage and declared trusted timestamp controls all pass. Provider declaration does not claim certification.
2. **Recovery leakage reconciliation added** — fail-closed monotonic ledger:
   `net documented exposure >= evidence-supported >= claimed >= approved >= settled`.
3. Reconciliation exposes distinct buckets:
   - `unsupported_exposure`;
   - `supported_unclaimed`;
   - `claimed_unapproved`;
   - `approved_unsettled`;
   - `supported_unsettled`.
4. Every reconciliation receives a deterministic SHA-256 hash.
5. Impossible economic chains fail closed instead of being silently reshaped.
6. **Certactum Supplier Recovery Dossier v2** added as canonical customer-facing layer over the legacy dossier schema, carrying the reconciliation while explicitly refusing to promote a gap into debt/legal entitlement.
7. Commercial operating model renamed to Certactum and narrowed around the primary NRE/change wedge, with direct-adjacency controls, ICP, offer ladder, pricing hypotheses and commercial proof gates.

## Repository truth — verified 2026-09-04
Repository: `MarcosTaz/Obrasignal`.

Current `main` observed before this state update: `a8a930dc653fa17817b5986c496fa8a917a8c501`.

Legacy branch `apps/industrial-claims` observed at `e39d3f42fd49864be29f0afe90b832ea728b746a` and is **909 commits ahead / 218 behind** current main at the observed comparison. It is historical development lineage, not a safe whole-branch merge source.

PR `#785` is **MERGED** (2026-09-03), despite stale historical Factory files that still described it as draft/open. Repository/API truth outranks those stale documents.

Active clean branch: `certactum/supplier-recovery-master`.
Executable/product head before this state-only update: `110daf1bb1e19cd2cb3eaa42b1f9367417667416`.
Active PR: `#947` — **OPEN / DRAFT / NOT MERGED**.

## Validation truth
`STATE = NOT_FULLY_VERIFIED` for the current clean branch.

Reason: no GitHub Actions workflow run/check was observed for the current clean-branch HEAD during this execution. The repository workflow is configured for pull requests, but absence of an observed run means no GREEN claim may be made.

Historical Certactum validation remains evidence only for the exact historical SHAs where it ran; it does not automatically validate the current Supplier Recovery Master delta.

## Five-layer trust state
1. Identity/authentication — internal controls exist; production IdP/MFA/account-recovery evidence remains external/pending.
2. Immutable originals/WORM/custody — internal abstractions/tests exist; production provider receipts/retention/DR remain external/pending.
3. Timestamp/signature/attestation — internal fail-closed interfaces exist; real trusted provider/key custody/historical validation remain external/pending.
4. Proof Pack/independent verification — internal proof and offline verification exist; independent third-party validation remains external/pending.
5. Operational/legal security — internal hardening exists; pentest, GDPR/DPA/privacy/retention/incident and jurisdiction-specific legal review remain external/pending.

## Production/data boundary
Commercial presentation, lead capture and **metadata-only triage** may proceed.

Do **not** accept real confidential customer documents until the live production identity/access/storage/data-handling controls required by the real-evidence activation gate are genuinely configured and verified. Do not route confidential evidence through ordinary email.

No production WORM/TSA/HSM certification, court acceptance, guaranteed recovery, legal entitlement or real-customer validation may be inferred from internal tests or provider names.

## Commercial truth
A symbolic LIVE EUR 1.00 Stripe payment was historically recorded as technical payment validation; it is not customer revenue, WTP proof or recovered customer value.

Real commercial validation remains separate:
- real paid customer: not proven in this state;
- real paid recovery audit: not proven;
- independently verified customer recovery: not proven;
- repeat monitoring revenue: not proven.

Pricing in `COMMERCIAL_OPERATING_MODEL.md` is explicitly hypothesis-only until costly buyer behavior validates it.

## Offer now
1. Metadata-only Recovery Triage.
2. Rapid Recovery Scan once secure documentary intake is allowed.
3. Forensic Recovery Audit producing Certactum dossier + evidence index + recovery reconciliation.
4. Customer-authorized Recovery Support with independently verified baseline/outcome.
5. Continuous Leakage Monitoring only after repeated patterns justify it.

## ACTIVE
`EXACT_HEAD_VALIDATION + ECONOMIC_RECONCILIATION_INTEGRATION + COMMERCIAL_ACTIVATION_WITHOUT_CONFIDENTIAL_INTAKE`

## NEXT
1. Obtain exact-head CI/check evidence for PR #947; repair any Certactum-caused regression without weakening truth gates.
2. Integrate recovery reconciliation into workflow/API surfaces where it can be persisted/audited rather than remaining only a pure calculation module.
3. Add adversarial lifecycle tests covering evidence-supported → claimed → approved → settled transitions and regression/reversal handling.
4. Add portfolio-level leakage roll-up with strict same-currency/no-double-count controls.
5. Prepare metadata-only diagnostic workflow and qualification assets against the frozen ICP.
6. Seek real buyer/problem evidence and a bounded paid diagnostic without accepting confidential documents through an unsafe channel.
7. Configure/verify production identity + WORM + timestamp/data-handling controls before real-document intake.
8. Only after real cases prove repeat patterns, automate monitoring and direct adjacencies.

## COMPLETION GATES
Supplier Recovery is not called commercially complete until all are true:
- current exact-head tests are GREEN;
- no P0/P1 truth/security regression;
- canonical Certactum dossier and recovery reconciliation are end-to-end persisted/auditable;
- safe production documentary intake exists;
- fresh-account customer-zero journey is verified;
- deliberate price/plan is tested with a real buyer;
- at least one paid diagnostic/audit or equivalent costly commercial commitment exists;
- at least one real case reaches independently documented recovery or defensible true-null outcome;
- customer payment truth is recorded without counting synthetic/test payments;
- repeatable delivery workflow and handoff are documented.

## RESUME_AT
`VERIFY_PR_947_EXACT_HEAD → PERSIST_RECONCILIATION → LIFECYCLE_ADVERSARIAL_TESTS → PORTFOLIO_LEAKAGE_ROLLUP → METADATA_TRIAGE_GTM → SECURE_PRODUCTION_INTAKE → PAID_CASE → VERIFIED_OUTCOME`
