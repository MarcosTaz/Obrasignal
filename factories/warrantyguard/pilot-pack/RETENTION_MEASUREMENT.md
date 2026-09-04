# DebitProof — Repeat Value / Retention Measurement

## Rule
Synthetic cycles may test product behavior; they never prove retention. One real cycle may prove a delivered outcome but does not prove repeat value.

## Minimum repeat-value evidence
A cycle marked `REAL_OBSERVED` requires an external evidence hash. Repeat value becomes `REPEAT_VALUE_OBSERVED` only after at least two evidenced real cycles for the same customer/tenant context.

## Per cycle capture
- period start/end;
- cases processed;
- verified value, if any;
- currency;
- evidence hash;
- customer-requested continuation or repeated use;
- operator/reviewer/support effort;
- unresolved UNKNOWN volume;
- process changes required since the previous cycle.

## Currency
Do not aggregate different currencies into one value total without an explicit FX policy and evidence. Mixed-currency cycles remain visibly mixed.

## Retention decisions
Do not call the product retained because a customer completed a pilot, attended another meeting or requested a report. Prefer evidenced repeat use/value or a renewed paid engagement.
