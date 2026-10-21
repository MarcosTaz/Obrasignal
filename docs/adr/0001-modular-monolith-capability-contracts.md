# ADR 0001 — Modular monolith, capability contracts and contextual simplicity

**Status:** Accepted  
**Date:** 2026-08-24

## Context

ObraSignal is evolving from procurement discovery into a Contractor Intelligence Operating System with many capabilities: SIGNAL, FUTURE DEMAND, FORCED DEMAND, UNLOCK, SUPPLY EDGE, TRUSTBRIDGE, MOBILIZE, SITE READY, MICROWORKS, OFFICE, DNA, SHADOW, COMMAND, ACTION and future engines.

The risk is not lack of functionality. The risk is architectural and UX scope inflation: direct module coupling, incompatible schemas, independent notification/workflow behavior, vendor lock-in, untraceable decisions and a UI that exposes the internal module graph.

## Decision

ObraSignal will use a **modular monolith by default**. Logical modularity comes first; physical service distribution is allowed only when scale, deployment, security, ownership or failure-isolation evidence justifies it.

The architectural north star is:

> SMALL STABLE CORE + REPLACEABLE CAPABILITIES + STANDARD CONTRACTS + CONTEXTUAL UX + ONE INTELLIGENCE LAYER.

### Stable Core

The Core changes slowly and contains only broadly reusable concepts/services: identity, organizations, users/roles, projects, opportunities, locations, documents/entities, evidence/provenance, permissions, events, notifications, audit and configuration.

Module-specific business logic must not migrate into Core merely for convenience.

### Capability boundaries

A capability owns its private implementation and data. Other capabilities may consume only explicit versioned contracts, canonical entities or published events. Direct reads/writes of another capability's private storage are prohibited unless documented as a temporary migration bridge with a removal plan.

### Contract first

Internal interfaces and events are versioned and validated. Optional fields, errors and compatibility expectations are explicit. Changes that break a consumer require a version transition rather than silent mutation.

### Event driven where appropriate

Events decouple producers from unknown consumers. Examples include `crew.capacity_changed`, `project.start_date_changed`, `supplier.quote_received`, `opportunity.updated`, `payment.status_changed` and `project.delay_detected`. Events are not used merely to imitate distributed systems; direct in-process calls remain appropriate for synchronous contracts.

### Canonical data language

Capabilities should reuse canonical concepts such as Opportunity, Project, Organization, Person, Location, Capacity, Requirement, Material, Product, Supplier, Quote, Contract, Asset, Event, Evidence, Task, Decision, Action and Transaction. New local models are allowed where genuinely domain-specific, but must not create a competing system language.

### Connectors

External integration remains:

`SOURCE → CONNECTOR → NORMALIZATION → CANONICAL MODEL → PRODUCT ENGINE`

Native source schemas do not leak into product logic.

### Capability Registry and flags

Capabilities declare lifecycle state, health, contracts, dependencies, ownership and flags. Lifecycle states are `RESEARCH`, `EXPERIMENT`, `PILOT`, `ENABLED`, `DISABLED`, `DEPRECATED`. Health is `HEALTHY`, `DEGRADED`, `UNAVAILABLE`.

Feature flags may scope rollout by environment, customer, country, role, subscription or cohort, with a kill switch where failure could materially affect the platform.

### Policy/workflow/state discipline

Reusable policy evaluation is preferred over scattered hard-coded decision thresholds. Long-running workflows must expose explicit state, retries, timeout/failure paths, audit and idempotency. Important entity lifecycles use explicit state machines rather than hidden inference.

### Decision evidence

The existing decision log is not treated as the final Decision Ledger. The richer ledger evolves alongside Evidence Graph and Outcome Graph work and will include material inputs, assumptions, evidence, model/rule versions, output, confidence, timestamp and later outcome. Critical engines should support replay and shadow evaluation before promotion.

### Failure isolation

Capability or connector failure must degrade gracefully. `UNAVAILABLE` is not equivalent to an empty result. External calls use bounded timeout/retry/backoff and circuit breaking when justified. Heavy jobs should become asynchronous when that improves latency/failure isolation, but no queue infrastructure is added merely for architectural fashion.

### UX

The UI does not mirror the module graph. Primary surfaces remain few and contextual (for example HOME, WORK, OFFICE, MARKET, COMMAND). Advanced complexity is progressively disclosed. A universal Command surface may route intent through multiple capabilities without requiring users to know their names. Pending human decisions converge into one Action Center with centralized notification policy.

### Privacy/security

Minimum data required, maximum intelligence extracted. Deep integrations are optional and consented. Least privilege applies between capabilities and roles.

## Architecture fitness gate

A new capability is not architecturally complete until reviewers can answer positively, or document an explicit exception, to:

1. Can it be isolated?
2. Can it be disabled?
3. Can it be tested independently?
4. Can it be replaced with limited blast radius?
5. Does it use canonical contracts/data where appropriate?
6. Does it avoid unnecessary coupling/circular dependencies?
7. Does it avoid proportional UI complexity?
8. Can it fail without collapsing unrelated capabilities?
9. Is it observable and failure-transparent?
10. Is the economic/product reason strong enough to justify its complexity?

## Consequences

- No microservices theatre.
- No module-specific menu by default.
- No direct vendor/API schema propagation into product logic.
- No hidden automatic action without idempotency/authorization/audit appropriate to risk.
- Architectural debt is corrected when it blocks the next economically valuable step, not through indiscriminate rewrites.
- Current execution priority remains owned exclusively by `master_execution_queue.py`; this ADR is a cross-cutting guardrail, not a parallel roadmap.
