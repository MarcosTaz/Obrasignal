# INDUSTRIAL SUPPLIER CLAIMS & MARGIN RECOVERY / CAUSLEDGER — FACTORY STATE

## MISSION
Operate CausLedger as a real assisted supplier-side recovery business that is rapidly automating itself. The first product is an evidence-first professional dossier, not a completed dashboard. Commercial execution and product hardening run in parallel.

## FROZEN INITIAL WEDGE
Until real commercial proof exists, concentrate on **supplier-side customer-caused cost / margin recovery**.

First case type: **customer-directed engineering/change cost (NRE / change-driven incremental cost)**.

Secondary categories remain subordinate until the first case type has real paid-case capability: premium freight/expedite, dedicated tooling/investment, customer-caused disruption, contractually supported volume shortfall and clearly supported material/cost adjustments.

## SOURCE TRUTH
- Repository: `MarcosTaz/Obrasignal`
- Branch: `apps/industrial-claims`
- Draft PR: `#785`; open, DRAFT, not merged; no automatic merge.
- Exact source snapshot tested before this state-only commit: `5069b2360535dc83e7e27780aa958925f219bd02`.
- Verification evidence: ObraSignal Quality `#4924`, run `33560775537`, checked out and tested that exact SHA.
- Mobile job: SUCCESS, including Expo Doctor, critical-detail wiring and bundle smoke test.
- Python repository/Factory Cloud suite: `1275 passed, 2 skipped, 1 failed`; the single failure is the unrelated time-dependent Chile MercadoPublico assertion `tests/test_chile_mercadopublico.py::test_observation_uses_visible_amount_only_and_preserves_publisher_state`. No CausLedger failure occurred on the tested source snapshot.
- Therefore `5069b236...` is **CausLedger-clean by scope**, but the full Quality workflow is NOT called green while the unrelated Chile test remains red.
- The subsequent state-only commit is not substituted for the tested source snapshot merely to create circular CI/state churn.
- Branch is unprotected and commits are unsigned; neither fact is treated as proof of production authority.

## DELIVERY MODEL
Default early model: **software + human review + evidence traceability + professional dossier**.

Manual steps are allowed when controlled, recorded and independently reviewable. Repeated manual steps become automation backlog only after delivery proves they repeat and matter economically.

Dossier chain:
DOCUMENTS → CONTRACT/PO/CHANGE TRUTH → EVENT → CAUSATION → CUSTOMER RESPONSIBILITY BASIS → COST → CALCULATION → PRIOR RECOVERY CHECK → EVIDENCE → CONFIDENCE → NOTICE/DEADLINE → DOSSIER → NEXT ACTION → DOCUMENTED FINAL OUTCOME.

If evidence is insufficient: **NO CLAIM / NEEDS REVIEW**.

## DONE — PRODUCT / DELIVERY
- Tenant-safe identity, roles, four-eyes review, documentary hashing, currency lineage, numeric safety, recovery cap, replay/atomicity, revision/supersession, backup/restore, tenant-safe queue/detail, secure console and final cumulative outcome controls remain in force.
- Current revision/successor navigation and revision-lineage integrity are hardened; stale/superseded revisions cannot transition.
- Package export requires current durable truth and rejects stale lifecycle/economic/evidence snapshots.
- Corrected recovery journey is covered end-to-end through amendment, fresh review, action, final outcome and restore.
- `COMMERCIAL_OPERATING_MODEL.md` freezes the business-first wedge and delivery priorities without storing private prospect data.
- `DOSSIER_STANDARD.md` defines the audit-grade paid deliverable.
- `ASSISTED_DELIVERY_SOP.md` defines qualification → intake → rapid scan → forensic reconstruction → human review → dossier → outcome → commercial close → automation learning.
- `DISCOVERY_AND_INTAKE_PACK.md` defines the bounded document request and real-data handling gate.
- `dossier.py` builds an assisted dossier from durable case truth plus explicit human causation/responsibility/prior-recovery assessment without upgrading legal truth.
- The assisted dossier can be rendered as customer-reviewable Markdown without raw documentary content.
- 24 adversarial customer-directed engineering/change/NRE scenarios are codified in `fixtures/nre_adversarial_cases.json`.
- `test_industrial_claims_assisted_dossier.py` tests those scenarios and fail-closed dispositions.
- Industrial Factory Cloud allowlist includes corrected-journey E2E and assisted-dossier red-team.
- Change Capture produces a deterministic versioned sheet and maintains a current-snapshot reminder so a new material fact requires a fresh export.

### Secure real-document intake
- `IntakeAuthorization` bounds real-document intake by tenant, case ref, authorizer, effective/expiry times, minimum immutable retention, transfer channel, allowed evidence roles, data-terms state, byte limit and a fixed historical rapid-scan purpose.
- `capture_authorized_original_evidence` rejects expired/not-yet-effective authorization, invalid chronology, uncleared data terms, unsupported roles/purpose, cross-tenant identity, out-of-namespace evidence IDs, oversized content and caller attempts to override authorization metadata.
- Authorizer and transfer-channel refs are represented by hashes in proof metadata rather than clear identifiers.
- Secure capture requires immutable-original persistence plus exact-version readback; later retrieval re-proves tenant/evidence binding, object/version, COMPLIANCE retention, byte length and SHA-256 rather than trusting capture-time success.
- `SecureCaptureRegistry` semantically revalidates authorization metadata on write and read. Low-level capture primitives cannot enter the durable real-case registry without bounded authorization.
- Real-case `secure-analyze` and `secure-amend` consume only IDs of already-authorized captures; they do not receive document bytes and preserve those exact evidence envelopes as case lineage.
- The normal `/analyze`, `/amend` and documentary `/resolve` paths reject inline documentary content by default. Inline documents exist only behind explicit `allow_inline_evidence_content=True` for synthetic/local tests.
- The assisted console follows that rule and does not invite raw-document entry in the secure default mode.

### Secure final-outcome evidence
- Final settlement/payment evidence has its own finding-bound authorization purpose and cannot reuse the earlier rapid-scan authorization.
- Secure outcome capture requires exact immutable original storage/readback, bounded data terms and retention; caller-controlled metadata cannot promote `CONTENT_HASHED` into source authenticity.
- `/secure-resolve` is operator-only and accepts one previously registered outcome `evidence_id`, never bytes.
- Source authentication remains an independent truth dimension and may remain `UNVERIFIED` after a fully valid immutable capture.
- A `RECOVERED` Proof Pack now includes the exact final outcome/settlement evidence envelope in its cryptographic manifest. The documentary record that closes a finding cannot silently disappear from the final proof lineage.
- Adding final outcome evidence changes the Proof Pack target. Externalization receipts for the pre-outcome target remain historically auditable but are not reconstructed as current trust, and stale-target re-externalization fails closed.

### Proof / externalization / offline verification
- External proof generation is an explicit operator-only POST operation; the normal Proof Pack GET remains side-effect free.
- Externalization enforces an operator-reviewed proof-target SHA-256 before any provider call; a stale target creates no operation event and invokes no provider.
- Externalization audit is append-only and records `STARTED → COMPLETED/FAILED`, preserving partial-failure truth without storing provider error messages.
- RFC3161 cryptographic validity is separated from eIDAS qualification; a timestamp cannot be called qualified solely from a provider assertion.
- eIDAS qualification verification is designed around signed LOTL → national Trusted List → service status at token `genTime`, failing closed on ambiguity.
- WORM proof is evidence-specific and byte-level: global case/object-lock metadata cannot elevate original-evidence immutability.
- Hardware seal/signature proof separates cryptographic signature validity, hardware-key evidence and eIDAS qualification.
- External attestation receipts are archived append-only, hash-linked, target/subject/purpose-bound, recoverable by operation and verified before retrieval.
- Receipt retrieval is operator-only, tenant/finding-bound, and remains available for superseded/replaced proof targets without reopening mutation rights.
- HTTP E2E proves analyst read-only access, operator-only externalization, explicit confirmation, stale-target rejection, no-effect GET behavior and durable audit/receipt recovery.
- `offline_export_bundle.py` creates an explicit confidential offline-verification bundle only when exact original bytes exist for every committed evidence item and rehash to the Proof Pack; missing/unknown/duplicate/tampered originals fail closed.
- Durable offline export resolves object/version references from tenant-scoped persisted evidence metadata, requires the configured immutable-store provider to match, re-reads exact immutable versions and invokes the independent offline verifier before release.
- VERIFIED/VALID external receipts do not become independently verified merely because CausLedger labels them so; the offline bundle requires independent verifier callbacks for those receipt kinds.
- The runtime route `POST /findings/<finding_id>/proof-pack/offline-export` is reviewer/operator-only, requires explicit `confirm_confidential_export=true` plus the exact current Proof Pack target SHA-256, and performs no immutable-original read before those preconditions pass.
- Analyst access, tenant-header spoofing, stale targets, legacy hash-only evidence and unconfigured immutable stores fail closed.
- Successful confidential export is `no-store`, is explicitly marked confidential, and contains exact document bytes only inside the deliberate offline bundle.
- A recovered-case E2E proves the bundle must retrieve and independently verify all original case documents plus the final settlement/payment original; tampered or missing final outcome bytes fail closed.
- Confidential export release has a dedicated append-only hash-chained audit ledger. It writes `STARTED` immediately before original reads and `COMPLETED` only after independent bundle verification; post-start failures record `FAILED` when the ledger remains writable.
- That export ledger stores only a closed metadata vocabulary (actor/case/target/evidence count/bundle SHA-256/verification/failure class) and structurally rejects arbitrary documentary/base64 fields.
- SQL update/delete triggers protect the export ledger, and hash-chain verification still detects mutation if an attacker first removes those triggers.

### Public preview / identity gate
- `public_site/index.html` is a branch-only canonical CausLedger public-site preview. It is `noindex,nofollow`, carries `domain-and-mailbox-pending`, has no form/file upload/confidential intake, states the initial wedge and preserves NO CLAIM / NEEDS REVIEW truth.
- `test_causledger_public_site_identity.py` prevents reintroduction of ChangeClaim identity, premature indexing/intake and recovery-guarantee language.
- `identity_release_gate.py` requires actual domain ownership/mailbox verification plus MX, exactly one SPF, DKIM and DMARC truth before public identity release; lookalike protocol strings fail closed.

## COMMERCIAL EXECUTION TRUTH
Commercial prospect names, direct outreach identifiers, pricing experiments, response playbooks and proposal details are intentionally stored outside this public repository in a private operations workspace.

Current public truth only:
- external outreach/channel validation activity has begun;
- one industrial-event channel has confirmed the service category is eligible for participation, but this is channel access only and is not product-market validation, a prospect reply or customer demand;
- no discovery, document sample, pilot, paid audit, customer dossier, recovery value or customer payment may be claimed without private evidence;
- pricing and willingness-to-pay remain unproven;
- unsupported cases must close as NO CLAIM / NEEDS REVIEW.

## IDENTITY / PUBLIC RELEASE TRUTH
- Canonical brand: **CausLedger**.
- Canonical domain: `causledger.com`.
- Canonical founder/business mailbox: `marcos@causledger.com`.
- `causledger.com` was observed available for purchase on 2026-09-01; no purchase or ownership is claimed by this repository state.
- The connected Vercel account still has a live `changeclaim` production shell carrying the old ChangeClaim identity. It has not been rebranded or redeployed by this Factory turn.
- The new CausLedger public-site preview exists only in the branch and is intentionally release-gated.
- No further brand-facing outbound should be sent from `obrasignal.pt@gmail.com` or another project identity.
- Public release remains blocked until domain ownership, mailbox, SPF, DKIM and DMARC are actually provisioned and verified.

## PRODUCT TRUTH
- `READY_FOR_REVIEW` = documentary candidate only.
- Human causation/customer-responsibility assessment is required for the assisted dossier; cost alone never establishes responsibility.
- `CONTENT_HASHED` proves supplied-content hash integrity, not source authenticity or legal sufficiency.
- `APPROVED` / `ACTIONED` remain internal workflow states only.
- External customer action/claim submission is never automatic.
- External proof operation `COMPLETED` does not imply every provider is verified and does not establish legal recoverability.
- Final recorded outcome requires documentary evidence and remains final-cumulative, not installment accounting.
- Real-document create/amend/outcome paths consume authorized immutable originals by ID. Normal production-mode HTTP does not accept inline documentary bytes.
- Normal Proof Pack GET never includes raw documentary bytes. Exact bytes exist only in the deliberately requested confidential offline bundle after identity, target and immutable-store checks.
- No currency conversion is implemented.

## BUSINESS TRUTH
- pricing: HYPOTHESIS
- willingness to pay: UNPROVEN
- market validation: UNPROVEN
- real incremental recovery: UNPROVEN
- customer payment/revenue: UNPROVEN
- production authority: false

This Factory is not MARKET_VALIDATED, PILOT_VALIDATED, COMMERCIAL_READY or PROJECT_COMPLETE.

## ACTIVE
Run the business and product critical path together:
1. preserve exact-head CI truth and repair CausLedger regressions immediately without weakening evidence gates;
2. red-team the remaining semantic binding between a persisted final outcome and its authorized outcome-registry evidence so DB-level reference substitution cannot create a superficially valid final Proof Pack;
3. finish the canonical CausLedger domain/mailbox/DNS identity before any further brand-facing outreach so CausLedger is never mixed with ObraSignal or another project identity;
4. process prospect/channel replies privately; event/channel eligibility alone does not count as customer interest;
5. convert a genuinely interested industrial supplier into a bounded discovery call when one exists;
6. obtain one bounded historical case/document sample only through an authorized secure handling path;
7. perform an assisted rapid scan and produce the first audit-grade real dossier or documented NO CLAIM;
8. quote/test a paid single-case audit if the rapid scan supports further work;
9. measure delivery hours/cost and customer response;
10. automate only repeated manual work that materially affects delivery economics.

## NEXT
- Red-team final-outcome reference substitution and, if a bypass exists, bind durable Proof Pack reconstruction to secure outcome authorization semantics fail-closed.
- Keep customer/prospect commercial truth out of the public repository.
- Complete `causledger.com` + `marcos@causledger.com` mailbox/DNS identity before further brand-facing outbound or publication of the canonical CTA.
- Do not deploy the CausLedger public site or replace the live ChangeClaim shell until the release gate is deliberately authorized and identity prerequisites are verified.
- Complete first real discovery/document sample/rapid scan through the private operating workflow when a genuinely interested company exists.
- Continue only security hardening required to accept and deliver a real case safely; do not return to broad infrastructure/taxonomy work.
- Do not buy an exhibition stand or other meaningful paid channel before a deliberate CAC/WTP decision; free/low-cost visitor/networking access may be evaluated separately.
- Follow up outreach only where lawful and from the correct CausLedger identity; change offer/ICP based on evidence rather than widening product taxonomy.

## WAIT / EXTERNAL DEPENDENCIES
These are not Factory stop conditions; other executable work continues.
- CausLedger domain purchase/ownership and mailbox provisioning.
- DNS email authentication (SPF, DKIM, DMARC) after domain/mailbox ownership exists.
- Prospect responses and customer decisions.
- Real customer documents require a verified authorized secure intake/data-handling path before product-runtime ingestion.
- Runtime workspace provisioning/supervised worker.
- Verified real upstream provider/JWT tenant/org/role mapping.
- Real browser authentication/session binding and authorized external runtime exposure.
- Production deploy/secrets/provider activation.
- Real qualified trust-service/HSM/WORM provider credentials and commercial activation.
- Legal/recoverability specialist review where a real case requires it.
- Real payment/recovery evidence can only exist after customer action.
- Merge approval for draft PR #785.

## COMPLETION GATE
PROJECT COMPLETE requires all of:
- secure reliable customer case E2E;
- complete audit/recovery dossier delivery;
- safe real external pilot handling;
- legitimate willingness-to-pay test and paid path;
- support/monitoring/incident handling;
- understood cost to serve and revenue;
- credible repeat case/continuous-monitoring mechanism.

## RESUME_AT
Read exact `apps/industrial-claims` HEAD and CI. Treat `5069b2360535dc83e7e27780aa958925f219bd02` as the last source snapshot proven CausLedger-clean by scope (1275 pass / 2 skipped / one unrelated Chile temporal failure; mobile SUCCESS) unless a later exact-head run supersedes it. Red-team final-outcome registry/reference substitution next. If identity ownership is still blocked externally, do not substitute another brand/email: continue only executable safe work, process real replies privately, and keep the branch/public-site release gate closed. Once `causledger.com` + `marcos@causledger.com` + SPF/DKIM/DMARC are verified, rebrand/replace the old ChangeClaim shell only under explicit deploy authority, then proceed discovery → bounded document sample → rapid scan → dossier/NO CLAIM → paid-audit test.
