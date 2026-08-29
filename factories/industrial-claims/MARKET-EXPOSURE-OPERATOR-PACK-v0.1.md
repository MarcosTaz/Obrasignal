# Industrial Claims — Market Exposure Operator Pack v0.1

Purpose: provide a reversible preparation pack for future real market exposure. This artifact contains no real prospect, no customer data and authorizes no external transmission by itself.

## Offer

Working offer: `Assisted Industrial Supplier Claim & Margin Recovery Scan`.

What it does:

- receives a bounded supplier transaction/evidence set;
- reconstructs candidate leakage from source documents;
- preserves conflicting/missing evidence as UNKNOWN;
- produces human-reviewable candidate outputs;
- distinguishes candidate amount, defensible claim value, recovered value and our fee.

What it does not promise:

- guaranteed recovery;
- legal representation;
- automatic supplier contact;
- ERP write access;
- percentage recovery from total supplier spend;
- unsupported ROI.

## Narrow qualification prompt

Ask only for enough information to determine pilot admissibility:

1. Is there a specific supplier transaction or recurring charge category you suspect is economically wrong or unreconciled?
2. Can you identify the relevant PO/agreement/invoice/receipt or credit documentation?
3. Can the suspected amount be reconstructed from those documents?
4. Is there an internal procurement/AP/operations reviewer who can validate the context?
5. Can a bounded evidence set be shared under an agreed review boundary?

If the answer to transaction identity/document access is no, do not force a pilot.

## Initial operator message skeleton

Subject concept: `Document-first supplier charge reconciliation`

Body skeleton:

`We run a bounded assisted review of supplier transactions where a charge, credit, rebate, expedite cost, warranty contribution or other commercial item may not reconcile to the underlying documents. The first step is not a claim against the supplier: we reconstruct one specific case from PO/agreement/invoice/receipt evidence, preserve missing facts as UNKNOWN and return a human-reviewable candidate. If there is no defensible discrepancy, the output says so.`

`A suitable pilot needs one document-rich case and an internal reviewer. No ERP write access or supplier contact is required for the initial scan.`

This text is a preparation draft only and must be adapted/approved before real external use.

## Prospect record template

- Prospect ID: `UNASSIGNED`
- Company: `UNASSIGNED`
- Sector: `UNASSIGNED`
- Country: `UNASSIGNED`
- Contact role: `UNASSIGNED`
- Qualification hypothesis: `UNASSIGNED`
- Evidence source: `UNASSIGNED`
- Exposure channel: `UNASSIGNED`
- Exposure timestamp: `UNASSIGNED`
- Exact message version: `UNASSIGNED`
- Transmission evidence: `UNASSIGNED`
- Response: `UNKNOWN`
- Qualified problem: `UNKNOWN`
- Admissible documents: `UNKNOWN`
- Reviewer access: `UNKNOWN`
- Authorization: `UNKNOWN`
- Commercial state: `NOT_EXPOSED`
- Next action: `SELECT_REAL_PROSPECT_ONLY_WHEN_EXTERNAL_RESEARCH/OUTREACH_LANE_IS_ACTIVE`

## Exposure execution checklist

Before sending/publishing:

- [ ] prospect identity is real and verified;
- [ ] target role reasonably owns procurement/AP/supplier economics;
- [ ] offer makes no unsupported recovery claim;
- [ ] privacy/contact rules for channel/jurisdiction checked;
- [ ] exact message frozen;
- [ ] operator has authority for external communication;
- [ ] CRM/evidence location ready to preserve transmission and response truth.

After exposure:

- [ ] record exact timestamp;
- [ ] save transmission/publication evidence;
- [ ] set response to UNKNOWN until observed;
- [ ] do not infer interest from delivery/open tracking alone;
- [ ] qualify only against the ICP screen;
- [ ] preserve rejection/no-response as valid market evidence.

## T2 transition rule

`NOT_EXPOSED -> T2_MARKET_EXPOSED` requires a real named exposure event satisfying `T2-TO-REAL-PILOT-EVIDENCE-GATE-v0.1.md`.

This preparation pack alone leaves the Factory at `T1_PILOT_CAPABLE / T2_PREPARED_NOT_EXPOSED`.
