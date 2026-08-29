from __future__ import annotations

from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request

from factory_cloud.assurance_kernel import AssuranceKernelError
from factory_cloud.assurance_ops import AssuranceOperationError
from factory_cloud.assurance_store import AssuranceStoreError
from factory_cloud.shared_contracts import SharedContractError
from vertical_apps.contractcredit.service import ContractCreditService

API_ERRORS = (KeyError, ValueError, AssuranceKernelError, AssuranceOperationError, AssuranceStoreError, SharedContractError)


def create_app(database: str | Path) -> Flask:
    app = Flask(__name__)
    service = ContractCreditService(database)

    def identity() -> tuple[str, str]:
        tenant_id = request.headers.get("X-Tenant-ID", "").strip()
        actor_id = request.headers.get("X-Actor-ID", "").strip()
        if not tenant_id or not actor_id:
            raise SharedContractError("trusted upstream tenant and actor identity headers are required")
        return tenant_id, actor_id

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "vertical": "contractcredit", "mode": "assisted"})

    @app.post("/analyze")
    def analyze():
        try:
            tenant_id, actor_id = identity()
            payload = request.get_json(force=True) or {}
            result = service.analyze(
                tenant_id=tenant_id,
                actor_id=actor_id,
                contract_ref=str(payload["contract_ref"]),
                incident_ref=str(payload["incident_ref"]),
                monthly_fee=str(payload["monthly_fee"]),
                credit_rate=str(payload["credit_rate"]),
                notice_due=date.fromisoformat(str(payload["notice_due"])),
            )
            return jsonify(result), 201
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<finding_id>/review")
    def review_finding(finding_id: str):
        try:
            tenant_id, actor_id = identity()
            payload = request.get_json(force=True) or {}
            approved = payload["approved"]
            if not isinstance(approved, bool):
                raise ValueError("approved must be boolean")
            state = service.review(tenant_id=tenant_id, finding_id=finding_id, reviewer=actor_id, approved=approved, reason=str(payload["reason"]))
            return jsonify({"finding_id": finding_id, "state": state})
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<finding_id>/action")
    def action_finding(finding_id: str):
        try:
            tenant_id, _ = identity()
            state = service.action(tenant_id=tenant_id, finding_id=finding_id)
            return jsonify({"finding_id": finding_id, "state": state})
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<finding_id>/resolve")
    def resolve_finding(finding_id: str):
        try:
            tenant_id, _ = identity()
            payload = request.get_json(force=True) or {}
            outcome = service.resolve(
                tenant_id=tenant_id,
                finding_id=finding_id,
                outcome_id=str(payload["outcome_id"]),
                recovered_amount=str(payload["recovered_amount"]),
                currency=str(payload["currency"]),
                evidence_ref=str(payload["evidence_ref"]),
            )
            return jsonify(outcome.__dict__), 201
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    return app
