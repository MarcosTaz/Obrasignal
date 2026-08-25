"""Public consumer seams for Company State without importing private downstream internals."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from company_state import CompanyState, FactCategory, FreshnessState, KnowledgeState, Money


@dataclass(frozen=True)
class AdapterValue:
    """Consumer-safe value envelope that preserves epistemic/source basis."""

    state: str
    value: Any = None
    fact_ids: tuple[str, ...] = ()
    reason: str | None = None
    knowledge_states: tuple[str, ...] = ()
    provenance_bases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = self.value.to_dict() if isinstance(self.value, Money) else self.value
        return {
            "state": self.state,
            "value": value,
            "fact_ids": list(self.fact_ids),
            "reason": self.reason,
            "knowledge_states": list(self.knowledge_states),
            "provenance_bases": list(self.provenance_bases),
        }


def _metadata(facts) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        tuple(sorted({fact.knowledge.value for fact in facts})),
        tuple(sorted({fact.provenance.basis.value for fact in facts})),
    )


def _extract(state: CompanyState, code: str, category: FactCategory, *, as_of: datetime | None = None) -> AdapterValue:
    at = as_of or state.as_of
    matching = [fact for fact in state.active_facts(as_of=at) if fact.code == code and fact.category is category]
    if not matching:
        return AdapterValue("UNKNOWN", reason="fact_not_recorded")

    current = [fact for fact in matching if fact.freshness(at) is not FreshnessState.STALE]
    if not current:
        knowledge, provenance = _metadata(matching)
        return AdapterValue(
            "UNKNOWN",
            fact_ids=tuple(sorted(f.fact_id for f in matching)),
            reason="fact_stale",
            knowledge_states=knowledge,
            provenance_bases=provenance,
        )

    knowledge, provenance = _metadata(current)
    known = [fact for fact in current if fact.knowledge is not KnowledgeState.UNKNOWN]
    if not known:
        return AdapterValue(
            "UNKNOWN",
            fact_ids=tuple(sorted(f.fact_id for f in current)),
            reason="explicit_unknown",
            knowledge_states=knowledge,
            provenance_bases=provenance,
        )
    first = known[0].value
    if any(fact.value != first for fact in known[1:]):
        return AdapterValue(
            "CONFLICT",
            fact_ids=tuple(sorted(f.fact_id for f in known)),
            reason="conflicting_current_facts",
            knowledge_states=knowledge,
            provenance_bases=provenance,
        )
    return AdapterValue(
        "KNOWN",
        first,
        tuple(sorted(f.fact_id for f in known)),
        knowledge_states=knowledge,
        provenance_bases=provenance,
    )


def readiness_inputs(state: CompanyState) -> dict[str, Any]:
    """Neutral fact envelope. Readiness remains owner of assessment semantics."""
    return {
        "contract_version": state.contract_version,
        "account_id": state.account_id,
        "company_state_version": state.state_version,
        "company_state_fingerprint": state.fingerprint,
        "unknowns": list(state.unknowns()),
        "conflicts": list(state.conflicts()),
        "facts": [fact.to_dict(as_of=state.as_of) for fact in state.active_facts()],
    }


def mobilize_inputs(state: CompanyState, *, as_of: datetime | None = None) -> dict[str, Any]:
    """Seed only Company State-owned inputs for future ``mobilize.v1`` mapping.

    Workers and own vehicles are returned as explicit KNOWN/UNKNOWN/CONFLICT
    values. Ownership never implies availability: only dedicated availability
    facts populate the availability outputs. Epistemic/provenance metadata is
    retained so ESTIMATE/ASSUMPTION/INFERENCE cannot masquerade as verified fact.
    """
    return {
        "account_id": state.account_id,
        "company_state_fingerprint": state.fingerprint,
        "workers": _extract(state, "crew.available_count", FactCategory.AVAILABILITY, as_of=as_of).to_dict(),
        "own_vehicles_available": _extract(state, "vehicle.available_count", FactCategory.AVAILABILITY, as_of=as_of).to_dict(),
        "base_location": _extract(state, "geography.base", FactCategory.GEOGRAPHY, as_of=as_of).to_dict(),
    }


def economics_constraints(state: CompanyState, *, as_of: datetime | None = None) -> dict[str, Any]:
    """Expose constraints only; Bid Economics remains owner of opportunity math."""
    return {
        "account_id": state.account_id,
        "company_state_fingerprint": state.fingerprint,
        "maximum_cash_exposure": _extract(state, "finance.maximum_cash_exposure", FactCategory.FINANCIAL_CONSTRAINT, as_of=as_of).to_dict(),
        "working_capital_limit": _extract(state, "finance.working_capital_limit", FactCategory.FINANCIAL_CONSTRAINT, as_of=as_of).to_dict(),
        "guarantee_limit": _extract(state, "finance.guarantee_limit", FactCategory.FINANCIAL_CONSTRAINT, as_of=as_of).to_dict(),
    }


def requirements_facts(state: CompanyState) -> dict[str, Any]:
    """Provide operational facts, never preferences or eligibility conclusions.

    Company Profile market countries/regions are projected as
    ``geography.preferred_*`` facts. They deliberately stay out of this seam so a
    preference cannot accidentally satisfy an opportunity geography requirement.
    """
    categories = {FactCategory.CAPABILITY, FactCategory.QUALIFICATION, FactCategory.GEOGRAPHY, FactCategory.CAPACITY, FactCategory.EQUIPMENT}
    facts = [
        fact
        for fact in state.active_facts()
        if fact.category in categories
        and not (fact.category is FactCategory.GEOGRAPHY and fact.code.startswith("geography.preferred_"))
    ]
    return {
        "account_id": state.account_id,
        "company_state_fingerprint": state.fingerprint,
        "facts": [fact.to_dict(as_of=state.as_of) for fact in facts],
        "conflicts": list(state.conflicts()),
    }


def bangs_inputs(state: CompanyState) -> dict[str, Any]:
    """Field-intelligence seed; no price/cost observation is manufactured here."""
    categories = {FactCategory.CAPACITY, FactCategory.AVAILABILITY, FactCategory.EQUIPMENT, FactCategory.GEOGRAPHY, FactCategory.OPERATIONAL_CONSTRAINT}
    return {
        "account_id": state.account_id,
        "company_state_fingerprint": state.fingerprint,
        "facts": [fact.to_dict(as_of=state.as_of) for fact in state.active_facts() if fact.category in categories],
    }
