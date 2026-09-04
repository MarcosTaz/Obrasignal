# SUPPLIER RECOVERY — SENDER IDENTITY REQUIREMENTS

## Purpose
Supplier Recovery must use its own commercial sender identity before any real outbound is sent.

## Hard isolation rules
- Do not send Supplier Recovery outreach from any Certactum, Varactum, ObraSignal, ContractCredit or other project mailbox.
- Do not use another project's domain, Vercel project, DKIM/SPF/DMARC configuration, mailing reputation or CRM sender identity.
- Do not use a personal mailbox as the canonical business sender.
- Do not infer, scrape or synthesize personal recipient email addresses.
- Public company-wide addresses and official contact forms are routing evidence only; they are not proof of permission, interest or recoverable value.

## Required sender state before outbound
All of the following must be explicitly known and verified:
1. `product = Supplier Recovery`.
2. Dedicated sender mailbox exists under a Supplier Recovery-controlled identity.
3. Sender can receive replies.
4. SPF/DKIM/DMARC or equivalent provider authentication is verified when a custom domain is used.
5. Reply handling and opt-out suppression are operational.
6. Sender signature identifies the real operator and Supplier Recovery without invented company facts.
7. No confidential documents are requested through ordinary email.
8. Every target is rechecked immediately before first send if its route or role evidence is marked MEDIUM/recheck-required.
9. The initial message is metadata/problem-discovery only and does not state that money is owed, leakage exists or a recovery amount has been found.
10. The user has authorized the real external send step after sender identity is ready.

## Domain boundary
No domain is selected or purchased by this document. Domain choice is an explicit founder decision boundary.

Until a dedicated sender is operational:

`OUTBOUND_STATE = PREPARED_NOT_SENDABLE`

## Safe preparation allowed now
- target/account research;
- current-role validation;
- corporate route validation;
- message drafting;
- objection handling;
- follow-up logic;
- CRM/outbound ledger schema;
- synthetic dry runs.

## Forbidden promotion
Research, an open email route, a successful delivery, an email open, or a reply must never automatically become:
- buyer interest;
- qualified opportunity;
- customer leakage;
- legal entitlement;
- recoverable amount;
- paid customer;
- recovered cash.
