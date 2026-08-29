from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from flask import Flask, jsonify, request

from factory_cloud.adjudication_api import register_adjudication_api
from factory_cloud.assisted_web_ui import render_assisted_workspace
from factory_cloud.assurance_kernel import AssuranceKernelError
from factory_cloud.assurance_observability import assurance_health
from factory_cloud.assurance_ops import AssuranceOperationError
from factory_cloud.assurance_store import AssuranceStoreError
from factory_cloud.finding_adjudication import FindingAdjudicationError, FindingAdjudicationLedger
from factory_cloud.shared_contracts import SharedContractError
from factory_cloud.support_api import register_support_api
from factory_cloud.support_continuity import SupportLedger
from factory_cloud.trusted_upstream_identity import TrustedUpstreamVerifier, VerifiedUpstreamIdentity
from vertical_apps.aviation_recovery.intake import AviationPilotIntakeError, AviationPilotIntakeService, EvidenceInput
from vertical_apps.aviation_recovery.service import AviationRecoveryService

API_ERRORS = (
    KeyError, TypeError, ValueError, AssuranceKernelError, AssuranceOperationError,
    AssuranceStoreError, SharedContractError, AviationPilotIntakeError,
    FindingAdjudicationError,
)
IdentityResolver = Callable[[object], VerifiedUpstreamIdentity]


def create_app(database: str | Path, *, identity_resolver: IdentityResolver | None = None) -> Flask:
    app = Flask(__name__)
    database_path = Path(database)
    service = AviationRecoveryService(database_path)
    shadow_service = AviationPilotIntakeService(database_path)
    adjudications = FindingAdjudicationLedger(database_path)
    support_ledger = SupportLedger(database_path.with_name(database_path.name + ".support.sqlite3"))
    resolver = identity_resolver or TrustedUpstreamVerifier.from_env().verify_request

    def identity() -> tuple[str, str]:
        verified = resolver(request)
        if not isinstance(verified, VerifiedUpstreamIdentity):
            raise SharedContractError("trusted upstream identity resolver returned invalid identity")
        return verified.tenant_id, verified.actor_id

    register_support_api(app, ledger=support_ledger, identity=identity)
    register_adjudication_api(app, ledger=adjudications, identity=identity)

    @app.get("/")
    def workspace():
        return render_assisted_workspace(
            title="Aviation Lease Recovery — Assisted Workspace",
            vertical="aviation-lease-entitlement-recovery",
            analysis_fields=(
                ("contract_ref", "Lease/contract reference", "text"),
                ("event_ref", "Maintenance event evidence reference", "text"),
                ("eligible_cost", "Eligible cost", "text"),
                ("reimbursed_amount", "Already reimbursed amount", "text"),
                ("notice_due", "Notice due", "date"),
            ),
        )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "vertical": "aviation-lease-entitlement-recovery", "mode": "assisted"})

    @app.get("/ready")
    def ready():
        health = assurance_health(service.store.path)
        payload = health.public_dict() | {"vertical": "aviation-lease-entitlement-recovery", "mode": "assisted"}
        return jsonify(payload), 200 if health.status == "ready" else 503

    @app.post("/analyze")
    def analyze():
        try:
            tenant_id, actor_id = identity()
            payload = request.get_json(force=True) or {}
            result = service.analyze(
                tenant_id=tenant_id, actor_id=actor_id,
                contract_ref=str(payload["contract_ref"]), event_ref=str(payload["event_ref"]),
                eligible_cost=str(payload["eligible_cost"]), reimbursed_amount=str(payload["reimbursed_amount"]),
                notice_due=date.fromisoformat(str(payload["notice_due"])),
            )
            return jsonify(result), 201
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/shadow/analyze")
    def shadow_analyze():
        try:
            tenant_id, actor_id = identity()
            payload = request.get_json(force=True) or {}
            contract = payload["lease_contract"]
            event = payload["maintenance_event"]
            result = shadow_service.analyze(
                tenant_id=tenant_id, actor_id=actor_id,
                lease_contract=EvidenceInput.create(
                    source_ref=contract["source_ref"], sha256=contract["sha256"],
                    provenance=contract["provenance"], authorized=contract["authorized"],
                ),
                maintenance_event=EvidenceInput.create(
                    source_ref=event["source_ref"], sha256=event["sha256"],
                    provenance=event["provenance"], authorized=event["authorized"],
                ),
                eligible_cost=str(payload["eligible_cost"]), reimbursed_amount=str(payload["reimbursed_amount"]),
                notice_due=date.fromisoformat(str(payload["notice_due"])),
            )
            adjudications.register_shadow(
                tenant_id=tenant_id, finding_id=str(result["finding_id"]),
                vertical="aviation-lease-entitlement-recovery", requires_breach=False,
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
            if approved and adjudications.exists(tenant_id=tenant_id, finding_id=finding_id):
                adjudications.require_actionable(tenant_id=tenant_id, finding_id=finding_id)
            state = service.review(
                tenant_id=tenant_id, finding_id=finding_id, reviewer=actor_id,
                approved=approved, reason=str(payload["reason"]),
            )
            return jsonify({"finding_id": finding_id, "state": state})
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<finding_id>/action")
    def action_finding(finding_id: str):
        try:
            tenant_id, _ = identity()
            if adjudications.exists(tenant_id=tenant_id, finding_id=finding_id):
                adjudications.require_actionable(tenant_id=tenant_id, finding_id=finding_id)
            state = service.action(tenant_id=tenant_id, finding_id=finding_id)
            return jsonify({"finding_id": finding_id, "state": state})
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @app.post("/findings/<finding_id>/resolve")
    def resolve_finding(finding_id: str):
        try:
            tenant_id, _ = identity()
            if adjudications.exists(tenant_id=tenant_id, finding_id=finding_id):
                adjudications.require_actionable(tenant_id=tenant_id, finding_id=finding_id)
            payload = request.get_json(force=True) or {}
            outcome = service.resolve(
                tenant_id=tenant_id, finding_id=finding_id,
                outcome_id=str(payload["outcome_id"]), recovered_amount=str(payload["recovered_amount"]),
                currency=str(payload["currency"]), evidence_ref=str(payload["evidence_ref"]),
            )
            return jsonify(outcome.__dict__), 201
        except API_ERRORS as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    return app
