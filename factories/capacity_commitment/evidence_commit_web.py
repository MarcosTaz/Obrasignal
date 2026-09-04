from __future__ import annotations

from flask import g, jsonify, request

from .engine import CostRecoveryMode, ExposureType
from .evidence import EvidenceRepository
from .evidence_case import HumanCaseControls, build_state_from_confirmed_evidence
from .service import process_state
from .workflow import WorkflowEvent, WorkflowEventType, WorkflowRepository


_REQUIRED_CONTROL_FIELDS = {
    "evidence_supported",
    "asset_dedicated",
    "already_fully_amortized",
    "already_paid",
    "exposure_type",
    "cost_recovery_mode",
    "duplicate_claim",
}
_OPTIONAL_CONTROL_FIELDS = {
    "customer_matches",
    "program_matches",
    "period_matches",
    "currency_matches",
    "unit_matches",
    "actuals_complete",
    "actuals_deduplicated",
    "cancelled_orders_excluded",
    "amortization_verified",
    "asset_dedication_verified",
    "mitigation_reviewed",
    "prior_recovery_reviewed",
    "notice_window_verified",
    "contract_matches",
    "contract_current",
    "amendment_reviewed",
    "amendment_matches",
    "duplicate_claim_reviewed",
}
_ALLOWED_CONTROL_FIELDS = _REQUIRED_CONTROL_FIELDS | _OPTIONAL_CONTROL_FIELDS


def _required_text(payload, key, *, max_len=500):
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required and must be a string")
    value = value.strip()
    if len(value) > max_len or "\x00" in value:
        raise ValueError(f"{key} is invalid")
    return value


def _optional_text(payload, key, *, max_len=2000):
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    value = value.strip()
    if not value or len(value) > max_len or "\x00" in value:
        raise ValueError(f"{key} is invalid")
    return value


def _required_bool(payload, key):
    if key not in payload or type(payload[key]) is not bool:
        raise ValueError(f"{key} must be an explicit boolean")
    return payload[key]


def _tri_bool(payload, key):
    value = payload.get(key)
    if value is not None and type(value) is not bool:
        raise ValueError(f"{key} must be boolean or null")
    return value


def _controls(payload) -> HumanCaseControls:
    if not isinstance(payload, dict):
        raise ValueError("controls must be a JSON object")
    unknown = set(payload) - _ALLOWED_CONTROL_FIELDS
    if unknown:
        raise ValueError(f"unknown controls fields: {sorted(unknown)}")
    missing = _REQUIRED_CONTROL_FIELDS - set(payload)
    if missing:
        raise ValueError(f"missing controls fields: {sorted(missing)}")
    try:
        exposure_type = ExposureType(payload["exposure_type"])
    except (ValueError, TypeError) as exc:
        raise ValueError("exposure_type must be a valid ExposureType") from exc
    try:
        cost_recovery_mode = CostRecoveryMode(payload["cost_recovery_mode"])
    except (ValueError, TypeError) as exc:
        raise ValueError("cost_recovery_mode must be a valid CostRecoveryMode") from exc

    kwargs = {
        "evidence_supported": _required_bool(payload, "evidence_supported"),
        "asset_dedicated": _required_bool(payload, "asset_dedicated"),
        "already_fully_amortized": _required_bool(payload, "already_fully_amortized"),
        "already_paid": _required_bool(payload, "already_paid"),
        "exposure_type": exposure_type,
        "cost_recovery_mode": cost_recovery_mode,
        "duplicate_claim": _required_bool(payload, "duplicate_claim"),
    }
    for key in sorted(_OPTIONAL_CONTROL_FIELDS):
        kwargs[key] = _tri_bool(payload, key)
    return HumanCaseControls(**kwargs)


def _processed_payload(processed):
    result = processed.result
    return {
        "case_id": result.case_id,
        "currency": result.currency,
        "recoverability_state": result.recoverability_state.value,
        "committed_units": format(result.committed_units, "f"),
        "actual_units": format(result.actual_units, "f"),
        "shortfall_units": format(result.shortfall_units, "f"),
        "economic_exposure": format(result.economic_exposure, "f"),
        "mitigation": format(result.mitigation, "f"),
        "prior_payment": format(result.prior_payment, "f"),
        "net_exposure": format(result.net_exposure, "f"),
        "recoverable_amount": format(result.recoverable_amount, "f"),
        "claimable_amount": format(result.claimable_amount, "f"),
        "reasons": list(result.reasons),
        "verified_recovery": False,
        "payment_received": False,
    }


def register_evidence_commit_routes(app, capacity_repository):
    evidence_repository = EvidenceRepository(capacity_repository.db_path)
    workflow_repository = WorkflowRepository(capacity_repository.db_path)

    @app.route(
        "/api/capacity/engagements/<engagement_id>/cases/from-evidence",
        methods=["POST"],
    )
    def create_case_from_evidence(engagement_id):
        if request.headers.get("X-Capacity-Intent") != "commit-reviewed-evidence-case":
            return jsonify({"error": "reviewed_evidence_commit_intent_required"}), 403
        payload = request.get_json(silent=False)
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        allowed = {"case_id", "occurred_at", "reviewer_ref", "review_note", "controls"}
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"unknown request fields: {sorted(unknown)}")
        missing = {"case_id", "occurred_at", "reviewer_ref", "controls"} - set(payload)
        if missing:
            raise ValueError(f"missing request fields: {sorted(missing)}")

        engagement = workflow_repository.load_engagement(
            tenant_id=g.capacity_tenant_id,
            engagement_id=engagement_id,
        )
        facts = evidence_repository.list_facts(tenant_id=g.capacity_tenant_id)
        state = build_state_from_confirmed_evidence(
            tenant_id=g.capacity_tenant_id,
            company_id=engagement.company_id,
            case_id=_required_text(payload, "case_id", max_len=200),
            facts=facts,
            controls=_controls(payload["controls"]),
        )
        mismatches = []
        if state.customer_id != engagement.customer_id:
            mismatches.append("customer_id")
        if state.program_id != engagement.program_id:
            mismatches.append("program_id")
        if state.recovery_case.currency.upper() != engagement.currency:
            mismatches.append("currency")
        if mismatches:
            raise ValueError("confirmed evidence does not match engagement: " + ", ".join(mismatches))

        processed = process_state(state)
        try:
            created = capacity_repository.save(state)
        except FileExistsError:
            return jsonify({"error": "case_conflict"}), 409

        event = WorkflowEvent(
            tenant_id=g.capacity_tenant_id,
            event_id=f"{state.recovery_case.case_id}:linked",
            engagement_id=engagement.engagement_id,
            event_type=WorkflowEventType.CASE_LINKED,
            occurred_at=_required_text(payload, "occurred_at", max_len=80),
            case_id=state.recovery_case.case_id,
            external_ref=_required_text(payload, "reviewer_ref", max_len=300),
            note=_optional_text(payload, "review_note", max_len=2000),
        )
        try:
            linked = workflow_repository.append_event(event)
        except FileExistsError:
            return jsonify({"error": "case_link_event_conflict", "case_created": created}), 409

        return jsonify(
            {
                "created": created,
                "linked": linked,
                "engagement_id": engagement.engagement_id,
                "period_id": state.period_id,
                "unit": state.unit,
                "evidence_refs": list(state.evidence_refs),
                "missing_evidence": list(state.missing_evidence),
                "result": _processed_payload(processed),
                "truth_rule": "engine result is reviewable analysis, not proof of customer recovery or payment",
            }
        ), 201 if created else 200

    return app
