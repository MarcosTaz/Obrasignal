from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from jwt import InvalidTokenError
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from auth_context import RequestIdentity, configured_identity
from auth_context_jwt import JwksUnavailableError
from factory_cloud.assurance_kernel import AssuranceKernelError
from factory_cloud.assurance_ops import AssuranceOperationError
from factory_cloud.assurance_store import AssuranceStoreError
from factory_cloud.recovery_index import RecoveryIndexError
from factory_cloud.shared_platform import SharedPlatformError
from vertical_apps.industrial_claims.amendment import amend_case
from vertical_apps.industrial_claims.change_capture import ChangeCaptureError, ChangeCaptureStore
from vertical_apps.industrial_claims.change_capture_web import create_change_capture_blueprint
from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.proof_externalization_audit import ProofExternalizationAuditStore
from vertical_apps.industrial_claims.proof_externalization_web import create_proof_externalization_blueprint
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle
from vertical_apps.industrial_claims.public_verification_store import PublicVerificationStore
from vertical_apps.industrial_claims.public_verification_web import create_public_verification_blueprint
from vertical_apps.industrial_claims.read_model import IndustrialClaimsReadModel
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
    ChangeCaptureError,
)
REVIEWER_QUEUE_STATES = {"READY_FOR_REVIEW"}
OPERATOR_QUEUE_STATES = {"APPROVED", "ACTIONED"}
ADMIN_QUEUE_STATES = REVIEWER_QUEUE_STATES | OPERATOR_QUEUE_STATES
REVIEW_SCOPE = "INTERNAL_WORKFLOW_APPROVAL"
INLINE_DOCUMENTARY_FIELDS = (
    "commercial_basis_content",
    "event_evidence_content",
    "cost_evidence_content",
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
    proof_providers: ProofProviderBundle | None = None,
    allow_inline_evidence_content: bool = False,
) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 3_500_000
    app.config["CAUSLEDGER_INLINE_EVIDENCE_CONTENT_ENABLED"] = bool(allow_inline_evidence_content)
    service = IndustrialClaimsService(database)
    read_model = IndustrialClaimsReadModel(database)
    public_verification_store = PublicVerificationStore(database)
    change_capture_store = ChangeCaptureStore(database)
    proof_externalization_audit_store = ProofExternalizationAuditStore(database)
    external_providers = proof_providers or ProofProviderBundle.fail_closed()
    resolve_identity = identity_resolver or configured_identity

    def identity_any(*required_roles: str) -> tuple[str, str, frozenset[str]]:
        if not required_roles:
            raise RuntimeError("at least one role is required")
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
        required = {role.strip().lower() for role in required_roles if role.strip()}
        if "admin" not in role_values and not role_values.intersection(required):
            raise IndustrialClaimsAuthorizationError(f"verified {'/'.join(sorted(required))} role required")
        requested_tenant = request.headers.get("X-Tenant-ID", "").strip()
        requested_actor = request.headers.get("X-Actor-ID", "").strip()
        if requested_tenant and requested_tenant != tenant_id:
            raise IndustrialClaimsAuthorizationError("requested tenant does not match verified identity", code="identity_scope_mismatch")
        if requested_actor and requested_actor != actor_id:
            raise IndustrialClaimsAuthorizationError("requested actor does not match verified identity", code="identity_scope_mismatch")
        return tenant_id, actor_id, frozenset(role_values)

    def identity(required_role: str) -> tuple[str, str]:
        tenant_id, actor_id, _roles = identity_any(required_role)
        return tenant_id, actor_id

    def change_capture_identity() -> tuple[str, str]:
        tenant_id, actor_id, _roles = identity_any("client", "analyst", "operator")
        return tenant_id, actor_id

    def json_object() -> dict:
        payload = request.get_json(force=True)
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def reject_inline_documentary_content(payload: dict, *, fields: tuple[str, ...]) -> None:
        if app.config["CAUSLEDGER_INLINE_EVIDENCE_CONTENT_ENABLED"]:
            return
        for field in fields:
            value = payload.get(field)
            if isinstance(value, str) and value.strip():
                raise ValueError(
                    "inline documentary content is disabled; use authorized secure evidence capture"
                )

    def candidate_payload(payload: dict) -> tuple[list, object, bool]:
        missing = payload.get("missing_evidence") or []
        if not isinstance(missing, list):
            raise ValueError("missing_evidence must be a list")
        for field in INLINE_DOCUMENTARY_FIELDS:
            value = payload.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{field} must be text when supplied")
        notice_raw = payload.get("notice_due")
        no_notice_deadline = payload.get("notice_deadline_not_applicable", False)
        if not isinstance(no_notice_deadline, bool):
            raise ValueError("notice_deadline_not_applicable must be boolean")
        return missing, notice_raw, no_notice_deadline

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
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

    @app.errorhandler(BadRequest)
    def invalid_json(_exc):
        return jsonify({"error": "invalid_json", "message": "request body must contain valid JSON"}), 400

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_exc):
        return jsonify({"error": "request_too_large", "message": "request body exceeds assisted intake limit"}), 413

    app.register_blueprint(
        create_public_verification_blueprint(
            service=service,
            store=public_verification_store,
            publication_identity=lambda: identity("operator"),
        )
    )
    app.register_blueprint(
        create_change_capture_blueprint(
            store=change_capture_store,
            capture_identity=change_capture_identity,
        )
    )
    app.register_blueprint(
        create_proof_externalization_blueprint(
            service=service,
            audit_store=proof_externalization_audit_store,
            providers=external_providers,
            operator_identity=lambda: identity("operator"),
        )
    )

    @app.get("/")
    def console():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return jsonify({
            "status": "ok",
            "vertical": "industrial-claims",
            "mode": "assisted",
            "inline_documentary_content_enabled": bool(
                app.config["CAUSLEDGER_INLINE_EVIDENCE_CONTENT_ENABLED"]
            ),
        })

    @app.get("/findings")
    def list_findings():
        try:
            tenant_id, _actor_id, roles = identity_any("reviewer", "operator")
            if "admin" in roles:
                permitted_states = set(ADMIN_QUEUE_STATES)
            else:
                permitted_states: set[str] = set()
                if "reviewer" in roles:
                    permitted_states.update(REVIEWER_QUEUE_STATES)
                if "operator" in roles:
                    permitted_states.update(OPERATOR_QUEUE_STATES)
            raw_states = request.args.getlist("state")
            if not raw_states and request.args.get("states"):
                raw_states = [item for item in request.args.get("states", "").split(",") if item.strip()]
            requested_states = {item.strip().upper() for item in raw_states if item.strip()}
            if requested_states and not requested_states.issubset(permitted_states):
                raise IndustrialClaimsAuthorizationError("requested queue state is not permitted for verified role")
            states = tuple(sorted(requested_states or permitted_states))
            raw_limit = request.args.get("limit", "100")
            try:
                limit = int(raw_limit)
            except (TypeError, ValueError) as exc:
                raise ValueError("limit must be an integer") from exc
            items = read_model.list_findings(tenant_id=tenant_id, states=states, limit=limit)
            return jsonify({"queue_scope": list(states), "count": len(items), "findings": [item.as_dict() for item in items]})
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.get("/findings/<path:finding_id>")
    def finding_detail(finding_id: str):
        try:
            tenant_id, _actor_id, _roles = identity_any("analyst", "reviewer", "operator")
            detail = read_model.get_finding(tenant_id=tenant_id, finding_id=finding_id)
            detail["review_contract"] = {
                "approval_scope": REVIEW_SCOPE,
                "approval_establishes_recoverability": False,
                "approval_is_legal_conclusion": False,
                "approval_authorizes_customer_contact": False,
                "approval_authorizes_external_claim_submission": False,
            }
            return jsonify(detail)
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.get("/findings/<path:finding_id>/proof-pack")
    def finding_proof_pack(finding_id: str):
        try:
            tenant_id, _actor_id, _roles = identity_any("analyst", "reviewer", "operator")
            pack = build_durable_claim_proof_pack(
                service,
                tenant_id=tenant_id,
                finding_id=finding_id,
            )
            return jsonify(pack)
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/analyze")
    def analyze():
        try:
            tenant_id, actor_id = identity("analyst")
            payload = json_object()
            missing, notice_raw, no_notice_deadline = candidate_payload(payload)
            reject_inline_documentary_content(payload, fields=INLINE_DOCUMENTARY_FIELDS)
            result = service.analyze(
                tenant_id=tenant_id, actor_id=actor_id, customer_ref=str(payload["customer_ref"]), program_ref=str(payload["program_ref"]), event_ref=str(payload["event_ref"]), claim_family=str(payload["claim_family"]), commercial_basis_ref=str(payload["commercial_basis_ref"]), cost_evidence_ref=str(payload["cost_evidence_ref"]), gross_cost=str(payload["gross_cost"]), currency=str(payload.get("currency", "")), commercial_basis_content=payload.get("commercial_basis_content"), event_evidence_content=payload.get("event_evidence_content"), cost_evidence_content=payload.get("cost_evidence_content"), avoided_cost=str(payload.get("avoided_cost", "0")), resale_reuse=str(payload.get("resale_reuse", "0")), third_party_recovery=str(payload.get("third_party_recovery", "0")), prior_payment=str(payload.get("prior_payment", "0")), other_mitigation=str(payload.get("other_mitigation", "0")), notice_due=date.fromisoformat(str(notice_raw)) if notice_raw else None, notice_deadline_not_applicable=no_notice_deadline, missing_evidence=tuple(str(item) for item in missing),
            )
            change_capture = change_capture_store.status(
                tenant_id=tenant_id,
                finding_id=result.finding.finding_id,
            )
            return jsonify({
                "finding_id": result.finding.finding_id,
                "state": result.finding.state,
                "claim_family": result.claim_family,
                "net_potential": result.calculation.output_value,
                "currency": result.calculation.output_unit,
                "calculation_hash": result.calculation.reproducibility_hash,
                "notice_deadline_state": result.notice_deadline_state,
                "evidence_states": {item.source_type: item.metadata.get("verification_state", "UNKNOWN") for item in result.evidence},
                "missing_evidence": list(result.missing_evidence),
                "is_new_recovery": result.is_new_recovery,
                "revision": 1,
                "change_capture": change_capture,
            }), 201
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<path:finding_id>/amend")
    def amend_finding(finding_id: str):
        try:
            tenant_id, actor_id = identity("analyst")
            payload = json_object()
            missing, notice_raw, no_notice_deadline = candidate_payload(payload)
            reject_inline_documentary_content(payload, fields=INLINE_DOCUMENTARY_FIELDS)
            result = amend_case(
                service,
                tenant_id=tenant_id, finding_id=finding_id, actor_id=actor_id,
                customer_ref=str(payload["customer_ref"]), program_ref=str(payload["program_ref"]), event_ref=str(payload["event_ref"]),
                claim_family=str(payload["claim_family"]), commercial_basis_ref=str(payload["commercial_basis_ref"]),
                cost_evidence_ref=str(payload["cost_evidence_ref"]), gross_cost=str(payload["gross_cost"]),
                currency=str(payload.get("currency", "")), commercial_basis_content=payload.get("commercial_basis_content"),
                event_evidence_content=payload.get("event_evidence_content"), cost_evidence_content=payload.get("cost_evidence_content"),
                avoided_cost=str(payload.get("avoided_cost", "0")), resale_reuse=str(payload.get("resale_reuse", "0")),
                third_party_recovery=str(payload.get("third_party_recovery", "0")), prior_payment=str(payload.get("prior_payment", "0")),
                other_mitigation=str(payload.get("other_mitigation", "0")),
                notice_due=date.fromisoformat(str(notice_raw)) if notice_raw else None,
                notice_deadline_not_applicable=no_notice_deadline, missing_evidence=tuple(str(item) for item in missing),
            )
            revision = service.revision_store.require_current(tenant_id=tenant_id, finding_id=result.finding.finding_id)
            change_capture = change_capture_store.status(
                tenant_id=tenant_id,
                finding_id=result.finding.finding_id,
            )
            return jsonify({
                "finding_id": result.finding.finding_id,
                "supersedes_finding_id": finding_id,
                "revision": revision.revision,
                "state": result.finding.state,
                "claim_family": result.claim_family,
                "net_potential": result.calculation.output_value,
                "currency": result.calculation.output_unit,
                "calculation_hash": result.calculation.reproducibility_hash,
                "notice_deadline_state": result.notice_deadline_state,
                "missing_evidence": list(result.missing_evidence),
                "is_new_recovery": False,
                "requires_fresh_review": True,
                "customer_contact_authorized": False,
                "external_claim_submission_authorized": False,
                "change_capture": change_capture,
            }), 201
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<path:finding_id>/review")
    def review_finding(finding_id: str):
        try:
            tenant_id, actor_id = identity("reviewer")
            payload = json_object()
            approved = payload["approved"]
            if not isinstance(approved, bool):
                raise ValueError("approved must be boolean")
            state = service.review(tenant_id=tenant_id, finding_id=finding_id, reviewer=actor_id, approved=approved, reason=str(payload["reason"]))
            return jsonify({
                "finding_id": finding_id,
                "state": state,
                "review_scope": REVIEW_SCOPE,
                "recoverability_established": False,
                "legal_conclusion": None,
                "customer_contact_authorized": False,
                "external_claim_submission_authorized": False,
            })
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<path:finding_id>/action")
    def action_finding(finding_id: str):
        try:
            tenant_id, actor_id = identity("operator")
            return jsonify({
                "finding_id": finding_id,
                "state": service.action(tenant_id=tenant_id, finding_id=finding_id, actor_id=actor_id),
                "internal_workflow_only": True,
                "customer_contact_performed": False,
                "external_claim_submitted": False,
            })
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<path:finding_id>/resolve")
    def resolve_finding(finding_id: str):
        try:
            tenant_id, actor_id = identity("operator")
            payload = json_object()
            if payload.get("final_cumulative") is not True:
                raise ValueError("final_cumulative must be true because resolve closes the finding")
            evidence_content = payload.get("evidence_content")
            if not isinstance(evidence_content, str) or not evidence_content.strip():
                raise ValueError("documentary outcome evidence content is required as text")
            reject_inline_documentary_content(payload, fields=("evidence_content",))
            outcome = service.resolve(
                tenant_id=tenant_id,
                finding_id=finding_id,
                outcome_id=str(payload["outcome_id"]),
                recovered_amount=str(payload["recovered_amount"]),
                currency=str(payload["currency"]),
                evidence_ref=str(payload["evidence_ref"]),
                evidence_content=evidence_content,
                actor_id=actor_id,
            )
            body = dict(outcome.__dict__)
            body["final_cumulative"] = True
            body["finding_closed_by_outcome"] = True
            return jsonify(body), 201
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    return app