from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from factory_cloud.assurance_store import AssuranceStoreError
from vertical_apps.industrial_claims.proof import verify_proof_manifest
from vertical_apps.industrial_claims.proof_storage import OriginalEvidenceStore
from vertical_apps.industrial_claims.proof_verifier import ExternalVerifier, verify_bundle


@dataclass(frozen=True)
class OfflineOriginal:
    evidence_id: str
    content: bytes


def _manifest_evidence_index(proof_pack: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    manifest = proof_pack.get("proof_manifest")
    if not isinstance(manifest, Mapping):
        raise AssuranceStoreError("offline export requires a proof manifest")
    evidence = manifest.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise AssuranceStoreError("offline export requires manifest evidence")

    result: dict[str, Mapping[str, Any]] = {}
    for item in evidence:
        if not isinstance(item, Mapping):
            raise AssuranceStoreError("offline export manifest evidence is invalid")
        evidence_id = str(item.get("evidence_id") or "").strip()
        hashes = item.get("hashes")
        if not evidence_id or not isinstance(hashes, Mapping):
            raise AssuranceStoreError("offline export manifest evidence identity is invalid")
        sha256 = str(hashes.get("sha256") or "").strip().lower()
        if len(sha256) != 64:
            raise AssuranceStoreError("offline export manifest sha256 commitment is invalid")
        if evidence_id in result:
            raise AssuranceStoreError("offline export manifest evidence is duplicated")
        result[evidence_id] = item
    return result


def _supplied_originals(
    originals: Sequence[OfflineOriginal],
    *,
    expected: Mapping[str, Mapping[str, Any]],
) -> dict[str, bytes]:
    supplied: dict[str, bytes] = {}
    for original in originals:
        evidence_id = str(original.evidence_id or "").strip()
        try:
            content = bytes(original.content)
        except (TypeError, ValueError) as exc:
            raise AssuranceStoreError("offline export original content must be bytes-like") from exc
        if not evidence_id or not content:
            raise AssuranceStoreError("offline export requires non-empty original bytes")
        if evidence_id in supplied:
            raise AssuranceStoreError("offline export original is duplicated")
        if evidence_id not in expected:
            raise AssuranceStoreError("offline export original is not part of this proof pack")
        supplied[evidence_id] = content

    missing = sorted(set(expected) - set(supplied))
    if missing:
        raise AssuranceStoreError(
            "offline export refused because original bytes are unavailable for: " + ", ".join(missing)
        )
    return supplied


def _verify_original_against_manifest(
    *,
    evidence_id: str,
    content: bytes,
    manifest_item: Mapping[str, Any],
) -> None:
    hashes = manifest_item.get("hashes")
    if not isinstance(hashes, Mapping):
        raise AssuranceStoreError(f"offline export manifest hashes invalid for {evidence_id}")

    expected256 = str(hashes.get("sha256") or "").strip().lower()
    expected512 = str(hashes.get("sha512") or "").strip().lower()
    actual256 = hashlib.sha256(content).hexdigest()
    actual512 = hashlib.sha512(content).hexdigest()
    if actual256 != expected256:
        raise AssuranceStoreError(f"offline export original sha256 mismatch for {evidence_id}")
    if expected512 and actual512 != expected512:
        raise AssuranceStoreError(f"offline export original sha512 mismatch for {evidence_id}")

    byte_length = manifest_item.get("byte_length")
    if byte_length is not None:
        try:
            expected_length = int(byte_length)
        except (TypeError, ValueError) as exc:
            raise AssuranceStoreError(f"offline export byte length invalid for {evidence_id}") from exc
        if expected_length != len(content):
            raise AssuranceStoreError(f"offline export original length mismatch for {evidence_id}")


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "verified", "valid"}


def read_durable_originals_for_offline_export(
    *,
    service: Any,
    proof_pack: Mapping[str, Any],
    original_store: OriginalEvidenceStore,
) -> tuple[OfflineOriginal, ...]:
    """Resolve exact immutable versions from durable tenant-scoped evidence metadata.

    No object reference supplied by the caller is trusted. The references come from
    persisted evidence metadata, the configured store must match that persisted
    provider identity, and every returned byte string is rehashed against the Proof
    Pack before it is eligible for export.
    """
    core = proof_pack.get("core_package")
    if not isinstance(core, Mapping):
        raise AssuranceStoreError("offline export requires durable core package truth")
    tenant_id = str(core.get("tenant_id") or "").strip()
    if not tenant_id:
        raise AssuranceStoreError("offline export tenant identity is missing")
    expected = _manifest_evidence_index(proof_pack)

    store_name = str(getattr(original_store, "name", "") or "").strip()
    if not store_name:
        raise AssuranceStoreError("offline export immutable original store is unidentified")
    try:
        database_path = service.store.path
    except AttributeError as exc:
        raise AssuranceStoreError("offline export service does not expose durable evidence storage") from exc

    originals: list[OfflineOriginal] = []
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        for evidence_id, manifest_item in expected.items():
            row = conn.execute(
                "SELECT content_hash, metadata_json FROM evidence WHERE tenant_id=? AND evidence_id=?",
                (tenant_id, evidence_id),
            ).fetchone()
            if row is None:
                raise AssuranceStoreError(f"offline export durable evidence missing: {evidence_id}")
            try:
                metadata = json.loads(str(row["metadata_json"]))
            except (TypeError, ValueError) as exc:
                raise AssuranceStoreError(f"offline export durable evidence metadata invalid: {evidence_id}") from exc
            if not isinstance(metadata, dict):
                raise AssuranceStoreError(f"offline export durable evidence metadata invalid: {evidence_id}")
            if not _truthy(metadata.get("raw_content_persisted")):
                raise AssuranceStoreError(f"offline export original bytes were not durably persisted: {evidence_id}")

            provider = str(metadata.get("original_store_provider") or "").strip()
            object_ref = str(metadata.get("original_object_ref") or "").strip()
            version_ref = str(metadata.get("original_version_ref") or "").strip()
            if provider != store_name:
                raise AssuranceStoreError(f"offline export original-store provider mismatch: {evidence_id}")
            if not object_ref or not version_ref:
                raise AssuranceStoreError(f"offline export immutable version identity missing: {evidence_id}")

            hashes = manifest_item.get("hashes") or {}
            manifest_sha256 = str(hashes.get("sha256") or "").strip().lower()
            if str(row["content_hash"] or "").strip().lower() != manifest_sha256:
                raise AssuranceStoreError(f"offline export durable evidence digest drift: {evidence_id}")

            try:
                content = original_store.read_immutable_version(
                    tenant_id=tenant_id,
                    evidence_id=evidence_id,
                    object_ref=object_ref,
                    version_ref=version_ref,
                )
            except Exception as exc:
                raise AssuranceStoreError(f"offline export immutable original retrieval failed: {evidence_id}") from exc
            if not isinstance(content, bytes) or not content:
                raise AssuranceStoreError(f"offline export immutable original retrieval returned no bytes: {evidence_id}")
            _verify_original_against_manifest(
                evidence_id=evidence_id,
                content=content,
                manifest_item=manifest_item,
            )
            originals.append(OfflineOriginal(evidence_id=evidence_id, content=content))
    return tuple(originals)


def build_offline_verification_export_bundle(
    proof_pack: Mapping[str, Any],
    *,
    originals: Sequence[OfflineOriginal],
    external_verifiers: Mapping[str, ExternalVerifier] | None = None,
) -> dict[str, Any]:
    """Build a confidential package that a third party can verify offline.

    The ordinary Proof Pack remains hash/metadata only. This explicit export refuses
    to exist unless exact bytes are supplied for every committed evidence item and
    those bytes match the manifest. VERIFIED/VALID external receipts are also
    fail-closed: if the pack contains them, an independent verifier callback for each
    attestation kind must validate them before this function releases the bundle.
    """
    core_package = proof_pack.get("core_package")
    manifest = proof_pack.get("proof_manifest")
    if not isinstance(core_package, Mapping) or not isinstance(manifest, Mapping):
        raise AssuranceStoreError("offline export requires a complete proof pack")

    self_check = verify_proof_manifest(dict(core_package), dict(manifest))
    if not self_check.get("valid"):
        raise AssuranceStoreError("offline export refused an internally invalid proof pack")

    expected = _manifest_evidence_index(proof_pack)
    supplied = _supplied_originals(originals, expected=expected)

    offline_evidence: dict[str, dict[str, str]] = {}
    for evidence_id in sorted(expected):
        content = supplied[evidence_id]
        _verify_original_against_manifest(
            evidence_id=evidence_id,
            content=content,
            manifest_item=expected[evidence_id],
        )
        offline_evidence[evidence_id] = {
            "content_base64": base64.b64encode(content).decode("ascii")
        }

    bundle: dict[str, Any] = {
        "schema_version": 1,
        "deliverable": "VINDORUM_CONFIDENTIAL_OFFLINE_VERIFICATION_BUNDLE",
        "confidential": True,
        "core_package": dict(core_package),
        "proof_manifest": dict(manifest),
        "offline_evidence": offline_evidence,
        "truth_boundaries": {
            "contains_raw_original_bytes": True,
            "must_not_be_published": True,
            "ordinary_proof_pack_contains_raw_original_bytes": False,
            "independent_verifier_required": True,
            "missing_original_bytes_fail_closed": True,
        },
    }

    independent = verify_bundle(bundle, external_verifiers=external_verifiers)
    if not independent.get("valid"):
        errors = ", ".join(str(item) for item in independent.get("errors") or [])
        raise AssuranceStoreError(
            "offline export failed independent verification before release"
            + (f": {errors}" if errors else "")
        )
    bundle["independent_verification"] = independent
    return bundle


def build_durable_offline_verification_export_bundle(
    *,
    service: Any,
    proof_pack: Mapping[str, Any],
    original_store: OriginalEvidenceStore,
    external_verifiers: Mapping[str, ExternalVerifier] | None = None,
) -> dict[str, Any]:
    originals = read_durable_originals_for_offline_export(
        service=service,
        proof_pack=proof_pack,
        original_store=original_store,
    )
    return build_offline_verification_export_bundle(
        proof_pack,
        originals=originals,
        external_verifiers=external_verifiers,
    )
