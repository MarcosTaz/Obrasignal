# Operational Eligibility & Readiness Integration Cell

Status: **integration candidate only — do not merge automatically, do not promote queue/capability state, do not activate production**.

## Exact input heads

This branch is assembled repository-first from:

- `main`: `fce51d5b5524e09691f9187f7619ea0166217487`
- Q090 Company State PR #223: `31c77577e1b9cd82505e24e2dcf45cee7c29ed11`
- Opportunity Requirements PR #152: `020399a5fca4082272cbbe45eef67f13366a0c32`
- Opportunity Readiness PR #153: `5cfb2c3e751c19b59ca0a98e8d438a90bd0271c1`
- Golden Path GP02 PR #215 acceptance source: `1a2a9c5c4f66c663695905da0a693441f170738a`

Repository truth must be rechecked before any later integration/merge decision.

## Ownership

- Company State owns **what is known about the company**.
- Requirements owns **what the opportunity requires**.
- Readiness owns **how prepared/complete the company is**.
- `requirements_company_state_adapter.py` owns only the public comparison seam.

No downstream module reads Company State storage directly for eligibility comparison. `requirements_facts(...)` transports company facts without making an eligibility decision.

## Requirement comparison states

The integration preserves `MET`, `NOT_MET`, `UNKNOWN`, `NOT_EVALUATED`, `CONFLICT`, and `NOT_APPLICABLE`.

Absence is never converted to `NOT_MET`. Partial extraction is never converted to full eligibility. A profile preference is never converted to operational geography.

Certification handling is validity-aware: a matching current verified certification can be `MET`; an explicitly expired matching certification can be `NOT_MET`; a recorded certification with unknown validity remains `UNKNOWN`.

Workforce comparison uses `crew.available_count`, not `crew.total_count`. Missing availability remains `UNKNOWN`; known zero remains a real zero.

## Temporal precision

Readiness no longer coerces date-only or broader precision into an invented instant.

The parser preserves `DATE`, `MONTH`, `QUARTER`, `YEAR`, `DATETIME`, and `UNKNOWN`. A `DATETIME` without an authoritative timezone remains unresolved. Only a timezone-aware datetime, or a naive datetime with an explicit valid `deadline_timezone`, may be classified as exactly open/due/expired.

This closes `BUG-GP-READINESS-DATE-001`; the GP02 strict expected failure is replaced by a normal passing acceptance test in this integration branch.

## Economic Fit separation

`opportunity_readiness.py` no longer passes canonical Company State into the legacy profile-shaped `evaluate_economic_fit(...)` interface. Economic Fit is resolved separately at the HTTP adapter using legacy Company Profile until that domain exposes a canonical Company State adapter.

A failure in Economic Fit becomes `UNKNOWN`, never favourable.

## Tenant boundary

The API derives account identity from the trusted authentication provider. Company State is loaded for that tenant only. A mismatched Company State fails closed with `503 readiness_unavailable`; no foreign company facts are serialized.

Company State storage/provider failure becomes an explicit `company_state_unavailable` critical unknown.

## Evidence

Q080 has integration candidates but no public Evidence contract on the requested integration base (`main + Q090 + Requirements + Readiness`). This branch therefore does **not** import Evidence internals.

Readiness exposes `evidence_contract.status = UNAVAILABLE`. Existing raw source references, requirement locators, Company State fact IDs, provenance bases and evidence references are preserved for a future public Q080 adapter.

## Product API

`readiness_api.install_readiness_api(...)` is a real authenticated read-only API adapter for `GET /api/v1/opportunities/{id}/readiness`.

It consumes canonical opportunity/lifecycle data, optional Signal requirement context, tenant Company State, Requirements comparison and separately-owned Economic Fit.

This integration intentionally does **not** modify `cors_app.py`, so no production route/capability is registered by this cell.

## Adversarial coverage

Acceptance tests cover missing/expired/unknown-validity/conflicting certification; trade/total crew without available crew; known zero/unknown/sufficient available crew; known wrong operational geography; preferred geography only; date/month/quarter/year precision; datetime with unknown/explicit timezone; partial Requirements extraction; Requirements conflict; cross-tenant Company State; Company State and Requirements provider failure; explicit Q080 `UNAVAILABLE`; and absence of pursuit decision vocabulary.

## Integration Lab handoff

Combination under test: `current main + Q090 + Requirements + Readiness`.

The dedicated workflow checks out the exact PR head and runs integration, API, architecture and Golden GP02 acceptance tests. General repository Quality remains the broader regression gate.

## Golden Path handoff

GP02 is transported to canonical Company State semantics. The date-only test is no longer `xfail`; it must pass normally before this branch is considered stable.

## Sentinel handoff

Fitness invariants protect: no legacy Economic Fit import inside Readiness policy; Requirements/Company State comparison through `requirements_facts(...)`, not storage; preferred geography filtering; availability at the Requirements seam; expired/non-current facts explicitly transported; no production runtime registration; and no Master Queue/capability-registry ownership inside integration modules.

No automatic merge.
