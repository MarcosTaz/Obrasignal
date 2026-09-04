# SUPPLIER RECOVERY — FACTORY STATE

## Canonical identity
**Product/company: SUPPLIER RECOVERY.**

This Factory is a distinct company/project. It must remain separate from **CERTACTUM** and **VARACTUM**.

`Industrial Supplier Claims & Margin Recovery` was the descriptive factory title. `CausLedger` was an earlier working name. The explicit canonical decision is now **SUPPLIER RECOVERY**; new product, commercial, repository and customer-facing work must use only that identity.

No Supplier Recovery production domain or business mailbox is declared in this state. Do not reuse another project's domain, email, Vercel project or production repository.

## Mission and hard scope
Supplier Recovery reconstructs **supplier-side customer/OEM-caused engineering/change cost and NRE recovery** from evidence to economic outcome.

Core chain:

`CUSTOMER/PO → CHANGE/EVENT → CAUSATION → INCREMENTAL COST → MITIGATION → COMMERCIAL BASIS → EVIDENCE → HUMAN REVIEW → EVIDENCE-SUPPORTED AMOUNT → CLAIMED → APPROVED → SETTLED → DOSSIER/PROOF`

Cost is not money owed. Evidence support is not legal entitlement. Claim, approval and settlement are separate truth states.

Direct adjacencies are allowed only when bound to the same customer/program/change mechanism: change-driven premium freight/expedite, tooling/dedicated investment, rework/production disruption, contractually supported volume shortfall and clearly supported material/cost adjustments. Warranty supplier recovery, procurement-side vendor recovery, generic rebates/pricing, M&A/debt/utility recovery and unrelated claims software are outside this Factory.

## Current product truth
Durable capabilities include:
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
- billing lifecycle logic;
- synthetic/adversarial NRE cases and customer-zero tests.

## Supplier Recovery Master delta — 2026-09-04
The clean Supplier Recovery continuation preserves the economic/product work developed on the previously mislabelled branch while correcting the company identity.

Implemented:
1. **Real-evidence activation gate** — real documentary intake stays disabled unless database integrity, production authentication, WORM storage and trusted timestamp controls pass. Provider declaration does not claim certification.
2. **Recovery leakage reconciliation** — fail-closed monotonic ledger:
   `net documented exposure >= evidence-supported >= claimed >= approved >= settled`.
3. Distinct leakage buckets:
   - `unsupported_exposure`;
   - `supported_unclaimed`;
   - `claimed_unapproved`;
   - `approved_unsettled`;
   - `supported_unsettled`.
4. Deterministic SHA-256 reconciliation hash.
5. Impossible economic chains fail closed rather than being silently reshaped.
6. Append-only reconciliation persistence with actor/evidence binding and explicit reversal reasons for economic decreases.
7. Current-finding-only recovery workflow; superseded findings cannot receive/render new reconciliation.
8. **Supplier Recovery Dossier v2** with explicit refusal to promote an economic gap into debt/legal entitlement.
9. Portfolio roll-up with current-revision/latest-reconciliation controls, no duplicate findings, no cross-tenant aggregation and no cross-currency aggregation without an explicit FX evidence layer.
10. Metadata-only 0–10 qualification that routes fit but never scores recoverability.
11. Customer-safe metadata triage brief.
12. REAL-vs-TEST commercial proof ledger so technical/test payments cannot become market proof.
13. Commercial operating model, discovery/intake pack, target-account thesis and outbound playbook focused on the frozen NRE/change wedge.

## Repository truth — 2026-09-04
Repository: `MarcosTaz/Obrasignal`.

Legacy branch `apps/industrial-claims` is historical development lineage and is materially diverged from current main; it is not a safe whole-branch merge source.

PR `#785` is **MERGED** and remains historical repository truth.

The incorrectly named continuation PR `#947` is **CLOSED / NOT MERGED** because Supplier Recovery was wrongly labelled as Certactum. Its exact-head work was preserved before closure.

Canonical active branch: `supplier-recovery/master`.

The branch was created from exact-head GREEN SHA `ef6132aabf1b8757e22507c64fcb9fda2d9949a5`, then identity corrections began. Therefore the old GREEN is historical evidence only; the identity-corrected HEAD must obtain its own exact-head GREEN before a replacement PR is considered technically ready.

## Identity-collision correction
A cross-project attempt to align Supplier Recovery with the Certactum production repository/domain was identified as an identity error and reversed. Certactum production is outside this Factory.

Hard rule from this state forward:
- never deploy Supplier Recovery to `certactum.com`;
- never use `marcos@certactum.com` as Supplier Recovery's mailbox;
- never use `MarcosTaz/certactum-outreach-hub` as Supplier Recovery's production repository;
- never label Supplier Recovery code, dossier, workflow, database tables, tests or commercial assets as Certactum or Varactum.

## Validation truth
`STATE = IDENTITY_CORRECTION_IN_PROGRESS / EXACT_HEAD_GREEN_REQUIRED`.

Last known exact-head GREEN before identity correction:
- SHA `ef6132aabf1b8757e22507c64fcb9fda2d9949a5`;
- `ObraSignal Quality` run `#5270` SUCCESS.

That GREEN must not be inherited by subsequent identity-correction commits.

## Five-layer trust state
1. Identity/authentication — internal controls exist; production IdP/MFA/account-recovery evidence remains external/pending.
2. Immutable originals/WORM/custody — internal abstractions/tests exist; production provider receipts/retention/DR remain external/pending.
3. Timestamp/signature/attestation — internal fail-closed interfaces exist; real trusted provider/key custody/historical validation remain external/pending.
4. Proof Pack/independent verification — internal proof and offline verification exist; independent third-party validation remains external/pending.
5. Operational/legal security — internal hardening exists; pentest, GDPR/DPA/privacy/retention/incident and jurisdiction-specific legal review remain external/pending.

## Production/data boundary
Commercial presentation and **metadata-only triage** may proceed once attached to Supplier Recovery's own approved surface.

Do **not** accept real confidential customer documents until Supplier Recovery has its own verified production identity/access/storage/data-handling controls and the real-evidence activation gate is genuinely green. Do not route confidential evidence through ordinary email.

No production WORM/TSA/HSM certification, court acceptance, guaranteed recovery, legal entitlement or real-customer validation may be inferred from internal tests or provider names.

## Commercial truth
Real commercial validation remains separate:
- real paid Supplier Recovery customer: not proven in this state;
- real paid recovery audit: not proven;
- independently verified customer recovery: not proven;
- repeat monitoring revenue: not proven.

Any historical technical/test payment from another product or environment is excluded from Supplier Recovery commercial proof.

Pricing in `COMMERCIAL_OPERATING_MODEL.md` remains hypothesis-only until costly buyer behavior validates it.

## Offer now
1. Metadata-only Recovery Triage.
2. Rapid Recovery Scan once secure documentary intake is allowed.
3. Forensic Recovery Audit producing Supplier Recovery dossier + evidence index + recovery reconciliation.
4. Customer-authorized Recovery Support with independently verified baseline/outcome.
5. Continuous Leakage Monitoring only after repeated patterns justify it.

## ACTIVE
`IDENTITY_CLEANUP → EXACT_HEAD_VALIDATION → REPLACEMENT_PR → OWN_PRODUCTION_SURFACE → COMMERCIAL_ACTIVATION`

## NEXT
1. Remove remaining Certactum identity references introduced in Supplier Recovery-specific files/tests/docs.
2. Rename Supplier Recovery-specific tests/symbols to the canonical identity.
3. Obtain exact-head CI/check evidence; repair any Supplier Recovery-caused regression without weakening truth gates.
4. Open a clean replacement PR from `supplier-recovery/master` only after identity scan + exact-head GREEN.
5. Keep Certactum/Varactum repositories, domains and runtime untouched.
6. Establish Supplier Recovery's own production surface only after product identity is clean; no domain purchase/selection is implied by this state.
7. Seek real buyer/problem evidence and a bounded paid diagnostic without accepting confidential documents through an unsafe channel.
8. Configure/verify Supplier Recovery production identity + WORM + timestamp/data-handling controls before real-document intake.
9. Only after real cases prove repeat patterns, automate monitoring and direct adjacencies.

## COMPLETION GATES
Supplier Recovery is not commercially complete until all are true:
- current exact-head tests are GREEN;
- no cross-project identity contamination remains in Supplier Recovery-specific surfaces;
- no P0/P1 truth/security regression;
- canonical Supplier Recovery dossier and recovery reconciliation are end-to-end persisted/auditable;
- Supplier Recovery has its own safe production documentary-intake path;
- fresh-account customer-zero journey is verified;
- deliberate price/plan is tested with a real buyer;
- at least one paid diagnostic/audit or equivalent costly commercial commitment exists;
- at least one real case reaches independently documented recovery or defensible true-null outcome;
- customer payment truth is recorded without counting synthetic/test payments;
- repeatable delivery workflow and handoff are documented.

## RESUME_AT
`IDENTITY_SCAN → RENAME_TESTS/SYMBOLS → EXACT_HEAD_GREEN → CLEAN_PR → OWN_SURFACE → METADATA_TRIAGE_GTM → SECURE_INTAKE → PAID_CASE → VERIFIED_OUTCOME`
