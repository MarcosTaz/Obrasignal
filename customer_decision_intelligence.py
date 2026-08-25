"""Truth-preserving composition for customer decision and outcome intelligence.

This module is a read-model seam. It owns no Evidence, Company State,
Readiness, Economics, Pursuit Decision, Change History, Workflow, or Outcome
persistence and never synthesizes a PURSUE/DECLINE recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "customer-decision-intelligence.v1"
TRUTH_STATES = frozenset({"KNOWN", "UNKNOWN", "STALE", "UNAVAILABLE", "CONFLICTED"})
PURSUIT_DECISIONS = frozenset({"PURSUE", "NO_BID", "HOLD", "NEEDS_INFO", "UNDECIDED"})
OUTCOME_TYPES = frozenset({"BID_SUBMITTED", "WON", "LOST", "WITHDRAWN", "NO_SUBMISSION", "CANCELLED", "UNKNOWN"})
DECISION_CRITICAL_INPUTS = frozenset({"source_truth", "evidence", "company_state", "readiness", "economics"})
DEGRADED_STATES = frozenset({"UNKNOWN", "STALE", "UNAVAILABLE", "CONFLICTED"})


class TenantBoundaryError(ValueError):
    pass


@dataclass(frozen=True)
class DecisionInput:
    name: str
    truth_state: str
    account_id: str | None = None
    version: str | None = None
    ref: str | None = None
    fingerprint: str | None = None
    summary: str | None = None
    unknowns: tuple[str, ...] = ()
    change_triggers: tuple[str, ...] = ()
    attributes: tuple[tuple[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "truth_state": self.truth_state,
            "account_id": self.account_id,
            "version": self.version,
            "ref": self.ref,
            "fingerprint": self.fingerprint,
            "summary": self.summary,
            "unknowns": list(self.unknowns),
            "change_triggers": list(self.change_triggers),
            "attributes": dict(self.attributes),
        }


def _clean_text(value: Any, *, limit: int = 1000) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        raise ValueError("decision intelligence text contains control characters")
    if len(text) > limit:
        raise ValueError("decision intelligence text exceeds limit")
    return text


def _clean_many(values: Iterable[Any] | None, *, limit: int = 100) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        values = (values,)
    result: list[str] = []
    for value in values:
        text = _clean_text(value, limit=500)
        if text and text not in result:
            result.append(text)
        if len(result) > limit:
            raise ValueError("too many decision intelligence values")
    return tuple(result)


def _safe_attrs(attributes: Mapping[str, Any] | None) -> tuple[tuple[str, Any], ...]:
    if not attributes:
        return ()
    result: list[tuple[str, Any]] = []
    for key, value in sorted(attributes.items(), key=lambda item: str(item[0])):
        name = _clean_text(key, limit=80)
        if not name:
            continue
        if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
            safe_value = value
        elif isinstance(value, str):
            safe_value = _clean_text(value, limit=500)
        else:
            raise ValueError("decision intelligence attributes must be scalar")
        result.append((name, safe_value))
        if len(result) > 32:
            raise ValueError("too many decision intelligence attributes")
    return tuple(result)


def decision_input(
    name: str,
    truth_state: str,
    *,
    account_id: str | None = None,
    version: str | None = None,
    ref: str | None = None,
    fingerprint: str | None = None,
    summary: str | None = None,
    unknowns: Iterable[Any] | None = None,
    change_triggers: Iterable[Any] | None = None,
    attributes: Mapping[str, Any] | None = None,
) -> DecisionInput:
    input_name = _clean_text(name, limit=80)
    if not input_name:
        raise ValueError("decision input name is required")
    state = str(truth_state or "").strip().upper()
    if state not in TRUTH_STATES:
        raise ValueError(f"invalid truth state: {state}")
    return DecisionInput(
        input_name,
        state,
        _clean_text(account_id, limit=128),
        _clean_text(version, limit=160),
        _clean_text(ref, limit=512),
        _clean_text(fingerprint, limit=256),
        _clean_text(summary, limit=1000),
        _clean_many(unknowns),
        _clean_many(change_triggers),
        _safe_attrs(attributes),
    )


def _stable_fingerprint(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _owner(snapshot: Mapping[str, Any], account_id: str, label: str) -> None:
    owner = _clean_text(snapshot.get("account_id"), limit=128)
    if owner and owner != account_id:
        raise TenantBoundaryError(f"{label} belongs to a different account")


def evidence_input(snapshot: Mapping[str, Any] | None, *, account_id: str | None = None) -> DecisionInput:
    if snapshot is None:
        return decision_input("evidence", "UNAVAILABLE", account_id=account_id, summary="Evidence contract is unavailable.")
    state = str(snapshot.get("state") or "").strip().upper()
    conflicts = list(snapshot.get("conflicts") or ())
    unknowns = list(snapshot.get("missing_inputs") or ())
    truth = "CONFLICTED" if conflicts else "KNOWN" if state == "READY" else "STALE" if state == "STALE" else "UNAVAILABLE" if state == "UNAVAILABLE" else "UNKNOWN"
    identity = {
        "contract_version": snapshot.get("contract_version"),
        "state": state,
        "decision_claim_id": snapshot.get("decision_claim_id"),
        "missing_inputs": sorted(str(item) for item in unknowns),
        "conflict_count": len(conflicts),
    }
    return decision_input(
        "evidence", truth, account_id=account_id,
        version=snapshot.get("contract_version"), ref=snapshot.get("decision_claim_id"),
        fingerprint=_stable_fingerprint(identity), summary=snapshot.get("reason"), unknowns=unknowns,
        change_triggers=("evidence lineage or provenance changed",),
    )


def company_state_input(snapshot: Mapping[str, Any] | None, *, account_id: str) -> DecisionInput:
    if snapshot is None:
        return decision_input("company_state", "UNAVAILABLE", account_id=account_id, summary="Company State contract is unavailable.")
    _owner(snapshot, account_id, "company state")
    conflicts = list(snapshot.get("conflicts") or ())
    unknowns = list(snapshot.get("unknowns") or ())
    facts = snapshot.get("facts")
    truth = "CONFLICTED" if conflicts else "UNKNOWN" if isinstance(facts, (list, tuple)) and not facts and unknowns else "KNOWN"
    return decision_input(
        "company_state", truth, account_id=account_id,
        version=snapshot.get("company_state_version") or snapshot.get("contract_version"),
        ref=snapshot.get("company_state_fingerprint"), fingerprint=snapshot.get("company_state_fingerprint"),
        unknowns=unknowns,
        change_triggers=("company facts, availability, certification, geography, or financial constraints changed",),
        attributes={"conflict_count": len(conflicts), "unknown_count": len(unknowns)},
    )


def readiness_input(assessment: Mapping[str, Any] | None, *, account_id: str) -> DecisionInput:
    if assessment is None:
        return decision_input("readiness", "UNAVAILABLE", account_id=account_id, summary="Readiness contract is unavailable.")
    _owner(assessment, account_id, "readiness")
    overall = str(assessment.get("overall_status") or assessment.get("status") or "UNKNOWN").strip().upper()
    legacy_items = list(assessment.get("items") or ())
    conflicts = list(assessment.get("conflict_items") or ()) or [item for item in legacy_items if isinstance(item, Mapping) and str(item.get("status") or "").upper() == "CONFLICT"]
    unknown_items = list(assessment.get("unknown_items") or ()) or [item for item in legacy_items if isinstance(item, Mapping) and str(item.get("status") or "").upper() == "UNKNOWN"]
    truth = "CONFLICTED" if conflicts else "UNKNOWN" if overall == "UNKNOWN" else "KNOWN" if overall in {"READY", "CONDITIONALLY_READY", "NOT_READY"} else "UNKNOWN"
    unknowns = [item.get("code") or item.get("description") for item in unknown_items if isinstance(item, Mapping) and (item.get("code") or item.get("description"))]
    return decision_input(
        "readiness", truth, account_id=account_id,
        version=assessment.get("assessment_version") or assessment.get("policy_version"),
        ref=assessment.get("assessment_id"), fingerprint=assessment.get("fingerprint"), unknowns=unknowns,
        change_triggers=("readiness blocker, warning, unknown, or verified input changed",),
        attributes={"overall_status": overall},
    )


def economics_input(assessment: Mapping[str, Any] | None, *, account_id: str) -> DecisionInput:
    if assessment is None:
        return decision_input("economics", "UNAVAILABLE", account_id=account_id, summary="Economic decision support is unavailable.")
    status = str(assessment.get("status") or "UNKNOWN").strip().upper()
    truth = "UNKNOWN" if status in {"", "UNKNOWN"} else "UNAVAILABLE" if status in {"UNAVAILABLE", "FAILED"} else "CONFLICTED" if status == "CONFLICT" else "STALE" if status == "STALE" else "KNOWN"
    return decision_input(
        "economics", truth, account_id=account_id,
        version=assessment.get("rule_version") or assessment.get("contract_version"),
        ref=assessment.get("assessment_id"), fingerprint=assessment.get("fingerprint"),
        summary=assessment.get("reason"), unknowns=assessment.get("unknowns") or (),
        change_triggers=("contract value, cost, cash exposure, margin, guarantees, fees, or economic rules changed",),
        attributes={"status": status},
    )


def pursuit_decision_input(decision: Mapping[str, Any] | None, *, account_id: str) -> DecisionInput:
    if decision is None:
        return decision_input("pursuit_decision", "UNKNOWN", account_id=account_id, summary="No explicit pursuit decision is recorded.")
    _owner(decision, account_id, "pursuit decision")
    value = str(decision.get("decision") or decision.get("decision_type") or "UNDECIDED").strip().upper()
    if value not in PURSUIT_DECISIONS:
        return decision_input("pursuit_decision", "UNKNOWN", account_id=account_id, unknowns=("pursuit_decision_type",))
    return decision_input(
        "pursuit_decision", "KNOWN", account_id=account_id, version=decision.get("contract_version"),
        ref=decision.get("decision_id") or decision.get("id"), fingerprint=decision.get("fingerprint"),
        summary=decision.get("note"), unknowns=decision.get("unknowns") or (),
        change_triggers=("explicit customer pursuit decision changed",),
        attributes={"decision": value, "actor_type": decision.get("actor_type")},
    )


def outcome_input(outcome: Mapping[str, Any] | None, *, account_id: str) -> DecisionInput:
    if outcome is None:
        return decision_input("outcome", "UNKNOWN", account_id=account_id, summary="No outcome is recorded.")
    _owner(outcome, account_id, "outcome")
    value = str(outcome.get("outcome_type") or outcome.get("outcome") or "UNKNOWN").strip().upper()
    truth = "KNOWN" if value in OUTCOME_TYPES and value != "UNKNOWN" else "UNKNOWN"
    return decision_input(
        "outcome", truth, account_id=account_id, version=outcome.get("contract_version"),
        ref=outcome.get("outcome_id") or outcome.get("id"), fingerprint=outcome.get("fingerprint"),
        summary=outcome.get("reason"), unknowns=() if truth == "KNOWN" else ("outcome",),
        change_triggers=("observed outcome or correction changed",), attributes={"outcome": value},
    )


def source_truth_input(opportunity: Mapping[str, Any], *, account_id: str | None = None) -> DecisionInput:
    source = _clean_text(opportunity.get("source"), limit=128)
    external_id = _clean_text(opportunity.get("external_id") or opportunity.get("id"), limit=256)
    missing = [name for name, value in (("source", source), ("external_id", external_id)) if not value]
    lifecycle = str(opportunity.get("lifecycle_status") or "").strip().upper() or None
    return decision_input(
        "source_truth", "KNOWN" if not missing else "UNKNOWN", account_id=account_id,
        version=opportunity.get("source_version") or opportunity.get("lifecycle_source_updated_at"),
        ref=f"{source}:{external_id}" if source and external_id else source or external_id,
        fingerprint=_stable_fingerprint({
            "source": source, "external_id": external_id, "lifecycle": lifecycle,
            "deadline": opportunity.get("deadline"), "is_actionable": opportunity.get("is_actionable"),
        }),
        summary=_clean_text(opportunity.get("lifecycle_reason"), limit=1000), unknowns=missing,
        change_triggers=("source identity, lifecycle, deadline, or actionability changed",),
        attributes={"lifecycle_status": lifecycle},
    )


def _attribute(item: DecisionInput | None, name: str) -> Any:
    return dict(item.attributes).get(name) if item else None


def _normalize_inputs(inputs: Iterable[DecisionInput], account_id: str) -> dict[str, DecisionInput]:
    result: dict[str, DecisionInput] = {}
    for item in inputs:
        if not isinstance(item, DecisionInput):
            raise TypeError("inputs must contain DecisionInput values")
        if item.account_id and item.account_id != account_id:
            raise TenantBoundaryError(f"{item.name} belongs to a different account")
        if item.name in result:
            raise ValueError(f"duplicate decision input: {item.name}")
        result[item.name] = item
    return result


def _effective_state(item: DecisionInput | None) -> str:
    if item is None:
        return "UNAVAILABLE"
    if item.truth_state != "KNOWN":
        return item.truth_state
    if item.unknowns:
        return "UNKNOWN"
    return "KNOWN"


def _critical_degraded(inputs: Mapping[str, DecisionInput]) -> dict[str, str]:
    return {
        name: _effective_state(inputs.get(name))
        for name in sorted(DECISION_CRITICAL_INPUTS)
        if _effective_state(inputs.get(name)) != "KNOWN"
    }


def _action_support(inputs: Mapping[str, DecisionInput]) -> dict[str, dict[str, Any]]:
    pursuit = inputs.get("pursuit_decision")
    explicit = _attribute(pursuit, "decision") if pursuit and pursuit.truth_state == "KNOWN" else None
    degraded_map = _critical_degraded(inputs)
    degraded = sorted(degraded_map)
    pursue_state = "RECORDED_EXPLICIT_DECISION" if explicit == "PURSUE" else "EXPLICIT_CUSTOMER_DECISION_REQUIRED"
    decline_state = "RECORDED_EXPLICIT_DECISION" if explicit == "NO_BID" else "EXPLICIT_CUSTOMER_DECISION_REQUIRED"
    return {
        "VIEW": {"state": "SUPPORTED", "reason": "Opportunity identity can be inspected without a pursuit recommendation."},
        "WATCH": {"state": "SUPPORTED", "reason": "Customer-controlled watch state does not imply commercial suitability."},
        "INVESTIGATE": {"state": "SUPPORTED", "reason": "Investigation is valid when decision inputs are incomplete, stale, unavailable, or conflicted."},
        "PURSUE": {"state": pursue_state, "decision_context": "DEGRADED" if degraded else "REVIEWABLE", "degraded_inputs": degraded},
        "DECLINE": {"state": decline_state, "decision_context": "DEGRADED" if degraded else "REVIEWABLE", "degraded_inputs": degraded},
    }


def build_decision_audit(
    account_id: str,
    opportunity: Mapping[str, Any],
    inputs: Iterable[DecisionInput],
    *,
    previous_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    account = _clean_text(account_id, limit=128)
    if not account:
        raise TenantBoundaryError("account_id is required")
    source = _clean_text(opportunity.get("source"), limit=128)
    external_id = _clean_text(opportunity.get("external_id") or opportunity.get("id"), limit=256)
    if not source or not external_id:
        raise ValueError("decision audit requires source and external_id")

    normalized = _normalize_inputs(inputs, account)
    if "source_truth" not in normalized:
        normalized["source_truth"] = source_truth_input(opportunity, account_id=account)

    effective_degraded = _critical_degraded(normalized)
    noncritical_degraded = {
        name: _effective_state(item)
        for name, item in normalized.items()
        if name not in DECISION_CRITICAL_INPUTS and _effective_state(item) != "KNOWN"
    }
    degraded = dict(sorted({**effective_degraded, **noncritical_degraded}.items()))
    unknowns = sorted({unknown for item in normalized.values() for unknown in item.unknowns})
    current_decision = _attribute(normalized.get("pursuit_decision"), "decision")
    current_outcome = _attribute(normalized.get("outcome"), "outcome")
    safe_inputs = [normalized[name].to_dict() for name in sorted(normalized)]

    base = {
        "contract_version": CONTRACT_VERSION,
        "account_id": account,
        "opportunity": {"source": source, "external_id": external_id},
        "inputs": safe_inputs,
        "degraded_inputs": degraded,
        "unknowns": unknowns,
        "explicit_pursuit_decision": current_decision,
        "current_outcome": current_outcome,
        "action_support": _action_support(normalized),
    }
    base["audit_fingerprint"] = _stable_fingerprint({
        "contract_version": CONTRACT_VERSION,
        "opportunity": base["opportunity"],
        "inputs": [{
            "name": item["name"], "truth_state": item["truth_state"], "version": item["version"],
            "ref": item["ref"], "fingerprint": item["fingerprint"], "summary": item["summary"],
            "unknowns": item["unknowns"], "attributes": item["attributes"],
        } for item in safe_inputs],
    })
    base["change_impact"] = compare_decision_audits(previous_audit, base) if previous_audit else {
        "status": "BASELINE", "material_changes": [], "review_required": False, "historical_decision_preserved": True,
    }
    return base


def compare_decision_audits(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> dict[str, Any]:
    if not previous:
        return {"status": "BASELINE", "material_changes": [], "review_required": False, "historical_decision_preserved": True}
    if previous.get("account_id") != current.get("account_id"):
        raise TenantBoundaryError("cannot compare decision audits across accounts")
    if previous.get("opportunity") != current.get("opportunity"):
        raise ValueError("cannot compare audits for different opportunities")

    def by_name(audit: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
        return {item.get("name"): item for item in audit.get("inputs", []) if isinstance(item, Mapping) and item.get("name")}

    before, after = by_name(previous), by_name(current)
    material: list[dict[str, Any]] = []
    for name in sorted(set(before) | set(after)):
        old, new = before.get(name), after.get(name)
        if old is None:
            material.append({"input": name, "change": "ADDED", "from": None, "to": new.get("truth_state")})
            continue
        if new is None:
            material.append({"input": name, "change": "REMOVED", "from": old.get("truth_state"), "to": None})
            continue
        changed = [field for field in ("truth_state", "version", "ref", "fingerprint", "summary", "unknowns", "attributes") if old.get(field) != new.get(field)]
        if changed:
            material.append({"input": name, "change": "CHANGED", "changed_fields": changed, "from": old.get("truth_state"), "to": new.get("truth_state")})

    critical_material = any(item["input"] in DECISION_CRITICAL_INPUTS for item in material)
    current_by_name = by_name(current)
    current_degraded = any(
        item.get("truth_state") in DEGRADED_STATES or bool(item.get("unknowns"))
        for name, item in current_by_name.items()
        if name in DECISION_CRITICAL_INPUTS
    ) or any(name not in current_by_name for name in DECISION_CRITICAL_INPUTS)
    explicit = current.get("explicit_pursuit_decision")
    review_required = bool(explicit in {"PURSUE", "NO_BID", "HOLD", "NEEDS_INFO"} and (critical_material or current_degraded))
    return {
        "status": "REVIEW_REQUIRED" if review_required else "CHANGED" if material else "CURRENT",
        "material_changes": material,
        "review_required": review_required,
        "historical_decision_preserved": True,
    }


def learning_observation(audit: Mapping[str, Any]) -> dict[str, Any]:
    decision = audit.get("explicit_pursuit_decision")
    outcome = audit.get("current_outcome")
    if not decision or decision == "UNDECIDED":
        state, reason = "INSUFFICIENT", "explicit pursuit decision missing"
    elif not outcome or outcome == "UNKNOWN":
        state, reason = "INSUFFICIENT", "outcome missing or unknown"
    else:
        state, reason = "OBSERVED_PAIR", "explicit decision and observed outcome are both available"
    return {
        "state": state,
        "decision": decision,
        "outcome": outcome,
        "causal_attribution": "NOT_ESTABLISHED",
        "model_update_allowed": False,
        "reason": reason,
    }
