# ObraSignal — Ancillary Revenue & Transaction Monetization Architecture

**Strategic architecture directive — 2026-08-25**

This directive is subordinate to product-market fit, product quality and initial SaaS revenue. It does not create a parallel execution roadmap and does not authorize any partner, referral, transaction or finance monetization by itself.

## Economic model

- **SaaS = base revenue**
- **Transactions = upside**
- **Partner revenue = ancillary margin**
- **Supplier tools = second-side SaaS**
- **Aggregated intelligence = future enterprise revenue**

North star: **increase ECONOMIC VALUE CREATED BY OBRASIGNAL and capture a small, transparent share without damaging trust, independence, privacy, product quality or customer economics.**

## Sequencing

1. Phase 1 — prove value + SaaS.
2. Phase 2 — transaction facilitation.
3. Phase 3 — partner monetization.
4. Phase 4 — network/platform revenue.

This order may change only with strong evidence and an explicit master-queue decision.

## Candidate revenue vectors

Future candidates include Supply Edge procurement/transaction/referral economics; licensed trade-finance referrals; insurance/guarantee referrals; equipment/vehicle rental; accommodation; logistics; MicroWorks success fees; supplier-side SaaS; Trade Agent procurement-as-a-service; and aggregated anonymized market intelligence.

No candidate is authorized merely because it is technically possible.

## Non-negotiable ranking independence

**PAY-TO-RANK is prohibited.**

A supplier or partner may pay for software, access, processing, premium functionality or a transparently disclosed referral arrangement. Payment must never improve recommendation rank.

Recommendation ranking remains based on economic and execution fit such as:

- price / landed cost;
- quality;
- compliance;
- lead time;
- reliability;
- cash/payment terms;
- risk;
- contractor-specific economic fit.

Commercial remuneration is stored and evaluated in a separate monetization context. It is not an input to the ranking contract.

## Conflict-of-interest controls

Whenever ObraSignal can receive remuneration from a partner appearing in a recommendation:

1. the remuneration relationship must be represented explicitly;
2. ranking must be computed independently of remuneration;
3. disclosure must be technically possible and shown when legally or contextually relevant;
4. the contractor's economic objective remains the primary decision objective;
5. the decision and remuneration path must be auditable.

## Monetization gate

Before activating a monetization route, answer with evidence:

1. Does it improve or preserve customer experience?
2. Does it reduce cost or friction?
3. Does it create a conflict of interest?
4. Does it require licensing or regulated activity?
5. Could it damage trust?
6. Is expected margin sufficient to justify complexity and maintenance?
7. Can revenue, conversion, conflicts and customer impact be measured and audited?

If the gate fails: **DO NOT IMPLEMENT / DO NOT ACTIVATE.**

## Architectural contracts

The neutral domain interfaces are defined in `transaction_monetization_contracts.py`:

- `Quote`
- `Supplier`
- `Transaction`
- `Referral`
- `Partner`
- `Commission`
- `FinancingRoute`
- `InsuranceRoute`
- `Booking`
- `Conversion`

These objects describe economic events and relationships without implementing billing, lender activity, insurance intermediation or ranking bias.

Key design rule: a transaction may exist without monetization; monetization may be absent, pending, prohibited or external. `Commission` and `Referral` link to an economic event but never define its recommendation rank.

## Regulated routes

ObraSignal must not silently become a lender, insurer, broker or regulated intermediary. Financing and insurance routes point to authorized external partners and carry jurisdiction/regulatory state. Any future deeper role requires separate legal validation and master-queue promotion.

## Supplier-side SaaS

Potential supplier tools include RFQ management, analytics, lead qualification, demand intelligence and response automation. Supplier SaaS must be separable from contractor ranking so that paying for tools cannot buy recommendation preference.

## Aggregated intelligence

Future enterprise intelligence may use only appropriately aggregated, anonymized, non-identifiable information with minimum-cohort/privacy controls. Private contractor strategy, bids, margins, capacity, supplier choices or operational data must never be sold as identifiable intelligence.

## Measurement evolution

Subscription metrics remain important, but the economic system should eventually measure:

> **Useful economic volume originated or materially influenced by ObraSignal**

and distinguish value created from revenue captured. The existing `Q230_VALUE_CREATED` framework is the prerequisite measurement layer; monetization must not claim value it cannot evidence or double count.

## Queue relationship

This document is supporting architecture only. `master_execution_queue.py` remains the sole execution order. Monetization implementation stays GATED/FUTURE behind product core, Value Created, ACTION authorization and the relevant transaction capabilities (Supply Edge, TrustBridge/Trade Agent, Mobilize, MicroWorks).