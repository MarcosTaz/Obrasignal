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
from vertical_apps.contractcredit.intake import (
    ContractCreditPilotIntakeError,
    ContractCreditPilotIntakeService,
    EvidenceInput,
)
from vertical_apps.contractcredit.service import ContractCreditService

API_ERRORS = (
    KeyError, TypeError, ValueError, AssuranceKernelError, AssuranceOperationError,
    AssuranceStoreError, SharedContractError, ContractCreditPilotIntakeError,
    FindingAdjudicationError,
)
IdentityResolver = Callable[[object], VerifiedUpstreamIdentity]


def create_app(database: str | Path, *, identity_resolver: IdentityResolver | None = None) -> Flask:
    app = Flask(__name__)
    database_path = Path(database)
    service = ContractCreditService(database_path)
    shadow_service = ContractCreditPilotIntakeService(database_path)
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
            title="ContractCredit — Assisted Recovery Workspace",
            vertical="contractcredit",
            analysis_fields=(
                ("contract_ref", "Contract reference", "text"),
                ("incident_ref", "Incident evidence reference", "text"),
                ("monthly_fee", "Monthly fee", "text"),
                ("credit_rate", "Contractual credit rate", "text"),
                ("notice_due", "Notice due", "date"),
            ),
        )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "vertical": "contractcredit", "mode": "assisted"})

    @app.get("/ready")
    def ready():
        health = assurance_health(service.store.path)
        payload = health.public_dict() | {"vertical": "contractcredit", "mode": "assisted"}
        return jsonify(payload), 200 if health.status == "ready" else 503

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

    @app.post("/shadow/analyze")
    def shadow_analyze():
        try:
            tenant_id, actor_id = identity()
            payload = request.get_json(force=True) or {}
            contract = payload["service_contract"]
            incident = payload["incident_evidence"]
            result = shadow_service.analyze(
                tenant_id=tenant_id,
                actor_id=actor_id,
                service_contract=EvidenceInput.create(
                    source_ref=contract["source_ref"], sha256=contract["sha256"],
                    provenance=contract["provenance"], authorized=contract["authorized"],
                ),
                incident_evidence=EvidenceInput.create(
                    source_ref=incident["source_ref"], sha256=incident["sha256"],
                    provenance=incident["provenance"], authorized=incident["authorized"],
                ),
                monthly_fee=str(payload["monthly_fee"]),
                credit_rate=str(payload["credit_rate"]),
                notice_due=date.fromisoformat(str(payload["notice_due"])),
            )
            adjudications.register_shadow(
                tenant_id=tenant_id, finding_id=str(result["finding_id"]),
                vertical="contractcredit", requires_breach=True,
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
