# ObraSignal — Contractor Intelligence Operating System

**Canonical strategic architecture — 2026-08-24**

This document evolves ObraSignal cumulatively. It does not restart or invalidate correctly completed market research, source validation, connectors, commercial scoring, security gates, runtime work, or the 2026-08-24 international scope rebase.

## North star

ObraSignal is no longer designed only as construction-opportunity discovery. Its long-term product identity is:

> **CONTRACTOR INTELLIGENCE OPERATING SYSTEM**

The governing question is:

> **Given what we know about the market, the company, its assets, future demand, capacity, execution, capital, suppliers, risk and outcomes, what is the best next economic and operational decision for this contractor?**

The product must become an increasingly reliable decision layer, not a larger collection of software features.

## One execution system

`master_execution_queue.py` is the sole canonical execution queue for the project. New market work, product capabilities, architecture work, research, prototypes and strategic hypotheses must enter that same ordered queue.

There must not be independently managed international, OFFICE, AI, marketplace or future-feature roadmaps competing for execution. Supporting documents may describe domains, but they do not create a second execution queue.

Sequence is decided by:

1. dependencies;
2. economic value;
3. learning value;
4. technical reuse;
5. strategic moat;
6. risk;
7. maintenance burden;
8. timing.

A capability must not jump the queue because it is visually impressive or strategically fashionable.

## Two horizons

### Horizon A — current execution

Continue source implementation, market coverage, commercial validation, product core, security, legal/reuse, QA, frontend/backend, deployment and tests.

### Horizon B — future architecture

Every current decision must be checked for whether it unnecessarily blocks or duplicates future SIGNAL, OFFICE, DNA, SHADOW, COMMAND or ACTION capabilities.

Do not build the future prematurely. Do not make the future unnecessarily expensive.

## Six-layer target architecture

### SIGNAL — the external world

Purpose: detect potential economic activity before, during and after procurement.

Canonical signal classes may progressively include:
- TENDER;
- PROCUREMENT_PLAN;
- FORECAST;
- CAPITAL_PROJECT;
- MARKET_DIALOGUE;
- CONTRACT_EXPIRY;
- AWARD;
- CONTRACT;
- BUYER_SIGNAL;
- COMPETITOR_SIGNAL;
- ASSET_SIGNAL;
- OBLIGATION_SIGNAL;
- SUPPLIER_SIGNAL;
- RESCUE_SIGNAL.

SIGNAL answers: **What is happening or likely to happen outside the company?**

**Immediate architectural consequence:** non-TENDER signals must not be silently persisted as legacy tenders merely because the original product schema was tender-centric. A generic signal contract and provenance-first persistence path must exist before a planning/forecast connector is promoted to production.

### OFFICE — the company as a sensor

OFFICE is not permission to build a generic ERP. It captures only operational data that materially improves decisions.

Potential sensors include workforce, team availability, clock-in/out, calendars, live jobs, progress, daily reports, incidents, hours, materials, costs, RFQs, documents, deadlines and future capacity.

Rule: **integrate rather than rebuild** generic accounting, payroll, full email, Word, Excel, storage and calendar products when their data can be safely imported.

Crew-facing UX must remain radically simple and privacy-proportionate. No invasive tracking.

### DNA — observed operating truth

Contractor DNA learns from **predicted versus actual** instead of trusting declarations indefinitely.

It may learn real productivity, margin, estimating error, waste, duration, mobilisation, payment behaviour, supplier performance, performance by work type/team/geography, win/loss/no-bid and cash behaviour.

DNA is not an employee-punishment system. It exists to improve company-level decision quality.

### SHADOW — probabilistic future company

SHADOW compares alternative futures rather than pretending to know one future.

It should progressively model cash, workforce utilisation, backlog, margin, guarantees, equipment, management capacity, supplier risk, overlap, mobilisation, bid capacity and probability.

The strategic question is portfolio-level:

> **Which combination of opportunities and operating choices maximises expected return without violating the contractor's constraints?**

### COMMAND — next-best decision

COMMAND consumes SIGNAL + OFFICE + DNA + SHADOW and answers:

> **WHAT SHOULD WE DO NEXT?**

It must prioritise, quantify, explain confidence and uncertainty, and separate fact from inference.

The desired output is not a dashboard of everything known. It is a small number of economically important next actions with evidence.

### ACTION — execute safely

When safe and authorised, recommendations should progress into execution: RFQ preparation, supplier comparison, partner outreach, buyer follow-up, financing-pack preparation or other high-value workflows.

ACTION must never bypass procurement rules, legal authority, consent, finance controls, competition law, privacy or security.

## Strategic differentiation hypotheses

These remain important hypotheses, not unproven exclusivity claims.

### Future Demand Engine / Asset Clock

Connect asset age, condition, inspections, energy performance, prior interventions, budgets, grants, policy, permits, climate and lifecycle to predict where physical construction demand is likely to emerge before a tender exists.

### Forced Demand / Obligation-to-Opportunity

Translate regulation, standards, safety, accessibility, environmental rules, inspections, grants, expiry and enforcement into:

> **rule → affected assets → physical work → value → timing → suitable contractors**

Concept: **LAW → BILL OF WORKS**.

### Dynamic Eligibility / Opportunity Unlock

Replace binary GO/NO-GO where appropriate with:
- NATIVE GO;
- CONDITIONAL GO;
- UNLOCKABLE;
- HARD NO-GO.

For workforce, equipment, qualification, partner, capital, guarantees, insurance, certification or references, test whether a legal and economically rational unlock plan exists.

### Supply Edge

Use BoQ/specification intelligence, equivalent products, suppliers, compliance, landed cost, logistics, FX, tariffs, finance, lead time, supply risk, RFQs and value engineering to improve bid economics.

Supplier ranking must remain independent; no disguised pay-to-rank.

### Portfolio optimisation

Do not optimise one bid at a time when resources are shared. Model combinations of opportunities and constraints as contractor capital allocation.

## Additional queued capabilities

The master queue also tracks:
- Contractor Growth Simulator;
- Live Capacity Network;
- Rescue Mode;
- Work Package Release Prediction;
- Proof / Evidence Graph;
- regret prevention (GOOD NO-BID / MISSED OPPORTUNITY);
- Value Created by ObraSignal;
- Forward Work Coverage;
- Capacity Value at Risk;
- Obligation Pressure;
- explainable company/shadow health;
- privacy-preserving benchmark network;
- chain-reaction intelligence for second- and third-order demand.

None is automatically authorised for implementation merely by being listed here.

## Proof / Evidence contract

Important recommendations must support:

- **WHY?** reasoning;
- **SHOW ME** sources, data and calculations;
- **WHAT IF?** sensitivity to assumptions.

Every material recommendation should distinguish:
- fact;
- estimate;
- inference;
- assumption;
- confidence.

No opaque single score may substitute for a complex risk explanation.

## Feature maturity gates

Large capabilities progress only through:

`RESEARCH → PROTOTYPE → PILOT → PRODUCTION`

Promotion requires evidence appropriate to the capability. Examples:
- Future Demand: predictive precision, useful lead time, actionable output, willingness to pay;
- Unlock: correct blockers, legal solutions, positive economics, actual user action;
- Shadow: calibrated scenarios, useful decisions, understandable uncertainty and user trust.

A visually successful demo is not a production gate.

## Anti-bloat rules

Do not build a generic CRM, ERP, HR suite, accounting system, email client, spreadsheet editor, file store, chat system or marketplace merely to increase surface area.

Deeply build only what:
1. improves intelligence;
2. captures proprietary decision-relevant data;
3. reduces decision friction;
4. automates high-value action;
5. creates legitimate retention through usefulness.

Complexity belongs in the engine; the decision experience must remain simple.

## Data and legal standard

For every source and new data domain verify officiality, completeness, freshness, legal access, reuse rights, rate limits, stability, attribution, machine readability, commercial reuse and retention requirements.

Never use CAPTCHA bypass, authentication circumvention, prohibited scraping, rate-limit bypass or unlawful reuse.

## Moat model

Long-term defensibility should accumulate through:
- Market Graph;
- Asset Graph;
- Buyer Graph;
- Supplier Graph;
- Contractor Graph;
- Company DNA;
- Outcome Graph;
- Shadow History.

The moat must not depend on an LLM alone.

## Value measurement

Where causally defensible, distinguish **measured** from **estimated** value across qualified opportunity value, margin improvement, sourcing savings, risk avoided, hours saved, idle capacity recovered, unlocked opportunities, financing stress avoided, bad bids avoided and contractual value protected.

Never fabricate ROI.

## Brand direction

The strategic category is closer to **Contractor Decision Intelligence** / **Contractor Intelligence Operating System** than tender software, ERP or marketplace.

Conceptual promise:

> **See what is coming.**  
> **Know what you can win.**  
> **Build the capacity to capture it.**  
> **Protect the economics.**  
> **Decide what to do next.**

## Permanent decision test

Before a significant component is promoted in the master queue, ask:
1. Does it materially improve decision quality?
2. Does it solve a real economic problem?
3. Does it create data that improves the system?
4. Is it hard to replace or meaningfully differentiated?
5. Is it reusable?
6. Is the need sufficiently frequent?
7. Will the customer understand the value?
8. Can it eventually produce action?
9. Does benefit justify maintenance?
10. Does it move ObraSignal toward legitimate indispensability?

If the answer is materially weak, do not build it because it sounds interesting.

## Governing product principle

> **ObraSignal should know enough of the right things to answer better than any isolated tool: “What should this company do now to be in a better economic position tomorrow?”**
