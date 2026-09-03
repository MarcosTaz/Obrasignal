from __future__ import annotations

import argparse
import base64
import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from vertical_apps.industrial_claims.proof import verify_proof_manifest


ExternalVerifier = Callable[[Mapping[str, Any], Mapping[str, Any]], bool]
_VERIFIED_STATES = {"VERIFIED", "VALID"}


def _digest_for_algorithm(hashes: Mapping[str, Any], algorithm: str) -> str | None:
    normalized = str(algorithm or "").strip().upper()
    if normalized == "SHA-256":
        return str(hashes.get("sha256") or "").strip().lower() or None
    if normalized == "SHA-512":
        return str(hashes.get("sha512") or "").strip().lower() or None
    return None


def _verified_external_attestations(manifest: Mapping[str, Any]) -> list[tuple[str, str | None, Mapping[str, Any]]]:
    items: list[tuple[str, str | None, Mapping[str, Any]]] = []
    for raw in list(manifest.get("external_attestations") or []):
        if isinstance(raw, Mapping) and str(raw.get("state") or "").strip().upper() in _VERIFIED_STATES:
            items.append(("proof_target", None, raw))
    for evidence in list(manifest.get("evidence") or []):
        if not isinstance(evidence, Mapping):
            continue
        evidence_id = str(evidence.get("evidence_id") or "").strip() or None
        for raw in list(evidence.get("external_attestations") or []):
            if isinstance(raw, Mapping) and str(raw.get("state") or "").strip().upper() in _VERIFIED_STATES:
                items.append(("evidence", evidence_id, raw))
    return items


def _verify_original_bytes(
    manifest: Mapping[str, Any],
    offline_evidence: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    evidence = list(manifest.get("evidence") or [])
    expected_ids: set[str] = set()
    verified_ids: list[str] = []

    for index, item in enumerate(evidence):
        if not isinstance(item, Mapping):
            errors.append(f"EVIDENCE_{index}_STRUCTURE_INVALID")
            continue
        evidence_id = str(item.get("evidence_id") or "").strip()
        if not evidence_id:
            errors.append(f"EVIDENCE_{index}_ID_MISSING")
            continue
        if evidence_id in expected_ids:
            errors.append(f"EVIDENCE_ID_DUPLICATE:{evidence_id}")
            continue
        expected_ids.add(evidence_id)
        supplied = offline_evidence.get(evidence_id)
        if not isinstance(supplied, Mapping):
            errors.append(f"OFFLINE_ORIGINAL_MISSING:{evidence_id}")
            continue
        encoded = supplied.get("content_base64")
        if not isinstance(encoded, str) or not encoded:
            errors.append(f"OFFLINE_ORIGINAL_BASE64_MISSING:{evidence_id}")
            continue
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            errors.append(f"OFFLINE_ORIGINAL_BASE64_INVALID:{evidence_id}:{type(exc).__name__}")
            continue

        hashes = item.get("hashes") or {}
        if not isinstance(hashes, Mapping):
            errors.append(f"OFFLINE_ORIGINAL_HASHES_INVALID:{evidence_id}")
            continue
        expected256 = str(hashes.get("sha256") or "").strip().lower()
        expected512 = str(hashes.get("sha512") or "").strip().lower()
        actual256 = hashlib.sha256(payload).hexdigest()
        actual512 = hashlib.sha512(payload).hexdigest()
        if expected256 != actual256:
            errors.append(f"OFFLINE_ORIGINAL_SHA256_MISMATCH:{evidence_id}")
        if expected512 and expected512 != actual512:
            errors.append(f"OFFLINE_ORIGINAL_SHA512_MISMATCH:{evidence_id}")
        byte_length = item.get("byte_length")
        if byte_length is not None:
            try:
                if int(byte_length) != len(payload):
                    errors.append(f"OFFLINE_ORIGINAL_LENGTH_MISMATCH:{evidence_id}")
            except (TypeError, ValueError):
                errors.append(f"OFFLINE_ORIGINAL_LENGTH_INVALID:{evidence_id}")
        if not any(error.endswith(f":{evidence_id}") for error in errors):
            verified_ids.append(evidence_id)

    for supplied_id in offline_evidence:
        if str(supplied_id) not in expected_ids:
            errors.append(f"OFFLINE_EVIDENCE_UNKNOWN_ID:{supplied_id}")

    return errors, {
        "expected_count": len(expected_ids),
        "supplied_count": sum(1 for evidence_id in expected_ids if isinstance(offline_evidence.get(evidence_id), Mapping)),
        "verified_count": len(verified_ids),
        "verified_evidence_ids": sorted(verified_ids),
        "complete": bool(expected_ids) and len(verified_ids) == len(expected_ids),
    }


def _verify_external_attestations(
    manifest: Mapping[str, Any],
    verifiers: Mapping[str, ExternalVerifier],
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    verified = _verified_external_attestations(manifest)
    checked = 0
    target = manifest.get("attestation_target") or {}
    evidence_by_id = {
        str(item.get("evidence_id") or "").strip(): item
        for item in list(manifest.get("evidence") or [])
        if isinstance(item, Mapping) and str(item.get("evidence_id") or "").strip()
    }

    for index, (scope, evidence_id, attestation) in enumerate(verified):
        kind = str(attestation.get("kind") or "").strip()
        provider = str(attestation.get("provider") or "").strip()
        provider_ref = str(attestation.get("provider_ref") or "").strip()
        algorithm = str(attestation.get("digest_algorithm") or "").strip().upper()
        digest = str(attestation.get("digest") or "").strip().lower()
        details = attestation.get("details") or {}
        if not isinstance(details, Mapping):
            errors.append(f"EXTERNAL_{index}_DETAILS_INVALID")
            continue
        if not kind or not provider or not provider_ref:
            errors.append(f"EXTERNAL_{index}_IDENTITY_INCOMPLETE")
            continue

        if scope == "proof_target":
            expected_digest = _digest_for_algorithm(target, algorithm)
            subject_context: dict[str, Any] = {
                "scope": scope,
                "expected_digest": expected_digest,
                "attestation_target": dict(target) if isinstance(target, Mapping) else {},
            }
        else:
            if evidence_id is None or evidence_id not in evidence_by_id:
                errors.append(f"EXTERNAL_{index}_EVIDENCE_ID_INVALID")
                continue
            evidence = evidence_by_id[evidence_id]
            if str(details.get("evidence_id") or "").strip() != evidence_id:
                errors.append(f"EXTERNAL_{index}_EVIDENCE_BINDING_MISMATCH")
                continue
            hashes = evidence.get("hashes") or {}
            if not isinstance(hashes, Mapping):
                errors.append(f"EXTERNAL_{index}_EVIDENCE_HASHES_INVALID")
                continue
            expected_digest = _digest_for_algorithm(hashes, algorithm)
            subject_context = {
                "scope": scope,
                "evidence_id": evidence_id,
                "expected_digest": expected_digest,
                "evidence_hashes": dict(hashes),
            }

        if expected_digest is None or digest != expected_digest:
            errors.append(f"EXTERNAL_{index}_DIGEST_BINDING_MISMATCH")
            continue

        verifier = verifiers.get(kind)
        if verifier is None:
            errors.append(f"EXTERNAL_VERIFIER_MISSING:{kind}:{provider}")
            continue
        try:
            accepted = verifier(attestation, subject_context) is True
        except Exception as exc:
            errors.append(f"EXTERNAL_VERIFIER_ERROR:{kind}:{provider}:{type(exc).__name__}")
            continue
        if not accepted:
            errors.append(f"EXTERNAL_VERIFICATION_FAILED:{kind}:{provider}")
            continue
        checked += 1

    return errors, {
        "verified_state_count": len(verified),
        "independently_checked_count": checked,
        "complete": checked == len(verified),
        "note": "VERIFIED/VALID labels are never trusted without an independent verifier for their attestation kind.",
    }


def verify_bundle(
    bundle: dict[str, Any],
    *,
    external_verifiers: Mapping[str, ExternalVerifier] | None = None,
) -> dict[str, Any]:
    """Verify a Proof Pack without treating CausLedger assertions as trust anchors.

    The JSON bundle may include ``offline_evidence`` keyed by evidence_id with exact
    ``content_base64`` bytes. External receipts marked VERIFIED/VALID require an
    independent verifier callback for their kind. Missing bytes or trust verification
    material is a hard failure for *independent* verification rather than something a
    server-side state label may silently satisfy.
    """
    core = bundle.get("core_package")
    manifest = bundle.get("proof_manifest")
    if not isinstance(core, dict) or not isinstance(manifest, dict):
        return {
            "valid": False,
            "manifest_integrity_valid": False,
            "independently_verifiable_without_causledger": False,
            "errors": ["BUNDLE_STRUCTURE_INVALID"],
            "warnings": [],
        }

    manifest_result = verify_proof_manifest(core, manifest)
    errors = list(manifest_result.get("errors") or [])
    warnings = list(manifest_result.get("warnings") or [])
    offline_evidence = bundle.get("offline_evidence") or {}
    if not isinstance(offline_evidence, Mapping):
        errors.append("OFFLINE_EVIDENCE_STRUCTURE_INVALID")
        offline_evidence = {}

    original_errors, original_result = _verify_original_bytes(manifest, offline_evidence)
    external_errors, external_result = _verify_external_attestations(
        manifest,
        external_verifiers or {},
    )
    errors.extend(original_errors)
    errors.extend(external_errors)

    manifest_integrity_valid = bool(manifest_result.get("valid"))
    independent = (
        manifest_integrity_valid
        and original_result["complete"] is True
        and external_result["complete"] is True
        and not errors
    )
    return {
        **manifest_result,
        "valid": independent,
        "manifest_integrity_valid": manifest_integrity_valid,
        "independently_verifiable_without_causledger": independent,
        "errors": errors,
        "warnings": warnings,
        "offline_originals": original_result,
        "external_attestations": external_result,
        "verification_scope": [
            "core_package_sha256_sha512",
            "manifest_sha256_sha512",
            "evidence_merkle_root",
            "stable_attestation_target",
            "embedded_original_bytes_sha256_sha512_and_length",
            "evidence_attestation_exact_digest_binding",
            "independent_external_attestation_verifiers",
        ],
        "trust_model": "DO NOT TRUST CAUSLEDGER STATE LABELS; REHASH ORIGINAL BYTES AND VERIFY EXTERNAL RECEIPTS WITH INDEPENDENT TRUST MATERIAL.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline verifier for a CausLedger Proof Pack JSON bundle")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"valid": False, "errors": [f"BUNDLE_READ_FAILED:{exc}"]}, indent=2))
        return 2
    result = verify_bundle(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    # The CLI is intentionally stricter than a manifest-only integrity checker: a
    # third party gets success only when every original and every VERIFIED external
    # receipt was independently checked without trusting CausLedger servers.
    return 0 if result.get("independently_verifiable_without_causledger") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
