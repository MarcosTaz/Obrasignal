# VINDORUM — SENDER IDENTITY REQUIREMENTS

## Purpose
VINDORUM must use its own commercial sender identity before any real outbound is sent.

## Hard isolation rules
- Do not send VINDORUM outreach from any other project or personal mailbox.
- Do not reuse another project's domain, deployment identity, sender authentication, mailing reputation or CRM sender identity.
- Do not infer, scrape or synthesize personal recipient email addresses.
- Public company-wide addresses and official contact forms are routing evidence only; they are not proof of permission, interest or recoverable value.

## Required sender state before outbound
All must be known and verified:
1. `product = VINDORUM`.
2. Dedicated VINDORUM sender mailbox exists.
3. Sender can receive replies.
4. SPF/DKIM/DMARC or equivalent provider authentication is verified when a custom domain is used.
5. Reply handling and opt-out suppression are operational.
6. Signature identifies the real operator and VINDORUM without invented company facts.
7. Confidential documents are never requested through ordinary email.
8. MEDIUM/recheck-required role or route evidence is rechecked immediately before first send.
9. Initial outreach is metadata-only and does not state that money is owed, leakage exists or recovery has been found.
10. The irreversible external-send step has the applicable founder/authority approval.

## Domain boundary
No domain is selected or purchased by this document. Domain choice remains an explicit founder boundary.

Until a dedicated sender is operational:
`OUTBOUND_STATE = PREPARED_NOT_SENDABLE`

## Safe preparation
Target research, current-role validation, corporate-route validation, drafts, objection handling, ledger preparation and synthetic dry-runs are allowed.

## Proof boundary
Research, a route, delivery, open, click or reply must never automatically become buyer interest, qualification, customer leakage, legal entitlement, recoverable amount, paid customer or recovered cash.
