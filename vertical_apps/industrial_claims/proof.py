from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

PROOF_SCHEMA_VERSION = 2
EVIDENCE_STATE_ORDER = (
    "UNVERIFIED",
    "SOURCE_AUTHENTICATED",
    "INTEGRITY_SEALED",
    "TIME_SEALED",
    "CORROBORATED",
    "HUMAN_REVIEWED",
    "COUNTERPARTY_ACKNOWLEDGED",
    "QUALIFIED_SEALED",
)
_EXTERNAL_KINDS = {
    "QUALIFIED_TIMESTAMP",
    "QUALIFIED_SEAL",
    "QUALIFIED_SIGNATURE",
    "WORM_LOCK",
    "PUBLIC_ANCHOR",
    "EVIDENCE_ESCROW",
    "COUNTERPARTY_ACKNOWLEDGEMENT",
}
_VERIFIED_EXTERNAL_STATES = {"VERIFIED", "VALID"}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    payload = value if isinstance(value, (bytes, bytearray, memoryview)) else canonical_json_bytes(value)
    return hashlib.sha256(bytes(payload)).hexdigest()


def sha512_hex(value: Any) -> str:
    payload = value if isinstance(value, (bytes, bytearray, memoryview)) else canonical_json_bytes(value)
    return hashlib.sha512(bytes(payload)).hexdigest()


def _valid_hex_digest(value: object, *, size: int) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == size and all(char in "0123456789abcdef" for char in text)


def merkle_root_sha256(leaves: Iterable[str]) -> str | None:
    """Return a domain-separated SHA-256 Merkle root for hex SHA-256 leaves."""
    values = [str(item).strip().lower() for item in leaves]
    if not values:
        return None
    if any(not _valid_hex_digest(item, size=64) for item in values):
        raise ValueError("Merkle leaves must be SHA-256 hex digests")
    level = [hashlib.sha256(b"\x00" + bytes.fromhex(item)).digest() for item in values]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256(b"\x01" + level[index] + level[index + 1]).digest()
            for index in range(0, len(level), 2)
        ]
    return level[0].hex()


@dataclass(frozen=True)
class ExternalAttestation:
    kind: str
    provider: str
    state: str
    digest_algorithm: str
    digest: str
    provider_ref: str | None = None
    issued_at: str | None = None
    validation_ref: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in _EXTERNAL_KINDS:
            raise ValueError("unsupported proof attestation kind")
        if not str(self.provider).strip() or not str(self.state).strip():
            raise ValueError("proof attestation provider and state are required")
        algorithm = self.digest_algorithm.upper()
        if algorithm not in {"SHA-256", "SHA-512"}:
            raise ValueError("unsupported proof attestation digest algorithm")
        expected = 64 if algorithm == "SHA-256" else 128
        if not _valid_hex_digest(self.digest, size=expected):
            raise ValueError("proof attestation digest is invalid")
        if self.state.upper() in _VERIFIED_EXTERNAL_STATES and not self.provider_ref:
            raise ValueError("verified proof attestation requires provider reference")

    @property
    def verified(self) -> bool:
        return self.state.upper() in _VERIFIED_EXTERNAL_STATES

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "provider": self.provider,
            "state": self.state,
            "digest_algorithm": self.digest_algorithm.upper(),
            "digest": self.digest.lower(),
            "provider_ref": self.provider_ref,
            "issued_at": self.issued_at,
            "validation_ref": self.validation_ref,
            "details": dict(self.details),
        }


def _metadata_bool(metadata: Mapping[str, Any], key: str) -> bool:
    value = metadata.get(key)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "verified", "valid"}


def _metadata_state(metadata: Mapping[str, Any], key: str) -> str:
    return str(metadata.get(key) or "").strip().upper()


def evidence_assurance_state(
    metadata: Mapping[str, Any],
    *,
    content_hash_present: bool,
    attestations: Sequence[ExternalAttestation] = (),
) -> tuple[str, dict[str, Any]]:
    """Compute the highest strictly supported state without turning hashes into truth claims."""
    source_authenticated = _metadata_state(metadata, "source_authentication") in {
        "VERIFIED",
        "DKIM_VALID",
        "API_VERIFIED",
        "SIGNATURE_VALID",
        "DIRECT_SOURCE_CAPTURE",
    }
    evidence_worm_attested = any(item.kind == "WORM_LOCK" and item.verified for item in attestations)
    original_immutability_verified = content_hash_present and (
        _metadata_bool(metadata, "worm_lock_verified") or evidence_worm_attested
    )
    integrity_sealed = content_hash_present and (
        _metadata_bool(metadata, "proof_integrity_sealed")
        or original_immutability_verified
    )
    time_sealed = integrity_sealed and (
        _metadata_state(metadata, "time_attestation") in {"RFC3161_VALID", "QUALIFIED_TIMESTAMP_VALID"}
        or any(item.kind == "QUALIFIED_TIMESTAMP" and item.verified for item in attestations)
    )
    corroborated = time_sealed and _metadata_bool(metadata, "corroborated")
    human_reviewed = corroborated and _metadata_bool(metadata, "human_reviewed")
    counterparty_acknowledged = human_reviewed and (
        _metadata_bool(metadata, "counterparty_acknowledged")
        or any(item.kind == "COUNTERPARTY_ACKNOWLEDGEMENT" and item.verified for item in attestations)
    )
    qualified_sealed = counterparty_acknowledged and any(
        item.kind in {"QUALIFIED_SEAL", "QUALIFIED_SIGNATURE"} and item.verified
        for item in attestations
    )

    if qualified_sealed:
        state = "QUALIFIED_SEALED"
    elif counterparty_acknowledged:
        state = "COUNTERPARTY_ACKNOWLEDGED"
    elif human_reviewed:
        state = "HUMAN_REVIEWED"
    elif corroborated:
        state = "CORROBORATED"
    elif time_sealed:
        state = "TIME_SEALED"
    elif integrity_sealed:
        state = "INTEGRITY_SEALED"
    elif source_authenticated:
        state = "SOURCE_AUTHENTICATED"
    else:
        state = "UNVERIFIED"

    dimensions = {
        "content_hash_present": bool(content_hash_present),
        "source_authenticated": source_authenticated,
        "integrity_sealed": integrity_sealed,
        "original_immutability_verified": original_immutability_verified,
        "time_sealed": time_sealed,
        "corroborated": corroborated,
        "human_reviewed": human_reviewed,
        "counterparty_acknowledged": counterparty_acknowledged,
        "qualified_sealed": qualified_sealed,
    }
    return state, dimensions


def _evidence_entry(item: Any, attestations: Sequence[ExternalAttestation]) -> dict[str, Any]:
    metadata = dict(getattr(item, "metadata", {}) or {})
    content_hash = str(getattr(item, "content_hash", "") or "").strip().lower()
    if content_hash and not _valid_hex_digest(content_hash, size=64):
        raise ValueError("evidence SHA-256 content hash is invalid")
    sha512 = str(metadata.get("content_sha512") or "").strip().lower() or None
    if sha512 is not None and not _valid_hex_digest(sha512, size=128):
        raise ValueError("evidence SHA-512 content hash is invalid")
    relevant = [
        attestation
        for attestation in attestations
        if str(attestation.details.get("evidence_id") or "") == str(getattr(item, "evidence_id", ""))
    ]
    state, dimensions = evidence_assurance_state(
        metadata,
        content_hash_present=bool(content_hash),
        attestations=relevant,
    )
    return {
        "evidence_id": str(getattr(item, "evidence_id", "")),
        "source_type": str(getattr(item, "source_type", "")),
        "source_ref": str(getattr(item, "source_ref", "")),
        "received_at": str(getattr(item, "received_at", "")),
        "hashes": {
            "sha256": content_hash or None,
            "sha512": sha512,
        },
        "byte_length": metadata.get("content_size_bytes"),
        "raw_content_persisted": _metadata_state(metadata, "raw_content_persisted") == "TRUE",
        "capture_mode": metadata.get("capture_mode", "UNKNOWN"),
        "source_authentication": metadata.get("source_authentication", "UNVERIFIED"),
        "time_attestation": metadata.get("time_attestation", "LOCAL_SERVER_ONLY"),
        "immutability": metadata.get("immutability", "NOT_PROVEN"),
        "assurance_state": state,
        "assurance_dimensions": dimensions,
        "external_attestations": [item.as_dict() for item in relevant],
    }


def _attestation_target(
    *,
    core_package: Mapping[str, Any],
    package_sha256: str,
    package_sha512: str,
    evidence_entries: Sequence[Mapping[str, Any]],
    merkle_root: str | None,
    revision_number: int,
    supersedes_finding_id: str | None,
) -> dict[str, Any]:
    body = {
        "target_version": 1,
        "proof_system": "CausLedger Proof Pack",
        "tenant_id": core_package.get("tenant_id"),
        "finding_id": (core_package.get("finding") or {}).get("finding_id"),
        "revision": {
            "number": revision_number,
            "supersedes_finding_id": supersedes_finding_id,
        },
        "package_sha256": package_sha256,
        "package_sha512": package_sha512,
        "evidence_merkle_root_sha256": merkle_root,
        "evidence_ids": [str(item.get("evidence_id") or "") for item in evidence_entries],
        "evidence_sha256": [str((item.get("hashes") or {}).get("sha256") or "") for item in evidence_entries],
        "truth_boundary": {
            "integrity_target_only": True,
            "does_not_establish_factual_truth": True,
            "does_not_establish_recoverability": True,
        },
    }
    return {"sha256": sha256_hex(body), "body": body}


def _revision_lineage(core_package: Mapping[str, Any]) -> tuple[int, str | None]:
    revision = core_package.get("revision") or {}
    try:
        number = int(revision.get("number", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("proof package revision number is invalid") from exc
    if number < 1:
        raise ValueError("proof package revision number is invalid")
    supersedes = revision.get("supersedes_finding_id")
    return number, str(supersedes) if supersedes else None


def build_proof_manifest(
    core_package: Mapping[str, Any],
    *,
    attestations: Sequence[ExternalAttestation] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a stable proof manifest over the current durable package and evidence lineage."""
    package_sha256 = sha256_hex(core_package)
    package_sha512 = sha512_hex(core_package)
    evidence_items = list(core_package.get("evidence") or [])
    evidence_entries = [_evidence_entry(item, attestations) for item in evidence_items]
    merkle_root = merkle_root_sha256(
        str((item.get("hashes") or {}).get("sha256") or "") for item in evidence_entries
    ) if evidence_entries else None
    revision_number, supersedes = _revision_lineage(core_package)
    target = _attestation_target(
        core_package=core_package,
        package_sha256=package_sha256,
        package_sha512=package_sha512,
        evidence_entries=evidence_entries,
        merkle_root=merkle_root,
        revision_number=revision_number,
        supersedes_finding_id=supersedes,
    )
    target_sha = target["sha256"]
    for attestation in attestations:
        if attestation.verified and attestation.kind != "WORM_LOCK" and attestation.digest.lower() != target_sha:
            raise ValueError("verified external proof attestation is not bound to current stable proof target")

    return {
        "proof_schema_version": PROOF_SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "package_hashes": {"sha256": package_sha256, "sha512": package_sha512},
        "evidence": evidence_entries,
        "evidence_merkle_root_sha256": merkle_root,
        "dual_hash_coverage": {
            "sha256": bool(evidence_entries) and all(bool((item.get("hashes") or {}).get("sha256")) for item in evidence_entries),
            "sha512": bool(evidence_entries) and all(bool((item.get("hashes") or {}).get("sha512")) for item in evidence_entries),
        },
        "attestation_target": target,
        "external_attestations": [item.as_dict() for item in attestations],
        "truth_boundary": {
            "hashes_prove_integrity_not_truth": True,
            "cryptographic_proof_does_not_establish_customer_responsibility": True,
            "cryptographic_proof_does_not_establish_legal_recoverability": True,
            "human_review_remains_required": True,
        },
    }


def verify_proof_manifest(core_package: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Independently recompute package/evidence/Merkle/target integrity."""
    errors: list[str] = []
    if str((manifest.get("package_hashes") or {}).get("sha256") or "") != sha256_hex(core_package):
        errors.append("PACKAGE_SHA256_MISMATCH")
    if str((manifest.get("package_hashes") or {}).get("sha512") or "") != sha512_hex(core_package):
        errors.append("PACKAGE_SHA512_MISMATCH")

    evidence_entries = list(manifest.get("evidence") or [])
    expected_merkle = merkle_root_sha256(
        str((item.get("hashes") or {}).get("sha256") or "") for item in evidence_entries
    ) if evidence_entries else None
    if manifest.get("evidence_merkle_root_sha256") != expected_merkle:
        errors.append("EVIDENCE_MERKLE_ROOT_MISMATCH")

    package_sha256 = sha256_hex(core_package)
    package_sha512 = sha512_hex(core_package)
    revision_number, supersedes = _revision_lineage(core_package)
    expected_target = _attestation_target(
        core_package=core_package,
        package_sha256=package_sha256,
        package_sha512=package_sha512,
        evidence_entries=evidence_entries,
        merkle_root=expected_merkle,
        revision_number=revision_number,
        supersedes_finding_id=supersedes,
    )
    if manifest.get("attestation_target") != expected_target:
        errors.append("ATTESTATION_TARGET_MISMATCH")

    return {
        "valid": not errors,
        "errors": errors,
        "package_sha256": package_sha256,
        "evidence_merkle_root_sha256": expected_merkle,
        "attestation_target_sha256": expected_target["sha256"],
    }
