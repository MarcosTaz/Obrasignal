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
    integrity_sealed = content_hash_present and (
        _metadata_bool(metadata, "proof_integrity_sealed")
        or _metadata_state(metadata, "immutability") in {"WORM_LOCKED", "IMMUTABLE_VERIFIED"}
        or any(item.kind == "WORM_LOCK" and item.verified for item in attestations)
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
    return {
        "algorithm": "CANONICAL_JSON_V1",
        "body": body,
        "sha256": sha256_hex(body),
        "sha512": sha512_hex(body),
    }


def _attestation_matches_target(attestation: ExternalAttestation, target: Mapping[str, Any]) -> bool:
    expected = target.get("sha256") if attestation.digest_algorithm.upper() == "SHA-256" else target.get("sha512")
    return str(attestation.digest).lower() == str(expected or "").lower()


def build_proof_manifest(
    *,
    core_package: Mapping[str, Any],
    evidence: Sequence[Any],
    revision_number: int,
    supersedes_finding_id: str | None,
    attestations: Sequence[ExternalAttestation] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    if not evidence:
        raise ValueError("proof manifest requires evidence")
    generated = generated_at or datetime.now(timezone.utc).isoformat()
    evidence_entries = [_evidence_entry(item, attestations) for item in evidence]
    sha256_leaves = [entry["hashes"]["sha256"] for entry in evidence_entries if entry["hashes"]["sha256"]]
    sha512_complete = all(entry["hashes"]["sha512"] for entry in evidence_entries)
    package_bytes = canonical_json_bytes(core_package)
    package_sha256 = hashlib.sha256(package_bytes).hexdigest()
    package_sha512 = hashlib.sha512(package_bytes).hexdigest()
    merkle_root = merkle_root_sha256(sha256_leaves)
    attestation_target = _attestation_target(
        core_package=core_package,
        package_sha256=package_sha256,
        package_sha512=package_sha512,
        evidence_entries=evidence_entries,
        merkle_root=merkle_root,
        revision_number=revision_number,
        supersedes_finding_id=supersedes_finding_id,
    )
    global_attestations = [item for item in attestations if not item.details.get("evidence_id")]
    for item in global_attestations:
        if item.verified and not _attestation_matches_target(item, attestation_target):
            raise ValueError("verified external attestation does not match stable CausLedger proof target")
    external = [item.as_dict() for item in global_attestations]
    strongest_state = max(
        (entry["assurance_state"] for entry in evidence_entries),
        key=lambda state: EVIDENCE_STATE_ORDER.index(state),
    )
    weakest_state = min(
        (entry["assurance_state"] for entry in evidence_entries),
        key=lambda state: EVIDENCE_STATE_ORDER.index(state),
    )
    manifest_body = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "proof_system": "CausLedger Proof Pack",
        "generated_at": generated,
        "tenant_id": core_package.get("tenant_id"),
        "finding_id": (core_package.get("finding") or {}).get("finding_id"),
        "revision": {
            "number": revision_number,
            "supersedes_finding_id": supersedes_finding_id,
        },
        "package_hashes": {
            "sha256": package_sha256,
            "sha512": package_sha512,
            "canonicalization": "JCS-LIKE_SORTED_UTF8_V1",
        },
        "evidence": evidence_entries,
        "evidence_merkle": {
            "algorithm": "SHA-256",
            "leaf_count": len(sha256_leaves),
            "root": merkle_root,
            "leaf_order": [entry["evidence_id"] for entry in evidence_entries if entry["hashes"]["sha256"]],
        },
        "attestation_target": attestation_target,
        "dual_hash_coverage": {
            "sha256": len(sha256_leaves) == len(evidence_entries),
            "sha512": sha512_complete,
        },
        "chronology": {
            "server_received_at_preserved": all(bool(entry["received_at"]) for entry in evidence_entries),
            "effective_time_is_distinct_from_first_seen_time": True,
            "backdating_policy": "DECLARED_EFFECTIVE_TIME_NEVER_REPLACES_SERVER_FIRST_SEEN_TIME",
        },
        "assurance_summary": {
            "strongest_evidence_state": strongest_state,
            "weakest_evidence_state": weakest_state,
            "original_bytes_reverification_available": all(entry["raw_content_persisted"] for entry in evidence_entries),
            "cryptographic_integrity_is_not_factual_truth": True,
            "recoverability_established_by_proof_system": False,
            "legal_conclusion": None,
        },
        "external_attestations": external,
        "required_external_gates": {
            "qualified_timestamp": not any(item.kind == "QUALIFIED_TIMESTAMP" and item.verified and _attestation_matches_target(item, attestation_target) for item in global_attestations),
            "qualified_seal": not any(item.kind == "QUALIFIED_SEAL" and item.verified and _attestation_matches_target(item, attestation_target) for item in global_attestations),
            "worm_lock": not any(item.kind == "WORM_LOCK" and item.verified and _attestation_matches_target(item, attestation_target) for item in global_attestations),
            "public_anchor": not any(item.kind == "PUBLIC_ANCHOR" and item.verified and _attestation_matches_target(item, attestation_target) for item in global_attestations),
            "evidence_escrow": not any(item.kind == "EVIDENCE_ESCROW" and item.verified and _attestation_matches_target(item, attestation_target) for item in global_attestations),
        },
        "verification_policy": {
            "fail_closed": True,
            "no_claim_is_valid_outcome": True,
            "no_external_attestation_may_be_marked_valid_without_provider_reference": True,
            "external_attestations_bind_to_stable_target_not_recursive_manifest_hash": True,
            "supersession_never_deletes_prior_proof": True,
            "contradictory_evidence_must_be_preserved": True,
        },
    }
    manifest_body["manifest_hashes"] = {
        "sha256": sha256_hex(manifest_body),
        "sha512": sha512_hex(manifest_body),
    }
    return manifest_body


def verify_proof_manifest(core_package: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    package_hashes = manifest.get("package_hashes") or {}
    expected256 = sha256_hex(core_package)
    expected512 = sha512_hex(core_package)
    if package_hashes.get("sha256") != expected256:
        errors.append("PACKAGE_SHA256_MISMATCH")
    if package_hashes.get("sha512") != expected512:
        errors.append("PACKAGE_SHA512_MISMATCH")

    evidence = list(manifest.get("evidence") or [])
    leaves = [str((item.get("hashes") or {}).get("sha256") or "") for item in evidence]
    expected_root: str | None = None
    if any(not _valid_hex_digest(item, size=64) for item in leaves):
        errors.append("EVIDENCE_SHA256_INVALID")
    else:
        expected_root = merkle_root_sha256(leaves)
        if (manifest.get("evidence_merkle") or {}).get("root") != expected_root:
            errors.append("EVIDENCE_MERKLE_ROOT_MISMATCH")

    revision = manifest.get("revision") or {}
    expected_target = _attestation_target(
        core_package=core_package,
        package_sha256=expected256,
        package_sha512=expected512,
        evidence_entries=evidence,
        merkle_root=expected_root,
        revision_number=int(revision.get("number") or 0),
        supersedes_finding_id=revision.get("supersedes_finding_id"),
    )
    stored_target = manifest.get("attestation_target") or {}
    if stored_target.get("sha256") != expected_target["sha256"] or stored_target.get("sha512") != expected_target["sha512"]:
        errors.append("ATTESTATION_TARGET_MISMATCH")
    for index, item in enumerate(manifest.get("external_attestations") or []):
        state = str(item.get("state") or "").upper()
        if state not in _VERIFIED_EXTERNAL_STATES:
            continue
        algorithm = str(item.get("digest_algorithm") or "").upper()
        expected_digest = expected_target["sha256"] if algorithm == "SHA-256" else expected_target["sha512"] if algorithm == "SHA-512" else None
        if expected_digest is None or str(item.get("digest") or "").lower() != expected_digest:
            errors.append(f"EXTERNAL_ATTESTATION_{index}_TARGET_MISMATCH")
        if not str(item.get("provider_ref") or "").strip():
            errors.append(f"EXTERNAL_ATTESTATION_{index}_PROVIDER_REF_MISSING")

    stored_manifest_hashes = manifest.get("manifest_hashes") or {}
    body = dict(manifest)
    body.pop("manifest_hashes", None)
    if stored_manifest_hashes.get("sha256") != sha256_hex(body):
        errors.append("MANIFEST_SHA256_MISMATCH")
    if stored_manifest_hashes.get("sha512") != sha512_hex(body):
        errors.append("MANIFEST_SHA512_MISMATCH")

    if not (manifest.get("assurance_summary") or {}).get("original_bytes_reverification_available"):
        warnings.append("ORIGINAL_BYTES_NOT_INCLUDED_OR_NOT_IMMUTABLY_PERSISTED")
    if any(bool(value) for value in (manifest.get("required_external_gates") or {}).values()):
        warnings.append("ONE_OR_MORE_EXTERNAL_PROOF_GATES_UNSATISFIED")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "package_sha256": expected256,
        "package_sha512": expected512,
        "attestation_target_sha256": expected_target["sha256"],
        "attestation_target_sha512": expected_target["sha512"],
    }
