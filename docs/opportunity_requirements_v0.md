# Opportunity Requirements / Eligibility Checklist v0

## PURPOSE

Answer one bounded question: **what must a contractor prove or satisfy to submit a valid bid for this opportunity?**

The capability converts explicit structured source fields and already-parsed official text into a small, auditable checklist. It is conservative by design: silence or missing data means **UNKNOWN**, never `NOT REQUIRED`.

## NON-GOALS

V0 does not implement Opportunity Unlock, partner search, finance/bond/insurance sourcing, hiring, equipment rental, consortium creation, bid submission, global registry verification, OCR, document generation, or an LLM-based document intelligence pipeline.

It also does not promote `Q110_DYNAMIC_ELIGIBILITY_RESEARCH` or otherwise alter the canonical Master Execution Queue.

## DOMAIN MODEL

`OpportunityRequirement` is the canonical v0 contract. Its material fields are:

- stable `requirement_id` and `opportunity_id`;
- `category` and `requirement_type`;
- human-readable `description`;
- `priority`: `MANDATORY | OPTIONAL | PREFERRED | UNKNOWN`;
- optional comparison semantics: `operator`, `required_value`, `unit`, `currency`, `period`, `jurisdiction`;
- one or more `RequirementEvidence` records;
- `confidence` and lifecycle `status`;
- extractor and normalization versions.

`OpportunityRequirementsChecklist` is the read model. It reports requirements and counts without reducing incomplete evidence to a binary Eligible/Not Eligible verdict.

## REQUIREMENT CATEGORIES

V0 consolidates requirements into: `LEGAL`, `FINANCIAL`, `TECHNICAL`, `EXPERIENCE`, `CERTIFICATION`, `INSURANCE`, `GUARANTEE`, `WORKFORCE`, `EQUIPMENT`, `REGISTRATION`, `GEOGRAPHY`, `DOCUMENT`, `CONSORTIUM`, and `OTHER`.

These categories are a normalization vocabulary, not a claim that every opportunity contains every category.

## EVIDENCE RULES

A material requirement must carry evidence sufficient to answer **“show me where it says that.”** `RequirementEvidence` keeps:

- source reference;
- locator (field path or parsed-text sentence locator in v0);
- extraction method;
- raw value/text;
- source version;
- optional document id and observation timestamp.

Priority is: explicit structured official data, then explicit official parsed text, then derived extraction. V0 does not promote ambiguous AI output to fact and has no LLM dependency.

Evidence Graph is not duplicated. The v0 evidence object is deliberately adapter-friendly so it can later point at the canonical Evidence Graph when Q080 is available.

## UNKNOWN SEMANTICS

`UNKNOWN` means evidence is insufficient. It is distinct from:

- `OPTIONAL` or `PREFERRED`;
- `NOT_MET`;
- “not required”.

Missing company data is never treated as proof of non-compliance. A non-empty list of recorded certifications is also not assumed exhaustive.

## NORMALIZATION

Normalization occurs only when semantics are safe. V0 supports canonical currency identifiers, numeric values, count/years/percentage-style units, and period/jurisdiction preservation. The raw representation remains attached to evidence.

A value such as annual turnover is not compared with project value merely because both are money. Period and requirement type remain part of identity and comparison semantics.

## EXTRACTION

`StructuredRequirementExtractor` is deterministic and cheap. It accepts an explicit `requirements` list and a small set of normalized fields such as `minimum_turnover`, `required_certifications`, `minimum_experience_years`, insurance, guarantees, workforce, equipment, registration, documents, geography and consortium conditions.

`ConservativeTextRequirementExtractor` operates only on text that has already been parsed. V0 intentionally recognizes only narrow bidder-facing certification obligations. Mere mentions, negations and historical context are ignored. This limits recall in order to protect precision.

No country-specific extractor is introduced where the generic contract is sufficient.

## DEDUPLICATION AND CONFLICTS

Stable IDs are derived from opportunity identity and normalized requirement semantics, not extraction time. Reprocessing the same source version is therefore idempotent at the contract level.

Equivalent requirements merge evidence. When two current requirements share the same semantic subject but assert incompatible values, both are retained and marked `CONFLICT`; the system does not silently choose one.

## VERSIONING AND SUPERSESSION

Requirements retain `extractor_version`, `normalization_version`, evidence `source_version`, and lifecycle state. `supersede()` preserves the former requirement as `SUPERSEDED` and records the relationship from the replacement.

This is deliberately sufficient for later corrigenda/change-alert integration without implementing alerts now.

## COMPANY EVALUATION

The current persisted company profile is not the queued Company State contract. It contains useful fields such as certifications but does not establish authoritative turnover, insurance, workforce, equipment, references or guarantee capacity.

Accordingly v0 does **not** infer those facts. The core assessment helper can confirm an exact recorded certification (`MET`) but otherwise returns `UNKNOWN`/`NOT_EVALUATED`; absence from an open-ended profile is not `NOT_MET`.

Assessment calls may bind an expected `account_id`; a profile from another account is rejected. This prevents accidental cross-tenant use at the capability boundary. Rich tenant-private assessment persistence remains future Company State work.

## SECURITY

Source text is untrusted data. The capability does not execute source content, does not render source HTML, performs no filesystem/path access, constructs no SQL, and serializes plain values only. Consumers must continue to HTML-escape descriptions/evidence at render time.

Do not log full private documents. Public opportunity requirements and tenant-private company assessments remain separate domains.

## TESTS

The dedicated test module covers structured financial/certification/experience/insurance/guarantee/workforce/equipment/registration/document/geography/consortium extraction, mandatory/optional/preferred/unknown semantics, raw-value preservation, currency normalization, period semantics, idempotency, evidence merge, conflicts, supersession, missing data, deterministic IDs, tenant-bound assessment, and false-positive/negation/context controls for parsed text.

## LIMITATIONS

- no persistence table yet; requirements are computed from supplied normalized context;
- no API/UI wiring until a canonical source-to-requirements input path is established without leaking native connector schemas into product logic;
- parsed-text extraction is intentionally narrow;
- no authoritative negative company facts exist in the current profile, so v0 refuses to manufacture `NOT_MET` blockers;
- no full corrigenda resolver; supersession is represented but upstream source-version selection remains the caller's responsibility.

These are deliberate v0 boundaries, not claims of completed future architecture.

## FUTURE UNLOCK INTEGRATION

A future Dynamic Eligibility / Opportunity Unlock capability may consume stable requirement IDs and explicit `NOT_MET` facts to model blocker-removal routes. This module will not search partners, source capital, acquire qualifications, or transform a requirement into an unlock plan.

The intended evolution is:

`explicit requirement -> evidence-backed company comparison -> known blocker (when provable) -> future unlock route`

The first arrow is implemented here; the later arrows remain gated by Company State, Evidence Graph and Dynamic Eligibility work.
