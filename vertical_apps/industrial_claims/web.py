from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from jwt import InvalidTokenError

from auth_context import RequestIdentity, configured_identity
from auth_context_jwt import JwksUnavailableError
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


class IndustrialClaimsAuthenticationError(Exception):
    pass


class IndustrialClaimsAuthorizationError(Exception):
    def __init__(self, message: str, *, code: str = "authorization_denied"):
        super().__init__(message)
        self.code = code


def create_app(
    database: str | Path,
    *,
    identity_resolver: Callable[[], RequestIdentity] | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 3_500_000
    service = IndustrialClaimsService(database)
    resolve_identity = identity_resolver or configured_identity

    def identity(required_role: str) -> tuple[str, str]:
        try:
            verified = resolve_identity()
        except JwksUnavailableError:
            raise
        except (InvalidTokenError, RuntimeError) as exc:
            raise IndustrialClaimsAuthenticationError("verified identity required") from exc
        if not verified.authenticated:
            raise IndustrialClaimsAuthenticationError("verified identity required")

        tenant_id = verified.account_id.strip()
        actor_id = (verified.subject or verified.account_id).strip()
        if not tenant_id or not actor_id:
            raise IndustrialClaimsAuthenticationError("verified tenant and actor identity required")

        claims = verified.claims if isinstance(verified.claims, dict) else {}
        role_values: set[str] = set()
        for claim_name in ("roles", "role"):
            raw = claims.get(claim_name)
            if isinstance(raw, str):
                role_values.add(raw.strip().lower())
            elif isinstance(raw, (list, tuple, set)):
                role_values.update(str(item).strip().lower() for item in raw if str(item).strip())
        if required_role not in role_values and "admin" not in role_values:
            raise IndustrialClaimsAuthorizationError(f"verified {required_role} role required")

        requested_tenant = request.headers.get("X-Tenant-ID", "").strip()
        requested_actor = request.headers.get("X-Actor-ID", "").strip()
        if requested_tenant and requested_tenant != tenant_id:
            raise IndustrialClaimsAuthorizationError(
                "requested tenant does not match verified identity",
                code="identity_scope_mismatch",
            )
        if requested_actor and requested_actor != actor_id:
            raise IndustrialClaimsAuthorizationError(
                "requested actor does not match verified identity",
                code="identity_scope_mismatch",
            )
        return tenant_id, actor_id

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.path != "/health":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(IndustrialClaimsAuthenticationError)
    def authentication_error(_exc):
        return jsonify({"error": "authentication_required"}), 401

    @app.errorhandler(IndustrialClaimsAuthorizationError)
    def authorization_error(exc):
        return jsonify({"error": exc.code}), 403

    @app.errorhandler(JwksUnavailableError)
    def authentication_provider_unavailable(_exc):
        return jsonify({"error": "authentication_service_unavailable"}), 503

    @app.get("/")
    def console():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "vertical": "industrial-claims", "mode": "assisted"})

    @app.post("/analyze")
    def analyze():
        try:
            tenant_id, actor_id = identity("analyst")
            payload = request.get_json(force=True) or {}
            missing = payload.get("missing_evidence") or []
            if not isinstance(missing, list):
                raise ValueError("missing_evidence must be a list")
            document_fields = (
                "commercial_basis_content",
                "event_evidence_content",
                "cost_evidence_content",
            )
            for field in document_fields:
                value = payload.get(field)
                if value is not None and not isinstance(value, str):
                    raise ValueError(f"{field} must be text when supplied")
            notice_raw = payload.get("notice_due")
            no_notice_deadline = payload.get("notice_deadline_not_applicable", False)
            if not isinstance(no_notice_deadline, bool):
                raise ValueError("notice_deadline_not_applicable must be boolean")
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
                commercial_basis_content=payload.get("commercial_basis_content"),
                event_evidence_content=payload.get("event_evidence_content"),
                cost_evidence_content=payload.get("cost_evidence_content"),
                avoided_cost=str(payload.get("avoided_cost", "0")),
                resale_reuse=str(payload.get("resale_reuse", "0")),
                third_party_recovery=str(payload.get("third_party_recovery", "0")),
                prior_payment=str(payload.get("prior_payment", "0")),
                other_mitigation=str(payload.get("other_mitigation", "0")),
                notice_due=date.fromisoformat(str(notice_raw)) if notice_raw else None,
                notice_deadline_not_applicable=no_notice_deadline,
                missing_evidence=tuple(str(item) for item in missing),
            )
            return jsonify({
                "finding_id": result.finding.finding_id,
                "state": result.finding.state,
                "claim_family": result.claim_family,
                "net_potential": result.calculation.output_value,
                "calculation_hash": result.calculation.reproducibility_hash,
                "notice_deadline_state": result.notice_deadline_state,
                "evidence_states": {
                    item.source_type: item.metadata.get("verification_state", "UNKNOWN")
                    for item in result.evidence
                },
                "missing_evidence": list(result.missing_evidence),
                "is_new_recovery": result.is_new_recovery,
            }), 201
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<finding_id>/review")
    def review_finding(finding_id: str):
        try:
            tenant_id, actor_id = identity("reviewer")
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
            tenant_id, actor_id = identity("operator")
            return jsonify({
                "finding_id": finding_id,
                "state": service.action(tenant_id=tenant_id, finding_id=finding_id, actor_id=actor_id),
            })
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<finding_id>/resolve")
    def resolve_finding(finding_id: str):
        try:
            tenant_id, actor_id = identity("operator")
            payload = request.get_json(force=True) or {}
            outcome = service.resolve(
                tenant_id=tenant_id,
                finding_id=finding_id,
                outcome_id=str(payload["outcome_id"]),
                recovered_amount=str(payload["recovered_amount"]),
                currency=str(payload["currency"]),
                evidence_ref=str(payload["evidence_ref"]),
                actor_id=actor_id,
            )
            return jsonify(outcome.__dict__), 201
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    return app
