# ObraSignal — Trade Agent + Supply Edge + TrustBridge

Status: official strategic architecture, queued behind current dependencies. This file does not activate outreach, financing, purchasing or supplier workflows.

## North-star outcome

ObraSignal should answer:

> What is the best technical, logistical and financial way to supply this project, who can actually deliver it, on what terms and with what risk — and how much of the process can be completed before the contractor must make a material decision?

This is not a marketplace, supplier directory or price-comparison feature.

## Integrated circuit

Opportunity/project evidence → BoQ/drawings/specification parsing → quantities/waste/need dates → technically admissible alternatives → supplier discovery local→international → RFQ → price/stock/logistics/compliance/payment terms → TrustBridge → SHADOW cash/margin/timing simulation → COMMAND recommendation → authorized Trade Agent action → OFFICE actuals → Outcome Graph / Contractor DNA / supplier learning.

A previous NO-GO may become CONDITIONAL GO only when evidence and economics genuinely change.

## Supply Edge

Optimize installed economic cost, not headline purchase price. Model material, accessories, quantity, waste, labour consequence, transport, logistics, lead time, project need date, FX/tariffs/insurance where applicable, financing/payment timing and supply risk.

Payment terms are transaction evidence, never assumptions. Canonical states:
- `PUBLISHED`
- `VERIFIED`
- `NEGOTIABLE`
- `APPROVED`
- `UNKNOWN`

Cash / Net 30 / Net 60 / Net 90 are transaction attributes, not permanent supplier badges.

SHADOW should compare nominal price with liquidity effect, working-capital usage, delivery risk and project timing. A higher quote can be economically better if it materially protects cash or execution.

## ObraSignal Trade Agent

The agent must identify itself as an authorized digital agent and never impersonate a real person.

Example:
> ObraSignal, acting as the authorized digital agent of Company ABC, requests a quotation for Project X.

Potential gated actions: prepare RFQs; request price/stock/lead time/delivery/documents; request Cash/30/60/90 alternatives; request trade-account assessment; send only authorized company/project information; follow up; normalize responses; request clarification; negotiate inside explicit limits; recalculate economics; escalate material decisions.

Principle: **AUTOMATE THE PROCESS. ESCALATE THE DECISION.**

### Autonomy levels
- `LEVEL 0 — ADVISE`: analysis only.
- `LEVEL 1 — PREPARE`: prepare actions, transmit nothing.
- `LEVEL 2 — CONTACT`: contact approved counterparties with authorized identity/context.
- `LEVEL 3 — NEGOTIATE`: negotiate only inside explicit boundaries.
- `LEVEL 4 — EXECUTE LOW RISK`: execute pre-authorized low-risk operations with audit and cancellation/rollback where possible.

Material legal/financial obligations, debt, financing, guarantees, insurance commitments, important purchases, material technical substitutions or contract changes require appropriate authorization and, where necessary, explicit human approval. Silence is never authorization.

## TrustBridge

TrustBridge reduces bilateral commercial uncertainty; it never certifies that a buyer will pay or a supplier will perform.

### Trade Passport
Potential authorized evidence: KYB/active company identity, verified project/award evidence, verified trade volume, payment timing, proven disputes, licensed financial/insurance evidence and operating history.

### Supplier Passport
Potential evidence: KYB, delivery punctuality, quality/conformity, documentation/certification performance, quote-vs-final price, promised-vs-actual lead time, disputes and licensed financial/insurance evidence where relevant.

### Transaction Confidence
Evaluate the specific combination:
`buyer + supplier + countries + project + amount + currency + payment term + exposure + evidence + history`.

Outputs must be probabilistic and explainable, separating fact, estimate, inference, assumption and confidence.

### Project-backed trust
A verified project or awarded public contract may improve transaction context but is never a payment guarantee.

### Credit orchestration
When direct supplier credit is unavailable, seek lawful routes such as open trade credit, trade-credit insurance, licensed partner early-payment/deferred-buyer structures, guarantees or partial-upfront/deferred-balance arrangements.

ObraSignal should normally orchestrate authorized partners rather than become a bank, lender, factor or insurer. Regulated-credit/insurance flows require jurisdiction-specific legal/product review before PILOT or PRODUCTION.

## Supplier Portal

A supplier must not need an ObraSignal subscription merely to answer an RFQ. A secure scoped expiring link may show the minimum necessary buyer/project/quantity/specification/location/date context and accept price, stock, lead time, transport, payment terms, certificates and documents.

Required controls: token scope, expiry/revocation, audit, least disclosure, safe document handling and clear privacy/data notices.

## Learning loop

OFFICE/outcomes may capture actual consumption, waste, delivery timing, price variance, conformity, productivity effect, invoice/payment timing and disputes. These can improve Supplier Truth, Trade Passport, Contractor DNA and SHADOW calibration. Negative evidence requires provenance, correction/dispute mechanisms and proportional retention.

## Promotion gates

### Supply Edge
Validate BoQ/spec extraction, safe technical equivalence, installed/landed-cost usefulness and current lawful supplier evidence.

### TrustBridge
Validate lawful data sources by jurisdiction, explainability/calibration, correction rights and partner orchestration without ObraSignal becoming regulated principal.

### Trade Agent
Validate machine-enforceable authority scopes, explicit agent identity, auditability/revocation and hard prevention of unauthorized commitments.

### Supplier Portal
Validate low-friction response, secure scoped links and reliable quote normalization.

### Integrated Trade Loop
Promote only if it measurably improves margin, liquidity, delivery reliability or decision time; SHADOW models terms/risk credibly; COMMAND returns 2–5 valid decisions rather than a supplier dump; and legal/security/authorization gates pass in each launch jurisdiction.

No capability progresses because a demo looks impressive.
