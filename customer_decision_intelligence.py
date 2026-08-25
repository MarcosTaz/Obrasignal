"""Truth-preserving composition for customer decision and outcome intelligence.

This module is deliberately a read-model seam. It owns no Evidence, Company
State, Readiness, Economics, Pursuit Decision, Change History, Workflow, or
Outcome persistence and it never turns those contracts into an autonomous
PURSUE/DECLINE recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "customer-decision-intelligence.v1"
TRUTH_STATES = frozenset({"KNOWN", "UNKNOWN", "STALE", "UNAVAILABLE", "CONFLICTED"})
PURSUIT_DECISIONS = frozenset({"PURSUE", "NO_BID", "HOLD", "NEEDS_INFO", "UNDECIDED"})
OUTCOME_TYPES = frozenset({
    "BID_SUBMITTED", "WON", "LOST", "WITHDRAWN", "NO_SUBMISSION",
    "CANCELLED", "UNKNOWN",
})
DECISION_CRITICAL_INPUTS = frozenset({
    "source_truth", "evidence", "company_state", "readiness", "economics",
})


class TenantBoundaryError(ValueError):
    """Raised when private decision inputs cross account boundaries."""


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
    safe: list[tuple[str, Any]] = []
    for key, value in sorted(attributes.items(), key=lambda item: str(item[0])):
        name = _clean_text(key, limit=80)
        if not name:
            continue
        if isinstance(value, bool) or value is None:
            safe.append((name, value))
        elif isinstance(value, (int, float)):
            safe.append((name, value))
        elif isinstance(value, str):
            safe.append((name, _clean_text(value, limit=500)))
        else:
            raise ValueError("decision intelligence attributes must be scalar")
        if len(safe) > 32:
            raise ValueError("too many decision intelligence attributes")
    return tuple(safe)


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
    account = _clean_text(account_id, limit=128)
    return DecisionInput(
        name=input_name,
        truth_state=state,
        account_id=account,
        version=_clean_text(version, limit=160),
        ref=_clean_text(ref, limit=512),
        fingerprint=_clean_text(fingerprint, limit=256),
        summary=_clean_text(summary, limit=1000),
        unknowns=_clean_many(unknowns),
        change_triggers=_clean_many(change_triggers),
        attributes=_safe_attrs(attributes),
    )


def _stable_fingerprint(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def evidence_input(snapshot: Mapping[str, Any] | None, *, account_id: str | None = None) -> DecisionInput:
    """Adapt the public Q080 decision-evidence envelope without reading graph internals."""
    if snapshot is None:
        return decision_input("evidence", "UNAVAILABLE", account_id=account_id, summary="Evidence contract is unavailable.")
    state = str(snapshot.get("state") or "").strip().upper()
    conflicts = snapshot.get("conflicts") or ()
    if conflicts:
        truth = "CONFLICTED"
    elif state == "READY":
        truth = "KNOWN"
    elif state == "STALE":
        truth = "STALE"
    elif state == "UNAVAILABLE":
        truth = "UNAVAILABLE"
    else:
        truth = "UNKNOWN"
    unknowns = list(snapshot.get("missing_inputs") or ())
    safe_identity = {
        "contract_version": snapshot.get("contract_version"),
        "state": state,
        "decision_claim_id": snapshot.get("decision_claim_id"),
        "missing_inputs": sorted(str(item) for item in unknowns),
        "conflict_count": len(conflicts),
    }
    return decision_input(
        "evidence",
        truth,
        account_id=account_id,
        version=snapshot.get("contract_version"),
        ref=snapshot.get("decision_claim_id"),
        fingerprint=_stable_fingerprint(safe_identity),
        summary=snapshot.get("reason"),
        unknowns=unknowns,
        change_triggers=("evidence lineage or provenance changed",),
    )


def company_state_input(snapshot: Mapping[str, Any] | None, *, account_id: str) -> DecisionInput:
    """Adapt Q090 readiness_inputs() metadata; private facts are not copied into the audit."""
    if snapshot is None:
        return decision_input("company_state", "UNAVAILABLE", account_id=account_id, summary="Company State contract is unavailable.")
    owner = _clean_text(snapshot.get("account_id"), limit=128)
    if owner and owner != account_id:
        raise TenantBoundaryError("company state belongs to a different account")
    conflicts = list(snapshot.get("conflicts") or ())
    unknowns = list(snapshot.get("unknowns") or ())
    truth = "CONFLICTED" if conflicts else "KNOWN"
    return decision_input(
        "company_state",
        truth,
        account_id=account_id,
        version=snapshot.get("company_state_version") or snapshot.get("contract_version"),
        ref=snapshot.get("company_state_fingerprint"),
        fingerprint=snapshot.get("company_state_fingerprint"),
        unknowns=unknowns,
        change_triggers=("company facts, availability, certification, geography, or financial constraints changed",),
        attributes={"conflict_count": len(conflicts), "unknown_count": len(unknowns)},
    )


def readiness_input(assessment: Mapping[str, Any] | None, *, account_id: str) -> DecisionInput:
    """Adapt Opportunity Readiness without converting readiness into a pursuit choice."""
    if assessment is None:
        return decision_input("readiness", "UNAVAILABLE", account_id=account_id, summary="Readiness contract is unavailable.")
    owner = _clean_text(assessment.get("account_id"), limit=128)
    if owner and owner != account_id:
        raise TenantBoundaryError("readiness belongs to a different account")
    overall = str(
        assessment.get("overall_status")
        or assessment.get("status")
        or "UNKNOWN"
    ).strip().upper()
    items = assessment.get("items") or ()
    conflicts = [
        item for item in items
        if isinstance(item, Mapping) and str(item.get("status") or "").upper() == "CONFLICT"
    ]
    unknown_items = [
        item for item in items
        if isinstance(item, Mapping) and str(item.get("status") or "").upper() == "UNKNOWN"
    ]
    if conflicts:
        truth = "CONFLICTED"
    elif overall == "UNKNOWN":
        truth = "UNKNOWN"
    elif overall in {"READY", "CONDITIONALLY_READY", "NOT_READY"}:
        truth = "KNOWN"
    else:
        truth = "UNKNOWN"
    unknowns = [
        item.get("code") or item.get("description")
        for item in unknown_items
        if item.get("code") or item.get("description")
    ]
    return decision_input(
        "readiness",
        truth,
        account_id=account_id,
        version=assessment.get("assessment_version") or assessment.get("policy_version"),
        ref=assessment.get("assessment_id"),
        fingerprint=assessment.get("fingerprint"),
        unknowns=unknowns,
        change_triggers=("readiness blocker, warning, unknown, or verified input changed",),
        attributes={"overall_status": overall},
    )


def economics_input(assessment: Mapping[str, Any] | None, *, account_id: str) -> DecisionInput:
    """Adapt canonical economic assessment while preserving UNKNOWN as non-zero truth."""
    if assessment is None:
        return decision_input("economics", "UNAVAILABLE", account_id=account_id, summary="Economic decision support is unavailable.")
    status = str(assessment.get("status") or "UNKNOWN").strip().upper()
    if status in {"UNKNOWN", ""}:
        truth = "UNKNOWN"
    elif status in {"UNAVAILABLE", "FAILED"}:
        truth = "UNAVAILABLE"
    elif status == "CONFLICT":
        truth = "CONFLICTED"
    elif status == "STALE":
        truth = "STALE"
    else:
        truth = "KNOWN"
    return decision_input(
        "economics",
        truth,
        account_id=account_id,
        version=assessment.get("rule_version") or assessment.get("contract_version"),
        ref=assessment.get("assessment_id"),
        fingerprint=assessment.get("fingerprint"),
        summary=assessment.get("reason"),
        unknowns=assessment.get("unknowns") or (),
        change_triggers=("contract value, cost, cash exposure, margin, guarantees, fees, or economic rules changed",),
        attributes={"status": status},
    )


def pursuit_decision_input(decision: Mapping[str, Any] | None, *, account_id: str) -> DecisionInput:
    """Adapt Decision Journal current decision. Absence is UNKNOWN, not NO_BID."""
    if decision is None:
        return decision_input("pursuit_decision", "UNKNOWN", account_id=account_id, summary="No explicit pursuit decision is recorded.")
    owner = _clean_text(decision.get("account_id"), limit=128)
    if owner and owner != account_id:
        raise TenantBoundaryError("pursuit decision belongs to a different account")
    value = str(decision.get("decision") or decision.get("decision_type") or "UNDECIDED").strip().upper()
    if value not in PURSUIT_DECISIONS:
        return decision_input("pursuit_decision", "UNKNOWN", account_id=account_id, unknowns=("pursuit_decision_type",))
    return decision_input(
        "pursuit_decision",
        "KNOWN",
        account_id=account_id,
        version=decision.get("contract_version"),
        ref=decision.get("decision_id") or decision.get("id"),
        fingerprint=decision.get("fingerprint"),
        summary=decision.get("note"),
        unknowns=decision.get("unknowns") or (),
        change_triggers=("explicit customer pursuit decision changed",),
        attributes={"decision": value, "actor_type": decision.get("actor_type")},
    )


def outcome_input(outcome: Mapping[str, Any] | None, *, account_id: str) -> DecisionInput:
    """Adapt Outcome Capture current outcome. Missing outcome is UNKNOWN, never LOST."""
    if outcome is None:
        return decision_input("outcome", "UNKNOWN", account_id=account_id, summary="No outcome is recorded.")
    owner = _clean_text(outcome.get("account_id"), limit=128)
    if owner and owner != account_id:
        raise TenantBoundaryError("outcome belongs to a different account")
    value = str(outcome.get("outcome_type") or outcome.get("outcome") or "UNKNOWN").strip().upper()
    truth = "KNOWN" if value in OUTCOME_TYPES and value != "UNKNOWN" else "UNKNOWN"
    return decision_input(
        "outcome",
        truth,
        account_id=account_id,
        version=outcome.get("contract_version"),
        ref=outcome.get("outcome_id") or outcome.get("id"),
        fingerprint=outcome.get("fingerprint"),
        summary=outcome.get("reason"),
        unknowns=() if truth == "KNOWN" else ("outcome",),
        change_triggers=("observed outcome or correction changed",),
        attributes={"outcome": value},
    )


def source_truth_input(opportunity: Mapping[str, Any], *, account_id: str | None = None) -> DecisionInput:
    """Build only a source identity/lifecycle envelope from the Opportunity read model."""
    source = _clean_text(opportunity.get("source"), limit=128)
    external_id = _clean_text(opportunity.get("external_id") or opportunity.get("id"), limit=256)
    missing = []
    if not source:
        missing.append("source")
    if not external_id:
        missing.append("external_id")
    lifecycle = str(opportunity.get("lifecycle_status") or "").strip().upper() or None
    truth = "KNOWN" if source and external_id else "UNKNOWN"
    summary = _clean_text(opportunity.get("lifecycle_reason"), limit=1000)
    return decision_input(
        "source_truth",
        truth,
        account_id=account_id,
        version=opportunity.get("source_version") or opportunity.get("lifecycle_source_updated_at"),
        ref=f"{source}:{external_id}" if source and external_id else source or external_id,
        fingerprint=_stable_fingerprint({
            "source": source,
            "external_id": external_id,
            "lifecycle": lifecycle,
            "deadline": opportunity.get("deadline"),
            "is_actionable": opportunity.get("is_actionable"),
        }),
        summary=summary,
        unknowns=missing,
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


def _action_support(inputs: Mapping[str, DecisionInput]) -> dict[str, dict[str, Any]]:
    pursuit = inputs.get("pursuit_decision")
    explicit = _attribute(pursuit, "decision") if pursuit and pursuit.truth_state == "KNOWN" else None
    degraded = sorted(
        name for name in DECISION_CRITICAL_INPUTS
        if name not in inputs or inputs[name].truth_state != "KNOWN"
    )
    can_assess = not degraded

    pursue_state = "RECORDED_EXPLICIT_DECISION" if explicit == "PURSUE" else "EXPLICIT_CUSTOMER_DECISION_REQUIRED"
    decline_state = "RECORDED_EXPLICIT_DECISION" if explicit == "NO_BID" else "EXPLICIT_CUSTOMER_DECISION_REQUIRED"

    return {
        "VIEW": {"state": "SUPPORTED", "reason": "Opportunity identity can be inspected without a pursuit recommendation."},
        "WATCH": {"state": "SUPPORTED", "reason": "Customer-controlled watch state does not imply commercial suitability."},
        "INVESTIGATE": {
            "state": "SUPPORTED",
            "reason": "Investigation is valid when decision inputs are incomplete, stale, unavailable, or conflicted.",
        },
        "PURSUE": {
            "state": pursue_state,
            "decision_context": "REVIEWABLE" if can_assess else "DEGRADED",
            "degraded_inputs": degraded,
        },
        "DECLINE": {
            "state": decline_state,
            "decision_context": "REVIEWABLE" if can_assess else "DEGRADED",
            "degraded_inputs": degraded,
        },
    }


def build_decision_audit(
    account_id: str,
    opportunity: Mapping[str, Any],
    inputs: Iterable[DecisionInput],
    *,
    previous_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose a privacy-safe decision audit without changing any owner state."""
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

    degraded = {
        name: item.truth_state
        for name, item in sorted(normalized.items())
        if item.truth_state != "KNOWN"
    }
    unknowns = sorted({
        unknown
        for item in normalized.values()
        for unknown in item.unknowns
    })
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
        "inputs": [
            {
                "name": item["name"],
                "truth_state": item["truth_state"],
                "version": item["version"],
                "ref": item["ref"],
                "fingerprint": item["fingerprint"],
                "summary": item["summary"],
                "unknowns": item["unknowns"],
                "attributes": item["attributes"],
            }
            for item in safe_inputs
        ],
    })
    base["change_impact"] = compare_decision_audits(previous_audit, base) if previous_audit else {
        "status": "BASELINE",
        "material_changes": [],
        "review_required": False,
        "historical_decision_preserved": True,
    }
    return base


def compare_decision_audits(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Identify changed dependencies; never rewrite the historical decision."""
    if not previous:
        return {
            "status": "BASELINE",
            "material_changes": [],
            "review_required": False,
            "historical_decision_preserved": True,
        }

    if previous.get("account_id") != current.get("account_id"):
        raise TenantBoundaryError("cannot compare decision audits across accounts")
    if previous.get("opportunity") != current.get("opportunity"):
        raise ValueError("cannot compare audits for different opportunities")

    def by_name(audit):
        return {
            item.get("name"): item
            for item in audit.get("inputs", [])
            if isinstance(item, Mapping) and item.get("name")
        }

    before = by_name(previous)
    after = by_name(current)
    material = []
    for name in sorted(set(before) | set(after)):
        old = before.get(name)
        new = after.get(name)
        if old is None:
            material.append({"input": name, "change": "ADDED", "from": None, "to": new.get("truth_state")})
            continue
        if new is None:
            material.append({"input": name, "change": "REMOVED", "from": old.get("truth_state"), "to": None})
            continue
        changed_fields = [
            field for field in ("truth_state", "version", "ref", "fingerprint", "summary", "unknowns", "attributes")
            if old.get(field) != new.get(field)
        ]
        if changed_fields:
            material.append({
                "input": name,
                "change": "CHANGED",
                "changed_fields": changed_fields,
                "from": old.get("truth_state"),
                "to": new.get("truth_state"),
            })

    critical_material = any(item["input"] in DECISION_CRITICAL_INPUTS for item in material)
    current_degraded = any(
        item.get("truth_state") in {"UNKNOWN", "STALE", "UNAVAILABLE", "CONFLICTED"}
        for item in current.get("inputs", [])
        if item.get("name") in DECISION_CRITICAL_INPUTS
    )
    explicit = current.get("explicit_pursuit_decision")
    review_required = bool(explicit in {"PURSUE", "NO_BID", "HOLD", "NEEDS_INFO"} and (critical_material or current_degraded))
    return {
        "status": "REVIEW_REQUIRED" if review_required else ("CHANGED" if material else "CURRENT"),
        "material_changes": material,
        "review_required": review_required,
        "historical_decision_preserved": True,
    }


def learning_observation(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Expose only proven decision/outcome pairing; never infer causality or model weight."""
    decision = audit.get("explicit_pursuit_decision")
    outcome = audit.get("current_outcome")
    if not decision or decision == "UNDECIDED":
        state = "INSUFFICIENT"
        reason = "explicit pursuit decision missing"
    elif not outcome or outcome == "UNKNOWN":
        state = "INSUFFICIENT"
        reason = "outcome missing or unknown"
    else:
        state = "OBSERVED_PAIR"
        reason = "explicit decision and observed outcome are both available"
    return {
        "state": state,
        "decision": decision,
        "outcome": outcome,
        "causal_attribution": "NOT_ESTABLISHED",
        "model_update_allowed": False,
        "reason": reason,
    }
