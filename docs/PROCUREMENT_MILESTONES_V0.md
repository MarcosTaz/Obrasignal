# Procurement Milestones / Bid Calendar Engine v0

## PURPOSE
Provide a conservative canonical representation of procurement dates so product consumers can answer what date exists, what it means, how precise it is, where it came from, whether it was superseded, and whether conflicting evidence remains unresolved.

## NON-GOALS
This module is not a generic calendar, alert engine, workflow/task manager, legal business-day calculator, PDF/OCR deadline extractor, Google/Microsoft Calendar integration, COMMAND recommendation engine, or bid/no-bid decision system. It performs no network calls.

## MILESTONE TYPES
The central `MilestoneType` registry supports publication/document availability, site visit and registration, clarification/questions, EOI, qualification, bid submission/opening/validity, standstill, expected/actual award, contract signing, expected/actual contract start, guarantee deadline, OTHER and UNKNOWN. Strings are not scattered through product logic.

## DATE BASIS
`OFFICIAL`, `SOURCE_DERIVED`, `SYSTEM_DERIVED`, `USER_ENTERED`, `INFERRED`, and `UNKNOWN` are explicit. Legacy adapter date fields are treated as official source facts because they are already normalized source data. Derived values must be supplied explicitly by adapters/consumers; v0 does not manufacture legal deadlines.

## PRECISION
`EXACT_DATETIME`, `DATE`, `MONTH`, `QUARTER`, `YEAR`, `RANGE`, `APPROXIMATE`, and `UNKNOWN` remain distinct. A date-only value never receives 23:59. `Q3 2027` remains a quarter; it is not converted to 1 July. Approximate text remains approximate.

## TIMEZONE
Exact datetimes preserve an explicit timezone when supplied. A naive timestamp with no timezone remains timezone-unknown and therefore cannot produce a precise temporal status. `zoneinfo` validates IANA zone names and provides DST-aware arithmetic. Source adapters should preserve publisher semantics before handing canonical values to this module.

A legacy adapter that has already converted a native source timestamp into UTC without separately carrying the publisher timezone cannot have that lost timezone reconstructed safely by this core. CanadaBuys is a concrete example: its connector preserves the closing instant by converting the publisher's fixed UTC-05:00 timestamp to UTC, but a future structured milestone emitted by that adapter is needed if the original fixed-offset semantics must also be displayed. The core deliberately contains no `if source == ...` recovery logic.

## DATE RANGES
Ranges require both start and end and reject start > end. v0 does not infer ranges from month/quarter values; lower precision remains lower precision.

## LOTS
Milestones can be scoped by `lot_id`. Deadlines for different lots are separate resolution groups and never collapse to one opportunity deadline. Opportunity-level inheritance into lots is intentionally not performed in v0 because inheritance semantics are source/procedure dependent.

## MULTI-STAGE PROCUREMENT
The optional `stage` dimension keeps EOI, qualification and later bid stages independent without creating a workflow engine.

## SUPERSESSION
A new milestone may explicitly point at `supersedes_milestone_id`. Resolution marks the older item `SUPERSEDED` while retaining it in history and exposes the replacement as current. No historical row is silently overwritten by the pure service.

## CONFLICTS
If multiple non-cancelled, non-superseded milestones exist in the same opportunity/lot/stage/type group with different temporal values, every active candidate is marked `NEEDS_VERIFICATION`. v0 deliberately refuses silent winner selection without explicit revision evidence. Multiple sources carrying the same effective value are non-conflicting and may remain as separate provenance-bearing facts; cross-source provenance collapsing is deferred until the repository has a canonical multi-evidence container rather than discarding evidence in the name of deduplication.

## SOURCE NORMALIZATION
`normalize_milestones(source_record)` consumes already-ingested records. Rich adapters may supply a `milestones` array with type, value/range, precision, timezone, basis, requirement level, provenance, lot/stage and revision metadata. Existing flattened fields such as `deadline`, `publication_date`, `question_deadline`, `eoi_deadline`, `qualification_deadline`, `opening_date`, `expected_award`, and `expected_contract_start` are mapped conservatively for backward compatibility.

Source-native parsing belongs in adapters. OCDS/eForms/SAM/Canada/source-specific XML/JSON must not leak conditional source logic into this core module. OCDS periods such as `tenderPeriod`, `enquiryPeriod`, `awardPeriod`, and `contractPeriod` should be mapped by the OCDS adapter only when their semantics are defensible for the source implementation.

## PROVENANCE
Each milestone carries source, source reference, source field, native label, basis, confidence and normalizer version. Deterministic IDs/fingerprints exclude retrieval timestamps. Oversized native labels are rejected.

## READ MODEL / API
v0 exposes deterministic in-process read helpers: `resolve_current_milestones`, `temporal_status`, and `next_upcoming_milestone`. A public HTTP endpoint is intentionally not added in this parallel branch because the repository's current opportunity API is tightly coupled to the legacy tender read model; adding a route before persistence/integration ownership is settled would create a misleading API contract. A future endpoint can serialize the stable dataclasses without changing source adapters.

## CAPABILITY REGISTRY
v0 is intentionally not registered as `PILOT`/`ENABLED`: there is no runtime wiring or public product surface yet, and registration would imply an integration state that does not exist. This branch therefore makes no capability-maturity claim. Registration is an integration step after persistence/source wiring is selected and tested.

## ICS LIMITS
ICS export is not implemented in v0. It is safe only for sufficiently precise current milestones and should never coerce month/quarter/approximate/unknown values into fake event timestamps.

## TESTS
The dedicated suite covers publication, exact and date-only submission, partial precision, ranges, invalid dates/ranges/timezones, unknown timezone behavior, DST, mandatory/optional site visits, questions, EOI, qualification, opening, bid validity, expected/actual award, expected/actual contract start, provenance/basis, idempotency, duplicate suppression, supersession/history, unresolved conflict, lot separation, multi-stage separation, cancellation, deterministic next milestone and explicit absence of alert/pursuit side effects.

## SECURITY
Input validation rejects impossible ISO dates, invalid IANA zones, invalid ranges, confidence outside 0..1 and oversized native labels. Native metadata remains inert data: the module does not execute labels/metadata, construct SQL, render HTML, make network calls, or access tenant-private data. Public procurement milestones are treated as shared source facts; private user annotations are out of scope.

## KNOWN LIMITATIONS
- No persistence/migration: v0 is a pure capability contract/read model.
- No automatic legal/business-day calculations.
- No arbitrary natural-language date parser.
- No source precedence policy beyond explicit supersession; conflicts remain visible.
- No cross-source evidence collapsing until a canonical multi-provenance container exists.
- No lot inheritance.
- No Change History event emission; explicit supersession is compatible with future history integration.
- Legacy adapters may already have discarded native timezone/precision metadata; the core cannot safely recreate it.
- No HTTP/UI integration in this isolated parallel branch.

## FUTURE CONSUMERS
Alerts, Readiness, Pursuit Workspace, Decision Brief and COMMAND may consume milestone facts/state through an explicit contract. They must own notification, readiness, prioritization and action semantics respectively.

## ROLLBACK
The capability is additive. Rollback is deletion of `procurement_milestones.py`, its dedicated tests and this document. No database migration, source-record mutation, capability-registry change or Master Queue change is involved.
