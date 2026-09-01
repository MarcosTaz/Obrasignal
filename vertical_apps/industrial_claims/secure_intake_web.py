from __future__ import annotations

import base64
import binascii
from collections.abc import Callable, Mapping
from typing import Any

from flask import Blueprint, jsonify, request

from vertical_apps.industrial_claims.intake_authorization import (
    BOUNDED_RAPID_SCAN_PURPOSE,
    IntakeAuthorization,
    capture_authorized_original_evidence,
)
from vertical_apps.industrial_claims.outcome_authorization import (
    DOCUMENTED_FINAL_OUTCOME_PURPOSE,
    OutcomeEvidenceAuthorization,
    capture_authorized_outcome_evidence,
)
from vertical_apps.industrial_claims.proof_storage import OriginalEvidenceStore
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry, SecureCaptureRegistryError
from vertical_apps.industrial_claims.secure_outcome_registry import SecureOutcomeRegistry, SecureOutcomeRegistryError


class SecureIntakeWebError(ValueError):
    pass


IdentityResolver = Callable[[], tuple[str, str]]
MAX_ROUTE_ORIGINAL_BYTES = 2_000_000
_ALLOWED_AUTHORIZATION_KEYS = {
    "authorization_id",
    "authorized_by_ref",
    "authorized_at",
    "expires_at",
    "minimum_immutable_retention_until",
    "transfer_channel_ref",
    "data_terms_state",
    "immutable_retention_acknowledged",
    "max_bytes_per_evidence",
    "max_bytes",
    "evidence_roles",
    "purpose",
    "case_ref",
}


def _json_object() -> dict[str, Any]:
    payload = request.get_json(force=True)
    if not isinstance(payload, dict):
        raise SecureIntakeWebError("JSON body must be an object")
    return payload


def _required_text(value: object, *, label: str, maximum: int) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise SecureIntakeWebError(f"invalid secure intake {label}")
    return text


def _authorization_object(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = payload.get("authorization")
    if not isinstance(raw, dict):
        raise SecureIntakeWebError("authorization must be an object")
    unknown = set(raw) - _ALLOWED_AUTHORIZATION_KEYS
    if unknown:
        raise SecureIntakeWebError("authorization contains unsupported fields")
    return dict(raw)


def _strict_original(payload: Mapping[str, Any]) -> tuple[bytes, str]:
    encoded = payload.get("content_base64")
    if not isinstance(encoded, str) or not encoded:
        raise SecureIntakeWebError("content_base64 is required")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise SecureIntakeWebError("content_base64 is invalid") from exc
    if not content:
        raise SecureIntakeWebError("secure intake original must be non-empty")
    if len(content) > MAX_ROUTE_ORIGINAL_BYTES:
        raise SecureIntakeWebError("secure intake original exceeds assisted route byte limit")
    content_type = _required_text(payload.get("content_type"), label="content_type", maximum=128)
    if "/" not in content_type or any(ch.isspace() for ch in content_type):
        raise SecureIntakeWebError("secure intake content_type is invalid")
    return content, content_type


def _capture_identity(tenant_id: str, actor_id: str) -> CaptureIdentity:
    return CaptureIdentity(
        tenant_id=tenant_id,
        actor_id=actor_id,
        subject=actor_id,
        amr=(),
        request_ref=request.headers.get("X-Request-ID", "").strip() or None,
    )


def _unverified_upload_receipt() -> SourceAuthenticationReceipt:
    # The web route never accepts a caller assertion that source authenticity was
    # independently verified. Stronger source proof must come through a separately
    # validated provider path and can never be manufactured by an upload request.
    return SourceAuthenticationReceipt(
        state="UNVERIFIED",
        scheme="AUTHORIZED_UPLOAD",
        provider="causledger-assisted-intake",
    )


def _result_body(captured, *, evidence_role: str | None = None) -> dict[str, Any]:
    metadata = dict(captured.evidence.metadata or {})
    return {
        "evidence_id": captured.evidence.evidence_id,
        "tenant_id": captured.evidence.tenant_id,
        "evidence_role": evidence_role,
        "source_type": captured.evidence.source_type,
        "source_ref": captured.evidence.source_ref,
        "received_at": captured.evidence.received_at,
        "content_sha256": captured.evidence.content_hash,
        "content_sha512": metadata.get("content_sha512"),
        "byte_length": metadata.get("content_size_bytes"),
        "capture_mode": metadata.get("capture_mode"),
        "source_authentication": metadata.get("source_authentication"),
        "immutability": metadata.get("immutability"),
        "exact_version_readback_verified": metadata.get("original_version_readback_verified") is True,
        "raw_content_persisted": str(metadata.get("raw_content_persisted") or "").lower() == "true",
        "raw_content_returned": False,
        "recoverability_established": False,
        "source_authenticity_established": False,
    }


def create_secure_intake_blueprint(
    *,
    capture_registry: SecureCaptureRegistry,
    outcome_registry: SecureOutcomeRegistry,
    capture_identity: IdentityResolver,
    original_store: OriginalEvidenceStore | None,
) -> Blueprint:
    blueprint = Blueprint("causledger_secure_intake", __name__)

    @blueprint.post("/secure-evidence/capture")
    def capture_case_original():
        tenant_id, actor_id = capture_identity()
        try:
            if original_store is None:
                raise SecureIntakeWebError("secure intake immutable original store is not configured")
            payload = _json_object()
            authorization_raw = _authorization_object(payload)
            content, content_type = _strict_original(payload)
            role = _required_text(payload.get("evidence_role"), label="evidence_role", maximum=64).lower()
            evidence_id = _required_text(payload.get("evidence_id"), label="evidence_id", maximum=2048)
            source_ref = _required_text(payload.get("source_ref"), label="source_ref", maximum=2048)
            case_ref = _required_text(authorization_raw.get("case_ref"), label="case_ref", maximum=512)
            raw_roles = authorization_raw.get("evidence_roles")
            if not isinstance(raw_roles, list):
                raise SecureIntakeWebError("authorization evidence_roles must be a list")
            purpose = str(authorization_raw.get("purpose") or BOUNDED_RAPID_SCAN_PURPOSE).strip().upper()
            max_bytes = authorization_raw.get("max_bytes_per_evidence", MAX_ROUTE_ORIGINAL_BYTES)
            authorization = IntakeAuthorization(
                authorization_id=_required_text(authorization_raw.get("authorization_id"), label="authorization_id", maximum=256),
                tenant_id=tenant_id,
                case_ref=case_ref,
                authorized_by_ref=_required_text(authorization_raw.get("authorized_by_ref"), label="authorized_by_ref", maximum=512),
                authorized_at=_required_text(authorization_raw.get("authorized_at"), label="authorized_at", maximum=128),
                expires_at=_required_text(authorization_raw.get("expires_at"), label="expires_at", maximum=128),
                minimum_immutable_retention_until=_required_text(
                    authorization_raw.get("minimum_immutable_retention_until"),
                    label="minimum_immutable_retention_until",
                    maximum=128,
                ),
                transfer_channel_ref=_required_text(
                    authorization_raw.get("transfer_channel_ref"),
                    label="transfer_channel_ref",
                    maximum=1024,
                ),
                evidence_roles=tuple(str(item) for item in raw_roles),
                data_terms_state=_required_text(authorization_raw.get("data_terms_state"), label="data_terms_state", maximum=64),
                immutable_retention_acknowledged=authorization_raw.get("immutable_retention_acknowledged") is True,
                purpose=purpose,
                max_bytes_per_evidence=max_bytes,
            )
            captured = capture_authorized_original_evidence(
                authorization=authorization,
                evidence_role=role,
                original_store=original_store,
                evidence_id=evidence_id,
                identity=_capture_identity(tenant_id, actor_id),
                source_ref=source_ref,
                content=content,
                content_type=content_type,
                source_authentication=_unverified_upload_receipt(),
                effective_at=str(payload.get("effective_at") or "").strip() or None,
            )
            capture_registry.record(
                evidence=captured.evidence,
                evidence_role=role,
                captured_by=actor_id,
            )
            return jsonify(_result_body(captured, evidence_role=role)), 201
        except (SecureIntakeWebError, ValueError, SecureCaptureRegistryError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.post("/findings/<path:finding_id>/secure-outcome-evidence/capture")
    def capture_outcome_original(finding_id: str):
        tenant_id, actor_id = capture_identity()
        try:
            if original_store is None:
                raise SecureIntakeWebError("secure intake immutable original store is not configured")
            payload = _json_object()
            authorization_raw = _authorization_object(payload)
            content, content_type = _strict_original(payload)
            evidence_id = _required_text(payload.get("evidence_id"), label="evidence_id", maximum=2048)
            source_ref = _required_text(payload.get("source_ref"), label="source_ref", maximum=2048)
            purpose = str(authorization_raw.get("purpose") or DOCUMENTED_FINAL_OUTCOME_PURPOSE).strip().upper()
            max_bytes = authorization_raw.get("max_bytes", MAX_ROUTE_ORIGINAL_BYTES)
            authorization = OutcomeEvidenceAuthorization(
                authorization_id=_required_text(authorization_raw.get("authorization_id"), label="authorization_id", maximum=256),
                tenant_id=tenant_id,
                finding_id=finding_id,
                authorized_by_ref=_required_text(authorization_raw.get("authorized_by_ref"), label="authorized_by_ref", maximum=512),
                authorized_at=_required_text(authorization_raw.get("authorized_at"), label="authorized_at", maximum=128),
                expires_at=_required_text(authorization_raw.get("expires_at"), label="expires_at", maximum=128),
                minimum_immutable_retention_until=_required_text(
                    authorization_raw.get("minimum_immutable_retention_until"),
                    label="minimum_immutable_retention_until",
                    maximum=128,
                ),
                transfer_channel_ref=_required_text(
                    authorization_raw.get("transfer_channel_ref"),
                    label="transfer_channel_ref",
                    maximum=1024,
                ),
                data_terms_state=_required_text(authorization_raw.get("data_terms_state"), label="data_terms_state", maximum=64),
                immutable_retention_acknowledged=authorization_raw.get("immutable_retention_acknowledged") is True,
                purpose=purpose,
                max_bytes=max_bytes,
            )
            captured = capture_authorized_outcome_evidence(
                authorization=authorization,
                original_store=original_store,
                evidence_id=evidence_id,
                identity=_capture_identity(tenant_id, actor_id),
                source_ref=source_ref,
                content=content,
                content_type=content_type,
                source_authentication=_unverified_upload_receipt(),
                effective_at=str(payload.get("effective_at") or "").strip() or None,
            )
            outcome_registry.record(evidence=captured.evidence, captured_by=actor_id)
            return jsonify(_result_body(captured)), 201
        except (SecureIntakeWebError, ValueError, SecureOutcomeRegistryError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    return blueprint
