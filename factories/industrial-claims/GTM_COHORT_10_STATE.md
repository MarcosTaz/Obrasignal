# SUPPLIER RECOVERY — GTM COHORT 10 STATE

Date: 2026-09-04

## Milestone
Supplier Recovery now has **10 unique named buyer research targets** across the first Portuguese industrial-supplier beachhead.

The first four remain in `GTM_COHORT_1.json`. Six additional targets are in `GTM_COHORT_EXPANSION_6.json`.

## Ten named buyer targets
1. TMG Automotive — Isabel Furtado — CEO.
2. Simoldes Plastics — Hugo Garcia de Carvalho — Chief Operating Officer, Simoldes Plastic Division.
3. FEHST Componentes — Alexandre Ferreira — CEO.
4. HFA, S.A. — Sérgio Paulo Coelho — CEO.
5. PLASTIFA — Manuel Carvalho — Gerente / CEO.
6. SWJ Portugal — Stefan Hartmann — Executive Director / Management.
7. TRANSFORMADE — Ruben Lopes — CEO.
8. EPALFER — Eduardo Oliveira — General Manager and owner.
9. VianaPlásticos — Rene Galves — Administrator.
10. Mold-Tech Portugal / Standex Engraving — Raul Souto — current affiliation confirmed; last explicit General Manager title evidence is older and must be rechecked before outbound.

## Truth boundary
This milestone is **research readiness, not commercial validation**.

Across both cohort files:
- outbound sent: false;
- buyer interest proven: false;
- customer leakage proven: false;
- recoverable value proven: false;
- paid customer proven: false;
- confidential documents requested: false;
- paid enrichment credits used: false;
- personal email guessed: none;
- personal phone guessed: none;
- outbound authorized: false for every target.

Generic company contacts may be stored only when published by the company itself. They remain company channels, not personal contacts and not permission to send.

## Role confidence gate
Nine targets have current/recent public role evidence considered sufficient for research routing.

Mold-Tech Portugal is deliberately weaker:
- current Raul Souto affiliation is confirmed by a recently crawled public profile;
- the explicit `General Manager` title source is an older Standex company post;
- therefore `role_recheck_required_before_outbound=true`.

No weaker target may silently be upgraded to HIGH.

## ACTIVE
`EXACT_HEAD_VALIDATION → MERGE_COHORT_10 → VERIFY_SAFE_CONTACT_ROUTES → OWN_SENDER_IDENTITY → AUTHORIZED_METADATA_OUTBOUND`

## NEXT
1. Run exact-head CI for the cohort-10 branch.
2. Merge only if Python + mobile are GREEN on the exact head.
3. Verify current official company/contact routes for all ten; do not infer personal emails from formats.
4. Recheck Raul Souto's current title before any Mold-Tech message.
5. Establish Supplier Recovery's own sender identity/mailbox; never reuse another project's mailbox.
6. Create/import Supplier Recovery's isolated Vercel project when tooling permits; keep generated Vercel hostname until a domain decision is explicitly required.
7. Only after sender authority exists, execute a metadata-only outbound experiment and record each real action in the commercial-proof ledger.
8. First external objective: a qualified buyer + bounded historical case, still without confidential document intake.
9. Next economic objective: paid diagnostic/audit or equivalent costly commitment.

## RESUME_AT
`VERIFY_COHORT_10_HEAD → MERGE → CONTACT_ROUTE_MATRIX → SUPPLIER_RECOVERY_SENDER → AUTHORIZED_OUTBOUND → QUALIFIED_BUYER → PAID_DIAGNOSTIC`
