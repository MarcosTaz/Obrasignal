# ObraSignal BANGS Engine v0

## Purpose

BANGS is a lateral, provider-neutral field-intelligence capability that converts explicit construction execution inputs and observed market evidence into deterministic, auditable cost assessments. It does not infer a complete BOQ, submit bids, book travel, purchase supplies, or claim market completeness.

Core rule: **price is not cost; unknown is not zero.**

## Architecture

`bangs/` is intentionally split into small modules: strict Money and compatible units; provenance/freshness; project/company contracts; material and supplier observations; provider contracts; landed cost; equipment; routes; accommodation; field expenses; mobilization; optional financial exposure; true job cost; scenarios; comparator; presentation; tenant-owned observation storage.

External discovery is separated from fast deterministic calculation. Provider replacement does not require engine changes.

## Public contracts

Primary consumable contracts are `MaterialPriceObservation`, `LandedCostAssessment`, `EquipmentAssessment`, `RouteCostAssessment`, `AccommodationAssessment`, `MobilizationAssessment`, `FinancialExposureAssessment`, `TrueJobCostAssessment`, `ComparisonResult`, and `ExecutiveBangResult`.

## Money, currency, tax and units

Money uses `Decimal`, explicit ISO-style three-letter currency codes, finite non-negative values, and fails closed on mixed-currency aggregation. BANGS does not implement FX, global tax, or customs engines. Tax basis is explicit; cross-border duty is UNKNOWN unless explicitly supplied. Unit conversion is restricted to compatible dimensions; no density/specification inference is performed.

## Materials and suppliers

Requirements preserve their basis: document/BOQ explicit, user supplied, system derived, estimate, or unknown. Price observations preserve supplier, unit, price, currency, tax basis, quantity constraints, availability, visibility and evidence. A catalogue/list/market observation is never promoted to a supplier quote. Exact duplicate observations can be deduplicated while temporal history is retained. Outliers are marked for verification rather than silently discarded.

Supplier identity remains source/provider supplied. No fuzzy company merging is performed.

## Landed cost

Landed cost composes purchase cost with explicit delivery, handling, unloading, known tax/duty, explicit waste and other known lines. Waste has no universal default. Material price and landed cost are separate contracts. Unknown tax/customs/logistics remain unknown components.

## Equipment / plant

Rent and buy are explicit modes. Rental duration/rate basis, transport, operator, insurance and fuel are separate inputs. A refundable deposit contributes to cash outlay, not economic cost. Availability is explicit and heavy-equipment transport is not hidden inside the rental rate.

## Travel / route economics

Routes preserve distance basis and provenance. Straight-line distance is never presented as road distance. One-way, round-trip and trip count are explicit. Fuel arithmetic uses distance, vehicle consumption and observed/supplied fuel price with unit checks. Tolls are UNKNOWN unless the caller/provider explicitly states that the supplied toll set is complete. Ferry/rail/flight/parking and paid travel time can be explicit components.

## Accommodation / rest intelligence

Accommodation candidates preserve type, location, rate basis, capacity/occupancy, availability state, evidence and optional work-relevant amenities. A room rate is not a person rate. An observed rate is not confirmed availability. Crew/night/occupancy arithmetic is deterministic and supports comparison with local or long-distance commuting when the corresponding route inputs are supplied.

## Field expenses

Per diem, parking, laundry, local transport, consumables, waste disposal, welfare, communications and other explicit expenses can be represented. BANGS does not invent fiscal/legal per-diem or meal rates. Missing material expenses remain UNKNOWN.

## Mobilization

Mobilization composes explicit crew travel, vehicles, equipment/material transport, temporary setup, initial accommodation, site establishment, known permits/fees and other supplied components. Demobilization is separately representable. Mobilization is never presented as total execution cost.

## Financial exposure bridge

BANGS does not duplicate Bid Economics. `FinancialExposureProvider` is optional. When no canonical economics provider exists, the bridge returns `ECONOMICS_PROVIDER_UNAVAILABLE`; it does not manufacture working-capital, bond, retention, payment-lag or advance values.

## True job cost and scenarios

`TrueJobCostAssessment` aggregates declared cost categories only when currency semantics permit. It preserves unknown categories/components and completeness. A known subtotal with material unknowns remains a partial known cost; total job cost remains unknown. MINIMUM/PROBABLE/PRUDENT scenarios are explicit structured scenarios, not Monte Carlo and not invented by the engine.

## Comparator

The comparator is deterministic, not LLM scoring. It compares equivalent normalized cost options and distinguishes confirmed lowest-known cost from lowest-known partial cost. Unavailable options cannot win; unknown availability cannot become confirmed best; non-equivalent alternatives are rejected as substitutes. Time/cost conflicts are exposed as trade-offs rather than hidden behind universal weights.

## Executive result

The read model exposes known cost, total-cost state, unknowns, best observed options, major cost drivers, major risks, evidence references and next information needed. It avoids ranking cost drivers across unresolved currencies.

## Provider contracts

Provider boundaries exist for material prices, suppliers, equipment, routes, fuel, tolls and accommodation. Requests have bounded result counts and timeout semantics. Failures are explicit (`PROVIDER_UNAVAILABLE`, timeout, rate limit, invalid response, etc.) and never map to zero cost. `ManualObservationProvider` provides a real offline/manual-input path.

No arbitrary user URL is fetched by the core. Provider endpoints must pass configured HTTPS/host policy; URL/reference fields are untrusted evidence metadata, not fetch instructions.

## Provenance and freshness

Evidence records source, basis, observation timestamp, validity and optional reference/URL. Freshness uses an injected clock. Expired quotes may remain historical evidence but are not current confirmed prices. Source failure means provider unavailable, not absence of market supply.

## Tenancy and privacy

Public observations and tenant-private observations are distinct. Private supplier quotes/company rates require a tenant identifier; public observations cannot carry a tenant owner. The module-owned observation store enforces account scope and idempotent identity, and tests reject cross-tenant reads. Negotiated prices should not be logged indiscriminately.

## Security

Domain validation rejects malformed/non-finite/negative money, unsafe evidence metadata, oversized domain values and unsafe supplier URLs. Provider endpoint policy rejects non-HTTPS, non-allow-listed hosts and literal private/loopback targets. Core calculations perform no HTTP and no LLM calls.

A production HTTP provider must additionally resolve DNS and revalidate every redirect target before connecting; BANGS v0 deliberately does not ship an HTTP fetch runtime.

## Persistence

No database migration is introduced in v0. The deterministic core and module-owned in-memory observation boundary are sufficient for manual/structured observations. Canonical persistence should be added only during controlled integration using existing ObraSignal DB/auth patterns; Opportunity is not duplicated.

## API / UI

No API or UI is wired in this branch. That is intentional: the current repository composition root and authenticated API should be extended only after the public contracts are accepted. A future API must derive tenant identity from verified auth context, never request payload.

## Capability state

The canonical capability registry receives only an additive `BANGS` entry in `RESEARCH` state with feature flag `bangs_field_intelligence_v0` and a required kill switch. The flag is a future rollout control, not an activation. This branch does not alter the Master Queue, bypass its gates, or promote MOBILIZE, SUPPLY_EDGE, COMMAND, ACTION or SHADOW.

## Testing

The BANGS suite covers money/unit safety, freshness, quotes/list prices, outliers, provider failures, tenancy, landed cost, equipment, route arithmetic, accommodation, commute comparison, field expenses, true cost, scenarios, comparator semantics, executive output and all nine required product scenarios. The implementation was locally executed at 70/70 passing before publication; repository CI remains the exact-head authority after PR creation and after any later branch changes.

## Live validation

Public-source investigation was treated separately from implementation. A Portuguese DGEG fuel-price source was not integrated because the discovered terms were unsuitable for assumed commercial reuse. The European Commission Weekly Oil Bulletin was identified only as a future provider candidate; no parser/provider is claimed as implemented or validated in v0.

## Known limitations

No live supplier/hotel/equipment provider is shipped; no FX/tax/customs engine; no full BOQ takeoff; no booking/purchasing/RFQ; no accounting/payroll/bank dependency; no canonical DB persistence; no API/UI; no autonomous procurement/bid action. Financial exposure remains unavailable without a future canonical provider.

## Future integration

The contracts are designed to accept future observations/adapters from Supply Edge, Build Optimizer, Crew Economics, MOBILIZE, Bid Economics and Company State without depending on unmerged implementations. COMMAND/ACTION/SHADOW remain future consumers, not dependencies or promoted capabilities. Any maturity increase from `RESEARCH` requires a separate canonical queue/capability decision; tests alone never promote it.
