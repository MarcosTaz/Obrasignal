# ObraSignal Opportunity Financial Exposure / Bid Economics v0

## PURPOSE

Bid Economics v0 is a deterministic, one-opportunity-at-a-time economic skeleton for pre-execution decision support. It makes four things separate and visible: **profit, cash, exposure and uncertainty**.

It does not decide whether to pursue an opportunity.

## NON-GOALS

Not implemented here: portfolio optimisation/SHADOW, Monte Carlo, accounting/ERP, payroll, tax/VAT engines, supplier discovery, BOQ extraction, crew optimisation, bank integrations, automatic bid pricing or GO/NO-GO.

## ECONOMIC MODEL

`BidEconomicsInput -> evaluate_bid_economics(...) -> BidEconomicsAssessment`.

The engine is stateless and contains no external API/LLM call. Same economic input + same policy + same injected timestamp produces the same assessment.

`economic_fit.py` remains a separate commercial-review filter. Bid Economics does not reuse its float parser for monetary arithmetic because that module intentionally scores fit rather than calculating project economics.

## FACT / ESTIMATE / ASSUMPTION / UNKNOWN

Material economic values and cost components carry an `InputBasis`. Unknown amounts remain `None`; they are never converted to zero. A known zero is valid and semantically distinct from unknown.

Source/basis text may identify supplier quote, historical estimate, manual assumption or another provenance supplied by the caller.

## MONEY AND CURRENCY

All calculations use `Decimal` through the immutable `Money` type. Money requires a three-letter currency code and rejects NaN/Infinity.

There is no FX engine in v0. Any attempted arithmetic across currencies fails closed with `MULTI_CURRENCY_UNRESOLVED`.

## REVENUE BASIS

Revenue is explicitly labelled as one of:

- `PUBLISHED_ESTIMATED_VALUE`
- `BID_PRICE`
- `TARGET_PRICE`
- `AWARD_VALUE`
- `UNKNOWN`

A published estimated value is therefore not silently represented as guaranteed revenue.

## COST COMPONENTS

Supported categories are LABOUR, MATERIAL, EQUIPMENT, SUBCONTRACT, MOBILIZATION, PRELIMINARIES, INSURANCE, BONDING, FINANCING, OVERHEAD, CONTINGENCY and OTHER.

Each component also has a nature:

- `DIRECT` — execution cost directly attributable to delivery;
- `INDIRECT` — execution cost such as preliminaries/overhead/contingency;
- `BID_PREPARATION` — pursuit cost incurred before award.

Bid preparation is never automatically included in project execution cost, preserving the lost-bid/sunk-cost boundary.

## MARKUP VS MARGIN

For cost 100 and price 125:

- profit = 25;
- markup = profit / cost = 25%;
- margin = profit / revenue = 20%.

Zero revenue yields undefined margin rather than division by zero.

## BREAK-EVEN AND TARGET-MARGIN PRICE

Economic break-even price equals known total execution cost. It is deliberately not named “minimum bid”.

For target margin `m`, target-margin price is `cost / (1 - m)` with `m < 100%`.

## WORKING CAPITAL

V0 only estimates peak working-capital requirement when enough coarse inputs exist:

- total known execution cost;
- project duration in months;
- contractual or expected payment delay.

The conservative coarse model is:

`monthly burn = execution cost / duration months`

`lag funding = min(total execution cost, monthly burn * payment days / 30)`

`working capital = max(0, lag funding + retained revenue - advance payment)`

This is intentionally not a detailed certification/cash-flow simulator. Longer payment lag cannot reduce the estimate under otherwise identical inputs. Advance payment can reduce it. Retention delays cash and does not increase revenue.

If inputs are insufficient, working capital remains unknown rather than being fabricated.

## PAYMENT TERMS

Structured terms: CASH, NET30, NET60, NET90, CUSTOM and UNKNOWN. Contractual days and expected/observed payment days are separate. Expected delay overrides the contractual term only for the cash-exposure calculation.

Retention and advance percentages are optional explicit inputs; there are no universal defaults.

## BONDING AND INSURANCE

Guarantee amount is exposure, not cost. `GuaranteeExposure` therefore separates guarantee amount from fee. Bid/performance/advance/retention guarantee names are caller-supplied `kind` values in v0 without inventing additional business policy.

Insurance exposure/coverage likewise remains separate from insurance premium cost, which may be represented as a cost component.

## SCENARIOS

Every known cost component carries MINIMUM, PROBABLE and PRUDENT amounts. PRUDENT may equal but cannot be below PROBABLE for a component. MINIMUM is a plausible low-cost case, not a fantasy best case.

The engine calculates each scenario independently and emits deterministic negative-margin warnings for probable/prudent cases.

## WHAT-IF

`recalculate_bid_economics` supports only validated structured overrides in v0:

- expected payment days;
- material-cost multiplier;
- labour-cost multiplier.

Arbitrary formulas or executable expressions are not accepted.

## MISSING INPUTS AND CONFIDENCE

Missing revenue, cost components, payment terms and bonding inputs are explicit. Unknown cost lines block execution-cost, profit and margin calculation instead of becoming zero.

Confidence is qualitative (`HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`) and based on calculability/completeness, not invented probability.

## WARNINGS

Current deterministic warnings can include:

- `NEGATIVE_PROBABLE_MARGIN`
- `NEGATIVE_PRUDENT_MARGIN`
- `HIGH_WORKING_CAPITAL` when an explicit same-currency policy threshold exists
- `MISSING_MAJOR_COST`
- `BONDING_UNKNOWN`
- `PAYMENT_TERM_UNKNOWN`

Warnings are economic observations, never pursuit decisions.

## TENANT PRIVACY

Bid Economics v0 is stateless and does not persist company economics. `tenant_id` is mandatory in the input and assessment and participates in the input fingerprint, preventing two company contexts from being represented as the same assessment identity.

No bank account, payroll, bank statement or accounting-system access is required.

Any future saved-assessment/API layer must enforce authenticated tenant ownership before reading or writing company-specific economics.

## INPUT FINGERPRINT / STALENESS

A deterministic SHA-256 fingerprint covers the complete economic input plus policy. A caller can compare fingerprints after opportunity value, requirements, mobilisation or other inputs change and mark the previous assessment stale without duplicating the platform's future change-detection graph.

## MOBILIZE / REQUIREMENTS / READINESS BOUNDARIES

At the inspected `main` baseline, MOBILIZE is registered as RESEARCH and no production public runtime contract for Mobilize/Requirements/Readiness economics exists. Therefore v0 does not couple to them. Their future outputs may populate normal cost/guarantee/insurance inputs through public contracts.

Mobilisation currently degrades gracefully to explicit manual/estimated/unknown cost components.

Readiness may consume the presence of missing economic inputs but Bid Economics does not decide overall readiness.

## API / UI

No persistence/API/UI surface is added in v0. This is deliberate: the repository currently has no canonical private economics storage contract and Q090 Company State is still queued. The safe integration surface is the pure domain API.

A future authenticated endpoint can wrap the engine without changing the calculation contract. UI priority should remain probable margin, prudent margin, peak cash exposure and major unknowns rather than exposing every accounting line.

## SECURITY

The engine accepts typed/structured values only. It rejects malformed/non-finite Decimal values, invalid currency shapes, negative costs, invalid percentages and invalid payment days. No SQL, HTML or arbitrary expression evaluation is present in the calculation path.

Because v0 is stateless, there is no cross-tenant persistence surface, SQL injection surface or stored-XSS surface introduced by this module.

## TESTS

`test_bid_economics.py` covers monetary precision, margin/markup, break-even, target margin, unknown-vs-zero, multi-currency, NaN/Infinity, negative cost, scenario ordering, payment lag, advance, retention, guarantee exposure, bid-preparation separation, what-if, missing/zero revenue, determinism, tenant fingerprint separation, absence of automatic pursuit decisions and huge Decimal values.

`test_economic_fit.py` remains an explicit regression gate for the pre-existing fit engine.

## KNOWN LIMITATIONS

- Working capital is intentionally coarse and requires duration + payment lag + known execution cost.
- No monthly billing/certification schedule.
- No FX conversion.
- No automatic escalation/inflation forecast.
- No company funding/bonding capacity comparison until a legitimate Company State public contract exists.
- No persistence, API or UI in v0.
- Cost scenario construction is caller/policy responsibility; there are no hidden default contingency percentages.

## FUTURE INTEGRATION

Future public contracts may feed Bid Economics from MOBILIZE, Requirements, Crew Economics and Supply Edge. SHADOW may consume one-opportunity assessments for portfolio work. Decision Ledger/COMMAND may reference `assessment_version`, `policy_version` and `input_fingerprint`, but this module must not itself write pursuit decisions.

Prepared in parallel. Does not modify the canonical Master Execution Queue, implement SHADOW, make autonomous pursuit decisions, or claim production integration.
