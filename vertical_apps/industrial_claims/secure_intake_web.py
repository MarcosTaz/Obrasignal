from __future__ import annotations

import base64
import binascii
import hashlib
import os
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, jsonify, request

from factory_cloud.assurance_ops import AssuranceOperationError
from factory_cloud.assurance_store import AssuranceStoreError
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
from vertical_apps.industrial_claims.production_trust_gate import (
    ProductionTrustGate,
    ProductionTrustGateError,
)
from vertical_apps.industrial_claims.proof_storage import OriginalEvidenceStore
from vertical_apps.industrial_claims.secure_capture import CaptureIdentity, SourceAuthenticationReceipt
from vertical_apps.industrial_claims.secure_capture_registry import SecureCaptureRegistry, SecureCaptureRegistryError
from vertical_apps.industrial_claims.secure_outcome_registry import SecureOutcomeRegistry, SecureOutcomeRegistryError


class SecureIntakeWebError(ValueError):
    pass


IdentityResolver = Callable[[], tuple[str, str]]
ClaimsResolver = Callable[[], Mapping[str, object]]
MAX_ROUTE_ORIGINAL_BYTES = 2_000_000
_COMMON_AUTHORIZATION_KEYS = {
    "authorization_id", "authorized_by_ref", "authorized_at", "expires_at",
    "minimum_immutable_retention_until", "transfer_channel_ref", "data_terms_state",
    "immutable_retention_acknowledged", "purpose",
}
_CASE_AUTHORIZATION_KEYS = _COMMON_AUTHORIZATION_KEYS | {"case_ref", "evidence_roles", "max_bytes_per_evidence"}
_OUTCOME_AUTHORIZATION_KEYS = _COMMON_AUTHORIZATION_KEYS | {"max_bytes"}


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


def _authorization_object(payload: Mapping[str, Any], *, allowed_keys: set[str]) -> dict[str, Any]:
    raw = payload.get("authorization")
    if not isinstance(raw, dict):
        raise SecureIntakeWebError("authorization must be an object")
    unknown = set(raw) - allowed_keys
    if unknown:
        raise SecureIntakeWebError("authorization contains unsupported fields for this capture route")
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


def _positive_byte_limit(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not (1 <= value <= 100_000_000):
        raise SecureIntakeWebError(f"{label} must be an integer byte limit")
    return value


def _normalized_effective_at(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SecureIntakeWebError("invalid effective_at") from exc
    if parsed.tzinfo is None:
        raise SecureIntakeWebError("effective_at must include timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _capture_identity(tenant_id: str, actor_id: str) -> CaptureIdentity:
    return CaptureIdentity(tenant_id=tenant_id, actor_id=actor_id, subject=actor_id, amr=(), request_ref=request.headers.get("X-Request-ID", "").strip() or None)


def _unverified_upload_receipt() -> SourceAuthenticationReceipt:
    return SourceAuthenticationReceipt(state="UNVERIFIED", scheme="AUTHORIZED_UPLOAD", provider="certactum-assisted-intake")


def _result_body(evidence, *, evidence_role: str | None = None, idempotent_replay: bool) -> dict[str, Any]:
    metadata = dict(evidence.metadata or {})
    return {
        "evidence_id": evidence.evidence_id, "tenant_id": evidence.tenant_id, "evidence_role": evidence_role,
        "source_type": evidence.source_type, "source_ref": evidence.source_ref, "received_at": evidence.received_at,
        "content_sha256": evidence.content_hash, "content_sha512": metadata.get("content_sha512"),
        "byte_length": metadata.get("content_size_bytes"), "capture_mode": metadata.get("capture_mode"),
        "source_authentication": metadata.get("source_authentication"), "immutability": metadata.get("immutability"),
        "exact_version_readback_verified": metadata.get("original_version_readback_verified") is True,
        "raw_content_persisted": str(metadata.get("raw_content_persisted") or "").lower() == "true",
        "raw_content_returned": False, "idempotent_replay": idempotent_replay,
        "recoverability_established": False, "source_authenticity_established": False,
        "authorization_identity_independently_verified": False,
    }


def _same_existing_capture(existing, *, content: bytes, content_type: str, actor_id: str, authorization_scope_sha256: str, scope_metadata_key: str, effective_at: str | None) -> bool:
    metadata = dict(existing.metadata or {})
    return (
        existing.content_hash.lower() == hashlib.sha256(content).hexdigest()
        and str(metadata.get("content_type") or "") == content_type
        and str(metadata.get(scope_metadata_key) or "").strip().lower() == authorization_scope_sha256
        and str(metadata.get("identity_actor_id") or "").strip() == actor_id
        and (str(metadata.get("effective_at") or "").strip() or None) == effective_at
    )


def _require_production_trust(
    *,
    production_trust_gate: ProductionTrustGate | None,
    verified_claims: ClaimsResolver | None,
) -> None:
    """Automatically protect documentary ingress whenever provider auth is live.

    Development/synthetic execution remains testable. In provider-auth production,
    there is no manual "open intake" switch. If the caller did not inject a gate,
    Certactum auto-builds one from protected production configuration. Missing or
    invalid external configuration therefore closes intake rather than downgrading.
    """
    auth_mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").strip().lower()
    if auth_mode != "provider":
        return
    gate = production_trust_gate
    if gate is None:
        from vertical_apps.industrial_claims.production_trust_runtime import configured_production_trust_gate
        gate = configured_production_trust_gate()
    if gate is None or verified_claims is None:
        raise ProductionTrustGateError("real confidential intake blocked: production trust gate is not configured")
    claims = verified_claims()
    if not isinstance(claims, Mapping):
        raise ProductionTrustGateError("real confidential intake blocked: verified JWT claims are unavailable")
    gate.require_ready(verified_claims=claims)


def create_secure_intake_blueprint(
    *,
    capture_registry: SecureCaptureRegistry,
    outcome_registry: SecureOutcomeRegistry,
    capture_identity: IdentityResolver,
    original_store: OriginalEvidenceStore | None,
    service=None,
    production_trust_gate: ProductionTrustGate | None = None,
    verified_claims: ClaimsResolver | None = None,
) -> Blueprint:
    if service is None:
        from vertical_apps.industrial_claims.service import IndustrialClaimsService
        service = IndustrialClaimsService(capture_registry.path)
    blueprint = Blueprint("certactum_secure_intake", __name__)

    @blueprint.post("/secure-evidence/capture")
    def capture_case_original():
        tenant_id, actor_id = capture_identity()
        try:
            _require_production_trust(
                production_trust_gate=production_trust_gate,
                verified_claims=verified_claims,
            )
            if original_store is None:
                raise SecureIntakeWebError("secure intake immutable original store is not configured")
            payload = _json_object(); authorization_raw = _authorization_object(payload, allowed_keys=_CASE_AUTHORIZATION_KEYS)
            content, content_type = _strict_original(payload)
            role = _required_text(payload.get("evidence_role"), label="evidence_role", maximum=64).lower()
            evidence_id = _required_text(payload.get("evidence_id"), label="evidence_id", maximum=2048)
            source_ref = _required_text(payload.get("source_ref"), label="source_ref", maximum=2048)
            effective_at = _normalized_effective_at(payload.get("effective_at"))
            case_ref = _required_text(authorization_raw.get("case_ref"), label="case_ref", maximum=512)
            raw_roles = authorization_raw.get("evidence_roles")
            if not isinstance(raw_roles, list): raise SecureIntakeWebError("authorization evidence_roles must be a list")
            purpose = str(authorization_raw.get("purpose") or BOUNDED_RAPID_SCAN_PURPOSE).strip().upper()
            max_bytes = _positive_byte_limit(authorization_raw.get("max_bytes_per_evidence", MAX_ROUTE_ORIGINAL_BYTES), label="max_bytes_per_evidence")
            authorization = IntakeAuthorization(
                authorization_id=_required_text(authorization_raw.get("authorization_id"), label="authorization_id", maximum=256), tenant_id=tenant_id, case_ref=case_ref,
                authorized_by_ref=_required_text(authorization_raw.get("authorized_by_ref"), label="authorized_by_ref", maximum=512), authorized_at=_required_text(authorization_raw.get("authorized_at"), label="authorized_at", maximum=128),
                expires_at=_required_text(authorization_raw.get("expires_at"), label="expires_at", maximum=128), minimum_immutable_retention_until=_required_text(authorization_raw.get("minimum_immutable_retention_until"), label="minimum_immutable_retention_until", maximum=128),
                transfer_channel_ref=_required_text(authorization_raw.get("transfer_channel_ref"), label="transfer_channel_ref", maximum=1024), evidence_roles=tuple(str(item) for item in raw_roles),
                data_terms_state=_required_text(authorization_raw.get("data_terms_state"), label="data_terms_state", maximum=64), immutable_retention_acknowledged=authorization_raw.get("immutable_retention_acknowledged") is True, purpose=purpose, max_bytes_per_evidence=max_bytes,
            )
            now = datetime.now(timezone.utc); validated = authorization.validated(now=now)
            if len(content) > validated.max_bytes_per_evidence: raise SecureIntakeWebError("evidence exceeds authorized intake byte limit")
            try:
                existing = capture_registry.get(tenant_id=tenant_id, evidence_id=evidence_id, evidence_role=role, source_ref=source_ref)
            except SecureCaptureRegistryError as exc:
                if str(exc) != "tenant-scoped secure-capture envelope not found": raise
            else:
                if not _same_existing_capture(existing, content=content, content_type=content_type, actor_id=actor_id, authorization_scope_sha256=validated.scope_sha256, scope_metadata_key="intake_authorization_scope_sha256", effective_at=effective_at):
                    raise SecureIntakeWebError("immutable secure intake evidence id collision")
                return jsonify(_result_body(existing, evidence_role=role, idempotent_replay=True)), 200
            captured = capture_authorized_original_evidence(authorization=authorization, evidence_role=role, original_store=original_store, evidence_id=evidence_id, identity=_capture_identity(tenant_id, actor_id), source_ref=source_ref, content=content, content_type=content_type, source_authentication=_unverified_upload_receipt(), effective_at=effective_at, clock=lambda: now)
            capture_registry.record(evidence=captured.evidence, evidence_role=role, captured_by=actor_id)
            return jsonify(_result_body(captured.evidence, evidence_role=role, idempotent_replay=False)), 201
        except ProductionTrustGateError as exc:
            return jsonify({"error": "production_trust_not_ready", "message": str(exc)}), 503
        except (SecureIntakeWebError, ValueError, SecureCaptureRegistryError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422

    @blueprint.post("/findings/<path:finding_id>/secure-outcome-evidence/capture")
    def capture_outcome_original(finding_id: str):
        tenant_id, actor_id = capture_identity()
        try:
            _require_production_trust(
                production_trust_gate=production_trust_gate,
                verified_claims=verified_claims,
            )
            if original_store is None: raise SecureIntakeWebError("secure intake immutable original store is not configured")
            payload = _json_object(); authorization_raw = _authorization_object(payload, allowed_keys=_OUTCOME_AUTHORIZATION_KEYS)
            content, content_type = _strict_original(payload)
            evidence_id = _required_text(payload.get("evidence_id"), label="evidence_id", maximum=2048); source_ref = _required_text(payload.get("source_ref"), label="source_ref", maximum=2048)
            effective_at = _normalized_effective_at(payload.get("effective_at"))
            purpose = str(authorization_raw.get("purpose") or DOCUMENTED_FINAL_OUTCOME_PURPOSE).strip().upper()
            max_bytes = _positive_byte_limit(authorization_raw.get("max_bytes", MAX_ROUTE_ORIGINAL_BYTES), label="max_bytes")
            authorization = OutcomeEvidenceAuthorization(
                authorization_id=_required_text(authorization_raw.get("authorization_id"), label="authorization_id", maximum=256), tenant_id=tenant_id, finding_id=finding_id,
                authorized_by_ref=_required_text(authorization_raw.get("authorized_by_ref"), label="authorized_by_ref", maximum=512), authorized_at=_required_text(authorization_raw.get("authorized_at"), label="authorized_at", maximum=128),
                expires_at=_required_text(authorization_raw.get("expires_at"), label="expires_at", maximum=128), minimum_immutable_retention_until=_required_text(authorization_raw.get("minimum_immutable_retention_until"), label="minimum_immutable_retention_until", maximum=128),
                transfer_channel_ref=_required_text(authorization_raw.get("transfer_channel_ref"), label="transfer_channel_ref", maximum=1024), data_terms_state=_required_text(authorization_raw.get("data_terms_state"), label="data_terms_state", maximum=64),
                immutable_retention_acknowledged=authorization_raw.get("immutable_retention_acknowledged") is True, purpose=purpose, max_bytes=max_bytes,
            )
            now = datetime.now(timezone.utc); validated = authorization.validated(now=now)
            if len(content) > validated.max_bytes: raise SecureIntakeWebError("outcome evidence exceeds authorized byte limit")
            service.revision_store.require_current(tenant_id=tenant_id, finding_id=finding_id)
            if service.ops.get_state(tenant_id=tenant_id, finding_id=finding_id) != "ACTIONED": raise SecureIntakeWebError("secure outcome evidence may only be captured for an ACTIONED finding")
            try:
                existing = outcome_registry.get(tenant_id=tenant_id, evidence_id=evidence_id, finding_id=finding_id, source_ref=source_ref)
            except SecureOutcomeRegistryError as exc:
                if str(exc) != "tenant-scoped secure outcome evidence not found": raise
            else:
                if not _same_existing_capture(existing, content=content, content_type=content_type, actor_id=actor_id, authorization_scope_sha256=validated.scope_sha256, scope_metadata_key="outcome_authorization_scope_sha256", effective_at=effective_at):
                    raise SecureIntakeWebError("immutable secure outcome evidence id collision")
                return jsonify(_result_body(existing, idempotent_replay=True)), 200
            captured = capture_authorized_outcome_evidence(authorization=authorization, original_store=original_store, evidence_id=evidence_id, identity=_capture_identity(tenant_id, actor_id), source_ref=source_ref, content=content, content_type=content_type, source_authentication=_unverified_upload_receipt(), effective_at=effective_at, clock=lambda: now)
            outcome_registry.record(evidence=captured.evidence, captured_by=actor_id)
            return jsonify(_result_body(captured.evidence, idempotent_replay=False)), 201
        except ProductionTrustGateError as exc:
            return jsonify({"error": "production_trust_not_ready", "message": str(exc)}), 503
        except (SecureIntakeWebError, ValueError, AssuranceOperationError, AssuranceStoreError, SecureOutcomeRegistryError) as exc:
            return jsonify({"error": type(exc).__name__, "message": str(exc)}), 422
    return blueprint
