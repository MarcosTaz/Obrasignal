# Product Market Access — Synthetic Decision Packet v0.1

SCOPE: EU toy import by an EU-established importer from a non-EU manufacturer.
PURPOSE: prove a fail-closed decision-support contract; not legal advice, certification, or approval.

## Synthetic input
- Product class claimed by supplier: children's toy.
- Importer: EU-established economic operator.
- Manufacturer: non-EU.
- Intended market: one EU Member State (country-specific language/national requirements remain an explicit input).
- Evidence supplied: product photos, model/SKU, manufacturer identity, draft label, EC/EU Declaration of Conformity, technical file index, instructions/warnings, test/conformity records.
- Real product/customer data: NONE.

## Required intake facts
1. Intended use and target age.
2. Product/model/batch/serial identifier.
3. Manufacturer legal name/contact details and country.
4. EU importer legal name/contact details.
5. Destination Member State and intended sales channel.
6. CE mark evidence.
7. Conformity-assessment evidence and applicable harmonised standards or notified-body evidence where required.
8. Technical-documentation availability.
9. Declaration of Conformity availability.
10. Instructions, safety information and warnings, including destination-language readiness.
11. Known Safety Gate/recall identifiers or supplier risk notices.

## Authoritative rule branches
### R1 — Product/category classification
If it is not established that the item is legally a toy within the applicable EU framework, return `AUTHORITY_REQUIRED` or `UNKNOWN`; never infer toy status from marketing wording alone.

### R2 — CE marking
EU guidance identifies toys as a category subject to CE marking. Only products covered by harmonised EU legislation requiring CE may use the mark. For a toy, absence of required CE evidence => `CHECK_REQUIRED`, not "illegal" or "safe".

### R3 — Importer pre-market checks
Current EU guidance requires an importer to ensure that the manufacturer has performed the appropriate conformity assessment, prepared technical documentation, affixed required markings/traceability information, and supplied required instructions/safety information in an appropriate language. Missing evidence => `CHECK_REQUIRED` or `AUTHORITY_REQUIRED`.

### R4 — Toy-specific importer checks
European Commission toy-market guidance states that importers may only place compliant toys on the EU market and must ensure the manufacturer carried out the appropriate conformity assessment, created technical documentation, affixed CE marking and made the Declaration of Conformity available.

### R5 — Safety Gate risk signal
Safety Gate is an authoritative rapid-alert source for dangerous non-food products. A matching alert/recall is an `EVIDENCE_FOUND` risk signal requiring investigation/escalation; absence of a match is never proof of safety or compliance.

### R6 — Destination-language / national authority dependency
If required warnings/instructions cannot be verified for the destination Member State, return `AUTHORITY_REQUIRED` or `CHECK_REQUIRED`; do not generalise from another EU country.

## Output contract
- `decision_state`: one of `EVIDENCE_FOUND | CHECK_REQUIRED | AUTHORITY_REQUIRED | OUT_OF_SCOPE | UNKNOWN`.
- `jurisdiction`: EU + destination Member State.
- `actor_role`: importer.
- `product_scope`: toy (only if established; otherwise UNKNOWN).
- `requirements[]`: requirement_id, status, evidence_seen, missing_evidence, authority_url, authority_scope, retrieved_at/effective-date-if-known.
- `recall_signal`: MATCH | NO_MATCH_OBSERVED | NOT_CHECKED | UNKNOWN.
- `claim_boundary`: fixed text forbidding "approved", "certified", "legal to sell", or "compliant" conclusions from this packet alone.
- `escalation`: competent authority / qualified compliance professional when facts or rule applicability remain unresolved.

## Synthetic expected result
Given a toy import packet with CE image but no verifiable conformity-assessment record and no destination-language instructions, expected `decision_state=CHECK_REQUIRED`. CE presence alone must not upgrade the result. If a matching Safety Gate alert exists, expected state becomes `EVIDENCE_FOUND` with explicit escalation. If no alert is observed, the result remains CHECK_REQUIRED until all independent requirement branches have evidence; NO_MATCH_OBSERVED is not a safety proof.

## Evidence
- Your Europe CE marking, last checked 2026-07-17: https://europa.eu/youreurope/business/product-rules-compliance/general-product-compliance/ce-marking/index_en.htm
- Your Europe general product compliance, last checked 2026-07-13: https://europa.eu/youreurope/business/product-rules-compliance/general-product-compliance/index_en.htm
- European Commission, Placing toys on the EU market: https://single-market-economy.ec.europa.eu/sectors/toys/placing-toys-eu-market_en
- EUR-Lex Toy Safety Directive consolidated text: https://eur-lex.europa.eu/eli/dir/2009/48/2022-07-05/eng
- European Commission Safety Gate 2025 report news, 2026-03-09: https://commission.europa.eu/news-and-media/news/increased-action-against-dangerous-products-eu-2025-2026-03-09_en

## Proof result
PASS AS CONTRACT PROTOTYPE: the narrow importer/toy workflow can be represented without a binary legality claim and with explicit authoritative escalation boundaries.
NOT PROVEN: exhaustive toy-law coverage, destination-country completeness, automated product classification, Safety Gate matching quality, willingness-to-pay, liability model, or legal sufficiency.

## Next executable action
Define an MVP JSON schema plus 8-12 synthetic test cases covering missing CE, missing technical documentation, missing DoC, language gap, importer-identity gap, Safety Gate match, no-match, and ambiguous product classification; then test whether every case fails closed without producing a binary legality claim.
