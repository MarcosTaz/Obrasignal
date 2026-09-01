from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from vertical_apps.industrial_claims.hardware_seal_provider import (
    HardwareKeyEvidence,
    HardwareQualifiedSealProvider,
    HardwareSignatureResult,
    QualifiedSealEvidence,
)
from vertical_apps.industrial_claims.proof_providers import ProofRequest


NOW = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)


def _key_and_cert(name="CausLedger synthetic seal"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOW - timedelta(days=30))
        .not_valid_after(NOW + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM)


def _request(payload=b"stable CausLedger proof target bytes"):
    digest = hashlib.sha256(payload).hexdigest()
    return ProofRequest(
        tenant_id="tenant-a",
        subject_ref=f"causledger:proof-target:{digest}",
        digest_algorithm="SHA-256",
        digest=digest,
        purpose="CAUSLEDGER_PROOF_PACK_SEAL",
        metadata={"finding_id": "finding-a", "static_qualified_boolean": True},
        payload=payload,
    )


class RsaHardwareBackend:
    name = "synthetic-hsm"

    def __init__(self, key):
        self.key = key
        self.calls = []

    def sign(self, *, key_id, algorithm, payload):
        self.calls.append((key_id, algorithm, payload))
        signature = self.key.sign(
            payload,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=hashes.SHA256().digest_size),
            hashes.SHA256(),
        )
        return HardwareSignatureResult(
            signature=signature,
            key_version="kv-7",
            provider_ref="hsm:synthetic:signature-1",
            signed_at=NOW.isoformat(),
            key_attestation=b"synthetic-hardware-attestation",
        )


class HardwareVerifier:
    def __init__(self, *, verified=True, certificate_override=None):
        self.verified = verified
        self.certificate_override = certificate_override

    def verify(self, *, backend_name, key_id, result, certificate):
        cert = self.certificate_override or certificate
        return HardwareKeyEvidence(
            verified=self.verified,
            verifier="synthetic-hsm-attestation-verifier",
            validation_ref="hsm-attestation:verified",
            key_id=key_id,
            key_version=result.key_version,
            certificate_sha256=cert.fingerprint(hashes.SHA256()).hex(),
            details={"backend": backend_name, "attestation_bytes_verified": True},
        )


class QualificationVerifier:
    def __init__(self, *, verified=True, certificate_override=None):
        self.verified = verified
        self.certificate_override = certificate_override

    def verify(self, *, certificate, signing_time):
        cert = self.certificate_override or certificate
        return QualifiedSealEvidence(
            verified=self.verified,
            verifier="synthetic-eidas-qseal-verifier",
            validation_ref="qseal:trusted-list-chain",
            certificate_sha256=cert.fingerprint(hashes.SHA256()).hex(),
            valid_from=(NOW - timedelta(days=10)).isoformat(),
            valid_until=(NOW + timedelta(days=10)).isoformat(),
            details={"signed_trusted_list_chain_verified": True, "signing_time": signing_time.isoformat()},
        )


def test_valid_signature_without_hardware_attestation_never_claims_hsm_or_qualified_seal():
    key, cert = _key_and_cert()
    backend = RsaHardwareBackend(key)
    provider = HardwareQualifiedSealProvider(
        backend=backend,
        key_id="hsm/key/causledger-seal",
        signing_certificate_pem=_pem(cert),
    )
    result = provider.attest(_request())
    assert result.state == "CRYPTOGRAPHICALLY_VALID"
    assert result.details["cryptographic_signature_verified"] is True
    assert result.details["hardware_key_evidence"] is None
    assert result.details["static_qualified_boolean"] is True
    assert result.details["qualified_seal_claim_is_fail_closed"] is True


def test_verified_hardware_key_without_eidas_qualification_stays_below_verified():
    key, cert = _key_and_cert()
    provider = HardwareQualifiedSealProvider(
        backend=RsaHardwareBackend(key),
        key_id="hsm/key/causledger-seal",
        signing_certificate_pem=_pem(cert),
        hardware_verifier=HardwareVerifier(),
    )
    result = provider.attest(_request())
    assert result.state == "HSM_KEY_VERIFIED"
    assert result.details["hardware_key_evidence"]["validation_ref"] == "hsm-attestation:verified"
    assert result.details["qualified_seal_evidence"] is None


def test_only_signature_plus_hardware_plus_qualification_can_be_verified():
    key, cert = _key_and_cert()
    provider = HardwareQualifiedSealProvider(
        backend=RsaHardwareBackend(key),
        key_id="hsm/key/causledger-seal",
        signing_certificate_pem=_pem(cert),
        hardware_verifier=HardwareVerifier(),
        qualification_verifier=QualificationVerifier(),
    )
    result = provider.attest(_request())
    assert result.state == "VERIFIED"
    assert result.kind == "QUALIFIED_SEAL"
    assert result.provider_ref == "hsm:synthetic:signature-1"
    assert result.validation_ref.startswith("seal-validation:")
    assert result.details["hardware_key_evidence"]
    assert result.details["qualified_seal_evidence"]["validation_ref"] == "qseal:trusted-list-chain"


def test_backend_key_substitution_fails_against_pinned_certificate():
    _expected_key, expected_cert = _key_and_cert("expected")
    rogue_key, _rogue_cert = _key_and_cert("rogue")
    provider = HardwareQualifiedSealProvider(
        backend=RsaHardwareBackend(rogue_key),
        key_id="hsm/key/causledger-seal",
        signing_certificate_pem=_pem(expected_cert),
        hardware_verifier=HardwareVerifier(),
        qualification_verifier=QualificationVerifier(),
    )
    result = provider.attest(_request())
    assert result.state == "INVALID"
    assert result.details["error_code"] == "SIGNATURE_VERIFICATION_FAILED"


def test_hardware_attestation_bound_to_another_certificate_cannot_upgrade_signature():
    key, cert = _key_and_cert("expected")
    _other_key, other_cert = _key_and_cert("other")
    provider = HardwareQualifiedSealProvider(
        backend=RsaHardwareBackend(key),
        key_id="hsm/key/causledger-seal",
        signing_certificate_pem=_pem(cert),
        hardware_verifier=HardwareVerifier(certificate_override=other_cert),
        qualification_verifier=QualificationVerifier(),
    )
    result = provider.attest(_request())
    assert result.state == "CRYPTOGRAPHICALLY_VALID"
    assert result.details["hardware_verification_error"].startswith("HARDWARE_ATTESTATION_FAILED")


def test_qualification_bound_to_another_certificate_cannot_upgrade_verified_hsm_signature():
    key, cert = _key_and_cert("expected")
    _other_key, other_cert = _key_and_cert("other")
    provider = HardwareQualifiedSealProvider(
        backend=RsaHardwareBackend(key),
        key_id="hsm/key/causledger-seal",
        signing_certificate_pem=_pem(cert),
        hardware_verifier=HardwareVerifier(),
        qualification_verifier=QualificationVerifier(certificate_override=other_cert),
    )
    result = provider.attest(_request())
    assert result.state == "HSM_KEY_VERIFIED"
    assert result.details["qualified_seal_verification_error"].startswith("QUALIFIED_SEAL_VERIFICATION_FAILED")


def test_payload_digest_mismatch_fails_before_hardware_signing():
    key, cert = _key_and_cert()
    backend = RsaHardwareBackend(key)
    good = _request(b"correct")
    forged = ProofRequest(
        tenant_id=good.tenant_id,
        subject_ref=good.subject_ref,
        digest_algorithm=good.digest_algorithm,
        digest=good.digest,
        purpose=good.purpose,
        metadata=good.metadata,
        payload=b"different",
    )
    result = HardwareQualifiedSealProvider(
        backend=backend,
        key_id="hsm/key/causledger-seal",
        signing_certificate_pem=_pem(cert),
    ).attest(forged)
    assert result.state == "INVALID_REQUEST"
    assert result.details["error_code"] == "PAYLOAD_DIGEST_MISMATCH"
    assert backend.calls == []
