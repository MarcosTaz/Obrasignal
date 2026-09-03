from __future__ import annotations

import base64
import hashlib
from types import SimpleNamespace

from vertical_apps.industrial_claims.proof import ExternalAttestation, build_proof_manifest
from vertical_apps.industrial_claims.proof_verifier import verify_bundle


PAYLOAD = b"customer change request original bytes"
EVIDENCE_ID = "evidence-r17"


def _evidence():
    return SimpleNamespace(
        evidence_id=EVIDENCE_ID,
        source_type="CUSTOMER_CHANGE_REQUEST",
        source_ref="request-r17.eml",
        received_at="2026-09-01T15:00:00+00:00",
        content_hash=hashlib.sha256(PAYLOAD).hexdigest(),
        metadata={
            "content_sha512": hashlib.sha512(PAYLOAD).hexdigest(),
            "content_size_bytes": len(PAYLOAD),
            "raw_content_persisted": "TRUE",
            "capture_mode": "SECURE_ORIGINAL_CAPTURE",
            "source_authentication": "DIRECT_SOURCE_CAPTURE",
        },
    )


def _core():
    return {
        "tenant_id": "tenant-a",
        "finding": {"finding_id": "finding-a", "claim_family": "NRE"},
        "truth_boundary": {"recoverability_established": False},
    }


def _bundle(*, attestations=(), offline_payload: bytes | None = PAYLOAD):
    core = _core()
    manifest = build_proof_manifest(
        core_package=core,
        evidence=(_evidence(),),
        revision_number=1,
        supersedes_finding_id=None,
        attestations=attestations,
        generated_at="2026-09-01T16:00:00+00:00",
    )
    bundle = {"core_package": core, "proof_manifest": manifest}
    if offline_payload is not None:
        bundle["offline_evidence"] = {
            EVIDENCE_ID: {"content_base64": base64.b64encode(offline_payload).decode("ascii")}
        }
    return bundle


def _evidence_attestation(*, digest: str | None = None):
    return ExternalAttestation(
        kind="EVIDENCE_ESCROW",
        provider="independent-escrow",
        state="VERIFIED",
        digest_algorithm="SHA-256",
        digest=digest or hashlib.sha256(PAYLOAD).hexdigest(),
        provider_ref="escrow-receipt-1",
        issued_at="2026-09-01T15:30:00+00:00",
        validation_ref="escrow-validation-1",
        details={
            "evidence_id": EVIDENCE_ID,
            "subject_ref": "finding-a",
            "purpose": "INDEPENDENT_ORIGINAL_EVIDENCE_ESCROW",
        },
    )


def test_offline_verifier_rehashes_every_original_without_server_trust():
    result = verify_bundle(_bundle())
    assert result["manifest_integrity_valid"] is True
    assert result["offline_originals"]["complete"] is True
    assert result["external_attestations"]["complete"] is True
    assert result["independently_verifiable_without_causledger"] is True
    assert result["valid"] is True


def test_manifest_integrity_alone_is_not_an_independent_offline_success():
    result = verify_bundle(_bundle(offline_payload=None))
    assert result["manifest_integrity_valid"] is True
    assert result["independently_verifiable_without_causledger"] is False
    assert result["valid"] is False
    assert f"OFFLINE_ORIGINAL_MISSING:{EVIDENCE_ID}" in result["errors"]


def test_tampered_embedded_original_fails_closed():
    result = verify_bundle(_bundle(offline_payload=b"tampered bytes"))
    assert result["manifest_integrity_valid"] is True
    assert result["offline_originals"]["complete"] is False
    assert result["independently_verifiable_without_causledger"] is False
    assert f"OFFLINE_ORIGINAL_SHA256_MISMATCH:{EVIDENCE_ID}" in result["errors"]


def test_verified_external_label_requires_an_independent_kind_verifier():
    attestation = _evidence_attestation()
    bundle = _bundle(attestations=(attestation,))

    without_verifier = verify_bundle(bundle)
    assert without_verifier["manifest_integrity_valid"] is True
    assert without_verifier["valid"] is False
    assert "EXTERNAL_VERIFIER_MISSING:EVIDENCE_ESCROW:independent-escrow" in without_verifier["errors"]

    seen = {}

    def verify_escrow(receipt, context):
        seen["receipt"] = receipt
        seen["context"] = context
        return receipt["provider_ref"] == "escrow-receipt-1"

    verified = verify_bundle(bundle, external_verifiers={"EVIDENCE_ESCROW": verify_escrow})
    assert verified["external_attestations"]["independently_checked_count"] == 1
    assert verified["external_attestations"]["complete"] is True
    assert verified["valid"] is True
    assert seen["context"]["evidence_id"] == EVIDENCE_ID
    assert seen["context"]["expected_digest"] == hashlib.sha256(PAYLOAD).hexdigest()


def test_matching_evidence_id_cannot_hide_wrong_attestation_digest():
    attestation = _evidence_attestation(digest="f" * 64)
    result = verify_bundle(
        _bundle(attestations=(attestation,)),
        external_verifiers={"EVIDENCE_ESCROW": lambda *_args: True},
    )
    assert result["manifest_integrity_valid"] is True
    assert result["valid"] is False
    assert "EXTERNAL_0_DIGEST_BINDING_MISMATCH" in result["errors"]
    assert result["external_attestations"]["independently_checked_count"] == 0
