from __future__ import annotations

from types import SimpleNamespace

import pytest

from vertical_apps.industrial_claims.proof import ExternalAttestation
from vertical_apps.industrial_claims.proof_binding import (
    EvidenceAttestationBindingError,
    validate_evidence_attestation_bindings,
)
from vertical_apps.industrial_claims.proof_extensions import dual_digest


def _evidence(evidence_id: str = "tenant:e1"):
    digests = dual_digest(b"original evidence bytes")
    return SimpleNamespace(
        evidence_id=evidence_id,
        content_hash=digests["sha256"],
        metadata={"content_sha512": digests["sha512"]},
    )


def _attestation(*, evidence_id: str = "tenant:e1", digest: str | None = None, algorithm: str = "SHA-256"):
    evidence = _evidence(evidence_id)
    expected = evidence.content_hash if algorithm == "SHA-256" else evidence.metadata["content_sha512"]
    return ExternalAttestation(
        kind="QUALIFIED_TIMESTAMP",
        provider="qualified-provider",
        state="VERIFIED",
        digest_algorithm=algorithm,
        digest=digest or expected,
        provider_ref="provider:1",
        details={"evidence_id": evidence_id},
    )


def test_verified_evidence_attestation_must_match_exact_digest():
    evidence = _evidence()
    validate_evidence_attestation_bindings((evidence,), (_attestation(),))
    validate_evidence_attestation_bindings((evidence,), (_attestation(algorithm="SHA-512"),))


def test_verified_evidence_attestation_with_wrong_digest_is_rejected():
    with pytest.raises(EvidenceAttestationBindingError, match="digest does not match"):
        validate_evidence_attestation_bindings((_evidence(),), (_attestation(digest="b" * 64),))


def test_verified_evidence_attestation_for_unknown_evidence_is_rejected():
    attestation = ExternalAttestation(
        kind="WORM_LOCK",
        provider="object-store",
        state="VERIFIED",
        digest_algorithm="SHA-256",
        digest="a" * 64,
        provider_ref="object:1",
        details={"evidence_id": "tenant:unknown"},
    )
    with pytest.raises(EvidenceAttestationBindingError, match="unknown evidence"):
        validate_evidence_attestation_bindings((_evidence(),), (attestation,))


def test_unverified_receipt_cannot_upgrade_and_does_not_block_pack():
    attestation = ExternalAttestation(
        kind="QUALIFIED_TIMESTAMP",
        provider="provider",
        state="UNAVAILABLE",
        digest_algorithm="SHA-256",
        digest="b" * 64,
        details={"evidence_id": "tenant:e1"},
    )
    validate_evidence_attestation_bindings((_evidence(),), (attestation,))
