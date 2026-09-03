# France DECP authority evidence — 2026-08-30

Status: **RESEARCH EVIDENCE — NOT COVERAGE COMPLETENESS / NOT LAUNCH AUTHORIZATION**
Factory: Global Market Entry, Localization & Country Launch Automation

## Material evidence

1. AIFE states that a new API for `données essentielles de la commande publique` (DECP) was put into production for buyer profiles at the end of November 2025, with opening of the service planned for Q1 2026 and PLACE as the first consumer. AIFE describes the API as conforming to the 22 December 2022 DECP order and intended to improve publication quality/standardisation.
   - Source: https://aife.economie.gouv.fr/nos-applications/place/

2. The official data.gouv.fr `API DECP` dataset, produced by AIFE, states that from 1 January 2024 essential public-procurement and concession data must be published on data.gouv.fr and transmitted through the DECP API. On 2026-08-30 the dataset was current and contained daily JSON resources.
   - Source: https://www.data.gouv.fr/datasets/api-decp

3. DAJ reiterates that since 1 January 2024 French public buyers and concession authorities must publish essential contract data on the national open-data portal, either via buyer profile/financial software/PES marché or direct deposit conforming to the DECP schema.
   - Source: https://www.economie.gouv.fr/daj/commande-publique/conseils-aux-acheteurs/donnees-essentielles-de-la-commande-publique-la-daj-lance-son-podcast

## Product / launch implication

This materially strengthens the proposition that France has a current national post-award / contract-data authority beyond BOAMP + TED and that DECP can be investigated as an enrichment source for buyer, award, contract and market-history intelligence.

It **does not** prove that current ObraSignal ingestion consumes DECP, that DECP is complete for every relevant procurement event, that it covers pre-tender discovery, or that BOAMP + TED + DECP would equal full French procurement coverage. Existing launch copy must therefore remain fail-closed: current repository binding proves only the sources actually integrated and tested.

## State transition

- Previous France gap: `DECP/national-enrichment completeness must be proved before coverage claims`.
- New state: `DECP_NATIONAL_AUTHORITY_CURRENT_AND_RESEARCHABLE / INGESTION_NOT_PROVEN / COMPLETENESS_NOT_PROVEN`.
- Safe next executable action: build a synthetic, no-production DECP schema/sample adapter probe and compare its fields against the current opportunity/buyer/award model; do not activate a source or change production configuration.

No merge, deploy, production/config/secrets/customer-data mutation, paid spend, outreach or commercial commitment is authorized by this evidence note.
