from __future__ import annotations

from typing import Callable

from flask import Flask, jsonify, request

from factory_cloud.shared_contracts import SharedContractError
from factory_cloud.support_continuity import SupportContinuityError, SupportIncident, SupportLedger

SUPPORT_OPERATOR_ROLES = frozenset({"on_call", "support_operator", "support_manager"})
SUPPORT_API_ERRORS = (KeyError, TypeError, ValueError, SharedContractError, SupportContinuityError)


def _public_incident(incident: SupportIncident) -> dict:
    return {
        "incident_id": incident.incident_id,
        "severity": incident.severity,
        "state": incident.state,
        "owner_role": incident.owner_role,
        "opened_at": incident.opened_at,
        "acknowledged_at": incident.acknowledged_at,
        "last_customer_update_at": incident.last_customer_update_at,
        "closure_evidence_present": incident.closure_evidence_hash is not None,
    }


def register_support_api(
    app: Flask,
    *,
    ledger: SupportLedger,
    identity: Callable[[], tuple[str, str]],
) -> None:
    """Register a tenant-scoped operator-only support boundary.

    Tenant, actor, route and X-Support-Role are cryptographically bound by the
    trusted upstream verifier before this layer runs. This layer independently
    allowlists operator roles so a valid signed identity without support authority
    remains denied. Raw customer wording is only hashed by the durable ledger.
    """

    def support_context() -> tuple[str, str, str]:
        tenant_id, actor_id = identity()
        role = request.headers.get("X-Support-Role", "").strip()
        if not role:
            raise SupportContinuityError("trusted upstream support role header is required")
        if role not in SUPPORT_OPERATOR_ROLES:
            raise SupportContinuityError("trusted upstream role is not authorized for support operations")
        return tenant_id, actor_id, role

    @app.post("/support/incidents")
    def support_open():
        try:
            tenant_id, _actor_id, role = support_context()
            payload = request.get_json(force=True) or {}
            incident = ledger.open(
                tenant_id=tenant_id,
                incident_id=str(payload["incident_id"]),
                severity=str(payload["severity"]),
                owner_role=role,
                summary=str(payload["summary"]),
            )
            return jsonify(_public_incident(incident)), 201
        except SUPPORT_API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.get("/support/incidents/<incident_id>")
    def support_get(incident_id: str):
        try:
            tenant_id, _actor_id, _role = support_context()
            return jsonify(_public_incident(ledger.get(tenant_id=tenant_id, incident_id=incident_id)))
        except (SharedContractError, SupportContinuityError) as exc:
            message = str(exc)
            status = 404 if message == "support incident not found" else 422
            return jsonify({"error": type(exc).__name__, "message": message}), status

    @app.post("/support/incidents/<incident_id>/transition")
    def support_transition(incident_id: str):
        try:
            tenant_id, _actor_id, _role = support_context()
            payload = request.get_json(force=True) or {}
            incident = ledger.transition(
                tenant_id=tenant_id,
                incident_id=incident_id,
                target=str(payload["target"]),
                evidence_ref=(str(payload["evidence_ref"]) if payload.get("evidence_ref") is not None else None),
            )
            return jsonify(_public_incident(incident))
        except SUPPORT_API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/support/incidents/<incident_id>/customer-update")
    def support_customer_update(incident_id: str):
        try:
            tenant_id, _actor_id, _role = support_context()
            payload = request.get_json(force=True) or {}
            incident = ledger.record_customer_update(
                tenant_id=tenant_id,
                incident_id=incident_id,
                communication_evidence_ref=str(payload["communication_evidence_ref"]),
            )
            return jsonify(_public_incident(incident))
        except SUPPORT_API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422
