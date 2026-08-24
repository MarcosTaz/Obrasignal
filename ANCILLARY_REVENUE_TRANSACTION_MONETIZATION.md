# ObraSignal — Ancillary Revenue & Transaction Monetization Constitution

Status: ARCHITECTURE / GATED. This document preserves future monetization optionality; it does not activate billing, commissions, partner routing or paid ranking.

## North star

ObraSignal optimizes **economic value created for the contractor first** and may capture a small, transparent share of value it genuinely helps create.

Revenue order:

1. **SaaS = base revenue** — prove product value and willingness to pay first.
2. **Transactions = upside** — monetize facilitation only after useful transaction loops exist.
3. **Partner revenue = ancillary margin** — only through lawful, value-adding partners.
4. **Supplier tools = second-side SaaS** — software value, never ranking privilege.
5. **Aggregated intelligence = future enterprise revenue** — only aggregate, anonymous, non-identifiable outputs with privacy/competition safeguards.

Commercial sequencing is therefore:

**VALUE PROOF + SaaS → TRANSACTION FACILITATION → PARTNER MONETIZATION → NETWORK/PLATFORM REVENUE**

Do not invert this order without strong evidence.

## Permitted future revenue vectors

Subject to the monetization gate and jurisdiction-specific legal review:

- Supply Edge: procurement/transaction fees, transparent supplier referrals, logistics referrals, lawful volume rebates.
- Trade finance / net terms: referral or revenue share through authorized financial partners; ObraSignal does not become a lender by default.
- Insurance / guarantees: referral or integration revenue through appropriately authorized partners.
- Equipment / vehicle rental: commission on bookings actually originated by MOBILIZE / Capacity Optimizer.
- Accommodation: referral/booking revenue when ObraSignal originates project-related lodging.
- Logistics: referral or transaction revenue on freight/transport originated by the platform.
- MicroWorks / Capacity Market: small transparent success fee on actually closed work when economics and market design justify it.
- Supplier-side SaaS: RFQ management, analytics, lead qualification, demand intelligence and response automation.
- Trade Agent: procurement-as-a-service, managed RFQ or lawful success-based fees where appropriate.
- Aggregated market intelligence: only aggregated, anonymized, non-identifiable intelligence; never contractor-private strategy/data for resale.

## Non-negotiable independence rule

**NO PAY-TO-RANK.**

A supplier/partner may pay for software, processing, premium tooling, a transparently disclosed referral arrangement or another lawful service. It may not purchase a better recommendation.

Recommendation/ranking inputs remain economic/product inputs such as:

- price / installed economic cost;
- quality;
- compliance;
- delivery time;
- reliability;
- cash/payment terms;
- risk;
- economic fit.

Commercial relationship with ObraSignal is **not** a positive ranking feature.

If a partner cannot be separated from ranking influence technically and organizationally, do not activate that revenue model.

## Conflict-of-interest control

Whenever ObraSignal may receive compensation from an entity present in a recommendation or route:

- compensation metadata must be represented separately from decision/ranking features;
- ranking code must not consume commission/referral amount as a favorable signal;
- relationship and remuneration must be auditable;
- disclosure must be possible and shown when legally/materially relevant;
- unbiased alternatives must remain eligible where economically relevant;
- the primary recommendation continues to optimize contractor economics;
- a policy/kill switch must be able to disable monetization without disabling the underlying useful capability.

Recommended invariant for future implementation:

`ranking_result(inputs_without_commercial_compensation) == ranking_result(inputs_with_only_compensation_metadata_changed)`

subject to deterministic tie-breaking that is itself compensation-independent.

## Monetization gate

No ancillary revenue path is enabled merely because it is technically possible.

Before activation, answer with evidence:

1. Does it improve or at least preserve customer experience/economics?
2. Does it reduce cost or friction, or create measurable value?
3. Does it create a conflict of interest; if so, is the conflict technically controlled and transparently governable?
4. Does it require licence, authorization, regulated status or jurisdiction-specific partner structure?
5. Could it damage trust or perceived independence?
6. Is expected margin sufficient to justify engineering, support, compliance and audit complexity?
7. Can conversion, value created, remuneration and recommendation independence be measured and audited?

Any material failure → **DO NOT IMPLEMENT / DO NOT ACTIVATE**.

## Contract-first optionality

Future canonical-model work should preserve clean, versioned concepts for the following where the domain requires them:

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

This is not permission to create these tables/services now. The requirement is to avoid future domain models that make lawful monetization impossible without a rewrite.

### Boundary rule

Transaction/economic facts and monetization facts are separate concerns.

Example conceptual separation:

- `SupplierQuote` describes the supplier's offer.
- `EconomicEvaluation` describes landed/cash-adjusted contractor economics.
- `Recommendation` describes the decision result.
- `Referral` records that ObraSignal originated a route.
- `Commission` records compensation terms/accrual independently.

A `Commission` must never be a hidden input into `EconomicEvaluation` or ranking.

## Provenance and audit requirements

If implemented later, monetized transaction paths must preserve:

- origin capability / decision / action;
- partner identity and authorization status where applicable;
- customer consent/authority where required;
- referral/booking/transaction identifiers;
- conversion state;
- compensation basis, amount/currency and status;
- disclosure state where relevant;
- jurisdiction and applicable policy version;
- evidence supporting recommendation independence;
- reversals/refunds/chargebacks where applicable.

No fabricated attribution: influenced volume and originated volume must be distinguishable.

## Metrics

SaaS metrics remain primary until value and repeatability are proven.

Later, add carefully separated measures such as:

- economic value created / protected;
- useful transaction volume originated by ObraSignal;
- useful transaction volume influenced by ObraSignal;
- conversion rate;
- contractor savings/contribution after all costs;
- ancillary gross/net margin;
- partner revenue by vector;
- disclosure/conflict-control exceptions;
- recommendation-independence test failures.

Do not use gross transaction volume as proof of customer value.

## Privacy / aggregate intelligence

Aggregated intelligence is FUTURE and subject to the Privacy & Non-Intrusion constitution.

Never sell:

- identifiable contractor strategy;
- private bids/quotes;
- confidential supplier/customer behavior tied to identifiable firms;
- data whose aggregation threshold permits practical re-identification.

Any future benchmark/data product needs aggregation thresholds, purpose limitation, competition-law review where relevant, and explicit prevention of cross-company misuse.

## Product/UX principle

Do not turn ObraSignal into an affiliate catalogue.

Monetization should normally be invisible to the workflow except where disclosure/choice is material. The user sees the economically best decision and can inspect evidence. Commercial compensation must not create recommendation noise.

## Queue/gate intent

Ancillary monetization remains **GATED** until underlying value and transaction loops exist. It must not outrank current PMF, SaaS proof, Signal reliability, Evidence/Outcome architecture or the operational pilots that establish real economic value.

North-star question:

**How much real economic value is ObraSignal creating or legitimately originating, and can we capture a small aligned share without reducing trust, independence, privacy, product quality or customer economics?**
