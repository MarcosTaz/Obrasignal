# WarrantyGuard / DebitProof — Portugal B2B Outreach Compliance Gate

## Current state
`LEGAL_HOLD_DGC_LIST_PENDING`

No new unsolicited marketing email or follow-up to a Portuguese corporate recipient may be sent from this Factory until the current applicable DGC corporate opt-out list has been obtained/consulted and the intended recipient has been checked against it.

## Legal basis verified 2026-09-01
Lei n.º 41/2004, consolidated Article 13.º-A permits unsolicited direct-marketing communications to corporate subscribers until they refuse future communications / enter the Article 13.º-B list, but Article 13.º-B requires direct-marketing senders to consult the national list of corporate entities that opted out, updated monthly by Direção-Geral do Consumidor (DGC).

Official sources:
- https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2004-106523049-183878511
- https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2004-106523049-183907401

This repository note is an operational compliance gate, not legal advice or a substitute for professional legal review.

## Evidence state
- Requests for the current list/procedure have already been sent to DGC through the user's Gmail account.
- As of 2026-09-01 no responsive DGC message providing the current list/procedure was found.
- Public web search did not surface a current downloadable monthly list that could safely be treated as authoritative.

## Follow-up eligibility
A Portuguese follow-up is eligible only when **all** are true:
1. the current applicable DGC list/version has been obtained or an authoritative DGC procedure makes the check possible;
2. the target corporate recipient has been checked and is not suppressed;
3. the thread has no reply, bounce, rejection, reroute, or direct opt-out;
4. the target is not otherwise suppressed by portfolio collision/compliance state;
5. the message provides a valid way to refuse future communications;
6. no sensitive customer data is requested through ordinary email.

If any condition is unknown: `HOLD`.

## Current WarrantyGuard cohort
AFIA, Simoldes, FEHST and PLASTIFA remain `NO_REPLY_YET` based on Gmail thread evidence. Their follow-ups are **not** authorized for transmission while `DGC_LIST_PENDING` remains unresolved.

Standby Portuguese targets (including JAC Products Portugal and TMG Automotive) are also HOLD for new unsolicited outreach under the same gate.
