from __future__ import annotations

from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request

from factory_cloud.assurance_kernel import AssuranceKernelError
from factory_cloud.assurance_ops import AssuranceOperationError
from factory_cloud.assurance_store import AssuranceStoreError
from factory_cloud.recovery_index import RecoveryIndexError
from factory_cloud.shared_platform import SharedPlatformError
from vertical_apps.industrial_claims.service import IndustrialClaimsService

API_ERRORS = (
    KeyError,
    ValueError,
    ArithmeticError,
    AssuranceKernelError,
    AssuranceOperationError,
    AssuranceStoreError,
    RecoveryIndexError,
    SharedPlatformError,
)


def create_app(database: str | Path) -> Flask:
    app = Flask(__name__)
    service = IndustrialClaimsService(database)

    def identity() -> tuple[str, str]:
        tenant_id = request.headers.get("X-Tenant-ID", "").strip()
        actor_id = request.headers.get("X-Actor-ID", "").strip()
        if not tenant_id or not actor_id:
            raise SharedPlatformError("trusted upstream tenant and actor identity headers are required")
        return tenant_id, actor_id

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "vertical": "industrial-claims", "mode": "assisted"})

    @app.post("/analyze")
    def analyze():
        try:
            tenant_id, actor_id = identity()
            payload = request.get_json(force=True) or {}
            missing = payload.get("missing_evidence") or []
            if not isinstance(missing, list):
                raise ValueError("missing_evidence must be a list")
            notice_raw = payload.get("notice_due")
            result = service.analyze(
                tenant_id=tenant_id,
                actor_id=actor_id,
                customer_ref=str(payload["customer_ref"]),
                program_ref=str(payload["program_ref"]),
                event_ref=str(payload["event_ref"]),
                claim_family=str(payload["claim_family"]),
                commercial_basis_ref=str(payload["commercial_basis_ref"]),
                cost_evidence_ref=str(payload["cost_evidence_ref"]),
                gross_cost=str(payload["gross_cost"]),
                avoided_cost=str(payload.get("avoided_cost", "0")),
                resale_reuse=str(payload.get("resale_reuse", "0")),
                third_party_recovery=str(payload.get("third_party_recovery", "0")),
                prior_payment=str(payload.get("prior_payment", "0")),
                other_mitigation=str(payload.get("other_mitigation", "0")),
                notice_due=date.fromisoformat(str(notice_raw)) if notice_raw else None,
                missing_evidence=tuple(str(item) for item in missing),
            )
            return jsonify({
                "finding_id": result.finding.finding_id,
                "state": result.finding.state,
                "claim_family": result.claim_family,
                "net_potential": result.calculation.output_value,
                "calculation_hash": result.calculation.reproducibility_hash,
                "missing_evidence": list(result.missing_evidence),
                "is_new_recovery": result.is_new_recovery,
            }), 201
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
            state = service.review(
                tenant_id=tenant_id,
                finding_id=finding_id,
                reviewer=actor_id,
                approved=approved,
                reason=str(payload["reason"]),
            )
            return jsonify({"finding_id": finding_id, "state": state})
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<finding_id>/action")
    def action_finding(finding_id: str):
        try:
            tenant_id, _ = identity()
            return jsonify({"finding_id": finding_id, "state": service.action(tenant_id=tenant_id, finding_id=finding_id)})
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
