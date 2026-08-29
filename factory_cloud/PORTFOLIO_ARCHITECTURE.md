# Factory Cloud — Shared Platform Portfolio Architecture

## Purpose

Organize the application portfolio so new companies inherit proven capabilities instead of rebuilding ObraSignal-sized infrastructure independently.

The control rule is:

**reuse common capability first → keep vertical economics isolated → promote shared capabilities only after they are proven reusable.**

This does not authorize cross-app production access, shared secrets, customer-data sharing, billing mutation, deployment mutation, merge, or any other authority already excluded by Factory Cloud safety boundaries.

## Hierarchy

### 0. Factory Cloud / Control Tower

Owns orchestration metadata, BATON continuity, source verification, priority, dispatch and capability discovery.

It must not become the business-logic home of any vertical.

### 1. Shared Platform

Reusable infrastructure candidates:

- identity / authentication
- tenant and role isolation
- billing interfaces and entitlement gates
- document intake and storage contracts
- audit trail / decision lineage
- notifications
- observability
- deployment / release contracts
- backup / recovery contracts
- common security guardrails

A capability is not considered shared merely because two projects have similar code. Promotion requires an explicit stable contract and regression coverage.

### 2. Evidence & Economic Assurance Kernel

Reusable recovery/assurance primitives:

- contract / document ingestion contract
- structured obligation and entitlement representation
- evidence lineage and confidence state
- deterministic calculations with reproducible inputs
- deadlines / notice windows / expiry handling
- finding state and review workflow
- claim / recovery workflow abstractions
- duplicate / overlap detection
- fail-closed unresolved-evidence state
- recovery outcome and fee lineage

The kernel provides primitives, not vertical legal or commercial conclusions.

### 3. Vertical Applications

Each company retains its own domain vocabulary, economics, evidence requirements, calculations, workflows, outputs, source truth, repository authority and customer data.

Current priority recovery/assurance verticals include:

- Industrial Supplier Claims & Margin Recovery
- Aviation Lease Entitlement Recovery
- WarrantyGuard
- ContractCredit
- GuaranteeRelease
- DebtRecover
- RoyaltyRecover
- GovMargin
- GridRecover
- DealRecover
- Capacity Commitment
- LongLead
- Product Market Access / Legal Product Checker
- EU Cloud Switching / Migration Capital Network

ObraSignal remains a major application with domain-specific construction/procurement workflows and can consume shared infrastructure where contracts are genuinely reusable.

## Maturity gates

Every company advances through the same gates. Code volume is not a maturity metric.

### G0 — Thesis validated enough to build

Required truth:
- explicit buyer / ICP hypothesis
- defined economic pain
- differentiated wedge
- evidence that the problem exists
- explicit unknowns and rejection criteria

### G1 — Assisted offer defined

Required truth:
- exact inputs accepted
- exact output delivered
- what is manual vs automated
- pricing hypothesis
- fail-closed conditions
- customer-facing claim boundaries

### G2 — Minimum operation works

Required flow:

`intake → analysis → finding → evidence pack → review → action/recovery → outcome record`

Synthetic cases are acceptable here. Unsupported findings must fail closed.

### G3 — Pilot capable

Required truth:
- deterministic core path
- evidence lineage
- tenant isolation where multi-customer
- recovery / restart behavior
- synthetic adversarial cases
- delivery economics
- pilot onboarding and exit criteria

### G4 — First customer / first paid outcome

Required truth:
- real delivery completed
- value and cost measured
- operational gaps recorded
- no invented recovery or unsupported customer claim

### G5 — Repeatable

Required truth:
- multiple deliveries or equivalent repeated proof
- common failure modes handled
- reusable capability candidates identified
- stable unit economics direction

### G6 — Scale ready

Only now should a vertical routinely receive ObraSignal-level engineering depth where warranted:
- deeper automation
- integrations
- advanced dashboards
- continuous monitoring
- stronger SRE / release controls
- specialized agents

## Engineering investment rule

Approximate target depth relative to a mature application:

- G0 validation: 10–20%
- G1/G2 assisted + minimum operation: 20–40%
- G3 pilot capable: 30–50%
- G4 first paid delivery: 40–60%
- G5 repeatable: 60–80%
- G6 scale: as much as the evidence justifies

These are allocation heuristics, not progress percentages.

## Capability promotion rule

When a vertical builds a useful capability, Factory Cloud should classify it as one of:

1. `VERTICAL_ONLY` — domain-specific; keep local.
2. `CANDIDATE_SHARED` — appears reusable; do not couple other apps yet.
3. `SHARED_CONTRACT_PROPOSED` — stable interface and isolation boundary drafted.
4. `SHARED_VERIFIED` — regression-tested against at least two consuming contexts.
5. `SHARED_CORE` — canonical reusable capability with ownership and compatibility rules.

No copy/paste promotion. No shared database authority is implied.

## Portfolio scheduling rule

Factory Cloud should prioritize work by commercial and safety leverage, not repository size:

1. regressions / safety failures
2. work blocking pilot or first paid delivery
3. shared capability that unblocks multiple pilot-capable companies
4. evidence / calculation integrity
5. minimum operational completeness
6. commercial readiness
7. scale-only polish

A younger company may outrank ObraSignal if one small task moves it materially closer to a paid pilot.

## Initial shared-capability extraction candidates from ObraSignal

These are candidates only and require contract extraction before reuse:

- authentication / JWT verification patterns
- account / tenant scoping patterns
- billing gate patterns
- notification event patterns
- decision lineage / audit patterns
- persistent state and recovery patterns
- release / CI safety patterns

The extraction objective is to create reusable contracts, not to make other products depend on ObraSignal business modules.

## Factory Cloud next implementation slices

1. Add machine-readable portfolio architecture metadata.
2. Map every registered Factory to maturity gate and family.
3. Add missing current Factories without inventing source/repository authority.
4. Add capability inventory and promotion state.
5. Add prioritization inputs for `pilot_blocker`, `commercial_leverage`, `shared_leverage`, `safety_severity`.
6. Keep dispatch fail-closed when a Factory source is unresolved.
7. Add UI grouping: Control → Shared Platform → Kernel → Verticals → Specialist lanes.
8. Only after metadata is stable, wire orchestration decisions to these fields.
