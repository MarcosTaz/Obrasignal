# EU Cloud Switching — WTP Evidence Schema v0.1

Purpose: distinguish conversation interest from willingness to pay and actual revenue. This schema does not authorize outreach.

## Prospect state ladder

- `NOT_EXPOSED`: no durable transmission evidence.
- `EXPOSED`: exact offer transmitted/published to a named buyer context.
- `REPLIED`: buyer/contact produced a real response; sentiment not inferred from opens/clicks.
- `PROBLEM_CONFIRMED`: buyer explicitly confirms a switching/renewal economic decision problem.
- `DATA_FEASIBLE`: buyer can supply a bounded decision-ready estate/economic evidence set under an authorized boundary.
- `PRICE_PRESENTED`: exact paid founding-pilot price and scope were shown.
- `WTP_POSITIVE`: buyer explicitly accepts or counteroffers a non-zero price/fee basis. Interest alone is not WTP.
- `PILOT_ACCEPTED`: scope, fee, data boundary, owner/reviewer and start condition are explicitly agreed.
- `PAID`: separate durable payment-settlement evidence exists.

Never upgrade a state because an email was delivered/opened, a meeting was accepted, a buyer said “interesting”, a free pilot was accepted, or a procurement notice was found.

## Durable evidence record

For every material external state transition retain:

- `prospect_id`
- `organization`
- `buyer_role`
- `decision_event_id`
- `source_trigger_ids`
- `event_timestamp`
- `channel`
- `offer_version`
- `message_or_meeting_evidence_ref`
- `response_evidence_ref`
- `problem_statement`
- `data_boundary`
- `price_currency`
- `price_amount`
- `price_basis`
- `buyer_price_response`
- `commercial_state`
- `payment_evidence_ref`
- `unresolved_assumptions`
- `next_action`

UNKNOWN remains UNKNOWN. A missing field cannot be filled from operator inference.

## Paid founding baseline hypothesis

Current working pricing remains a hypothesis, not a fact:

- Baseline Certification: EUR 1,500
- optional checkpoint: EUR 1,000
- Outcome Verification: EUR 3,500
- typical lifecycle: EUR 5,000–6,000

A `WTP_POSITIVE` observation requires the buyer to accept/counteroffer a non-zero commercial basis after the scope is understood. Free use, synthetic usage and verbal problem validation do not qualify.

## Discovery questions

Use only after applicable outreach/channel authorization:

1. What decision is actually open: renew, replace, migrate, defer, or renegotiate?
2. What date makes the decision economically irreversible or materially harder to change?
3. Which current-run-cost, migration-cost and incentive inputs are authoritative versus estimates?
4. Who owns the decision and who can approve a paid independent baseline?
5. What decision error is most expensive: switching when value is negative, delaying a good switch, underestimating transition cost, or relying on unapproved incentives?
6. Would the buyer pay for a bounded independent baseline before committing to the migration? If yes, at what scope/price basis and subject to what procurement constraint?
7. Can post-decision actuals later be supplied for outcome verification, separately from any benchmark-contribution permission?

The operator records literal answers/evidence, not inferred WTP.