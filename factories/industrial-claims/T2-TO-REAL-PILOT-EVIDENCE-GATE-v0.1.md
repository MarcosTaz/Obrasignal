# Industrial Claims — T2 → Real Pilot Evidence Gate v0.1

Purpose: define the minimum external evidence required before this Factory may claim progress beyond preparation-only T2 artifacts.

## T2_MARKET_EXPOSED minimum

The Factory may claim `T2_MARKET_EXPOSED` only when all are evidenced:

1. a named real prospect or organization;
2. an exposure timestamp/date;
3. the exact proposition/offer exposed;
4. the exposure channel;
5. proof the message or offer was actually transmitted/published to that prospect/audience;
6. no claim of response, demand, qualification or willingness to pay unless separately evidenced.

Transmission alone proves exposure only.

## REAL_PILOT_CANDIDATE minimum

A real pilot candidate requires all of:

1. named buyer/company identity;
2. evidence of a real business problem or suspected leakage category;
3. at least one real admissible transaction/document class available or explicitly promised for review;
4. internal human reviewer/contact able to validate context;
5. buyer authorization boundary for document review;
6. qualification result of `ASSISTED_PILOT_CANDIDATE` under the pilot ICP screen;
7. commercial scope bounded to a specific case/data set;
8. pricing/fee basis presented separately from any recovery claim.

A positive reply without admissible evidence is not a pilot candidate.

## PILOT_ACCEPTED minimum

Claim `PILOT_ACCEPTED` only with durable evidence of:

- explicit buyer acceptance of scope;
- agreed price/fee basis, including zero-cost pilot only if explicitly agreed;
- permitted data/document access;
- named case owner/reviewer;
- start condition/date or clearly defined intake trigger;
- no unresolved legal/procurement blocker that prevents work starting.

## PILOT_STARTED minimum

Claim `PILOT_STARTED` only when:

- real customer evidence has been received under the agreed boundary;
- evidence provenance is retained;
- at least one transaction has entered the admissibility workflow;
- customer data is kept outside synthetic/public artifacts;
- no unsupported amount has been promoted to entitlement/recovery.

## VALUE_PROVEN minimum

Claim value only by tier:

- `CANDIDATE_VALUE`: reconstructable discrepancy, entitlement unresolved;
- `DEFENSIBLE_CLAIM_VALUE`: human-reviewed documentary basis supports a commercial claim position;
- `CUSTOMER_ACCEPTED_VALUE`: customer accepts the result/claim basis;
- `RECOVERED_VALUE`: durable evidence proves money/credit was actually recovered or a charge reversed/avoided;
- `PLATFORM_REVENUE`: separate evidence proves our fee became earned/paid under the commercial agreement.

Never collapse these tiers.

## Evidence register required per prospect/pilot

For each real external state change retain:

- entity/prospect identifier;
- event timestamp;
- source/evidence ref;
- operator/action;
- proposition/version;
- response state;
- qualification state;
- document-access state;
- authorization state;
- commercial state;
- unresolved blockers;
- exact next action.

## Forbidden upgrades

Do not advance terminal state because:

- an email was drafted but not sent;
- a message was sent but no response exists;
- a prospect replied positively but provided no admissible case;
- documents were mentioned but not received;
- a candidate amount exists but entitlement is UNKNOWN;
- the customer says a claim is valid without supporting evidence;
- a recovery is expected but not settled;
- a fee invoice exists but payment is not evidenced.

## Terminal boundary

This gate is itself preparation evidence only. It does not move the Factory to `T2_MARKET_EXPOSED`, `REAL_PILOT_CANDIDATE`, `PILOT_ACCEPTED`, `RECOVERED_VALUE` or revenue.