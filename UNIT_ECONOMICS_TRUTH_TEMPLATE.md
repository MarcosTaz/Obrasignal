# ObraSignal — Unit Economics Truth Template

Status: `STRUCTURE_READY / REAL_ECONOMICS_NOT_ESTABLISHED`

## Current observed commercial truth — 2026-08-29

- Paying customers observed in current GTM evidence: **0**.
- Revenue observed in current GTM evidence: **€0**.
- Qualified conversations observed: **0**.
- Active real pilots observed: **0**.
- Retention evidence: **UNKNOWN / not yet observable**.
- Validated monthly price: **UNKNOWN**.
- Validated CAC: **UNKNOWN**.
- Validated cost-to-serve: **UNKNOWN**.
- Validated gross margin: **UNKNOWN**.

No favorable economics may be inferred from technical maturity or synthetic tests.

## Per-customer revenue

Record only real amounts:

- Setup/pilot fee paid:
- Subscription MRR:
- Annual prepaid revenue normalized monthly:
- Usage/success fee where actually contracted and earned:
- Discounts/credits/refunds:
- Net recognized customer revenue for measurement period:

## Variable cost to serve

- Payment processing fees:
- Data/API fees attributable to customer:
- Hosting/compute/storage attributable where measurable:
- Notification/provider cost:
- Human onboarding time × measured internal cost rate:
- Human triage/assisted-service time × measured cost rate:
- Support time × measured cost rate:
- Data correction/review time × measured cost rate:
- Other customer-variable cost:

Do not pretend founder time is free when assessing scalability. If no internal cost rate has been chosen, keep labor cost `UNKNOWN` and separately report minutes/hours.

## Gross contribution

When inputs are real:

`CUSTOMER_CONTRIBUTION = NET_REVENUE - PAYMENT_FEES - VARIABLE_INFRA_DATA_COST - VARIABLE_SUPPORT_AND_ASSISTED_DELIVERY_COST`

`CONTRIBUTION_MARGIN = CUSTOMER_CONTRIBUTION / NET_REVENUE`

If net revenue is zero, do not report a percentage margin.

## Acquisition economics

Per cohort/campaign:

- Prospects researched:
- Research minutes:
- Prospects contacted:
- Outreach/tool cost:
- Replies:
- Qualified conversations:
- Pilots:
- Paid customers:
- Sales/onboarding labor minutes:

Only compute CAC when acquisition cost and paid-customer denominator are real. With zero paid customers, CAC is **NOT YET MEASURABLE**, not €0.

## Retention / LTV

Do not compute LTV from assumed churn while no retention curve exists.

Observe first:
- paid start date;
- renewal eligibility date;
- renewal/cancellation date;
- paid months retained;
- expansion/contraction;
- reason for churn.

Any pre-retention LTV model must be labeled `SCENARIO`, never `OBSERVED`.

## Assisted-pilot economics

A technically successful pilot can still be commercially poor if manual effort is excessive. Record:

- profile setup minutes;
- opportunity-quality review minutes;
- manual shortlist preparation minutes;
- customer support minutes;
- incident/data-correction minutes;
- number of useful work cycles;
- revenue received.

Calculate hours of human effort per useful customer cycle before deciding what to automate.

## Scale gate

Do not classify economics as viable until there is enough real evidence to judge at least:

- revenue/customer;
- variable cost/customer;
- support/assisted delivery burden;
- acquisition cost;
- retention/churn observation;
- contribution margin or a defensible path to it.

Current classification:

`REVENUE_ZERO / CAC_NOT_MEASURABLE / LTV_NOT_MEASURABLE / RETENTION_UNKNOWN / GROSS_MARGIN_UNKNOWN / SCALE_READY_FALSE`
