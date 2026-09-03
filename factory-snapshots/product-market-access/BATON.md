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
- ECHA SCIP creates a distinct article/SVHC obligation surface for certain articles containing Candidate List SVHCs above 0.1% w/w.
- A narrow EU toy-importer decision packet has now been created at `factory-snapshots/product-market-access/SYNTHETIC_DECISION_PACKET_v0.1.md`.

## PRODUCT TRUTH / SAFE WEDGE
PROVEN NEED SIGNAL: applicable compliance duties depend on product category, actor role, market and product facts; authorities expose multiple separate official systems/guidance.
PROVEN CONTRACT FEASIBILITY SIGNAL: a toy-importer workflow can be represented as evidence-backed requirement branches while remaining fail-closed and avoiding binary legality claims.
ASSUMPTION: a decision-support intake that routes a product to authoritative requirements, recall/Safety-Gate checks, CE/document requirements and chemical/SVHC checks can reduce research friction for SMEs/importers.
NOT PROVEN: willingness-to-pay, best ICP, exhaustive rule coverage, legal sufficiency, automated product classification, Safety Gate matching quality, liability position, country-local completeness, or that a single binary "legal / illegal" answer is safe.

## FAIL-CLOSED PRODUCT RULE
Never output "legal to sell", "approved", "compliant", or equivalent from incomplete documentary evidence. Default result classes: CHECK_REQUIRED, EVIDENCE_FOUND, AUTHORITY_REQUIRED, OUT_OF_SCOPE, UNKNOWN. Every material requirement must carry source, jurisdiction, product/actor scope and retrieval/effective date where available.

## COMPLETED
- Reconstructed minimum safe current truth without fabricating prior history.
- Selected `EU toy import by EU-established importer` as first evidence-dense wedge.
- Created synthetic decision packet with required intake facts, authoritative rule branches, output contract, Safety Gate semantics, country-language escalation, and explicit false-claim boundary.
- Synthetic expected result proves the contract can distinguish CE presence from sufficient compliance evidence; no Safety Gate match is treated as NO_MATCH_OBSERVED, never proof of safety.

## ACTIVE
Turn the decision packet into an executable product contract using synthetic fixtures only.

## NEXT
1. Define an MVP JSON schema.
2. Add 8-12 synthetic cases: missing CE, missing technical documentation, missing Declaration of Conformity, language gap, importer identity gap, Safety Gate match, no-match, ambiguous product classification, and multi-rule overlap.
3. Verify every case fails closed and never emits a binary legality claim.
4. Then test ICP/pricing and competitive collision for EU importers/small marketplaces/compliance consultancies.

## WAIT
- Exact prior Factory history/canonical application source: UNKNOWN.
- External legal opinion or regulator confirmation.
- Any claim of product legality/compliance certification.
- Real-customer/product data or outbound commercial messaging without explicit authorization.

## BLOCKERS
None for repository-safe research/specification/prototype work.

## EVIDENCE URLS
- https://europa.eu/youreurope/business/product-rules-compliance/general-product-compliance/index_en.htm
- https://europa.eu/youreurope/business/product-rules-compliance/general-product-compliance/ce-marking/index_en.htm
- https://single-market-economy.ec.europa.eu/sectors/toys/placing-toys-eu-market_en
- https://eur-lex.europa.eu/eli/dir/2009/48/2022-07-05/eng
- https://commission.europa.eu/news-and-media/news/increased-action-against-dangerous-products-eu-2025-2026-03-09_en
- https://echa.europa.eu/scip

## EXACT NEXT EXECUTABLE ACTION
Create `factory-snapshots/product-market-access/MVP_CONTRACT_v0.1.json` and a synthetic fixture matrix, then validate that every fixture resolves only to `EVIDENCE_FOUND | CHECK_REQUIRED | AUTHORITY_REQUIRED | OUT_OF_SCOPE | UNKNOWN` and never a binary legality/compliance conclusion.
