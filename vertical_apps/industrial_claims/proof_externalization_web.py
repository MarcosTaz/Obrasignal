from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from flask import Blueprint, jsonify, make_response, request

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.durable_proof import build_durable_claim_proof_pack
from vertical_apps.industrial_claims.offline_export_audit import OfflineExportAuditError, OfflineExportAuditStore
from vertical_apps.industrial_claims.offline_export_bundle import build_durable_offline_verification_export_bundle
from vertical_apps.industrial_claims.proof import ExternalAttestation, sha256_hex
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
from vertical_apps.industrial_claims.proof_storage import OriginalEvidenceStore
from vertical_apps.industrial_claims.proof_verifier import ExternalVerifier
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
    offline_export_identity: IdentityResolver | None = None,
    original_store: OriginalEvidenceStore | None = None,
    offline_external_verifiers: Mapping[str, ExternalVerifier] | None = None,
    offline_export_audit_store: OfflineExportAuditStore | None = None,
) -> Blueprint:
    blueprint = Blueprint("causledger_proof_externalization", __name__)
    # Construction is intentionally an application-startup concern. Read paths below
    # reuse these instances and never create schema while observing a Proof Pack.
    archive = attestation_archive or ProofAttestationArchive(audit_store.path)
    confidential_export_audit = offline_export_audit_store or OfflineExportAuditStore(audit_store.path)
    resolve_offline_export_identity = offline_export_identity or operator_identity

    def json_object() -> dict[str, Any]:
        payload = request.get_json(force=True)
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def reconstruct_archived_pack(
        base: Mapping[str, Any],
        *,
        tenant_id: str,
        finding_id: str,
    ) -> dict[str, Any]:
        manifest = base.get("proof_manifest") or {}
        target_block = manifest.get("attestation_target") or {}
        target_sha256 = str(target_block.get("sha256") or "").strip().lower()
        if len(target_sha256) != 64:
            raise ProofExternalizationIntegrityError("proof pack target is invalid")

        status = audit_store.status(tenant_id=tenant_id, finding_id=finding_id)
        completed = _completed_current_target_operations(status, target_sha256=target_sha256)
        if not completed:
            return dict(base)

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
        return enriched

    @blueprint.after_app_request
    def reconstruct_archived_attestations(response):
        """Enrich successful Proof Pack reads from verified durable receipts only."""
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

            enriched = reconstruct_archived_pack(
                base,
                tenant_id=tenant_id,
                finding_id=finding_id,
            )
            if "archived_externalization" not in enriched:
                return response
            return jsonify(enriched)
        except (
            ValueError,
            AssuranceStoreError,
            ProofExternalizationAuditError,
            ProofAttestationArchiveError,
            ProofExternalizationIntegrityError,
            sqlite3.Error,
        ):
            return make_response(jsonify({
                "error": "ProofExternalizationIntegrityError",
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

    @blueprint.post("/findings/<path:finding_id>/proof-pack/offline-export")
    def confidential_offline_export(finding_id: str):
        started_operation: dict[str, Any] | None = None
        tenant_id = ""
        actor_id = ""
        actual = ""
        try:
            tenant_id, actor_id = resolve_offline_export_identity()
            payload = json_object()
            if payload.get("confirm_confidential_export") is not True:
                raise ValueError("confirm_confidential_export must be true")
            expected = str(payload.get("expected_target_sha256") or "").strip().lower()
            if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
                raise ValueError("expected_target_sha256 must be the exact current proof target SHA-256")
            if original_store is None:
                raise AssuranceStoreError("offline export immutable original store is not configured")

            base = build_durable_claim_proof_pack(
                service,
                tenant_id=tenant_id,
                finding_id=finding_id,
            )
            pack = reconstruct_archived_pack(
                base,
                tenant_id=tenant_id,
                finding_id=finding_id,
            )
            actual = str(
                (pack.get("proof_manifest") or {}).get("attestation_target", {}).get("sha256") or ""
            ).strip().lower()
            if actual != expected:
                raise AssuranceStoreError("offline export proof target changed or was not explicitly confirmed")
            evidence = (pack.get("proof_manifest") or {}).get("evidence") or []
            if not isinstance(evidence, list) or not evidence:
                raise AssuranceStoreError("offline export proof manifest evidence is invalid")

            started_operation = confidential_export_audit.start(
                tenant_id=tenant_id,
                finding_id=finding_id,
                actor_id=actor_id,
                target_sha256=actual,
                evidence_count=len(evidence),
            )
            bundle = build_durable_offline_verification_export_bundle(
                service=service,
                proof_pack=pack,
                original_store=original_store,
                external_verifiers=offline_external_verifiers,
            )
            bundle_sha256 = sha256_hex(bundle)
            completed = confidential_export_audit.finish(
                operation_id=str(started_operation["operation_id"]),
                tenant_id=tenant_id,
                finding_id=finding_id,
                actor_id=actor_id,
                target_sha256=actual,
                state="COMPLETED",
                payload={
                    "evidence_count": len(evidence),
                    "bundle_sha256": bundle_sha256,
                    "independent_verification_valid": True,
                    "contains_documentary_bytes": False,
                },
            )
            response = make_response(jsonify(bundle), 200)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["Content-Disposition"] = (
                f'attachment; filename="causledger-offline-{actual[:16]}.json"'
            )
            response.headers["X-CausLedger-Confidential"] = "true"
            response.headers["X-CausLedger-Export-Operation"] = str(completed["operation_id"])
            return response
        except (
            ValueError,
            AssuranceStoreError,
            OfflineExportAuditError,
            ProofExternalizationAuditError,
            ProofAttestationArchiveError,
            ProofExternalizationIntegrityError,
            sqlite3.Error,
        ) as exc:
            if started_operation is not None:
                try:
                    confidential_export_audit.finish(
                        operation_id=str(started_operation["operation_id"]),
                        tenant_id=tenant_id,
                        finding_id=finding_id,
                        actor_id=actor_id,
                        target_sha256=actual,
                        state="FAILED",
                        payload={
                            "failure_class": type(exc).__name__,
                            "contains_documentary_bytes": False,
                        },
                    )
                except (OfflineExportAuditError, sqlite3.Error):
                    pass
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.get("/findings/<path:finding_id>/proof-pack/offline-exports")
    def confidential_offline_export_status(finding_id: str):
        try:
            tenant_id, _actor_id = resolve_offline_export_identity()
            service.revision_store.get(tenant_id=tenant_id, finding_id=finding_id)
            return jsonify(confidential_export_audit.status(tenant_id=tenant_id, finding_id=finding_id))
        except (AssuranceStoreError, OfflineExportAuditError, sqlite3.Error) as exc:
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
