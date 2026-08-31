from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from typing import Any, Mapping

from vertical_apps.industrial_claims.proof import sha256_hex
from vertical_apps.industrial_claims.proof_readiness import evaluate_proof_strength


_VERIFICATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{24,128}$")
_ALLOWED_STATES = {"CURRENT", "SUPERSEDED", "WITHDRAWN"}
_FORBIDDEN_PUBLIC_KEYS = {
    "tenant_id",
    "finding_id",
    "subject_ref",
    "customer_ref",
    "program_ref",
    "event_ref",
    "source_ref",
    "evidence_id",
    "actor_id",
    "reviewer",
    "decision_reason",
    "net_potential",
    "currency",
    "inputs",
    "outcomes",
    "audit_events",
    "original_object_ref",
    "original_provider_receipt_ref",
}


class PublicVerificationError(RuntimeError):
    pass


def new_verification_id() -> str:
    return secrets.token_urlsafe(24)


def _verification_id(value: object) -> str:
    text = str(value or "").strip()
    if not _VERIFICATION_ID_RE.fullmatch(text):
        raise PublicVerificationError("public verification id must be an opaque high-entropy URL-safe token")
    return text


def _iso(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PublicVerificationError("invalid public receipt issued_at") from exc
    if parsed.tzinfo is None:
        raise PublicVerificationError("public receipt issued_at must include timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _assert_public_shape(value: Any, *, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in _FORBIDDEN_PUBLIC_KEYS:
                location = ".".join((*path, key_text))
                raise PublicVerificationError(f"private field forbidden in public receipt: {location}")
            _assert_public_shape(item, path=(*path, key_text))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_public_shape(item, path=(*path, str(index)))


def build_public_receipt(
    proof_pack: Mapping[str, Any],
    *,
    verification_id: str,
    state: str = "CURRENT",
    issued_at: str | None = None,
    superseded_by: str | None = None,
) -> dict[str, Any]:
    token = _verification_id(verification_id)
    lifecycle = str(state or "").strip().upper()
    if lifecycle not in _ALLOWED_STATES:
        raise PublicVerificationError("invalid public verification lifecycle state")
    if lifecycle == "SUPERSEDED":
        if not superseded_by:
            raise PublicVerificationError("superseded public receipt requires successor verification id")
        successor = _verification_id(superseded_by)
        if successor == token:
            raise PublicVerificationError("public receipt cannot supersede itself")
    elif superseded_by is not None:
        raise PublicVerificationError("successor verification id is only valid for SUPERSEDED state")
    else:
        successor = None

    manifest = proof_pack.get("proof_manifest") or {}
    verification = proof_pack.get("self_verification") or {}
    if verification.get("valid") is not True:
        raise PublicVerificationError("only a self-verified Proof Pack may produce a public receipt")
    manifest_hashes = manifest.get("manifest_hashes") or {}
    target = manifest.get("attestation_target") or {}
    merkle = manifest.get("evidence_merkle") or {}
    required_external = manifest.get("required_external_gates") or {}
    if not manifest_hashes.get("sha256") or not target.get("sha256"):
        raise PublicVerificationError("proof manifest is missing public verification digests")

    strength = evaluate_proof_strength(manifest)
    body = {
        "schema_version": 1,
        "proof_system": "CausLedger Public Verification Receipt",
        "verification_id": token,
        "lifecycle": {
            "state": lifecycle,
            "superseded_by": successor,
        },
        "issued_at": _iso(issued_at),
        "proof": {
            "manifest_sha256": manifest_hashes.get("sha256"),
            "manifest_sha512": manifest_hashes.get("sha512"),
            "attestation_target_sha256": target.get("sha256"),
            "attestation_target_sha512": target.get("sha512"),
            "evidence_merkle_root_sha256": merkle.get("root"),
            "evidence_leaf_count": merkle.get("leaf_count"),
            "proof_strength": strength["level"],
            "external_gates_satisfied": {
                str(name): not bool(missing)
                for name, missing in sorted(required_external.items())
            },
        },
        "verification": {
            "proof_pack_self_verified": True,
            "external_verification_required": bool(proof_pack.get("external_verification_required")),
            "public_receipt_contains_customer_or_case_identifiers": False,
            "public_receipt_contains_document_content": False,
            "public_receipt_contains_economic_amounts": False,
        },
        "truth_boundary": {
            "integrity_verification_is_not_factual_truth": True,
            "commercial_responsibility_not_determined": True,
            "legal_recoverability_not_determined": True,
        },
    }
    _assert_public_shape(body)
    return {**body, "receipt_sha256": sha256_hex(body)}


def verify_public_receipt(proof_pack: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        _assert_public_shape(receipt)
        token = _verification_id(receipt.get("verification_id"))
    except PublicVerificationError as exc:
        return {"valid": False, "errors": [str(exc)]}

    body = dict(receipt)
    stored_hash = str(body.pop("receipt_sha256", ""))
    if stored_hash != sha256_hex(body):
        errors.append("PUBLIC_RECEIPT_HASH_MISMATCH")

    lifecycle = receipt.get("lifecycle") or {}
    try:
        expected = build_public_receipt(
            proof_pack,
            verification_id=token,
            state=str(lifecycle.get("state") or ""),
            issued_at=str(receipt.get("issued_at") or ""),
            superseded_by=lifecycle.get("superseded_by"),
        )
    except PublicVerificationError as exc:
        errors.append(str(exc))
    else:
        for key in ("proof", "verification", "truth_boundary"):
            if receipt.get(key) != expected.get(key):
                errors.append(f"PUBLIC_RECEIPT_{key.upper()}_MISMATCH")

    return {
        "valid": not errors,
        "errors": errors,
        "verification_id": token,
        "lifecycle_state": lifecycle.get("state"),
    }
