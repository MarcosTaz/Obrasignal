from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from vertical_apps.industrial_claims.proof_providers import ProofRequest
from vertical_apps.industrial_claims.worm_lock_provider import (
    EvidenceWormLockProvider,
    WormObjectHead,
    WormWriteReceipt,
)


NOW = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)


def _request(payload: bytes, *, evidence_id: str = "ev-123", retain_days: int = 400) -> ProofRequest:
    digest = hashlib.sha256(payload).hexdigest()
    return ProofRequest(
        tenant_id="tenant-a",
        subject_ref=f"causledger:evidence:{evidence_id}:{digest}",
        digest_algorithm="SHA-256",
        digest=digest,
        purpose="EVIDENCE_ORIGINAL_IMMUTABILITY",
        metadata={
            "evidence_id": evidence_id,
            "retain_until": (NOW + timedelta(days=retain_days)).isoformat(),
        },
        payload=payload,
    )


class MemoryWormBackend:
    name = "synthetic-worm"

    def __init__(self):
        self.objects = {}
        self.put_calls = []
        self.mode_override = None
        self.retain_until_override = None
        self.version_override = None
        self.checksum_override = None
        self.readback_override = None
        self.lock_enabled = True

    def put_immutable(self, *, object_key, payload, content_sha256, retention_mode, retain_until, metadata):
        self.put_calls.append({
            "object_key": object_key,
            "payload": payload,
            "content_sha256": content_sha256,
            "retention_mode": retention_mode,
            "retain_until": retain_until,
            "metadata": dict(metadata),
        })
        version_id = "v1"
        self.objects[(object_key, version_id)] = {
            "payload": payload,
            "digest": content_sha256,
            "retain_until": retain_until,
            "mode": retention_mode,
            "metadata": dict(metadata),
        }
        return WormWriteReceipt(object_key=object_key, version_id=version_id, provider_ref="worm:synthetic:v1")

    def head_version(self, *, object_key, version_id):
        item = self.objects[(object_key, version_id)]
        return WormObjectHead(
            object_key=object_key,
            version_id=self.version_override or version_id,
            content_sha256=self.checksum_override or item["digest"],
            content_length=len(item["payload"]),
            object_lock_enabled=self.lock_enabled,
            retention_mode=self.mode_override or item["mode"],
            retain_until=(self.retain_until_override or item["retain_until"]).isoformat(),
            provider_metadata=item["metadata"],
        )

    def read_version(self, *, object_key, version_id):
        item = self.objects[(object_key, version_id)]
        return self.readback_override if self.readback_override is not None else item["payload"]


def _provider(backend: MemoryWormBackend) -> EvidenceWormLockProvider:
    return EvidenceWormLockProvider(
        backend=backend,
        minimum_retention=timedelta(days=365),
        clock=lambda: NOW,
    )


def test_exact_evidence_bytes_are_written_compliance_locked_read_back_and_rehashed():
    backend = MemoryWormBackend()
    payload = b"original supplier evidence bytes\n"
    result = _provider(backend).attest(_request(payload))

    assert result.state == "VERIFIED"
    assert result.kind == "WORM_LOCK"
    assert result.details["evidence_id"] == "ev-123"
    assert result.details["exact_original_bytes_read_back_and_rehashed"] is True
    assert result.details["version_specific_object_lock_verified"] is True
    assert result.details["retention_mode"] == "COMPLIANCE"
    assert result.details["readback_sha256"] == hashlib.sha256(payload).hexdigest()
    assert result.validation_ref.startswith("worm-readback:")
    assert backend.put_calls[0]["payload"] == payload
    assert backend.put_calls[0]["retention_mode"] == "COMPLIANCE"
    assert backend.put_calls[0]["metadata"]["causledger_content_sha256"] == result.digest


def test_metadata_only_cannot_claim_original_immutability_and_no_provider_write_occurs():
    backend = MemoryWormBackend()
    request = _request(b"real bytes")
    request = ProofRequest(
        tenant_id=request.tenant_id,
        subject_ref=request.subject_ref,
        digest_algorithm=request.digest_algorithm,
        digest=request.digest,
        purpose=request.purpose,
        metadata=request.metadata,
        payload=None,
    )
    result = _provider(backend).attest(request)
    assert result.state == "INVALID_REQUEST"
    assert result.details["error_code"] == "EXACT_ORIGINAL_BYTES_REQUIRED"
    assert backend.put_calls == []


def test_payload_digest_mismatch_fails_before_storage_write():
    backend = MemoryWormBackend()
    good = _request(b"original")
    forged = ProofRequest(
        tenant_id=good.tenant_id,
        subject_ref=good.subject_ref,
        digest_algorithm=good.digest_algorithm,
        digest=good.digest,
        purpose=good.purpose,
        metadata=good.metadata,
        payload=b"different",
    )
    result = _provider(backend).attest(forged)
    assert result.state == "INVALID_REQUEST"
    assert result.details["error_code"] == "PAYLOAD_DIGEST_MISMATCH"
    assert backend.put_calls == []


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (lambda b: setattr(b, "mode_override", "GOVERNANCE"), "COMPLIANCE_MODE_REQUIRED"),
        (lambda b: setattr(b, "retain_until_override", NOW + timedelta(days=10)), "RETENTION_SHORTENED"),
        (lambda b: setattr(b, "version_override", "v-attacker"), "VERSION_ID_MISMATCH"),
        (lambda b: setattr(b, "checksum_override", "f" * 64), "PROVIDER_CHECKSUM_MISMATCH"),
        (lambda b: setattr(b, "readback_override", b"altered bytes"), "READBACK_DIGEST_MISMATCH"),
        (lambda b: setattr(b, "lock_enabled", False), "OBJECT_LOCK_NOT_ENABLED"),
    ],
)
def test_provider_readback_substitution_or_weaker_lock_never_verifies(mutator, expected):
    backend = MemoryWormBackend()
    mutator(backend)
    result = _provider(backend).attest(_request(b"immutable original"))
    assert result.state == "INVALID"
    assert result.details["error_code"] == "WORM_READBACK_VERIFICATION_FAILED"
    assert expected in result.details["verification_errors"]


def test_retention_below_causledger_minimum_is_rejected_before_write():
    backend = MemoryWormBackend()
    result = _provider(backend).attest(_request(b"original", retain_days=100))
    assert result.state == "INVALID_REQUEST"
    assert result.details["error_code"] == "RETENTION_BELOW_CONFIGURED_MINIMUM"
    assert backend.put_calls == []


def test_object_key_is_tenant_and_evidence_scoped_without_plain_identifiers():
    backend = MemoryWormBackend()
    evidence_id = "customer-sensitive-evidence-name"
    payload = b"bytes"
    result = _provider(backend).attest(_request(payload, evidence_id=evidence_id))
    assert result.state == "VERIFIED"
    key = backend.put_calls[0]["object_key"]
    assert "tenant-a" not in key
    assert evidence_id not in key
    assert hashlib.sha256(payload).hexdigest() in key
