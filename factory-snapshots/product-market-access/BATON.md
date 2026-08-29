# Product Market Access / Legal Product Checker — BATON

STATUS: ACTIVE
TRUTH_STATE: RECONSTRUCTED_MINIMUM_SAFE_TRUTH
CANONICAL_SOURCE: UNKNOWN
CONTROL_BRANCH: factory-cloud/app-development-control-plane

## MISSION
Determine whether a low-capital web product can help EU sellers/importers/distributors answer a narrower, evidence-backed question: what product-compliance checks and documentary obligations apply before placing a non-food product on an EU market, without pretending to give legal approval or replacing competent authorities.

## RECONSTRUCTED EVIDENCE
- No repository branch, issue, PR, file, or prior personal-context BATON matching "Product Market Access / Legal Product Checker" was recovered in this execution slice. Prior history is therefore UNKNOWN, not inferred.
- EU product-compliance obligations are materially fragmented by actor and product category. Current Your Europe guidance (last checked 2026-07-13) requires economic operators to know applicable rules, CE/label/documentation/language requirements, preserve supplier/manufacturer identity, and be able to demonstrate checks to market-surveillance authorities.
- Safety Gate remains the EU rapid-alert system for dangerous non-food products. The European Commission reported 4,671 Safety Gate alerts in 2025, +13% year over year, with cosmetics and toys accounting for over half of alerts; follow-up actions rose 35%.
- The General Product Safety Regulation has applied since 2024 and imposes additional online-marketplace/product-safety obligations.
- ECHA SCIP creates a distinct article/SVHC obligation surface: EU producers/assemblers/importers/distributors placing articles containing Candidate List SVHCs above 0.1% w/w on the EU market can have SCIP notification duties; direct-to-consumer-only retailers are excluded from that notification duty.

## PRODUCT TRUTH / SAFE WEDGE
PROVEN NEED SIGNAL: applicable compliance duties depend on product category, actor role, market and product facts; authorities expose multiple separate official systems/guidance.
ASSUMPTION: a decision-support intake that routes a product to authoritative requirements, recall/Safety-Gate checks, CE/document requirements and chemical/SVHC checks can reduce research friction for SMEs/importers.
NOT PROVEN: willingness-to-pay, best ICP, complete rule coverage, legal sufficiency, automation completeness, liability position, country-local requirements, or that a single binary "legal / illegal" answer is safe.

## FAIL-CLOSED PRODUCT RULE
Never output "legal to sell", "approved", "compliant", or equivalent unless an authoritative rule explicitly supports that exact conclusion. Default result classes should be: CHECK_REQUIRED, EVIDENCE_FOUND, AUTHORITY_REQUIRED, OUT_OF_SCOPE, or UNKNOWN. Every material requirement must carry source, jurisdiction, product/actor scope and retrieval/effective date where available.

## ACTIVE
Build a narrow synthetic decision packet for one tractable non-food product category and one actor role, using only public authoritative evidence. Prefer a category with CE/document requirements plus Safety Gate exposure, but avoid regulated medical/pharma/food domains in v0.

## NEXT
1. Select a single launch wedge by evidence density and decision tractability (candidate: toys, low-voltage electrical equipment, or PPE).
2. Map intake facts -> authoritative obligation checks -> evidence payload -> UNKNOWN/authority escalation.
3. Define MVP data contract and one synthetic end-to-end case.
4. Only after that, test ICP/pricing and competitive collision.

## WAIT
- Exact prior Factory history/canonical application source: UNKNOWN.
- External legal opinion or regulator confirmation.
- Any claim of product legality/compliance certification.
- Real-customer/product data or outbound commercial messaging without explicit authorization.

## BLOCKERS
None for repository-safe research/specification work.

## EVIDENCE URLS
- https://europa.eu/youreurope/business/product-rules-compliance/general-product-compliance/index_en.htm
- https://commission.europa.eu/topics/business-and-industry/product-safety_en
- https://commission.europa.eu/news-and-media/news/increased-action-against-dangerous-products-eu-2025-2026-03-09_en
- https://echa.europa.eu/scip
- https://echa.europa.eu/en-GB/scip-suppliers-of-articles

## EXACT NEXT EXECUTABLE ACTION
Create `factory-snapshots/product-market-access/SYNTHETIC_DECISION_PACKET_v0.1.md` for one selected category, with authoritative citations, mandatory input facts, rule branches, evidence fields and explicit UNKNOWN/escalation behavior. Do not build a broad legal checker until that narrow packet proves the contract is reconstructable.
