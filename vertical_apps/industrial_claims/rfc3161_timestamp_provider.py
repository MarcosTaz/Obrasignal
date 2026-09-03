from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol, Sequence
from urllib.parse import urlparse

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from rfc3161_client import (
    HashAlgorithm,
    TimestampRequestBuilder,
    VerifierBuilder,
    VerificationError,
    decode_timestamp_response,
)

from vertical_apps.industrial_claims.proof import ExternalAttestation, canonical_json_bytes
from vertical_apps.industrial_claims.proof_providers import ProofProvider, ProofRequest


MAX_TIMESTAMP_RESPONSE_BYTES = 262_144
DEFAULT_TIMEOUT = (4.0, 12.0)
EIDAS_QTST_SERVICE_TYPE = "http://uri.etsi.org/TrstSvc/Svctype/TSA/QTST"
EIDAS_GRANTED_STATUS = "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted"
EIDAS_CHAIN_VERIFICATION_METHOD = "XMLDSIG_LOTL_TO_MEMBER_STATE_TL"


class Rfc3161TimestampConfigurationError(ValueError):
    pass


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hex_sha256(value: object, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise Rfc3161TimestampConfigurationError(f"{label} must be a SHA-256 hex digest")
    return text


def _aware(value: str, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise Rfc3161TimestampConfigurationError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise Rfc3161TimestampConfigurationError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _https_uri(value: str, *, label: str, expected_host: str | None = None) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise Rfc3161TimestampConfigurationError(f"{label} must be a credential-free HTTPS URL")
    if expected_host is not None and parsed.hostname != expected_host:
        raise Rfc3161TimestampConfigurationError(f"{label} must use {expected_host}")
    return text


def _certs(pem_blobs: Sequence[bytes], *, label: str) -> list[x509.Certificate]:
    result: list[x509.Certificate] = []
    for blob in pem_blobs:
        if not isinstance(blob, bytes) or not blob.strip():
            raise Rfc3161TimestampConfigurationError(f"{label} certificate PEM is required")
        try:
            loaded = x509.load_pem_x509_certificates(blob)
        except ValueError as exc:
            raise Rfc3161TimestampConfigurationError(f"{label} certificate PEM is invalid") from exc
        result.extend(loaded)
    if not result:
        raise Rfc3161TimestampConfigurationError(f"at least one {label} certificate is required")
    return result


@dataclass(frozen=True)
class EidasQualifiedTimestampEvidence:
    """Receipt produced only after LOTL -> Member-State TL XMLDSig verification.

    The provider does not trust this object merely because it exists. It only
    accepts it from a configured qualification verifier invoked at the token's
    genTime. The receipt binds both signed-list byte hashes, signing certificate
    identities, sequence numbers, the exact TSA certificate and the status period.
    """

    territory: str
    service_type: str
    service_status: str
    service_certificate_sha256: str
    service_valid_from: str
    service_valid_until: str | None
    service_name: str | None
    lotl_uri: str
    lotl_sha256: str
    lotl_sequence: str
    lotl_signer_certificate_sha256: str
    national_tl_uri: str
    national_tl_sha256: str
    national_tl_sequence: str
    national_tl_signer_certificate_sha256: str
    verification_method: str
    verified_at: str

    def __post_init__(self) -> None:
        territory = self.territory.strip().upper()
        if len(territory) != 2 or not territory.isalpha():
            raise Rfc3161TimestampConfigurationError("eIDAS territory must be a two-letter code")
        if self.service_type.strip() != EIDAS_QTST_SERVICE_TYPE:
            raise Rfc3161TimestampConfigurationError("eIDAS service type must be TSA/QTST")
        if self.service_status.strip() != EIDAS_GRANTED_STATUS:
            raise Rfc3161TimestampConfigurationError("eIDAS qualified timestamp service must have granted status")
        for value, label in (
            (self.service_certificate_sha256, "service certificate"),
            (self.lotl_sha256, "LOTL"),
            (self.lotl_signer_certificate_sha256, "LOTL signer certificate"),
            (self.national_tl_sha256, "national TL"),
            (self.national_tl_signer_certificate_sha256, "national TL signer certificate"),
        ):
            _hex_sha256(value, label=label)
        _aware(self.service_valid_from, label="service_valid_from")
        if self.service_valid_until is not None:
            until = _aware(self.service_valid_until, label="service_valid_until")
            if until <= _aware(self.service_valid_from, label="service_valid_from"):
                raise Rfc3161TimestampConfigurationError("service validity interval is invalid")
        _aware(self.verified_at, label="verified_at")
        lotl = _https_uri(self.lotl_uri, label="LOTL URI", expected_host="ec.europa.eu")
        if urlparse(lotl).path != "/tools/lotl/eu-lotl.xml":
            raise Rfc3161TimestampConfigurationError("LOTL URI must be the official EU LOTL XML")
        _https_uri(self.national_tl_uri, label="national TL URI")
        if not self.lotl_sequence.strip() or not self.national_tl_sequence.strip():
            raise Rfc3161TimestampConfigurationError("trusted-list sequence numbers are required")
        if self.verification_method != EIDAS_CHAIN_VERIFICATION_METHOD:
            raise Rfc3161TimestampConfigurationError("eIDAS evidence must come from signed LOTL-to-TL verification")

    def covers(self, *, certificate: x509.Certificate, gen_time: datetime) -> bool:
        cert_fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
        if cert_fingerprint != self.service_certificate_sha256.strip().lower():
            return False
        instant = gen_time.astimezone(timezone.utc) if gen_time.tzinfo else gen_time.replace(tzinfo=timezone.utc)
        if instant < _aware(self.service_valid_from, label="service_valid_from"):
            return False
        if self.service_valid_until is not None and instant >= _aware(self.service_valid_until, label="service_valid_until"):
            return False
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "territory": self.territory.strip().upper(),
            "service_type": self.service_type,
            "service_status": self.service_status,
            "service_certificate_sha256": self.service_certificate_sha256.strip().lower(),
            "service_valid_from": self.service_valid_from,
            "service_valid_until": self.service_valid_until,
            "service_name": self.service_name,
            "lotl_uri": self.lotl_uri,
            "lotl_sha256": self.lotl_sha256.strip().lower(),
            "lotl_sequence": self.lotl_sequence,
            "lotl_signer_certificate_sha256": self.lotl_signer_certificate_sha256.strip().lower(),
            "national_tl_uri": self.national_tl_uri,
            "national_tl_sha256": self.national_tl_sha256.strip().lower(),
            "national_tl_sequence": self.national_tl_sequence,
            "national_tl_signer_certificate_sha256": self.national_tl_signer_certificate_sha256.strip().lower(),
            "verification_method": self.verification_method,
            "verified_at": self.verified_at,
        }


class EidasQualificationVerifier(Protocol):
    def verify(
        self,
        *,
        certificate: x509.Certificate,
        gen_time: datetime,
    ) -> EidasQualifiedTimestampEvidence:
        ...


class Rfc3161QualifiedTimestampProvider(ProofProvider):
    kind = "QUALIFIED_TIMESTAMP"

    def __init__(
        self,
        *,
        endpoint: str,
        provider_name: str,
        tsa_certificate_pem: bytes,
        root_certificates_pem: Sequence[bytes],
        intermediate_certificates_pem: Sequence[bytes] = (),
        qualification_verifier: EidasQualificationVerifier | None = None,
        qualification_evidence: EidasQualifiedTimestampEvidence | None = None,
        session: requests.Session | None = None,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    ) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise Rfc3161TimestampConfigurationError("RFC3161 endpoint must be credential-free HTTPS URL")
        name = str(provider_name or "").strip()
        if not name or len(name) > 128:
            raise Rfc3161TimestampConfigurationError("timestamp provider name is required")
        tsa_list = _certs((tsa_certificate_pem,), label="TSA")
        if len(tsa_list) != 1:
            raise Rfc3161TimestampConfigurationError("exactly one pinned TSA certificate is required")
        roots = _certs(root_certificates_pem, label="root")
        intermediates: list[x509.Certificate] = []
        if intermediate_certificates_pem:
            intermediates = _certs(intermediate_certificates_pem, label="intermediate")
        self.endpoint = endpoint
        self.name = name
        self.tsa_certificate = tsa_list[0]
        self.roots = roots
        self.intermediates = intermediates
        self.qualification_verifier = qualification_verifier
        self.legacy_qualification_evidence = qualification_evidence
        self.session = session or requests.Session()
        self.timeout = timeout

    def _base_details(self, request: ProofRequest) -> dict[str, Any]:
        return {
            "subject_ref": request.subject_ref,
            "purpose": request.purpose,
            "endpoint_origin": f"{urlparse(self.endpoint).scheme}://{urlparse(self.endpoint).netloc}",
            "payload_sha256": request.digest.lower(),
            "tsa_certificate_sha256": self.tsa_certificate.fingerprint(hashes.SHA256()).hex(),
            "root_certificate_sha256": [cert.fingerprint(hashes.SHA256()).hex() for cert in self.roots],
            "intermediate_certificate_sha256": [cert.fingerprint(hashes.SHA256()).hex() for cert in self.intermediates],
            "rfc3161_client_minimum_safe_version": "1.0.6",
            "rfc3161_client_pinned_version": "1.0.8",
            **dict(request.metadata),
        }

    def _nonverified(self, request: ProofRequest, *, state: str, details: dict[str, Any], provider_ref: str | None = None) -> ExternalAttestation:
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state=state,
            digest_algorithm="SHA-256",
            digest=request.digest,
            provider_ref=provider_ref,
            details=details,
        )

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        details = self._base_details(request)
        if request.digest_algorithm.upper() != "SHA-256":
            return self._nonverified(request, state="INVALID_REQUEST", details={**details, "error_code": "SHA256_REQUIRED"})
        digest = _hex_sha256(request.digest, label="proof request")
        payload = request.payload
        if not isinstance(payload, bytes) or not payload:
            return self._nonverified(request, state="INVALID_REQUEST", details={**details, "error_code": "EXACT_PAYLOAD_REQUIRED"})
        if _sha256(payload) != digest:
            return self._nonverified(request, state="INVALID_REQUEST", details={**details, "error_code": "PAYLOAD_DIGEST_MISMATCH"})

        timestamp_request = (
            TimestampRequestBuilder()
            .data(payload)
            .hash_algorithm(HashAlgorithm.SHA256)
            .cert_request(cert_request=True)
            .nonce(nonce=True)
            .build()
        )
        try:
            response = self.session.post(
                self.endpoint,
                data=timestamp_request.as_bytes(),
                headers={"Content-Type": "application/timestamp-query", "Accept": "application/timestamp-reply"},
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            return self._nonverified(
                request,
                state="UNAVAILABLE",
                details={**details, "error_code": "TSA_NETWORK_ERROR", "error_type": type(exc).__name__},
            )
        if response.is_redirect:
            return self._nonverified(request, state="INVALID_RESPONSE", details={**details, "error_code": "TSA_REDIRECT_REJECTED"})
        if response.status_code != 200:
            return self._nonverified(
                request,
                state="UNAVAILABLE" if response.status_code >= 500 else "INVALID_RESPONSE",
                details={**details, "error_code": "TSA_HTTP_STATUS", "http_status": response.status_code},
            )
        content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/timestamp-reply":
            return self._nonverified(
                request,
                state="INVALID_RESPONSE",
                details={**details, "error_code": "TSA_CONTENT_TYPE", "content_type": content_type},
            )
        response_bytes = bytes(response.content)
        if not response_bytes or len(response_bytes) > MAX_TIMESTAMP_RESPONSE_BYTES:
            return self._nonverified(
                request,
                state="INVALID_RESPONSE",
                details={**details, "error_code": "TSA_RESPONSE_SIZE", "response_bytes": len(response_bytes)},
            )
        response_sha256 = _sha256(response_bytes)
        provider_ref = f"rfc3161:{response_sha256}"
        try:
            timestamp_response = decode_timestamp_response(response_bytes)
            builder = VerifierBuilder.from_request(timestamp_request).tsa_certificate(self.tsa_certificate)
            for root in self.roots:
                builder = builder.add_root_certificate(root)
            for intermediate in self.intermediates:
                builder = builder.add_intermediate_certificate(intermediate)
            verifier = builder.build()
            verifier.verify_message(timestamp_response, payload)
        except (VerificationError, ValueError, TypeError) as exc:
            return self._nonverified(
                request,
                state="INVALID",
                provider_ref=provider_ref,
                details={**details, "error_code": "RFC3161_CRYPTOGRAPHIC_VERIFICATION_FAILED", "error_type": type(exc).__name__, "response_sha256": response_sha256},
            )

        gen_time = timestamp_response.tst_info.gen_time
        if gen_time.tzinfo is None:
            gen_time = gen_time.replace(tzinfo=timezone.utc)
        else:
            gen_time = gen_time.astimezone(timezone.utc)
        token_b64 = base64.b64encode(response_bytes).decode("ascii")
        validation_material: dict[str, Any] = {
            "response_sha256": response_sha256,
            "request_nonce": timestamp_request.nonce,
            "token_policy_oid": timestamp_response.tst_info.policy.dotted_string,
            "token_serial_number": str(timestamp_response.tst_info.serial_number),
            "token_gen_time": gen_time.isoformat(),
            "rfc3161_signature_and_chain_verified": True,
            "exact_payload_verified": True,
            "timestamp_response_base64": token_b64,
        }

        qualified = False
        qualification: dict[str, Any] | None = None
        qualification_error: str | None = None
        if self.qualification_verifier is not None:
            try:
                evidence = self.qualification_verifier.verify(
                    certificate=self.tsa_certificate,
                    gen_time=gen_time,
                )
                qualification = evidence.as_dict()
                qualified = evidence.covers(certificate=self.tsa_certificate, gen_time=gen_time)
                if not qualified:
                    qualification_error = "QUALIFICATION_RECEIPT_DOES_NOT_COVER_TOKEN"
            except Exception as exc:  # External trust-chain failure must fail closed, not erase valid RFC3161 proof.
                qualification_error = f"QUALIFICATION_VERIFICATION_FAILED:{type(exc).__name__}"
        elif self.legacy_qualification_evidence is not None:
            qualification = self.legacy_qualification_evidence.as_dict()
            qualification_error = "STATIC_QUALIFICATION_EVIDENCE_NOT_SUFFICIENT"

        validation_material["eidas_qualification_evidence"] = qualification
        validation_material["qualified_trusted_list_gate_satisfied"] = qualified
        validation_material["eidas_qualification_error"] = qualification_error
        validation_material["qualification_requires_runtime_signed_lotl_chain_verifier"] = True
        validation_ref = "rfc3161-validation:" + _sha256(canonical_json_bytes(validation_material))
        state = "VERIFIED" if qualified else "CRYPTOGRAPHICALLY_VALID"
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state=state,
            digest_algorithm="SHA-256",
            digest=digest,
            provider_ref=provider_ref,
            issued_at=gen_time.isoformat(),
            validation_ref=validation_ref,
            details={
                **details,
                **validation_material,
                "cryptographically_valid_does_not_imply_eidas_qualified": True,
            },
        )
