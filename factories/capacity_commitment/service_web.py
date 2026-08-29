from __future__ import annotations

from flask import g, jsonify, request

from .engine import ENGINE_VERSION
from .evidence import EvidenceRepository
from .service_ops import (
    MonitoringPlan,
    ServiceOperationsRepository,
    SupportCategory,
    SupportEvent,
    SupportEventType,
    SupportTicket,
)
from .workflow import WorkflowRepository


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


def _monitor_payload(item):
    return {
        "monitor_id": item.monitor_id,
        "engagement_id": item.engagement_id,
        "case_id": item.case_id,
        "cadence_days": item.cadence_days,
        "next_check_on": item.next_check_on,
        "supersedes_monitor_id": item.supersedes_monitor_id,
    }


def _ticket_payload(ticket, state):
    return {
        "ticket_id": ticket.ticket_id,
        "engagement_id": ticket.engagement_id,
        "case_id": ticket.case_id,
        "category": ticket.category.value,
        "summary": ticket.summary,
        "opened_at": ticket.opened_at,
        "status": state.status,
        "event_count": state.event_count,
        "latest_event_type": state.latest_event_type,
    }


def register_service_routes(app, capacity_repository):
    evidence = EvidenceRepository(capacity_repository.db_path)
    workflow = WorkflowRepository(capacity_repository.db_path)
    service_ops = ServiceOperationsRepository(capacity_repository.db_path)

    @app.route("/api/capacity/monitoring", methods=["GET"])
    def list_monitoring():
        items = service_ops.list_active_monitors(tenant_id=g.capacity_tenant_id)
        return jsonify({"items": [_monitor_payload(item) for item in items], "count": len(items)})

    @app.route("/api/capacity/monitoring", methods=["POST"])
    def create_monitoring():
        if request.headers.get("X-Capacity-Intent") != "create-monitor":
            return jsonify({"error": "monitor_intent_required"}), 403
        payload = _strict(
            request.get_json(silent=False),
            {
                "monitor_id",
                "engagement_id",
                "case_id",
                "cadence_days",
                "next_check_on",
                "supersedes_monitor_id",
            },
            {"monitor_id", "engagement_id", "case_id", "cadence_days", "next_check_on"},
        )
        cadence = payload["cadence_days"]
        if type(cadence) is not int:
            raise ValueError("cadence_days must be an integer")
        item = MonitoringPlan(
            tenant_id=g.capacity_tenant_id,
            monitor_id=_required(payload, "monitor_id"),
            engagement_id=_required(payload, "engagement_id"),
            case_id=_required(payload, "case_id"),
            cadence_days=cadence,
            next_check_on=_required(payload, "next_check_on"),
            supersedes_monitor_id=_optional(payload, "supersedes_monitor_id"),
        )
        try:
            created = service_ops.save_monitor(item)
        except FileExistsError:
            return jsonify({"error": "monitor_conflict"}), 409
        stored = service_ops.load_monitor(tenant_id=g.capacity_tenant_id, monitor_id=item.monitor_id)
        return jsonify({"created": created, "monitor": _monitor_payload(stored)}), 201 if created else 200

    @app.route("/api/capacity/support", methods=["POST"])
    def create_support_ticket():
        if request.headers.get("X-Capacity-Intent") != "open-support":
            return jsonify({"error": "support_intent_required"}), 403
        payload = _strict(
            request.get_json(silent=False),
            {"ticket_id", "engagement_id", "case_id", "category", "summary", "opened_at"},
            {"ticket_id", "engagement_id", "category", "summary", "opened_at"},
        )
        try:
            category = SupportCategory(payload["category"])
        except (ValueError, TypeError) as exc:
            raise ValueError("category must be a valid SupportCategory") from exc
        item = SupportTicket(
            tenant_id=g.capacity_tenant_id,
            ticket_id=_required(payload, "ticket_id"),
            engagement_id=_required(payload, "engagement_id"),
            category=category,
            summary=_required(payload, "summary"),
            opened_at=_required(payload, "opened_at"),
            case_id=_optional(payload, "case_id"),
        )
        try:
            created = service_ops.open_ticket(item)
        except FileExistsError:
            return jsonify({"error": "support_ticket_conflict"}), 409
        state = service_ops.support_state(tenant_id=g.capacity_tenant_id, ticket_id=item.ticket_id)
        return jsonify({"created": created, "ticket": _ticket_payload(item, state)}), 201 if created else 200

    @app.route("/api/capacity/support/<ticket_id>", methods=["GET"])
    def get_support_ticket(ticket_id):
        item = service_ops.load_ticket(tenant_id=g.capacity_tenant_id, ticket_id=ticket_id)
        state = service_ops.support_state(tenant_id=g.capacity_tenant_id, ticket_id=ticket_id)
        return jsonify({"ticket": _ticket_payload(item, state)})

    @app.route("/api/capacity/support/<ticket_id>/events", methods=["POST"])
    def create_support_event(ticket_id):
        if request.headers.get("X-Capacity-Intent") != "record-support-event":
            return jsonify({"error": "support_event_intent_required"}), 403
        payload = _strict(
            request.get_json(silent=False),
            {"support_event_id", "event_type", "occurred_at", "note"},
            {"support_event_id", "event_type", "occurred_at"},
        )
        try:
            event_type = SupportEventType(payload["event_type"])
        except (ValueError, TypeError) as exc:
            raise ValueError("event_type must be a valid SupportEventType") from exc
        event = SupportEvent(
            tenant_id=g.capacity_tenant_id,
            support_event_id=_required(payload, "support_event_id"),
            ticket_id=ticket_id,
            event_type=event_type,
            occurred_at=_required(payload, "occurred_at"),
            note=_optional(payload, "note"),
        )
        try:
            created = service_ops.append_support_event(event)
        except FileExistsError:
            return jsonify({"error": "support_event_conflict"}), 409
        state = service_ops.support_state(tenant_id=g.capacity_tenant_id, ticket_id=ticket_id)
        return jsonify({"created": created, "state": state.__dict__}), 201 if created else 200

    @app.route("/api/capacity/observability", methods=["GET"])
    def observability():
        tenant_id = g.capacity_tenant_id
        cases = capacity_repository.list_case_ids(tenant_id=tenant_id)
        sources = evidence.list_sources(tenant_id=tenant_id)
        engagements = workflow.list_engagements(tenant_id=tenant_id)
        monitors = service_ops.list_active_monitors(tenant_id=tenant_id)
        return jsonify(
            {
                "engine_version": ENGINE_VERSION,
                "tenant_scoped": True,
                "case_count": len(cases),
                "evidence_source_count": len(sources),
                "engagement_count": len(engagements),
                "active_monitor_count": len(monitors),
                "technical_ready": True,
                "commercial_ready": False,
                "commercial_ready_blockers": [
                    "no buyer-qualified real case yet",
                    "no Capacity-specific payment processor/account verified",
                    "no real pilot/payment/repeat-value evidence yet",
                ],
            }
        )

    return app
