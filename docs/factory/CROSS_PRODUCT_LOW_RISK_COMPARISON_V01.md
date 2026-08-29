# Cross-Product Low-Risk Capability Comparison v0.1

Status: OBSERVATION_ONLY / NON_RUNTIME / NO_SHARED_EXTRACTION / NO_MERGE_AUTHORIZATION

## Evidence scope

Products compared on exact connected source/runtime evidence:

### ObraSignal
- repository: `MarcosTaz/Obrasignal`;
- canonical baseline: `main@66d43f6fd51cf9cea08016dad335aaa04b711a24`;
- relevant evidence: `.github/workflows/quality.yml`, `source_registry.py`, `source_health.py`.

### Aircraft Lease Cash Assurance
- repository: `MarcosTaz/money-leakage-auditor`;
- exact observed main: `8309836b6c2a23e0f2215f45d8137f5476f37412`;
- source path: `aircraft-lease-cash-assurance/`;
- relevant evidence: `FACTORY_BATON.md`, `SCANNER_DIRECTION_AUTHORITY_GATE_V031.md`, `ATTRIBUTION_GUARD_V033.md`, `DEEP_AUDIT_ADMISSION_GATE_V035.md`;
- no `.github` directory on observed main;
- no GitHub Actions workflow runs on observed exact head.

This comparison does not assume semantic equivalence from similar words.

## Decision matrix

| Candidate | ObraSignal | Aircraft Lease Cash Assurance | Classification | Action |
|---|---|---|---|---|
| Exact-head CI revision identity | Proven implementation | No equivalent implementation proven | ONE_IMPLEMENTATION_ONLY | Keep contract local; no shared extraction |
| Source-authority gating | Official/legal/machine/runtime source gates | Executed/applicable/public/demo source-authority gate | PATTERN_OVERLAP / DIFFERENT_AUTHORITY_LAYER | Do not share domain policy |
| Source health/freshness | Durable health, success/error, source-specific SLA, cursor | No equivalent durable source-health implementation proven | ONE_IMPLEMENTATION_ONLY | Keep local |
| Fail-closed evidence labels | Present across source/product gates | Present across scanner/cash gates | VOCABULARY_OVERLAP_ONLY | No shared code from labels alone |
| Cash attribution / baseline economics | Not equivalent | Proven domain-specific lease recovery logic | DOMAIN_SPECIFIC | Never centralize for reuse |
| Directionality of obligations | Not equivalent procurement semantic | Lessee/Lessor direction is core lease logic | DOMAIN_SPECIFIC | Never centralize for reuse |
| Deep-audit admission economics | Not equivalent | Domain-specific review threshold / recovery economics | DOMAIN_SPECIFIC | Never centralize for reuse |
| Static proof/evidence pages | ObraSignal has product web/mobile surfaces but no equivalent proof-pack implementation established here | Static HTML proof-registry / benchmark surfaces | NON_EQUIVALENT | No UI sharing claim |

## Source authority — apparent similarity that must not be over-abstracted

### ObraSignal authority layer

`source_registry.py` classifies procurement publishers/connectors by facts including:
- official source identity;
- legal reuse state;
- verified machine access;
- runtime readiness;
- adapter availability;
- freshness expectations and capabilities.

Its output controls whether a procurement source can be treated as technically/legal/runtime ready for ingestion.

`source_health.py` separately tracks operational ingestion truth such as attempts, successes, errors, durations, freshness and cursors.

### Aircraft Lease Cash Assurance authority layer

The scanner authority gate answers a different question: whether a piece of evidence is capable of supporting a **customer-specific recovery-side candidate**.

Examples:
- public accounting evidence is structural, not a customer finding;
- a public filed lease without confirmed applicability is only a public contract rule signal;
- demo/sanitized/unverified evidence is not a customer finding;
- an executed applicable customer document may support a recovery-side candidate but still does not prove realized recovery.

### Classification

Both products use evidence authority, but at different trust layers:

`OBRASIGNAL SOURCE AUTHORITY -> MAY THIS PROCUREMENT SOURCE ENTER THE INGESTION TRUST BOUNDARY?`

`AVIATION EVIDENCE AUTHORITY -> MAY THIS DOCUMENT/EVIDENCE SUPPORT A CUSTOMER-SPECIFIC RECOVERY CANDIDATE?`

These are **not equivalent implementations** and must not be merged into one generic boolean such as `trusted=true`.

Result: `PATTERN_OVERLAP / DOMAIN-SPECIFIC POLICY / NO_SHARED_EXTRACTION`.

## Narrow neutral seam that may be compared later

A future source-proven candidate may exist below both policy layers: a neutral evidence envelope that records provenance without deciding business meaning.

Potential neutral fields for later comparison only:
- immutable evidence/reference id;
- source/publisher identity;
- observed or captured timestamp;
- authority/provenance class as a product-owned enum;
- raw reference/location;
- applicability state as a product-owned value;
- verification state;
- lineage to the rule/decision that consumed it.

This is **not approved for implementation** because no equivalent data model or second consumer has yet been proven. The product-owned enums and policy remain isolated.

## Why a generic `trusted` flag is forbidden

A shared boolean would erase material distinctions:
- official publisher vs commercially reusable source;
- machine access verified vs runtime enabled;
- public structural evidence vs customer-applicable executed evidence;
- successful fetch vs durable persisted success;
- rule signal vs enforceable entitlement;
- customer candidate vs realized recovery.

Therefore:

`TRUST IS LAYERED, TYPED, AND PRODUCT-OWNED.`

Never:

`ANY PROVENANCE SIGNAL -> TRUSTED=true -> CROSS-PRODUCT AUTHORITY`.

## Current low-risk ranking after second-source comparison

1. **Exact-head CI contract** — lowest blast radius, but G1/G5 still fail because Aviation has no equivalent CI implementation.
2. **Neutral evidence-envelope concept** — potentially reusable later, but currently only conceptual pattern overlap; no equivalent source-level schema proven.
3. **Generic diagnostic/logging conventions** — not yet compared on a second implementation.
4. **CORS/header helpers** — no second implementation proven.
5. **Production smoke structure** — higher coupling; remains later-stage.

No candidate is currently `DUPLICATE_CANDIDATE` or `SHARED_PROVEN`.

## Eliminated from shared-platform extraction

The following Aircraft Lease Cash Assurance capabilities are explicitly product-owned:
- Lessee/Lessor payment direction classification;
- Maintenance Reserve / lease reimbursement semantics;
- customer recovery eligibility;
- realized cash attribution against a frozen baseline;
- executed-clause applicability rules;
- deep-audit recovery-floor economics;
- claim/recovery outcome meaning.

Similar rules in other recovery products must not be centralized merely because they use words such as evidence, entitlement, baseline, recovery or claim.

## ACTIVE / NEXT / WAIT

ACTIVE: continue comparing only low-risk horizontal surfaces against proven second product source trees; preserve domain-policy isolation.

NEXT: compare bounded diagnostic/logging or generic evidence-envelope structures only when a second concrete implementation is source-proven. If an exact-head CI implementation appears first, evaluate that candidate before higher-risk seams.

WAIT: no shared package, schema migration, runtime adapter, auth, tenant, persistence, billing, database, secrets, production rollout or cross-product dependency may be created from this comparison.
