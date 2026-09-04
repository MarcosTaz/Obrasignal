# VINDORUM — DISCOVERY & INTAKE CONTRACT

## Objective
Qualify a bounded customer/OEM-caused engineering/change/NRE case without a meeting and without manufacturing a recovery number before evidence exists.

## Phase A — Free Exposure Check
Until real-document intake is genuinely GREEN, VINDORUM accepts only non-confidential metadata and customer-declared facts.

Allowed fields:
- supplier industry and approximate size band;
- customer/OEM type or anonymized identifier;
- program/change type and approximate date range;
- approximate gross-cost band;
- whether a PO/contract/change document exists: YES / NO / UNKNOWN;
- whether an engineering/NRE cost source exists: YES / NO / UNKNOWN;
- whether any claim was submitted: YES / NO / UNKNOWN;
- whether any value was approved/credited/paid: YES / NO / UNKNOWN;
- whether notice/deadline rules may exist: YES / NO / UNKNOWN;
- internal owner role.

Phase A may route fit. It may not establish evidence support, legal entitlement or a precise recoverable amount.

## Metadata qualification score
Score only observable answers:
- +2 identifiable customer/OEM-driven change/event;
- +2 incremental cost source known to exist;
- +2 commercial basis/PO/change document known to exist;
- +1 prior claim/approval/payment state reconstructable;
- +1 notice/deadline process known or checkable;
- +1 named internal economic owner;
- +1 approximate exposure comfortably above the likely scan fee.

Routing:
- `0–3` → `NO_FIT` / weak fit;
- `4–6` → `NEEDS_PREQUALIFICATION`;
- `7–10` → `METADATA_QUALIFIED`.

This is a routing score, not a recoverability score.

## Phase B — Secure evidence intake
Confidential source documents may be accepted only when the automated readiness result has `real_evidence_intake_enabled=true`.

Required controls:
- production authentication and account recovery;
- authorized tenant/case binding;
- secure case-bound transfer;
- immutable/WORM storage actually configured and probed;
- trusted timestamping actually configured and probed;
- tenant/case separation;
- retention/deletion policy;
- exclusion of credentials, secrets and unrelated personal data;
- required privacy/NDA/DPA/legal controls;
- incident handling and security review appropriate to production use.

If any required control is false or unknown, VINDORUM remains metadata-only.

## Minimum bounded evidence set
After the gate is green, request only what the case needs:
1. relevant PO/contract/commercial terms or bounded excerpt;
2. customer ECN/change order/instruction/release/cancellation evidence;
3. engineering/NRE cost source or equivalent;
4. prior credit/payment/settlement evidence, or explicit unknown state;
5. notice/deadline evidence when applicable.

Do not request an entire ERP export, mailbox or contract library for the first scan.

## Automated intake sequence
1. create tenant/case-bound upload authority;
2. receive only approved evidence categories;
3. preserve immutable original, source metadata and hash;
4. extract propositions with provenance;
5. surface conflicts/missing evidence;
6. ask the customer to confirm or correct extracted facts;
7. reconcile `documented cost → mitigation → evidence-supported → claimed → approved → settled`;
8. generate the VINDORUM Recovery Dossier;
9. expose a bounded next action in the claim workspace.

## Fail-closed outputs
Allowed outputs include:
- `NO CLAIM / INSUFFICIENT EVIDENCE`;
- `NEEDS EVIDENCE`;
- `DOCUMENTED CANDIDATE FOR CUSTOMER/INDEPENDENT REVIEW`;
- `CUSTOMER-CONFIRMED WORKFLOW CANDIDATE`.

A large cost number without causation/commercial-basis evidence is never enough to promote a case.

## Payment boundary
A paid Recovery Scan unlocks only after server-side payment verification. Browser/client checkout success alone cannot authorize paid analysis or confidential processing.
