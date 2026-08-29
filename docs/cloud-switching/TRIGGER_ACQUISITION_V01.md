# Cloud Switching — Trigger Acquisition v0.1

Status: **operational hypothesis**. No external outreach is authorized by this document.

## Acquisition principle

Do not buy generic CIO lists. Identify organizations already inside a material infrastructure switching event and prioritize cases where the original forecast can still be frozen before outcome realization.

`TRIGGER → ORGANIZATION → ESTATE/EVIDENCE SIGNAL → DECISION OWNER → QUALIFICATION → ASSISTED BASELINE`

## High-value trigger classes

### 1. Renewal / commercial deadline

Signals:
- VMware/Broadcom contract renewal or expiry approaching
- explicit licensing-cost review
- renewal dispute / material commercial change

Why valuable: creates a dated decision boundary and permits RETAIN/RENEW/SWITCH comparison.

### 2. Procurement / RFP

Signals:
- public RFP for virtualization replacement
- cloud migration / data-center exit procurement
- infrastructure modernization tender
- managed service procurement explicitly replacing current virtualization stack

Evidence requirements:
- source URL / notice ID
- publication date
- deadline
- named buyer
- scope excerpt / normalized trigger classification

### 3. Public footprint reduction / exit

Signals:
- announced VMware estate reduction
- announced data-center exit
- announced cloud consolidation / repatriation / replatforming

Do not infer a complete migration merely from a strategy announcement.

### 4. Hiring / capability build

Signals:
- VMware migration engineer
- cloud migration architect
- platform modernization lead
- FinOps / cloud economics role tied to transformation

Hiring is a weak-to-medium trigger by itself; combine with a second signal where possible.

### 5. Partner/project announcement

Signals:
- SI/MSP named migration engagement
- public assessment or modernization project
- provider migration-program participation

Conflict rule: partner/provider source may identify the event but cannot independently verify its resulting economics.

## Qualification fields

Each prospect record must preserve:

- organization name
- country / region
- trigger class
- trigger date
- decision deadline, if known
- source IDs / URLs
- source confidence
- estate-size signal (VMs or equivalent), if known
- alternatives under consideration, if known
- original business case likely available: YES / NO / UNKNOWN
- billing baseline likely available: YES / NO / UNKNOWN
- telemetry/estate evidence likely available: YES / NO / UNKNOWN
- FinOps / Finance involvement signal
- likely decision owner role
- qualification score
- qualification rationale
- outreach state: NOT_AUTHORIZED / AUTHORIZED_NOT_SENT / SENT / REPLIED / CLOSED

UNKNOWN must remain UNKNOWN; never score missing evidence as confirmed.

## Qualification score

- renewal/decision <=12 months: 20
- material estate: 15
- >=2 credible alternatives: 15
- original forecast/business case likely preserved: 15
- billing baseline likely accessible: 10
- telemetry/estate evidence likely accessible: 10
- willingness to freeze forecast: 10 (UNKNOWN until conversation)
- FinOps/Finance involvement: 5

Public-only research cannot award willingness-to-freeze points.

## Prioritization

Tier A: 70–100
Tier B: 50–69
Below 50: hold unless new trigger evidence materially changes qualification.

A prospect whose migration is already complete and has no preserved original forecast should be downgraded for the forecast-error wedge, although it may still be usable for outcome-schema testing.

## Data-production objective

The first cohort is not optimized merely for number of customers. Prefer cases that can produce a comparable verified record:

- source estate captured before migration
- route and migration strategy known
- forecast frozen
- switching-cost categories explicit
- incentives separately evidenced
- pre/post cost evidence available
- comparable observation windows
- outcome evidence independent enough for benchmark inclusion

## Safety / external-action boundary

Research and prioritization are autonomous safe work.

External outreach, contracts, payment collection, access to private customer billing/telemetry, and provider incentive applications remain external actions and require the applicable authorization/channel.
