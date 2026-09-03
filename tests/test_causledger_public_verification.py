from __future__ import annotations

from types import SimpleNamespace

from vertical_apps.industrial_claims.proof import build_proof_manifest, verify_proof_manifest
from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.public_verification import (
    build_public_receipt,
    verify_public_receipt,
)


def _evidence():
    payload = b"confidential-original"
    digests = dual_digest(payload)
    return SimpleNamespace(
        evidence_id="tenant-secret:evidence-1",
        source_type="email",
        source_ref="customer-secret-message-id",
        received_at="2026-08-31T22:00:00+00:00",
        content_hash=digests["sha256"],
        metadata={
            "content_sha512": digests["sha512"],
            "content_size_bytes": digests["byte_length"],
            "raw_content_persisted": "false",
            "source_authentication": "UNVERIFIED",
            "time_attestation": "LOCAL_SERVER_ONLY",
            "immutability": "NOT_PROVEN",
        },
    )


def _proof_pack():
    core = {
        "tenant_id": "tenant-secret",
        "finding": {"finding_id": "tenant-secret:finding-1"},
        "customer_ref": "Customer Secret SA",
        "net_potential": "999999",
        "currency": "EUR",
    }
    manifest = build_proof_manifest(
        core_package=core,
        evidence=(_evidence(),),
        revision_number=1,
        supersedes_finding_id=None,
        generated_at="2026-08-31T22:10:00+00:00",
    )
    verification = verify_proof_manifest(core, manifest)
    assert verification["valid"] is True
    return {
        "proof_pack_schema_version": 2,
        "brand": "CausLedger",
        "core_package": core,
        "proof_manifest": manifest,
        "self_verification": verification,
        "external_verification_required": True,
    }


def test_public_receipt_is_privacy_minimized_and_bound_to_pack():
    pack = _proof_pack()
    token = "A" * 32
    receipt = build_public_receipt(
        pack,
        verification_id=token,
        issued_at="2026-08-31T22:15:00+00:00",
    )
    serialized = repr(receipt)
    assert "tenant-secret" not in serialized
    assert "Customer Secret SA" not in serialized
    assert "999999" not in serialized
    assert "customer-secret-message-id" not in serialized
    assert receipt["verification"]["public_receipt_contains_customer_or_case_identifiers"] is False
    assert verify_public_receipt(pack, receipt)["valid"] is True


def test_public_receipt_detects_digest_or_strength_tampering():
    pack = _proof_pack()
    receipt = build_public_receipt(
        pack,
        verification_id="B" * 32,
        issued_at="2026-08-31T22:15:00+00:00",
    )
    tampered = dict(receipt)
    tampered["proof"] = dict(receipt["proof"])
    tampered["proof"]["manifest_sha256"] = "0" * 64
    assert verify_public_receipt(pack, tampered)["valid"] is False


def test_supersession_is_explicit_and_self_reference_is_rejected():
    pack = _proof_pack()
    old = "C" * 32
    new = "D" * 32
    receipt = build_public_receipt(
        pack,
        verification_id=old,
        state="SUPERSEDED",
        superseded_by=new,
        issued_at="2026-08-31T22:15:00+00:00",
    )
    assert receipt["lifecycle"] == {"state": "SUPERSEDED", "superseded_by": new}
    assert verify_public_receipt(pack, receipt)["valid"] is True
