# MENA Cell — Qatar / Ashghal implementation record

## Country/source record

- COUNTRY: Qatar
- ISO2: QA
- ISO3: QAT
- CELL: MENA
- RESEARCH_DATE: 2026-08-25
- LAST_UPDATED: 2026-08-25
- PRIMARY_OFFICIAL_SOURCES: Public Works Authority (Ashghal) open e-tenders
- SECONDARY_OFFICIAL_SOURCES: Ashghal project-planning / PRE-EOI / award surfaces remain research evidence only in PR #173; not implemented in this PR
- SOURCE_ID: QA_ASHGHAL / qa_ashghal_open_etenders
- SIGNAL_TYPES: TENDER
- COVERAGE_SCOPE: LIMITED_HIGH_VALUE_SLICE_ASHGHAL_OPEN_ETENDERS
- CONSTRUCTION_FILTER: source-specific conservative title/category keyword classifier with token boundaries
- ACCESS: public official HTML GET, no authentication required at validation time
- SOURCE_STATE: AVAILABLE at last live validation
- RIGHTS: YELLOW / commercial reuse not declared GREEN
- IDENTITY: publisher-native tender number, e.g. PWA/GTC/17/2026
- FRESHNESS: listing is current/open-tender state; publisher update timestamp not exposed; registry expected refresh 1440 minutes, stale threshold 4320 minutes
- EARLY_SIGNAL_DEPTH: this implementation = TENDER only; deeper PLAN/PRE-EOI chain remains research evidence from PR #173
- AWARD_CONTRACT_DEPTH: not implemented by this source slice
- TECHNICAL_ROUTE: official HTML list -> parse -> construction filter -> stable publisher identity -> canonical TENDER normalize -> canonical signal_store compatibility
- COMMERCIAL_ASSESSMENT: high-value public-works slice; production commercial ingestion remains gated pending rights decision
- IMPLEMENTATION_STATUS: IMPLEMENTED + TESTED + LIVE_VALIDATED; not PRODUCTION_PATH_VALIDATED
- TEST_STATUS: repository suite and source-specific tests pass on PR #183 head after each validated revision
- LIVE_VALIDATION_STATUS: official source live gate passes; observed 39 raw open tenders and 19 construction-classified records on 2026-08-25 during validated run
- BLOCKERS: commercial reuse rights unresolved; runtime intentionally not enabled
- FINAL_CLASSIFICATION: LIMITED HIGH-VALUE SLICE / GATED
- EVIDENCE_REFS: research PR #173; official Ashghal open e-tenders page; GitHub Actions live-gate logs on PR #183
- PR_REFS: research #173; code #183

## Evidence / interpretation / decision separation

### RAW / OBSERVED FACT

On 2026-08-25 the official Ashghal open-e-tender page was reachable by ordinary public GET without credentials. The bounded live gate parsed 39 publisher tender rows. The construction classifier admitted 19 rows. Publisher tender numbers such as `PWA/GTC/17/2026` were present and usable as stable source identity for the current listing contract.

### INTERPRETATION

Ashghal is a material public-works publisher and therefore a valuable Qatar slice for ObraSignal even though the implementation does not represent Qatar-wide procurement coverage. The public listing contains some non-construction procurement, so publisher identity alone is insufficient as a construction filter.

### COMMERCIAL DECISION

Implement the technically usable public slice now, but keep production/commercial ingestion gated while reuse rights remain unresolved. Do not equate public readability or public machine retrieval with a GREEN commercial redistribution decision.

### IMPLEMENTATION STATE

`QA_ASHGHAL` is implemented as `AshghalOpenTenderConnector`, normalized to canonical `TENDER` signals, registered in the canonical source registry with `machine_access=VERIFIED`, `legal_reuse=YELLOW`, `status=planned`, and excluded from active/production-ready sources by the existing canonical gates.

## Conflict record

### CONFLICT — research-only completion vs implementation-first correction

- previous finding: PR #173 concluded no source in the audited MENA wave met all production machine-access + commercial-reuse gates and therefore delivered research/evidence only.
- new finding: the Ashghal open-tender listing is technically fetchable and implementable as a bounded public slice without claiming production rights.
- evidence: live GET + parser/normalizer gate in PR #183; canonical registry retains YELLOW rights and planned runtime state.
- likely explanation: the prior audit applied the production gate to the decision to engineer; the later execution instruction explicitly separates technical implementation from commercial production enablement.
- recommended canonical resolution: preserve PR #173 as historical evidence, retain Ashghal as IMPLEMENTED/LIVE_VALIDATED but GATED, and do not rewrite the earlier observation as if production rights had become GREEN.

No contradictory evidence was found for the source's technical public availability as of 2026-08-25. No other `QA_ASHGHAL` implementation/source record was found in accessible repository search or PR search at consolidation time.

## Canonical integration manifest

CELL: MENA

COUNTRIES: Qatar (QA / QAT)

SOURCE RECORDS ADDED: `QA_ASHGHAL` / `qa_ashghal_open_etenders`

SOURCE RECORDS UPDATED: none pre-existing; repository/PR search found no competing Ashghal canonical record

SHARED FAMILIES: none; no abstraction introduced because transport/semantics were not proven reusable across another country source

CODE PRs: #183

RESEARCH PRs: #173

CANONICAL FILES TO UPDATE LATER: global market portfolio and any future international consolidation documents; `source_registry.py` is already enriched by a small targeted record in #183 and must be semantically reconciled if parallel registry edits land first

CONFLICTS: research-only completion semantics vs later implementation-first rule, recorded explicitly above; no source-identity contradiction detected

DEPENDENCIES: none on unmerged parallel branches; implementation is based on the PR's real base and existing canonical Signal/store contracts

BLOCKERS: commercial reuse rights remain YELLOW; source remains runtime-disabled/planned

MERGE RISKS: `source_registry.py` is a shared canonical file likely to receive parallel small edits; resolve by preserving all independent source records, not by choosing one whole-file version. Research files are cell-scoped/new and should be low-conflict.

SAFE INTEGRATION NOTES: merge code/source adapter and tests independently; when resolving source-registry conflicts, append/retain the `QA_ASHGHAL` record with ISO3 QAT and stable source_id, preserving other cells' entries. Do not create a MENA-specific runtime. Do not promote rights/status during conflict resolution. Preserve this research record after canonical consolidation as provenance/history.

## Zero-loss / zero-duplication / zero-silent-conflict / zero-runtime-fork checks

- ZERO-LOSS: PASS — decisions, source identity, live counts, rights gate, implementation state, research/code PR provenance and conflict semantics are recorded here plus executable code/tests.
- ZERO-DUPLICATION: PASS within currently accessible repo/PR state — no second `QA_ASHGHAL` or Ashghal code PR found. Future consolidation must dedupe by ISO3 `QAT` + stable source_id `qa_ashghal_open_etenders`, not URL/string country aliases.
- ZERO-SILENT-CONFLICT: PASS — the one material semantic change relative to PR #173 is explicitly recorded as a conflict/resolution, not overwritten.
- ZERO-RUNTIME-FORK: PASS — no MENA runtime/family was created; the connector uses canonical Signal and source-registry contracts.
