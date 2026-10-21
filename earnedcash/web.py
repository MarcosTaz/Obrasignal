from __future__ import annotations

from decimal import Decimal
import sqlite3

from flask import Blueprint, jsonify, render_template, request

from auth_context import configured_identity

from .recovery_queue import RecoveryQueueItem
from .service import PayloadError, reconcile_payload
from .store import EarnedCashStore


def create_earnedcash_blueprint(store: EarnedCashStore | None = None) -> Blueprint:
    bp = Blueprint("earnedcash_api", __name__, url_prefix="/api/v1/earnedcash")

    def payload_object():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return None, (jsonify({"error": "json_object_required"}), 400)
        if "tenant_id" in payload:
            return None, (jsonify({"error": "tenant_id_is_server_controlled"}), 400)
        return payload, None

    def persistence_error():
        return jsonify({"error": "earnedcash_persistence_not_configured"}), 503

    def mutation_error(exc: Exception):
        if isinstance(exc, sqlite3.IntegrityError):
            return jsonify({"error": "resource_conflict"}), 409
        return jsonify({"error": str(exc)}), 400

    @bp.get("/")
    def dashboard():
        return render_template("earnedcash/index.html")

    @bp.get("/health")
    def health():
        identity = configured_identity()
        return jsonify(
            {
                "service": "earnedcash",
                "state": "PILOT_BUILD",
                "tenant_id": identity.account_id,
                "truth_policy": "FAIL_CLOSED",
                "persistence": "CONFIGURED" if store is not None else "NOT_CONFIGURED",
                "cash_verification": "SERVER_EVIDENCE_GATED",
            }
        )

    @bp.post("/reconcile-ledger")
    def reconcile():
        identity = configured_identity()
        payload, error = payload_object()
        if error:
            return error
        try:
            result = reconcile_payload(
                payload.get("records"), tenant_id=identity.account_id
            )
        except PayloadError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    @bp.post("/companies")
    def create_company():
        if store is None:
            return persistence_error()
        identity = configured_identity()
        payload, error = payload_object()
        if error:
            return error
        try:
            store.create_company(
                tenant_id=identity.account_id,
                company_id=str(payload.get("company_id") or ""),
                name=str(payload.get("name") or ""),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            return mutation_error(exc)
        return jsonify({"company_id": payload["company_id"], "created": True}), 201

    @bp.post("/customers")
    def create_customer():
        if store is None:
            return persistence_error()
        identity = configured_identity()
        payload, error = payload_object()
        if error:
            return error
        try:
            store.create_customer(
                tenant_id=identity.account_id,
                customer_id=str(payload.get("customer_id") or ""),
                company_id=str(payload.get("company_id") or ""),
                name=str(payload.get("name") or ""),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            return mutation_error(exc)
        return jsonify({"customer_id": payload["customer_id"], "created": True}), 201

    @bp.post("/projects")
    def create_project():
        if store is None:
            return persistence_error()
        identity = configured_identity()
        payload, error = payload_object()
        if error:
            return error
        try:
            store.create_project(
                tenant_id=identity.account_id,
                project_id=str(payload.get("project_id") or ""),
                company_id=str(payload.get("company_id") or ""),
                customer_id=str(payload.get("customer_id") or ""),
                name=str(payload.get("name") or ""),
                currency=str(payload.get("currency") or ""),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            return mutation_error(exc)
        return jsonify({"project_id": payload["project_id"], "created": True}), 201

    @bp.post("/contracts")
    def create_contract():
        if store is None:
            return persistence_error()
        identity = configured_identity()
        payload, error = payload_object()
        if error:
            return error
        try:
            store.create_contract(
                tenant_id=identity.account_id,
                contract_id=str(payload.get("contract_id") or ""),
                project_id=str(payload.get("project_id") or ""),
                contract_ref=str(payload.get("contract_ref") or ""),
                original_value=payload.get("original_value"),
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            return mutation_error(exc)
        return jsonify({"contract_id": payload["contract_id"], "created": True}), 201

    @bp.post("/projects/<project_id>/reconcile-ledger")
    def reconcile_project(project_id: str):
        if store is None:
            return persistence_error()
        identity = configured_identity()
        payload, error = payload_object()
        if error:
            return error
        rows = payload.get("records")
        if not isinstance(rows, list):
            return jsonify({"error": "records_array_required"}), 400
        if any(
            not isinstance(row, dict) or str(row.get("project_id") or "") != project_id
            for row in rows
        ):
            return jsonify({"error": "route_project_mismatch"}), 400
        try:
            result = reconcile_payload(rows, tenant_id=identity.account_id)
            queue = tuple(
                RecoveryQueueItem(
                    case_id=item["case_id"],
                    category=item["category"],
                    amount=Decimal(item["amount"]),
                    currency=item["currency"],
                    confidence=item["confidence"],
                    evidence_quality=item["evidence_quality"],
                    blocker=item["blocker"],
                    action=item["action"],
                    priority_score=item["priority_score"],
                    evidence_chain=tuple(item["evidence_chain"]),
                )
                for item in result["recovery_queue"]
            )
            store.replace_recovery_queue(
                tenant_id=identity.account_id, project_id=project_id, items=queue
            )
        except (PayloadError, ValueError, sqlite3.IntegrityError) as exc:
            return mutation_error(exc)
        result["queue_persisted"] = True
        return jsonify(result)

    @bp.get("/projects/<project_id>/cases")
    def cases(project_id: str):
        if store is None:
            return persistence_error()
        identity = configured_identity()
        return jsonify(
            {
                "project_id": project_id,
                "cases": store.list_cases(
                    tenant_id=identity.account_id, project_id=project_id
                ),
            }
        )

    @bp.get("/audit")
    def audit():
        if store is None:
            return persistence_error()
        identity = configured_identity()
        history = store.audit_history(identity.account_id)
        return jsonify(
            {
                "valid": store.audit_valid(identity.account_id),
                "events": [
                    {
                        "sequence": event.sequence,
                        "event_type": event.event_type,
                        "entity_id": event.entity_id,
                        "payload": event.payload,
                        "previous_hash": event.previous_hash,
                        "event_hash": event.event_hash,
                    }
                    for event in history
                ],
            }
        )

    return bp
