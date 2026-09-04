from __future__ import annotations

from decimal import Decimal, InvalidOperation

from flask import g, jsonify, request

from .evidence import EvidenceRepository
from .evidence_case import build_case_draft
from .workflow import (
    Engagement,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowRepository,
)


def _required(payload, key):
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required and must be a string")
    return value.strip()


def _optional(payload, key):
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    return value


def _strict(payload, allowed, required=()):
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    unknown = set(payload) - set(allowed)
    if unknown:
        raise ValueError(f"unknown request fields: {sorted(unknown)}")
    missing = set(required) - set(payload)
    if missing:
        raise ValueError(f"missing request fields: {sorted(missing)}")
    return payload


def _decimal(payload, key):
    raw = payload.get(key)
    if raw is None:
        return None
    if isinstance(raw, bool) or isinstance(raw, float):
        raise ValueError(f"{key} must be an exact decimal string or integer")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{key} must be an exact decimal string or integer") from exc
    if not value.is_finite() or value < 0:
        raise ValueError(f"{key} must be finite and non-negative")
    return value


def _engagement_payload(item):
    return {
        "engagement_id": item.engagement_id,
        "company_id": item.company_id,
        "customer_id": item.customer_id,
        "program_id": item.program_id,
        "currency": item.currency,
    }


def _event_payload(item):
    return {
        "event_id": item.event_id,
        "engagement_id": item.engagement_id,
        "event_type": item.event_type.value,
        "occurred_at": item.occurred_at,
        "case_id": item.case_id,
        "amount": None if item.amount is None else format(item.amount, "f"),
        "currency": item.currency,
        "external_ref": item.external_ref,
        "note": item.note,
    }


def _summary_payload(item):
    return {
        "engagement_id": item.engagement_id,
        "linked_case_ids": list(item.linked_case_ids),
        "customer_recovery_received": format(item.customer_recovery_received, "f"),
        "our_invoice_issued": format(item.our_invoice_issued, "f"),
        "our_payment_received": format(item.our_payment_received, "f"),
        "action_submitted": item.action_submitted,
        "customer_accepted": item.customer_accepted,
        "customer_rejected": item.customer_rejected,
        "zero_outcome_confirmed": item.zero_outcome_confirmed,
        "latest_event_type": item.latest_event_type,
    }


def register_completion_routes(app, capacity_repository):
    """Attach customer-journey completion routes to the authenticated base app."""

    evidence_repository = EvidenceRepository(capacity_repository.db_path)
    workflow_repository = WorkflowRepository(capacity_repository.db_path)

    @app.route("/api/capacity/evidence/case-draft", methods=["GET"])
    def evidence_case_draft():
        company_id = request.args.get("company_id", "")
        facts = evidence_repository.list_facts(tenant_id=g.capacity_tenant_id)
        draft = build_case_draft(company_id, facts)
        return jsonify(
            {
                "company_id": draft.company_id,
                "case_inputs": dict(draft.case_inputs),
                "evidence_refs": list(draft.evidence_refs),
                "conflicts": list(draft.conflicts),
                "missing_required": list(draft.missing_required),
                "human_control_gates": list(draft.human_control_gates),
                "ready_for_human_case_creation": draft.ready_for_human_case_creation,
                "truth_rule": "draft is source-backed input only; it is not an entitlement decision",
            }
        )

    @app.route("/api/capacity/engagements", methods=["GET"])
    def list_engagements():
        items = workflow_repository.list_engagements(tenant_id=g.capacity_tenant_id)
        return jsonify({"items": [_engagement_payload(item) for item in items], "count": len(items)})

    @app.route("/api/capacity/engagements", methods=["POST"])
    def create_engagement():
        if request.headers.get("X-Capacity-Intent") != "create-engagement":
            return jsonify({"error": "engagement_intent_required"}), 403
        payload = _strict(
            request.get_json(silent=False),
            {"engagement_id", "company_id", "customer_id", "program_id", "currency"},
            {"engagement_id", "company_id", "customer_id", "program_id", "currency"},
        )
        item = Engagement(
            tenant_id=g.capacity_tenant_id,
            engagement_id=_required(payload, "engagement_id"),
            company_id=_required(payload, "company_id"),
            customer_id=_required(payload, "customer_id"),
            program_id=_required(payload, "program_id"),
            currency=_required(payload, "currency"),
        )
        try:
            created = workflow_repository.save_engagement(item)
        except FileExistsError:
            return jsonify({"error": "engagement_conflict"}), 409
        stored = workflow_repository.load_engagement(
            tenant_id=g.capacity_tenant_id, engagement_id=item.engagement_id
        )
        return jsonify({"created": created, "engagement": _engagement_payload(stored)}), 201 if created else 200

    @app.route("/api/capacity/engagements/<engagement_id>", methods=["GET"])
    def get_engagement(engagement_id):
        item = workflow_repository.load_engagement(
            tenant_id=g.capacity_tenant_id, engagement_id=engagement_id
        )
        events = workflow_repository.list_events(
            tenant_id=g.capacity_tenant_id, engagement_id=engagement_id
        )
        summary = workflow_repository.summary(
            tenant_id=g.capacity_tenant_id, engagement_id=engagement_id
        )
        return jsonify(
            {
                "engagement": _engagement_payload(item),
                "events": [_event_payload(event) for event in events],
                "summary": _summary_payload(summary),
            }
        )

    @app.route("/api/capacity/engagements/<engagement_id>/events", methods=["POST"])
    def append_workflow_event(engagement_id):
        if request.headers.get("X-Capacity-Intent") != "record-event":
            return jsonify({"error": "event_intent_required"}), 403
        payload = _strict(
            request.get_json(silent=False),
            {
                "event_id",
                "event_type",
                "occurred_at",
                "case_id",
                "amount",
                "currency",
                "external_ref",
                "note",
            },
            {"event_id", "event_type", "occurred_at"},
        )
        try:
            event_type = WorkflowEventType(payload["event_type"])
        except (ValueError, TypeError) as exc:
            raise ValueError("event_type must be a valid WorkflowEventType") from exc
        item = WorkflowEvent(
            tenant_id=g.capacity_tenant_id,
            event_id=_required(payload, "event_id"),
            engagement_id=engagement_id,
            event_type=event_type,
            occurred_at=_required(payload, "occurred_at"),
            case_id=_optional(payload, "case_id"),
            amount=_decimal(payload, "amount"),
            currency=_optional(payload, "currency"),
            external_ref=_optional(payload, "external_ref"),
            note=_optional(payload, "note"),
        )
        try:
            created = workflow_repository.append_event(item)
        except FileExistsError:
            return jsonify({"error": "workflow_event_conflict"}), 409
        stored = workflow_repository.load_event(
            tenant_id=g.capacity_tenant_id, event_id=item.event_id
        )
        summary = workflow_repository.summary(
            tenant_id=g.capacity_tenant_id, engagement_id=engagement_id
        )
        return jsonify(
            {
                "created": created,
                "event": _event_payload(stored),
                "summary": _summary_payload(summary),
            }
        ), 201 if created else 200

    return app
