# ObraSignal International Integration Manifest — Nordics + Baltics

CELL: NORDICS + BALTICS DEEP COVERAGE
RESEARCHED_AT: 2026-08-25
LAST_UPDATED: 2026-08-25
MODE: CANONICAL-INTEGRATION / ZERO-LOSS
OWNERSHIP: cell-scoped evidence for later international consolidation; not a competing global source of truth.

## Countries

Stable identities used by this cell:

| Country | ISO2 | ISO3 | Cell classification | Implementation state | Source state |
| --- | --- | --- | --- | --- | --- |
| Denmark | DK | DNK | BUILD/PREPARED | RESEARCHED / GATED | AUTH_REQUIRED |
| Norway | NO | NOR | BUILD/PREPARED | TECHNICALLY_PROVEN / GATED | AUTH_REQUIRED |
| Sweden | SE | SWE | PARTNERSHIP/LICENSE / HOLD | RESEARCHED / BLOCKED | PARTNERSHIP_REQUIRED / LICENSE_REQUIRED |
| Finland | FI | FIN | BUILD/PREPARED | IMPLEMENTED / TESTED / GATED | AUTH_REQUIRED |
| Estonia | EE | EST | NATIONAL ENRICHMENT — existing | pre-existing implementation; not owned by this cell | AVAILABLE per existing repository record |
| Lithuania | LT | LTU | NATIONAL ENRICHMENT — existing | pre-existing implementation; not owned by this cell | AVAILABLE per existing repository record |
| Latvia | LV | LVA | NATIONAL ENRICHMENT — existing | pre-existing implementation; not owned by this cell | AVAILABLE per existing repository record |
| Iceland | IS | ISL | TED/PORTAL SUFFICIENT CURRENT PHASE / HOLD | RESEARCHED | UNKNOWN machine-readable route |

## Source records added

- `FI_HILMA` / Finland / HILMA AVP. Stable source identity is country + publisher/system, not endpoint URL.
  - Signal types: `TENDER`, `PROCUREMENT_PLAN`.
  - Coverage implemented: publisher-native Works `ContractNotices` and Works `PlanNotices`.
  - Access: `HILMA_API_KEY`, `Ocp-Apim-Subscription-Key`.
  - Identity: publication `noticeId`; eForms `eFormsId` when present; procedure `procedureId` with documented fallbacks.
  - Freshness design: incremental publication watermark with 48-hour overlap.
  - Technical route: `HilmaAVPConnector` -> existing `incremental_runtime_plugin` -> canonical `Signal`; no regional runtime silo.
  - Implementation: IMPLEMENTED + TESTED.
  - Live validation: NOT PERFORMED in this cell; no real AVP credential was available.
  - Production path: GATED. Registry intentionally remains `status=planned`, `machine_access=CREDENTIAL_REQUIRED`.
  - PR: #181.

## Source records updated

None claimed as canonical historical ownership changes. `source_registry.py` receives only the minimal additive `FI_HILMA` record required for connector integration. Existing `EE_RHR`, `LT_VPT`, and `LV_IUB` records were inspected/reused and not duplicated.

## Candidate source identities preserved for later consolidation

These are evidence/candidates, not new production registry entries:

- Denmark / Udbud.dk system-provider API — AUTH_REQUIRED; national below-threshold and expected-purchase depth; no connector built.
- Norway / Doffin Public API — AUTH_REQUIRED; credible `/public/v2/search` + `/public/v2/download/{id}` technical route; no connector built because official key/reuse onboarding was not closed strongly enough.
- Sweden / registered procurement advertisement databases — PARTNERSHIP_REQUIRED / LICENSE_REQUIRED; no per-platform connectors built.
- Iceland / Útboðsvefur — machine-readable source state UNKNOWN; no scraper/API connector built.

## Shared families

No new Nordic/Baltic shared family created. The transports and publisher semantics are not homogeneous enough to justify a family abstraction. Finland reuses the canonical connector/Signal/runtime contracts already in the repository.

## Code PRs

- PR #181 — `Finland: add HILMA national works + procurement-plan enrichment`
- Branch: `feature/fi-hilma-national-enrichment-v0`
- Base at PR creation: `main`.
- No merge performed by this cell.

## Research PRs

No separate research-only PR. Cell evidence is carried inside PR #181 so the implementation and its provenance cannot be separated accidentally.

## Cell-scoped evidence

- `NORDICS_BALTICS_DEEP_COVERAGE.md` — detailed market/source findings, implementation boundary and country decisions.
- `NORDICS_BALTICS_INTEGRATION_MANIFEST.md` — this zero-loss handoff record.

The repository did not expose an established `research/international/...` convention during this cell, so existing root-level cell evidence is retained rather than inventing an incompatible tree late in the PR. A later consolidation pass may move/archive these files semantically while preserving history.

## Canonical files touched now

- `source_registry.py` — minimal additive `FI_HILMA` record only.
- `cors_app.py` — additive runtime installation only.

No Master Execution Queue, global market portfolio, global international scope document, architecture contract, or whole-world canonical Markdown was replaced.

## Canonical files to update later

Only during the dedicated `OBRASIGNAL INTERNATIONAL CONSOLIDATION PASS`, after comparing all parallel-cell evidence:

- canonical global market portfolio / international scope, if present at consolidation time;
- canonical source registry metadata after duplicate/conflict resolution;
- canonical shared-family mappings if cross-cell evidence proves a reusable family;
- any global architecture/runtime coverage documentation that already exists.

Do not regenerate these files from this cell alone.

## Conflicts found

### CONFLICT — Finland readiness claim corrected inside this PR
previous finding: `FI_HILMA` was temporarily registered as `status=ready`, `machine_access=VERIFIED` during implementation.
new finding: this cell had no real HILMA AVP key and therefore no live source smoke.
evidence: implementation/tests prove connector behavior against fixtures/contracts, but not live credential/source behavior.
likely explanation: code readiness was initially conflated with live source readiness.
recommended canonical resolution: retain the corrected state now present in PR #181: `status=planned`, `machine_access=CREDENTIAL_REQUIRED`; promote only after bounded live validation.

No other silent conflict with a duplicate Finland/HILMA PR was found by repository/PR search at the time of this manifest. Search can be incomplete for unindexed/unmerged parallel work, so the global consolidation pass must repeat country/source duplication checks across every parallel PR.

## Dependencies on other PRs

None required for PR #181 to compile/test against its real base. Existing canonical `Signal`, source registry, and `incremental_runtime_plugin` contracts are reused from main/base. Other parallel international branches are RELATED PARALLEL WORK only and are not assumed merged.

## Merge order

No special cross-PR merge dependency declared. If the later consolidation pass finds overlapping edits to `source_registry.py` or `cors_app.py`, integrate connector/runtime code first, then semantically merge the small registry/runtime wiring diffs, then consolidate global docs/portfolio last.

## Tests

PR #181 final quality run #1296 passed Python compile, repository pytest, Expo Doctor, critical mobile wiring, and web bundle smoke. Source-specific tests cover works filtering, tender/plan semantics, identity, pagination, overlap cursor, duplicate-page fail-closed behavior, malformed envelopes, missing credentials, Signal staging, legacy TENDER projection, failure isolation and registry gating.

## Live validation

- Finland HILMA: NOT LIVE VALIDATED; credential missing.
- Denmark: NOT LIVE VALIDATED by this cell.
- Norway: technical route supported by evidence but NOT registered/live-validated by this cell.
- Sweden: no connector/live validation; partnership/license route only.
- Iceland: no connector/live validation.
- Estonia/Latvia/Lithuania: this cell relies only on pre-existing repository evidence and does not re-claim those validations as work performed here.

## Provenance rule for consolidation

`NORDICS_BALTICS_DEEP_COVERAGE.md`, connector/tests, PR #181 discussion/body and Git history together form the evidence chain. Important states must be interpreted temporally: research/implementation on 2026-08-25 does not imply future source availability. Later live observations must append/resolve with dates rather than silently overwrite history.

## Blockers

- Legitimate HILMA AVP key required for Finland live smoke and production promotion.
- Denmark system-provider access required before connector contract/live validation.
- Norway official subscription-key/reuse onboarding must be closed before production registration.
- Sweden requires acceptable commercial partnership/license economics or a future public machine-readable route.
- Iceland requires a sufficiently valuable low-burden official machine-readable route to justify bespoke ingestion.

## Merge risks

- `source_registry.py` and `cors_app.py` are canonical/high-contention files likely to be edited by parallel cells. Treat PR #181 changes as minimal semantic additions, never as authoritative whole-file versions.
- Country evidence for Estonia, Latvia and Lithuania is observational/reuse evidence; another cell owning those implementations remains authoritative for its own code/history.
- Finland source readiness must not be upgraded merely because CI is green.

## Safe integration notes

1. Preserve `FI_HILMA` stable identity; enrich that record rather than create aliases such as `FIN_HILMA` or URL-derived IDs.
2. Preserve ISO identities: FI/FIN, DK/DNK, NO/NOR, SE/SWE, EE/EST, LT/LTU, LV/LVA, IS/ISL.
3. Keep signal domains canonical: `TENDER` and `PROCUREMENT_PLAN`; country remains metadata.
4. Reuse `incremental_runtime_plugin`; do not create a Nordic runtime.
5. During consolidation, compare every parallel PR for the same countries/sources before touching global portfolio documents.
6. Resolve registry conflicts semantically at record level; never choose an entire branch copy of `source_registry.py`.
7. Preserve this manifest and the deep-coverage report after consolidation as historical evidence/archive.

## Zero-loss test

PASS. If the working branch disappears after PR merge, the implementation, tests, country decisions, blockers, provenance boundary and integration instructions are retained in repository files plus PR #181/Git history.

## Zero-duplication test

PASS WITH CONSOLIDATION CHECK REQUIRED. No duplicate Finland/HILMA implementation was found in current repository/PR search. Existing Estonia/Latvia/Lithuania sources were reused rather than recreated. Candidate Denmark/Norway/Sweden/Iceland sources were not inserted as competing registry records. The global pass must still compare all parallel PRs because unmerged parallel work is not assumed visible/canonical.

## Zero-silent-conflict test

PASS. The known Finland readiness overclaim is explicitly recorded above as a temporal conflict and corrected in the current branch. No other known contradiction is being silently selected.

## Zero-runtime-fork test

PASS. No `NordicsRuntime`, `BalticsRuntime`, or other regional silo exists. Finland installs through the existing unified runtime/plugin architecture.

## Final integration contract

Parallel evidence from this cell is not a parallel truth. The later international consolidation pass should consume this manifest as one input and converge it with all other cells into one market portfolio, one source registry, one Signal model, one connector architecture and one canonical runtime without deleting this research history.
