# Product Market Access / Legal Product Checker — evidence note — 2026-08-30

## Classification

`PUBLIC_EVIDENCE_SIGNAL / COSMETICS_GENERIC_COMPLIANCE_WEDGE_REJECTED / PRODUCT_SCOPE_STILL_UNPROVEN / NO_CUSTOMER_OR_WTP_PROOF`

## Why this matters

The Factory registry contains `product-market-access`, but no exact canonical branch/BATON identity has been recovered. This note advances only research-safe current truth and does not claim a product implementation, customer, payment, regulatory certification, or legal advice.

## Current public evidence

1. **EU Safety Gate volume is increasing.** The European Commission reported 4,671 dangerous-product alerts in 2025, the highest since Safety Gate launched in 2003, up 13% from 2024. Authorities also recorded 5,794 follow-up actions, up 35% year-on-year. Cosmetics and toys together accounted for more than half of alerts. This is a concrete signal that product-safety/compliance monitoring volume is material.

2. **The Commission is actively using automated web surveillance.** Its eSurveillance product-safety application is designed to find products already notified in Safety Gate that remain or reappear in web shops and marketplaces. This reduces the plausibility of a naive 'search Safety Gate for me' wedge, because an official detection layer already exists.

3. **Digital Product Passport infrastructure is moving from framework to implementation.** The ESPR framework makes the DPP a core mechanism for structured product information. A May 2026 EU TBT notification describes proposed implementing arrangements for the DPP Registry, including roles and obligations for economic operators, value-chain actors, authorities and the Commission. This strengthens the case for tooling around evidence assembly, product-data readiness, and obligation mapping, but does not by itself prove willingness to pay.

## Cosmetics wedge test — 2026-08-30

Cosmetics was selected as the first category to falsify because it represented 36% of 2025 Safety Gate alerts in the Commission data and therefore provides both high regulatory activity and a large addressable seller/manufacturer population.

### Existing paid supply proves recurring spend — and strong crowding

Public providers already sell end-to-end EU cosmetics compliance at transparent prices:

- Eldris advertises CPSR + PIF + CPNP at **£195 per product**, with separate EU Responsible Person onboarding at **£195** and ongoing management from **£19.95/month** depending on SKU count.
- EU Compliance Partner advertises **$300 per product** for PIF + CPSR, with CPNP/OPSS notification and label-review services.
- INCIkit sells manufacturer documentation software with PIF/batch traceability from approximately **€29–€199/month** at current launch pricing.
- CosmERP advertises PIF, formulation, manufacturing and QC software at approximately **€79 / €179 / €349 per month**.

This is real evidence that businesses pay for compliance work and software. It is not evidence that they would pay BlackLeaf, nor that provider claims are independently verified.

### Rejected wedge

A generic cosmetics **PIF/CPSR/CPNP generator or compliance dashboard is rejected as the first wedge**. The category already has low-cost done-for-you services and dedicated software covering documentation, responsible-person workflows, formulas, labels, batch records and notifications. Competing directly would require either a materially better acquisition advantage or a differentiated truth/evidence boundary not yet proved.

### Surviving testable wedge

The stronger cross-category hypothesis is **SKU evidence-gap orchestration before specialist/legal work**:

1. ingest a seller/importer/manufacturer SKU list and existing evidence inventory;
2. map each SKU to the evidence/actor obligations that are actually supportable from authoritative rules;
3. identify missing, stale, inconsistent or unverified evidence without declaring the SKU 'legal';
4. monitor Safety Gate/recalls/restrictions as one source and flag affected product families;
5. package an evidence-ready handoff to an existing Responsible Person, assessor, lab or compliance provider instead of replacing them;
6. preserve `UNKNOWN / NEEDS_HUMAN_REVIEW` whenever applicability, classification or jurisdictional scope is not proven.

The economic thesis to test is that cross-SKU evidence triage and exception handling are fragmented across spreadsheets, supplier documents, marketplaces, compliance providers and internal teams even when downstream specialist services are already purchased.

## Product implication

A generic consumer-facing 'is this product legal?' checker is too broad and risks overclaiming legal certainty. The B2B product should be framed as evidence readiness / obligation mapping / exception orchestration, not legal certification.

## Falsifiable next test

Before implementation, find public proof from at least 20 EU sellers/importers/manufacturers or compliance operations teams that SKU evidence collection and exception handling create recurring manual work across multiple providers/systems. Evidence may include job descriptions, procurement notices, service descriptions, marketplace compliance workflows and public operational documentation. Reject the wedge if the work is already cheaply and completely absorbed by incumbent systems/services for the same ICP.

No outreach is authorized by this note.

## ACTIVE

Test cross-SKU evidence-fragmentation workload and buyer role rather than building a generic cosmetics compliance product.

## NEXT

1. Identify the buyer/operator role that owns multi-SKU evidence exceptions (marketplace compliance, importer QA/regulatory, brand operations, distributor compliance).
2. Collect 20 public workload signals and separate one-off market-entry work from recurring evidence maintenance.
3. Compare incumbent coverage for cross-provider evidence exception orchestration.
4. Only if a recurring uncovered workflow survives, define MVP data model and authoritative evidence sources.

## WAIT

- Exact historical/canonical Product Market Access BATON/source identity remains UNKNOWN.
- No customer problem interview, WTP, payment, or production evidence exists from this run.
- Provider pricing is public market evidence only; no provider capability claim is treated as independently verified product truth.
- No legal conclusion should be produced without authoritative rule-level evidence and jurisdiction/product applicability checks.
