# LATAM Next Wave — Integration Manifest Addendum: DGCP Lifecycle

CELL: LATAM_NEXT_WAVE
COUNTRIES: Dominican Republic (DO / DOM)
SOURCE RECORDS ADDED: none
SOURCE RECORDS UPDATED IN CODE PR: no new canonical lifecycle metadata in this addendum; existing `DO_DGCP` remains the identity to enrich semantically
SHARED FAMILIES: existing OCDS page/discovery family extended by reusable ReleasePackage lifecycle transport module `ocds_release_lifecycle.py`
CODE PRs: #176
RESEARCH PRs: #176 lifecycle evidence addendum; related #179 Peru; #180 Panama
CANONICAL FILES TO UPDATE LATER:
- `source_registry.py`: enrich existing `DO_DGCP` capabilities with awards/contracts/lifecycle and signal types AWARD/CONTRACT after semantic conflict resolution
- shared-family documentation/registry only if consolidation decides `OCDSReleasePackageConnector` is a named canonical sub-family rather than an extension of `OCDS_PAGE_API`
CONFLICTS:
- previous DGCP evidence said AWARD/CONTRACT publisher surfaces were not implemented; superseded by tested/live-validated branch implementation on 2026-08-25
- secondary `source_id=do_dgcp_ocds_pacc` is feature-encoded; consolidation should normalize it to stable publisher/system identity without creating a second source
DEPENDENCIES:
- no dependency on Peru #179 or Panama #180
- depends only on canonical `OCDSAPIConnector` contract already present on main/PR base
BLOCKERS:
- runtime not wired
- production-scale completeness/hydration economics not proven
- canonical lifecycle metadata enrichment deferred to semantic consolidation
MERGE RISKS:
- parallel cells may touch `source_registry.py` and shared-family metadata
- resolve by preserving every valid source record and unioning compatible capability/family enrichments; never choose a whole-file side
SAFE INTEGRATION NOTES:
1. Merge/reconcile reusable shared OCDS transport changes before country lifecycle metadata.
2. Preserve source key `DO_DGCP`; do not mint `DO_DGCP_CONTRACTS` or another country/source identity.
3. Keep signal domains canonical: `TENDER`, `PROCUREMENT_PLAN`, `AWARD`, `CONTRACT`.
4. Preserve `status=planned` until runtime integration and production-path gates pass.
5. Do not resurrect the rejected N+1 contract→process route or blind full-history XLSX ingestion without new evidence.
6. Preserve `LATAM_DGCP_LIFECYCLE_EVIDENCE.md` after canonical integration as research history.

ZERO-LOSS TEST: PASS — positive and negative lifecycle route evidence, implementation decisions, tests and live basis are persisted in PR #176.
ZERO-DUPLICATION TEST: PASS — lifecycle enriches existing `DO_DGCP`; no duplicate source/country record.
ZERO-SILENT-CONFLICT TEST: PASS — prior non-implemented lifecycle conclusion is explicitly superseded with dated evidence.
ZERO-RUNTIME-FORK TEST: PASS — shared OCDS extension only; no LATAM runtime silo.

NO-MERGE STATEMENT: this addendum prepares later clean consolidation. It does not authorize automatic merge or production promotion.
