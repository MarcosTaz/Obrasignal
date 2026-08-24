# ObraSignal — Privacy & Non-Intrusion Principle

Status: **permanent cross-cutting product and architecture constraint**. This is not a future feature gate and is not permission to collect more data.

## Governing rule

> **Minimum data required, maximum intelligence extracted.**

ObraSignal should feel informed enough to help, never as though it is surveilling the contractor.

The system must be useful with public data plus the smallest practical amount of information voluntarily provided by the company. Deeper integrations are optional accelerators, not prerequisites for basic product usefulness.

## Public-first, minimal-input default

The default operating model is:

1. public / lawfully reusable external data;
2. project or company facts intentionally entered by the user;
3. optional scoped integrations only when a clear decision benefit justifies them.

Do not assume access to:
- bank accounts;
- accounting ledgers;
- payroll;
- email inboxes;
- continuous GPS/location;
- employee communications;
- full document repositories;
- unrestricted calendar access;
- other sensitive internal systems.

If a useful recommendation can be produced without a sensitive integration, prefer the lower-data path.

## Optional integrations

Every deeper integration must be:
- **optional** — declining it must not break unrelated functionality;
- **granular** — request only the narrow resource/scope needed;
- **purpose-bound** — state the decision or workflow it improves;
- **reversible** — the company can disconnect/revoke it;
- **inspectable** — users can understand what categories of data are being used;
- **proportionate** — collection depth must match economic benefit and risk;
- **least-privilege** — read/write scope must be no broader than necessary.

Where possible, support progressive disclosure: ask for more data only when it materially improves a concrete decision.

## Recommendation provenance

For every material recommendation, ObraSignal should be able to explain:
- which public sources were used;
- which company-provided facts were used;
- which integration-derived facts were used;
- which values are estimates, assumptions or inferences;
- what changes if an optional data source is removed or unavailable.

A recommendation should not hide dependence on a sensitive data source behind a generic score.

## Company data isolation

Information identifiable to one company must not be used improperly to benefit another company.

Company-specific confidential data may improve that company's own Contractor DNA, SHADOW, COMMAND and ACTION decisions, but cross-company learning must use privacy-preserving aggregation or genuinely non-identifying abstractions with appropriate safeguards.

Do not expose competitor-sensitive pricing, payroll, productivity, supplier terms, project economics, customer lists, cash position or other confidential facts to another contractor.

## Workforce non-intrusion

Do not build employee surveillance into OFFICE, MOBILIZE, DEAD TIME, CREW ECONOMICS, MICROWORKS or CAPACITY systems.

Continuous worker GPS is not a default sensor. When location is genuinely needed, prefer the least intrusive useful representation, for example:
- project/site location;
- company base;
- vehicle/equipment location when operationally justified;
- coarse or event-based worker location only when explicitly authorized and necessary.

Avoid continuous behavioural monitoring where an event, schedule, declared availability or project-state signal can answer the decision question.

Workforce data should primarily improve company-level capacity, safety, scheduling and economic decisions, not become an employee punishment or ranking system.

## OFFICE boundary

OFFICE is a decision sensor layer, not a data-hoarding layer.

Before adding any internal sensor ask:
1. Which material decision becomes better?
2. Can public data or a smaller voluntary input answer it sufficiently?
3. What is the minimum field set and refresh cadence required?
4. Is continuous collection actually necessary?
5. Can the user inspect, revoke and delete/disconnect the source?
6. Does the benefit justify sensitivity and maintenance?

If the answer is weak, do not collect the data.

## SHADOW / COMMAND boundary

SHADOW must tolerate incomplete company data and express uncertainty rather than pressure the user into connecting sensitive systems.

COMMAND should distinguish:
- recommendation possible with current data;
- recommendation confidence limited by missing data;
- optional additional datum that could materially improve the decision.

The system should say, in effect: **“I can already help with what I know; sharing X would improve Y.”** It should not imply that maximum integration depth is inherently better.

## ACTION boundary

ACTION authorization and data authorization are separate.

Permission to read a data source does not imply permission to contact, purchase, negotiate, book, commit funds or create legal obligations. Likewise, authorization to perform an action does not grant broad access to unrelated company data.

Both scopes must remain explicit and independently revocable.

## TrustBridge boundary

TrustBridge should prefer independently verifiable, proportionate evidence and licensed sources before requesting invasive internal financial data.

A Trade Passport or Transaction Confidence assessment must not require unrestricted bank/accounting/payroll access by default. When stronger verification is commercially necessary, use the minimum evidence needed for that transaction and make the purpose clear.

## Data lifecycle

Where ObraSignal stores voluntary or integration-derived company data, architecture should support:
- purpose-aware retention;
- deletion or disconnection where applicable;
- credential/token revocation;
- stale-data marking;
- auditability of sensitive reads/writes where justified;
- no indefinite retention merely because storage is cheap.

## Product UX

Privacy should be understandable without reading legal text.

For integrations and material recommendations, the interface should make it easy to answer:
- **What am I sharing?**
- **Why does ObraSignal need it?**
- **What benefit do I get?**
- **Can I still use the product without it?**
- **How do I disconnect it?**
- **Which data influenced this recommendation?**

## Promotion test for every new capability

Before RESEARCH → PROTOTYPE → PILOT → PRODUCTION promotion, ask:
1. Can this capability work with less data?
2. Are all requested private data fields decision-relevant?
3. Is the cadence no more frequent than necessary?
4. Is continuous tracking avoidable?
5. Are scopes optional, granular and reversible?
6. Can the recommendation expose its data provenance?
7. Is company-confidential information isolated from other companies?
8. Does the economic value justify the sensitivity?

Failure on a material privacy/non-intrusion question blocks promotion until redesigned.

## Final product test

The desired user perception is:

> **“ObraSignal knows enough to make unusually good decisions from very little data, and I remain in control of everything deeper that I choose to share.”**

Not:

> “ObraSignal needs to watch my company in order to work.”
