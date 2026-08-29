# ObraSignal — Synthetic Assisted Fit Matrix v0.1

Status: `SYNTHETIC / REPOSITORY-SAFE / NOT CUSTOMER EVIDENCE`

Purpose: prove the decision structure for an assisted validation conversation without inventing a real customer's eligibility, pain, intent or willingness to pay.

## Synthetic company profile

- Company ID: `SYNTHETIC-AVAC-01`
- Geography appetite: North + Lisbon metro = `ASSUMPTION FOR FIXTURE`
- Work preference: AVAC installation + maintenance = `ASSUMPTION FOR FIXTURE`
- Preferred contract value: €100k–€600k = `ASSUMPTION FOR FIXTURE`
- Public-works contractor authorization / alvará class: `UNKNOWN`
- F-gas certification: `UNKNOWN`
- TRM/other technician qualification: `UNKNOWN`
- Available crew capacity September 2026: `UNKNOWN`
- Interest in 36-month recurring maintenance: `UNKNOWN`
- Appetite for multi-lot municipal programs: `UNKNOWN`

No row below may be promoted to `QUALIFIED` while any mandatory requirement needed for that procedure is UNKNOWN.

| Shortlist item | Observable fit | Mandatory/decision facts still needed | Safe fixture classification | Why |
|---|---|---|---|---|
| Paços de Ferreira municipal pools — AVAC requalification — €490k | AVAC scope, value inside synthetic preference, North geography | Required public-works authorization/subcategory/class; crew capacity; complete tender documents | `WORTH_INVESTIGATING / ELIGIBILITY_UNKNOWN` | Strong scope/value signal, but legal/operational eligibility is not established. |
| Lisbon SSCML — 36-month AVAC maintenance — €150k | AVAC maintenance, Lisbon geography, value inside range | F-gas applicability/certification; qualified technicians; appetite for recurring maintenance; capacity | `WORTH_INVESTIGATING / CAPABILITY_UNKNOWN` | Commercial pattern fits the broad fixture, but certifications and recurring-service appetite are unknown. |
| Almada — AVAC maintenance/repair — 3 lots — €410,306.94 total | AVAC maintenance, Lisbon metro, lot structure may permit smaller commitment | Lot-specific documents; certifications; capacity; appetite by lot | `WORTH_OPENING / LOT_FIT_UNKNOWN` | Lotting could improve fit but must be assessed at lot/document level. |
| Guimarães — AVAC/AQS/gas maintenance | AVAC component, North geography | Procedure documents; AQS/gas capability; certifications; scope boundaries; contract value | `WORTH_OPENING / SCOPE_UNKNOWN` | Mixed-system work may be outside the company's real operating scope; value is not captured in the recovered shortlist. |

## Required profile fields surfaced by this fixture

The assisted conversation should seek evidence for these fields, not merely ask whether the user likes the shortlist:

1. geography actually served;
2. preferred project/service types;
3. preferred contract-value range;
4. public-works authorization/subcategories/classes;
5. regulated technical certifications where relevant;
6. crew/capacity window;
7. maintenance vs project-work appetite;
8. lot-size/appetite constraints;
9. exclusions (AQS, gas, electrical, civil accessories, etc.);
10. information that is still missing before bid/no-bid.

## Response-capture rubric

For each real prospect response, capture independently:

- `RELEVANCE`: `IRRELEVANT | WORTH_OPENING | WORTH_INVESTIGATING | LIKELY_BID | UNKNOWN`
- `ALREADY_KNOWN`: `YES | NO | UNKNOWN`
- `WHY`: verbatim-enough reason supplied by the prospect
- `MISSING_DECISION_INFO`: fields the prospect says are still needed
- `WORKFLOW_IMPACT`: whether earlier/repeated receipt would change actual work; `YES | NO | UNKNOWN`
- `CURRENT_PROCESS`: customer-reported current discovery/triage process
- `TIME_COST`: only if explicitly reported; otherwise `UNKNOWN`
- `TEST_INTENT`: `YES | NO | UNKNOWN`
- `PRICE_DISCUSSION`: exact observed state only; no inference
- `PAYMENT`: exact observed state only; no inference

## Evidence semantics

- `WORTH_OPENING` is not a qualified opportunity.
- `LIKELY_BID` is prospect-reported intent, not a bid submission.
- `TEST_INTENT=YES` is not a pilot outcome.
- A free assisted test is not willingness to pay.
- A price quote is not payment.
- Payment is not retention.
- Silence is not rejection.
- Public tender participation does not prove discovery pain.

## Pass condition for this repository-safe milestone

PASS when every shortlist item can be routed to a bounded classification while preserving mandatory UNKNOWNs and when the rubric can capture real future evidence without semantic inflation.

Result: `PASS_BY_INSPECTION / SYNTHETIC ONLY / NO MARKET PROOF`.
