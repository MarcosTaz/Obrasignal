# Customer Decision & Outcome Intelligence v1

Status: additive integration candidate. No runtime registration, migration, queue promotion, deployment, or automatic merge.

## Purpose

This contract owns only the unowned composition layer between existing domain owners:

`Opportunity -> source/evidence/company/readiness/economics -> explicit pursuit decision -> observed outcome -> review/learning observation`.

It does not own or replace any source of truth.

## Ownership boundaries

| Concern | Canonical/parallel owner consumed | This contract does |
| --- | --- | --- |
| Opportunity/source truth | canonical Opportunity + Source/Lifecycle | captures identity/version/fingerprint metadata only |
| Evidence/provenance | Q080 Evidence | consumes public decision-evidence envelope only |
| Company operational reality | Q090 Company State | consumes public adapter metadata; never copies private facts into audit |
| Operational bid readiness | Opportunity Readiness #153/#239 | preserves READY/CONDITIONALLY_READY/NOT_READY/UNKNOWN/CONFLICT semantics; never emits a pursuit choice |
| Economics | canonical Economics / Execution Economics | preserves UNKNOWN/STALE/UNAVAILABLE/CONFLICTED; never manufactures profit |
| Explicit pursuit choice | Pursuit Decision Journal #160 | consumes PURSUE/NO_BID/HOLD/NEEDS_INFO/UNDECIDED as explicit history |
| Outcome | Outcome Capture #163 / Q100 | consumes BID_SUBMITTED/WON/LOST/WITHDRAWN/NO_SUBMISSION/CANCELLED/UNKNOWN |
| Change history | Opportunity Change History #155 and owner snapshots | compares only public versions/refs/fingerprints supplied to the seam |
| Workflow/watch/workspace | their owners | not persisted or mutated here |

Important semantic boundary: `NO_BID` is an explicit pursuit decision, while `NO_SUBMISSION` is an observed outcome. They are not interchangeable.

## Truth contract

Every decision dependency is represented as exactly one of:

- `KNOWN`
- `UNKNOWN`
- `STALE`
- `UNAVAILABLE`
- `CONFLICTED`

Numeric zero is never used as a truth state. An economic owner may expose an internal score of zero together with `status=UNKNOWN`; this layer preserves the status as `UNKNOWN`.

A contract can be known while containing explicitly listed unknown sub-inputs. Those unknowns remain visible in the audit and are never converted into false negatives.

## Decision support vs recommendation

The contract exposes action support, not autonomous recommendations:

- `VIEW`: supported when a canonical opportunity identity exists.
- `WATCH`: customer-controlled observation; does not imply suitability.
- `INVESTIGATE`: valid precisely when facts remain incomplete or disputed.
- `PURSUE`: only reported as `RECORDED_EXPLICIT_DECISION` when the Decision Journal already contains explicit `PURSUE`; otherwise `EXPLICIT_CUSTOMER_DECISION_REQUIRED`.
- `DECLINE`: only reported as `RECORDED_EXPLICIT_DECISION` when the Decision Journal contains explicit `NO_BID`; otherwise `EXPLICIT_CUSTOMER_DECISION_REQUIRED`.

Readiness, match score, evidence completeness, and economics can make the decision context reviewable or degraded, but none can synthesize PURSUE/NO_BID.

## Audit contract

`build_decision_audit(...)` returns a tenant-private, privacy-safe read model with:

- opportunity identity;
- contract/version/ref/fingerprint for each dependency;
- explicit epistemic state per dependency;
- unknown inputs;
- current explicit pursuit decision when one exists;
- current observed outcome when one exists;
- action-support boundary;
- stable audit fingerprint;
- change-impact result against an optional prior audit.

The Company State adapter deliberately excludes raw private fact payloads. The decision audit carries only bounded metadata needed to reproduce which snapshot was used.

## Change intelligence

`compare_decision_audits(...)` compares public dependency metadata without mutating prior state.

A material change in source truth, Evidence, Company State, Readiness, or Economics after an explicit pursuit decision can produce `REVIEW_REQUIRED`. The historical decision remains unchanged and `historical_decision_preserved=true`.

A stale, unavailable, unknown, or conflicted current critical dependency can also require review. This is a request to reassess the existing decision, not an automatic reversal.

## Outcome and learning safety

`learning_observation(...)` emits an `OBSERVED_PAIR` only when both an explicit pursuit decision and an observed non-UNKNOWN outcome exist.

Even then:

- `causal_attribution=NOT_ESTABLISHED`;
- `model_update_allowed=false`.

One win does not prove a good decision and one loss does not prove a bad decision. No ranking/filter/ICP rule may self-update from this v1 seam.

## Tenant/privacy boundaries

- account mismatch in Company State, Readiness, Pursuit Decision, Outcome, or a supplied input fails closed;
- audits for different tenants cannot be compared;
- audits for different opportunities cannot be compared;
- arbitrary raw owner payloads are not persisted by this module;
- no production logging, external fetch, DB write, API registration, or UI rendering is introduced.

## Adversarial regression matrix

Tests cover:

- UNKNOWN economics with numeric `score=0` remaining UNKNOWN;
- missing decision != NO_BID;
- missing outcome != LOST;
- NO_BID decision != NO_SUBMISSION outcome;
- READY readiness never becoming PURSUE;
- Company State private fact non-copying;
- Company State conflict preservation;
- Readiness unknown/conflict preservation;
- Q080 unavailable/missing-input semantics;
- cross-tenant fail-closed behavior;
- duplicate dependency rejection;
- material Company State drift after PURSUE -> REVIEW_REQUIRED with history preserved;
- stale critical input -> REVIEW_REQUIRED without recommendation flip;
- outcome correction not rewriting the historical decision;
- observed decision/outcome pair not granting causal/model-update authority.

## Integration handoff

The safest next integration sequence is:

1. validate this additive seam on current main;
2. combine with current Q080 + Q090 + Readiness + Economics candidates through Integration Lab public contracts only;
3. combine with Decision Journal #160 and Outcome #163 without importing their storage internals;
4. add Golden acceptance for stale evidence, Company State change, economic UNKNOWN, conflicting facts, expired opportunity, cross-tenant state, and historical-decision preservation;
5. only after the upstream owners are canonical, decide whether a bounded authenticated read-only API/UI surface is warranted.

No merge, deployment, source activation, capability promotion, queue mutation, secret/config mutation, or production data mutation is authorized by this candidate.
