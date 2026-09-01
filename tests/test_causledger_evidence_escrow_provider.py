from __future__ import annotations

import hashlib

from vertical_apps.industrial_claims.evidence_escrow_provider import IndependentEvidenceEscrowProvider
from vertical_apps.industrial_claims.proof_providers import ProofRequest


class FakeEscrow:
    def __init__(self):
        self.payload = b""
        self.deposit_calls = 0
        self.read_calls = 0
        self.receipt_overrides = {}
        self.read_override = None
        self.fail_deposit = False

    def deposit(self, *, tenant_id, subject_ref, evidence_id, payload, sha256):
        self.deposit_calls += 1
        if self.fail_deposit:
            raise RuntimeError("provider unavailable")
        self.payload = bytes(payload)
        receipt = {
            "provider": "escrow-independent",
            "tenant_id": tenant_id,
            "subject_ref": subject_ref,
            "evidence_id": evidence_id,
            "digest_algorithm": "SHA-256",
            "digest": sha256,
            "provider_ref": "escrow-receipt-1",
            "object_ref": "object-1",
            "object_version": "version-1",
            "validation_ref": "receipt-validation-1",
            "issued_at": "2026-09-01T17:00:00+00:00",
        }
        receipt.update(self.receipt_overrides)
        return receipt

    def read_back(self, *, provider_ref, object_ref, object_version):
        self.read_calls += 1
        assert provider_ref == "escrow-receipt-1"
        assert object_ref == "object-1"
        assert object_version == "version-1"
        return self.payload if self.read_override is None else self.read_override


def _request(payload: bytes = b"customer change original") -> ProofRequest:
    return ProofRequest(
        tenant_id="tenant-a",
        subject_ref="finding-a",
        digest_algorithm="SHA-256",
        digest=hashlib.sha256(payload).hexdigest(),
        purpose="INDEPENDENT_ORIGINAL_EVIDENCE_ESCROW",
        metadata={"evidence_id": "evidence-a"},
        payload=payload,
    )


def test_verified_escrow_requires_exact_original_readback_and_binding():
    transport = FakeEscrow()
    provider = IndependentEvidenceEscrowProvider(name="escrow-independent", transport=transport)
    result = provider.attest(_request())

    assert result.state == "VERIFIED"
    assert result.kind == "EVIDENCE_ESCROW"
    assert result.provider_ref == "escrow-receipt-1"
    assert result.validation_ref == "receipt-validation-1"
    assert result.details["evidence_id"] == "evidence-a"
    assert result.details["binding_verified"] is True
    assert result.details["original_bytes_escrowed"] is True
    assert result.details["read_back_verified"] is True
    assert result.details["escrow_is_not_immutability_proof"] is True
    assert result.details["read_back_sha256"] == _request().digest
    assert transport.deposit_calls == 1
    assert transport.read_calls == 1


def test_escrow_receipt_misbinding_fails_closed():
    transport = FakeEscrow()
    transport.receipt_overrides["evidence_id"] = "other-evidence"
    provider = IndependentEvidenceEscrowProvider(name="escrow-independent", transport=transport)
    result = provider.attest(_request())

    assert result.state == "INVALID"
    assert result.details["binding_verified"] is False
    assert result.details["original_bytes_escrowed"] is False
    assert result.details["read_back_verified"] is False
    assert transport.read_calls == 0


def test_escrow_readback_tampering_fails_closed():
    transport = FakeEscrow()
    transport.read_override = b"modified bytes"
    provider = IndependentEvidenceEscrowProvider(name="escrow-independent", transport=transport)
    result = provider.attest(_request())

    assert result.state == "INVALID"
    assert result.details["original_bytes_escrowed"] is False
    assert result.details["read_back_verified"] is False
    assert transport.deposit_calls == 1
    assert transport.read_calls == 1


def test_escrow_provider_outage_is_unavailable_not_verified():
    transport = FakeEscrow()
    transport.fail_deposit = True
    provider = IndependentEvidenceEscrowProvider(name="escrow-independent", transport=transport)
    result = provider.attest(_request())

    assert result.state == "UNAVAILABLE"
    assert result.details["fail_closed"] is True
    assert result.details["original_bytes_escrowed"] is False
    assert transport.read_calls == 0


def test_escrow_never_accepts_digest_without_original_bytes():
    transport = FakeEscrow()
    request = _request()
    request_without_payload = ProofRequest(
        tenant_id=request.tenant_id,
        subject_ref=request.subject_ref,
        digest_algorithm=request.digest_algorithm,
        digest=request.digest,
        purpose=request.purpose,
        metadata=request.metadata,
        payload=None,
    )
    provider = IndependentEvidenceEscrowProvider(name="escrow-independent", transport=transport)
    result = provider.attest(request_without_payload)

    assert result.state == "INVALID"
    assert result.details["original_bytes_escrowed"] is False
    assert transport.deposit_calls == 0
