# Product Market Access / Legal Product Checker — evidence note — 2026-08-30

## Classification

`PUBLIC_EVIDENCE_SIGNAL / PRODUCT_SCOPE_STILL_UNPROVEN / NO_CUSTOMER_OR_WTP_PROOF`

## Why this matters

The Factory registry contains `product-market-access`, but no exact canonical branch/BATON identity has been recovered. This note advances only research-safe current truth and does not claim a product implementation, customer, payment, regulatory certification, or legal advice.

## Current public evidence

1. **EU Safety Gate volume is increasing.** The European Commission reported 4,671 dangerous-product alerts in 2025, the highest since Safety Gate launched in 2003, up 13% from 2024. Authorities also recorded 5,794 follow-up actions, up 35% year-on-year. This is a concrete signal that product-safety/compliance monitoring volume is not trivial.

2. **The Commission is actively using automated web surveillance.** Its eSurveillance product-safety application is designed to find products already notified in Safety Gate that remain or reappear in web shops and marketplaces. This reduces the plausibility of a naive 'search Safety Gate for me' wedge, because an official detection layer already exists.

3. **Digital Product Passport infrastructure is moving from framework to implementation.** The ESPR framework makes the DPP a core mechanism for structured product information. A May 2026 EU TBT notification describes proposed implementing arrangements for the DPP Registry, including roles and obligations for economic operators, value-chain actors, authorities and the Commission. This strengthens the case for tooling around evidence assembly, product-data readiness, and obligation mapping, but does not by itself prove willingness to pay.

## Product implication

A generic consumer-facing 'is this product legal?' checker is too broad and risks overclaiming legal certainty. A more defensible B2B wedge to test is:

- product/compliance evidence readiness for sellers/importers/manufacturers;
- SKU-level obligation and missing-evidence mapping;
- Safety Gate / recall / restriction monitoring as one input, not the whole product;
- DPP-readiness gap detection where delegated/implementing rules make requirements concrete;
- explicit `UNKNOWN / NEEDS_HUMAN_REVIEW` states whenever legal applicability cannot be determined from authoritative evidence.

## Falsifiable next test

Before implementation, identify 20 EU sellers/importers/manufacturers in one high-alert category (cosmetics, toys, or electrical equipment) and test whether they already pay for or manually perform: SKU evidence collection, responsible-person/economic-operator checks, Safety Gate monitoring, technical-document completeness, and upcoming DPP-readiness work. No outreach is authorized by this note; research can use public job posts, service pages, forums, procurement notices and compliance-provider pricing.

## ACTIVE

Narrow the first ICP + workflow where product-compliance evidence fragmentation creates recurring paid work.

## NEXT

1. Compare existing compliance software/services for the chosen category.
2. Find proof of recurring manual workload and pricing.
3. Reject wedges already solved by official/free infrastructure alone.
4. Only then define MVP data model and evidence sources.

## WAIT

- Exact historical/canonical Product Market Access BATON/source identity remains UNKNOWN.
- No customer problem interview, WTP, payment, or production evidence exists from this run.
- No legal conclusion should be produced without authoritative rule-level evidence and jurisdiction/product applicability checks.
