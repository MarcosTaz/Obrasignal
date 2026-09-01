from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify, request

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.proof_attestation_archive import (
    ProofAttestationArchive,
    ProofAttestationArchiveError,
)
from vertical_apps.industrial_claims.proof_externalization import ProofExternalizationError
from vertical_apps.industrial_claims.proof_externalization_audit import (
    ProofExternalizationAuditError,
    ProofExternalizationAuditStore,
)
from vertical_apps.industrial_claims.proof_externalization_operation import externalize_proof_with_audit
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle
from vertical_apps.industrial_claims.service import IndustrialClaimsService


IdentityResolver = Callable[[], tuple[str, str]]


def create_proof_externalization_blueprint(
    *,
    service: IndustrialClaimsService,
    audit_store: ProofExternalizationAuditStore,
    providers: ProofProviderBundle,
    operator_identity: IdentityResolver,
    attestation_archive: ProofAttestationArchive | None = None,
) -> Blueprint:
    blueprint = Blueprint("causledger_proof_externalization", __name__)
    archive = attestation_archive or ProofAttestationArchive(audit_store.path)

    def json_object() -> dict[str, Any]:
        payload = request.get_json(force=True)
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    @blueprint.post("/findings/<path:finding_id>/proof-pack/externalize")
    def externalize(finding_id: str):
        try:
            tenant_id, actor_id = operator_identity()
            payload = json_object()
            if payload.get("confirm_external_proof_generation") is not True:
                raise ValueError("confirm_external_proof_generation must be true")
            expected = str(payload.get("expected_target_sha256") or "").strip().lower()
            if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
                raise ValueError("expected_target_sha256 must be the exact reviewed proof target SHA-256")
            pack = externalize_proof_with_audit(
                service,
                audit_store=audit_store,
                attestation_archive=archive,
                tenant_id=tenant_id,
                finding_id=finding_id,
                actor_id=actor_id,
                providers=providers,
                expected_target_sha256=expected,
            )
            return jsonify(pack), 201
        except (
            ValueError,
            AssuranceStoreError,
            ProofExternalizationError,
            ProofExternalizationAuditError,
            ProofAttestationArchiveError,
        ) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.get("/findings/<path:finding_id>/proof-pack/externalizations")
    def externalization_status(finding_id: str):
        try:
            tenant_id, _actor_id = operator_identity()
            service.revision_store.get(tenant_id=tenant_id, finding_id=finding_id)
            return jsonify(audit_store.status(tenant_id=tenant_id, finding_id=finding_id))
        except (AssuranceStoreError, ProofExternalizationAuditError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.get("/findings/<path:finding_id>/proof-pack/externalizations/<operation_id>/receipts")
    def externalization_receipts(finding_id: str, operation_id: str):
        try:
            tenant_id, _actor_id = operator_identity()
            service.revision_store.get(tenant_id=tenant_id, finding_id=finding_id)
            status = audit_store.status(tenant_id=tenant_id, finding_id=finding_id)
            operations = status.get("operations") or {}
            if operation_id not in operations:
                raise ProofAttestationArchiveError("externalization operation does not belong to this finding")
            return jsonify(archive.operation_receipts(tenant_id=tenant_id, operation_id=operation_id))
        except (AssuranceStoreError, ProofExternalizationAuditError, ProofAttestationArchiveError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    return blueprint
