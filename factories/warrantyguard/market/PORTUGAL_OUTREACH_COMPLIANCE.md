# WarrantyGuard / DebitProof — Portugal B2B Outreach Compliance Gate

## Current state
`HOLD_CURRENT_DGC_LIST_SCREEN_REQUIRED_BEFORE_SEND`

No new unsolicited marketing email or follow-up to a Portuguese corporate recipient may be sent from this Factory unless the then-current applicable DGC Article 13.º-B corporate opt-out list is consulted immediately before sending and the intended recipient is confirmed not suppressed.

## Legal basis verified 2026-09-01
Lei n.º 41/2004, consolidated Article 13.º-A permits unsolicited direct-marketing communications to corporate subscribers until they refuse future communications / enter the Article 13.º-B list, but Article 13.º-B requires direct-marketing senders to consult the national list of corporate entities that opted out.

Official sources:
- https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2004-106523049-183878511
- https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2004-106523049-183907401

This repository note is an operational compliance gate, not legal advice or a substitute for professional legal review.

## DGC procedure evidence — resolved 2026-09-02
Direção-Geral do Consumidor replied from `DGC.Fiscalizacao@dgconsumidor.gov.pt` to the existing request for access to the Article 13.º-B corporate opt-out list. The response states that the list is available on the official DGC/Consumidor portal, can be downloaded in Excel format, and is updated whenever a new inclusion request is made.

Operational consequence:
- the access procedure is no longer UNKNOWN;
- a previously downloaded copy must not be treated as permanently authoritative;
- the then-current official list must be retrieved/consulted immediately before an intended Portuguese send;
- each intended corporate recipient must be screened against that current list;
- if the list cannot be retrieved, its currency cannot be established, or recipient matching is ambiguous, status remains `HOLD`.

The current list file was not independently retrieved into this Factory during this update, so this change does **not** authorize any outbound email.

## Follow-up eligibility
A Portuguese follow-up is eligible only when **all** are true:
1. the then-current official DGC list has been retrieved/consulted immediately before send;
2. the target corporate recipient has been checked and is not suppressed;
3. the thread has no reply, bounce, rejection, reroute, or direct opt-out;
4. the target is not otherwise suppressed by portfolio collision/compliance state;
5. the message provides a valid way to refuse future communications;
6. no sensitive customer data is requested through ordinary email.

If any condition is unknown: `HOLD`.

## Current WarrantyGuard cohort
Existing Portuguese outreach remains `NO_REPLY_YET` at the last verified Gmail check. Follow-ups are **not** authorized merely because the prior DGC procedure blocker was resolved; each intended recipient still requires then-current DGC-list screening immediately before transmission.

Standby Portuguese targets remain HOLD for new unsolicited outreach under the same gate until that per-send screening succeeds.
