# ObraSignal — Pilot Measurement Scorecard

Status: `MEASUREMENT_READY / NO_REAL_PILOT_DATA_YET`

## Principle

Measure customer behavior and outcomes without converting activity into value claims. `UNKNOWN` remains `UNKNOWN`; a synthetic event never becomes real customer evidence.

## Pilot identity

- Pilot ID:
- Company:
- ICP segment:
- Primary user role:
- Start date:
- Review date:
- Product/build SHA:
- Support contact activated: YES / NO
- Pricing state: FREE_TEST / QUOTED / PAID / UNKNOWN

## Baseline before ObraSignal

Capture before interpreting improvement:

- How opportunities are found today:
- Who performs discovery/triage:
- Typical discovery frequency:
- Approximate time per discovery/triage cycle:
- Number of portals/sources routinely checked:
- Existing paid tool/service:
- Main failure mode: missed opportunity / excess noise / slow triage / poor fit explanation / other
- Baseline confidence: VERIFIED / CUSTOMER_REPORTED / ESTIMATED / UNKNOWN

## Funnel evidence

| Stage | Timestamp | Evidence | State |
|---|---|---|---|
| Prospect qualified | | | UNKNOWN |
| Pilot accepted | | | UNKNOWN |
| Account/signup completed | | | UNKNOWN |
| Profile completed | | | UNKNOWN |
| First radar loaded | | | UNKNOWN |
| First relevant opportunity opened | | | UNKNOWN |
| First opportunity saved/investigated/assigned | | | UNKNOWN |
| First Value Event | | | UNKNOWN |
| First return after FVE | | | UNKNOWN |
| Second useful shortlist/work cycle | | | UNKNOWN |
| Paid continuation offered | | | UNKNOWN |
| Payment observed | | | UNKNOWN |
| Renewal/retention observation | | | UNKNOWN |

## First Value Event

Candidate definition:

**A current, previously untriaged opportunity is surfaced with traceable source evidence and the real customer judges it useful enough to investigate, save or assign.**

Required evidence:
- opportunity source + external ID;
- source timestamp/freshness;
- profile/relevance explanation shown;
- customer action or explicit customer classification;
- event timestamp;
- whether the opportunity was already known to the customer.

If it was already known, record useful triage/explanation value separately; do not label it “discovered by ObraSignal.”

## Time to first value

Measure:

`FIRST_VALUE_AT - SIGNUP_OR_PILOT_START_AT`

Also capture setup minutes that required ObraSignal human assistance. Assisted time is part of cost-to-serve and cannot be hidden.

## Repeat value

Evidence requires a separate later work cycle, not repeated clicks in the same session.

For each cycle record:
- cycle date;
- new/current opportunities surfaced;
- customer-opened items;
- customer-saved/investigated/assigned items;
- irrelevant items;
- false/stale items;
- customer-reported triage time;
- whether customer returned because of a new shortlist/notification/work need.

D1/D7/D30 return should be recorded only when the observation window has actually elapsed.

## Relevance/trust scorecard

For each surfaced opportunity ask or infer only from auditable behavior:

- `IRRELEVANT`
- `WORTH_OPENING`
- `WORTH_INVESTIGATING`
- `LIKELY_BID`
- `ALREADY_KNOWN`
- `STALE_OR_INVALID`
- `UNCLASSIFIED`

Calculate precision-like usefulness only when the denominator and classifications are real. Do not extrapolate from synthetic data.

## Commercial evidence

Record distinct states:

- willingness to test;
- willingness to continue;
- price quoted;
- objection;
- purchase intent;
- payment attempt;
- payment completed;
- renewal.

Do not collapse these into one “conversion” metric.

## Support/cost evidence

Per pilot capture:
- onboarding minutes;
- manual shortlist/review minutes;
- support minutes;
- P0/P1/P2/P3 count;
- data-correction minutes;
- infrastructure/data cost attributable where measurable;
- payment fees where real.

## Pilot review outcome

Classify only one:

- `PROBLEM_NOT_CONFIRMED`
- `PROBLEM_CONFIRMED_VALUE_NOT_REACHED`
- `FIRST_VALUE_REACHED_NO_REPEAT_YET`
- `REPEAT_VALUE_OBSERVED_NO_PAYMENT_YET`
- `PAID_CONTINUATION_OBSERVED`
- `RETAINED_PAID_USE_OBSERVED`

A pilot is not `PILOT_VALIDATED` unless a real external customer used the intended workflow and the intended outcome was observed with auditable evidence.
