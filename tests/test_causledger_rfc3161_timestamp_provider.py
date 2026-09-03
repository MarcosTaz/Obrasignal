from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

import vertical_apps.industrial_claims.rfc3161_timestamp_provider as module
from vertical_apps.industrial_claims.proof_providers import ProofRequest
from vertical_apps.industrial_claims.rfc3161_timestamp_provider import (
    EIDAS_CHAIN_VERIFICATION_METHOD,
    EIDAS_GRANTED_STATUS,
    EIDAS_QTST_SERVICE_TYPE,
    EidasQualifiedTimestampEvidence,
    Rfc3161QualifiedTimestampProvider,
    Rfc3161TimestampConfigurationError,
)


def _certificates():
    now = datetime.now(timezone.utc)
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Root")])
    root = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .sign(root_key, hashes.SHA256())
    )
    tsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tsa_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Qualified TSA")])
    tsa = (
        x509.CertificateBuilder()
        .subject_name(tsa_name)
        .issuer_name(root_name)
        .public_key(tsa_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]), critical=True)
        .sign(root_key, hashes.SHA256())
    )
    pem = lambda cert: cert.public_bytes(serialization.Encoding.PEM)
    return root, tsa, pem(root), pem(tsa)


def _request(payload: bytes) -> ProofRequest:
    import hashlib
    return ProofRequest(
        tenant_id="tenant-a",
        subject_ref="causledger:change-sheet:sheet-a:" + hashlib.sha256(payload).hexdigest(),
        digest_algorithm="SHA-256",
        digest=hashlib.sha256(payload).hexdigest(),
        purpose="CHANGE_CAPTURE_SNAPSHOT_EXISTENCE_TIME",
        metadata={"sheet_id": "sheet-a"},
        payload=payload,
    )


def _qualification(tsa: x509.Certificate) -> EidasQualifiedTimestampEvidence:
    now = datetime.now(timezone.utc)
    return EidasQualifiedTimestampEvidence(
        territory="ES",
        service_type=EIDAS_QTST_SERVICE_TYPE,
        service_status=EIDAS_GRANTED_STATUS,
        service_certificate_sha256=tsa.fingerprint(hashes.SHA256()).hex(),
        service_valid_from=(now - timedelta(days=10)).isoformat(),
        service_valid_until=(now + timedelta(days=10)).isoformat(),
        service_name="Test Qualified TSA",
        lotl_uri="https://ec.europa.eu/tools/lotl/eu-lotl.xml",
        lotl_sha256="a" * 64,
        lotl_sequence="389",
        lotl_signer_certificate_sha256="b" * 64,
        national_tl_uri="https://example.test/es-trusted-list.xml",
        national_tl_sha256="c" * 64,
        national_tl_sequence="99",
        national_tl_signer_certificate_sha256="d" * 64,
        verification_method=EIDAS_CHAIN_VERIFICATION_METHOD,
        verified_at=now.isoformat(),
    )


class _QualificationVerifier:
    def __init__(self, tsa):
        self.tsa = tsa
        self.calls = []
    def verify(self, *, certificate, gen_time):
        self.calls.append((certificate, gen_time))
        assert certificate == self.tsa
        return _qualification(self.tsa)


class _Session:
    def __init__(self):
        self.calls = []
    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        class Response:
            status_code = 200
            is_redirect = False
            headers = {"Content-Type": "application/timestamp-reply"}
            content = b"synthetic-rfc3161-response"
        return Response()


class _FakeTimestampRequest:
    nonce = 777
    def as_bytes(self):
        return b"synthetic-rfc3161-request"


class _Builder:
    def __init__(self, recorder):
        self.recorder = recorder
    def data(self, value):
        self.recorder["request_payload"] = value
        return self
    def hash_algorithm(self, value):
        self.recorder["hash_algorithm"] = value
        return self
    def cert_request(self, *, cert_request=False):
        self.recorder["cert_request"] = cert_request
        return self
    def nonce(self, *, nonce=True):
        self.recorder["nonce_requested"] = nonce
        return self
    def build(self):
        return _FakeTimestampRequest()


class _Policy:
    dotted_string = "1.2.3.4"


class _TstInfo:
    policy = _Policy()
    serial_number = 42
    gen_time = datetime.now(timezone.utc)


class _TimestampResponse:
    tst_info = _TstInfo()


class _Verifier:
    def __init__(self, recorder):
        self.recorder = recorder
    def tsa_certificate(self, certificate):
        self.recorder["pinned_tsa"] = certificate
        return self
    def add_root_certificate(self, certificate):
        self.recorder.setdefault("roots", []).append(certificate)
        return self
    def add_intermediate_certificate(self, certificate):
        self.recorder.setdefault("intermediates", []).append(certificate)
        return self
    def build(self):
        return self
    def verify_message(self, response, payload):
        self.recorder["verified_payload"] = payload
        return True


class _VerifierFactory:
    recorder = None
    @classmethod
    def from_request(cls, request):
        cls.recorder["request_for_verifier"] = request
        return _Verifier(cls.recorder)


def _patch_rfc(monkeypatch, recorder):
    monkeypatch.setattr(module, "TimestampRequestBuilder", lambda: _Builder(recorder))
    monkeypatch.setattr(module, "decode_timestamp_response", lambda value: _TimestampResponse())
    _VerifierFactory.recorder = recorder
    monkeypatch.setattr(module, "VerifierBuilder", _VerifierFactory)


def test_provider_requires_https_and_canonical_lotl_receipt():
    _root, tsa, root_pem, tsa_pem = _certificates()
    with pytest.raises(Rfc3161TimestampConfigurationError, match="HTTPS"):
        Rfc3161QualifiedTimestampProvider(
            endpoint="http://tsa.example.test",
            provider_name="tsa",
            tsa_certificate_pem=tsa_pem,
            root_certificates_pem=(root_pem,),
        )
    good = _qualification(tsa)
    values = good.__dict__.copy()
    values["lotl_uri"] = "https://example.test/fake-lotl.xml"
    with pytest.raises(Rfc3161TimestampConfigurationError, match="ec.europa.eu|official EU LOTL"):
        EidasQualifiedTimestampEvidence(**values)


def test_exact_sheet_bytes_are_timestamped_and_crypto_valid_is_not_called_qualified(monkeypatch):
    _root, _tsa, root_pem, tsa_pem = _certificates()
    recorder = {}
    _patch_rfc(monkeypatch, recorder)
    session = _Session()
    provider = Rfc3161QualifiedTimestampProvider(
        endpoint="https://tsa.example.test/rfc3161",
        provider_name="tsa-test",
        tsa_certificate_pem=tsa_pem,
        root_certificates_pem=(root_pem,),
        session=session,
    )
    payload = b"CAUSLEDGER exact exported change sheet bytes\n"
    result = provider.attest(_request(payload))
    assert result.state == "CRYPTOGRAPHICALLY_VALID"
    assert result.details["qualified_trusted_list_gate_satisfied"] is False
    assert result.details["qualification_requires_runtime_signed_lotl_chain_verifier"] is True
    assert recorder["request_payload"] == payload
    assert recorder["verified_payload"] == payload
    assert recorder["cert_request"] is True
    assert recorder["nonce_requested"] is True
    assert session.calls[0][1]["allow_redirects"] is False


def test_static_qualification_object_is_never_enough_to_upgrade_rfc3161_token(monkeypatch):
    _root, tsa, root_pem, tsa_pem = _certificates()
    recorder = {}
    _patch_rfc(monkeypatch, recorder)
    provider = Rfc3161QualifiedTimestampProvider(
        endpoint="https://tsa.example.test/rfc3161",
        provider_name="tsa-test",
        tsa_certificate_pem=tsa_pem,
        root_certificates_pem=(root_pem,),
        qualification_evidence=_qualification(tsa),
        session=_Session(),
    )
    result = provider.attest(_request(b"exact bytes"))
    assert result.state == "CRYPTOGRAPHICALLY_VALID"
    assert result.details["qualified_trusted_list_gate_satisfied"] is False
    assert result.details["eidas_qualification_error"] == "STATIC_QUALIFICATION_EVIDENCE_NOT_SUFFICIENT"


def test_eidas_gate_requires_runtime_verifier_and_binds_receipt_into_validation_ref(monkeypatch):
    _root, tsa, root_pem, tsa_pem = _certificates()
    recorder = {}
    _patch_rfc(monkeypatch, recorder)
    qualification_verifier = _QualificationVerifier(tsa)
    provider = Rfc3161QualifiedTimestampProvider(
        endpoint="https://tsa.example.test/rfc3161",
        provider_name="tsa-test",
        tsa_certificate_pem=tsa_pem,
        root_certificates_pem=(root_pem,),
        qualification_verifier=qualification_verifier,
        session=_Session(),
    )
    result = provider.attest(_request(b"exact bytes"))
    assert result.state == "VERIFIED"
    assert result.details["qualified_trusted_list_gate_satisfied"] is True
    assert result.details["eidas_qualification_evidence"]["verification_method"] == EIDAS_CHAIN_VERIFICATION_METHOD
    assert result.validation_ref.startswith("rfc3161-validation:")
    assert result.provider_ref.startswith("rfc3161:")
    assert result.details["timestamp_response_base64"]
    assert len(qualification_verifier.calls) == 1


def test_payload_digest_mismatch_fails_before_any_network_call():
    _root, _tsa, root_pem, tsa_pem = _certificates()
    session = _Session()
    provider = Rfc3161QualifiedTimestampProvider(
        endpoint="https://tsa.example.test/rfc3161",
        provider_name="tsa-test",
        tsa_certificate_pem=tsa_pem,
        root_certificates_pem=(root_pem,),
        session=session,
    )
    request = _request(b"correct")
    forged = ProofRequest(
        tenant_id=request.tenant_id,
        subject_ref=request.subject_ref,
        digest_algorithm=request.digest_algorithm,
        digest=request.digest,
        purpose=request.purpose,
        metadata=request.metadata,
        payload=b"different",
    )
    result = provider.attest(forged)
    assert result.state == "INVALID_REQUEST"
    assert result.details["error_code"] == "PAYLOAD_DIGEST_MISMATCH"
    assert session.calls == []
