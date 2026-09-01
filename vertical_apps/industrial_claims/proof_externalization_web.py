from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from flask import Blueprint, jsonify, make_response, request

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.proof import ExternalAttestation
from vertical_apps.industrial_claims.proof_attestation_archive import (
    ProofAttestationArchive,
    ProofAttestationArchiveError,
)
from vertical_apps.industrial_claims.proof_externalization import ProofExternalizationError
from vertical_apps.industrial_claims.proof_externalization_audit import (
    ProofExternalizationAuditError,
    ProofExternalizationAuditStore,
)
from vertical_apps.industrial_claims.proof_externalization_integrity import (
    ProofExternalizationIntegrityError,
    verify_externalization_operation_integrity,
)
from vertical_apps.industrial_claims.proof_externalization_operation import externalize_proof_with_audit
from vertical_apps.industrial_claims.proof_providers import ProofProviderBundle
from vertical_apps.industrial_claims.service import IndustrialClaimsService


IdentityResolver = Callable[[], tuple[str, str]]


def _archived_attestation(raw: Mapping[str, Any]) -> ExternalAttestation:
    details = raw.get("details") or {}
    if not isinstance(details, Mapping):
        raise ProofExternalizationIntegrityError("archived attestation details are invalid")
    try:
        return ExternalAttestation(
            kind=str(raw.get("kind") or ""),
            provider=str(raw.get("provider") or ""),
            state=str(raw.get("state") or ""),
            digest_algorithm=str(raw.get("digest_algorithm") or ""),
            digest=str(raw.get("digest") or ""),
            provider_ref=raw.get("provider_ref"),
            issued_at=raw.get("issued_at"),
            validation_ref=raw.get("validation_ref"),
            details=dict(details),
        )
    except (TypeError, ValueError) as exc:
        raise ProofExternalizationIntegrityError("archived attestation payload is invalid") from exc


def _completed_current_target_operations(
    status: Mapping[str, Any],
    *,
    target_sha256: str,
) -> list[tuple[int, str]]:
    operations = status.get("operations") or {}
    if not isinstance(operations, Mapping):
        raise ProofExternalizationIntegrityError("externalization audit operations are invalid")
    completed: list[tuple[int, str]] = []
    for operation_id, raw_events in operations.items():
        if not isinstance(raw_events, Sequence) or isinstance(raw_events, (str, bytes)) or not raw_events:
            raise ProofExternalizationIntegrityError("externalization audit operation events are invalid")
        events = [event for event in raw_events if isinstance(event, Mapping)]
        if len(events) != len(raw_events):
            raise ProofExternalizationIntegrityError("externalization audit operation event is invalid")
        targets = {str(event.get("target_sha256") or "").strip().lower() for event in events}
        if targets != {target_sha256}:
            continue
        terminal = events[-1]
        if str(terminal.get("state") or "").strip().upper() != "COMPLETED":
            continue
        try:
            sequence = int(terminal.get("sequence"))
        except (TypeError, ValueError) as exc:
            raise ProofExternalizationIntegrityError("externalization audit sequence is invalid") from exc
        completed.append((sequence, str(operation_id)))
    return sorted(completed)


def create_proof_externalization_blueprint(
    *,
    service: IndustrialClaimsService,
    audit_store: ProofExternalizationAuditStore,
    providers: ProofProviderBundle,
    operator_identity: IdentityResolver,
    attestation_archive: ProofAttestationArchive | None = None,
) -> Blueprint:
    blueprint = Blueprint("causledger_proof_externalization", __name__)
    # Construction is intentionally an application-startup concern. Read paths below
    # reuse this instance and never create archive schema while observing a Proof Pack.
    archive = attestation_archive or ProofAttestationArchive(audit_store.path)

    def json_object() -> dict[str, Any]:
        payload = request.get_json(force=True)
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    @blueprint.after_app_request
    def reconstruct_archived_attestations(response):
        """Enrich successful Proof Pack reads from verified durable receipts only.

        The underlying Proof Pack endpoint performs tenant authorization first. This
        hook uses only the already-authorized pack's tenant/finding identifiers, does
        not invoke providers, does not write audit events, and does not create schema.
        Any corruption in either durable ledger fails the read closed instead of
        silently returning an apparently stronger proof state.
        """
        if request.method != "GET" or response.status_code != 200 or not request.path.endswith("/proof-pack"):
            return response
        base = response.get_json(silent=True)
        if not isinstance(base, dict):
            return response
        try:
            core = base.get("core_package") or {}
            manifest = base.get("proof_manifest") or {}
            target_block = manifest.get("attestation_target") or {}
            finding_block = core.get("finding") or {}
            tenant_id = str(core.get("tenant_id") or "").strip()
            finding_id = str(finding_block.get("finding_id") or "").strip()
            target_sha256 = str(target_block.get("sha256") or "").strip().lower()
            if not tenant_id or not finding_id or len(target_sha256) != 64:
                raise ProofExternalizationIntegrityError("proof pack identity or target is invalid")

            status = audit_store.status(tenant_id=tenant_id, finding_id=finding_id)
            completed = _completed_current_target_operations(status, target_sha256=target_sha256)
            if not completed:
                return response

            for _sequence, operation_id in completed:
                integrity = verify_externalization_operation_integrity(
                    audit_store=audit_store,
                    attestation_archive=archive,
                    tenant_id=tenant_id,
                    finding_id=finding_id,
                    operation_id=operation_id,
                )
                if integrity.get("valid") is not True:
                    raise ProofExternalizationIntegrityError("durable externalization integrity verification failed")

            _latest_sequence, latest_operation_id = completed[-1]
            archived = archive.operation_receipts(
                tenant_id=tenant_id,
                operation_id=latest_operation_id,
            )
            raw_receipts = archived.get("receipts") or []
            if not isinstance(raw_receipts, list) or not raw_receipts:
                raise ProofExternalizationIntegrityError("completed externalization receipts are missing")
            attestations = tuple(
                _archived_attestation(item)
                for item in raw_receipts
                if isinstance(item, Mapping)
            )
            if len(attestations) != len(raw_receipts):
                raise ProofExternalizationIntegrityError("archived attestation receipt is invalid")

            enriched = build_durable_claim_proof_pack(
                service,
                tenant_id=tenant_id,
                finding_id=finding_id,
                attestations=attestations,
            )
            reconstructed_target = str(
                (enriched.get("proof_manifest") or {}).get("attestation_target", {}).get("sha256") or ""
            ).lower()
            if reconstructed_target != target_sha256:
                raise ProofExternalizationIntegrityError("proof target changed during archived reconstruction")
            enriched["archived_externalization"] = {
                "source": "DURABLE_ATTESTATION_ARCHIVE",
                "operation_id": latest_operation_id,
                "target_sha256": target_sha256,
                "receipt_count": int(archived.get("receipt_count") or 0),
                "receipts_sha256": archived.get("receipts_sha256"),
                "archive_chain_head_sha256": archived.get("archive_chain_head_sha256"),
                "archive_chain_verified": archived.get("archive_chain_verified") is True,
                "integrity_verified": True,
                "read_only_reconstruction": True,
            }
            return jsonify(enriched)
        except (
            ValueError,
            AssuranceStoreError,
            ProofExternalizationAuditError,
            ProofAttestationArchiveError,
            ProofExternalizationIntegrityError,
            sqlite3.Error,
        ) as exc:
            return make_response(jsonify({
                "error": type(exc).__name__,
                "message": "durable external attestation reconstruction failed closed",
            }), 422)

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

    @blueprint.get("/findings/<path:finding_id>/proof-pack/externalizations/<operation_id>/integrity")
    def externalization_integrity(finding_id: str, operation_id: str):
        try:
            tenant_id, _actor_id = operator_identity()
            service.revision_store.get(tenant_id=tenant_id, finding_id=finding_id)
            result = verify_externalization_operation_integrity(
                audit_store=audit_store,
                attestation_archive=archive,
                tenant_id=tenant_id,
                finding_id=finding_id,
                operation_id=operation_id,
            )
            return jsonify(result)
        except (
            AssuranceStoreError,
            ProofExternalizationAuditError,
            ProofAttestationArchiveError,
            ProofExternalizationIntegrityError,
        ) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    return blueprint
