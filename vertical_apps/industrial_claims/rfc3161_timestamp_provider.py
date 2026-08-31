from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence
from urllib.parse import urlparse

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
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
    """Pinned evidence that a TSA service is qualified in an EU/EEA Trusted List.

    This is deliberately separate from ordinary PKI verification. A valid RFC3161
    signature becomes CausLedger VERIFIED only when the exact TSA certificate is
    also bound to independently verified Trusted List evidence covering gen_time.
    """

    service_uri: str
    territory: str
    service_type: str
    service_status: str
    service_certificate_sha256: str
    service_valid_from: str
    service_valid_until: str | None
    trusted_list_sequence: str
    trusted_list_sha256: str
    trusted_list_signature_verified: bool
    verified_at: str

    def __post_init__(self) -> None:
        parsed = urlparse(self.service_uri)
        if parsed.scheme != "https" or parsed.netloc != "eidas.ec.europa.eu" or not parsed.path.startswith("/efda/trust-services/"):
            raise Rfc3161TimestampConfigurationError("eIDAS service URI must reference the official EU eIDAS Dashboard")
        territory = self.territory.strip().upper()
        if len(territory) != 2 or not territory.isalpha():
            raise Rfc3161TimestampConfigurationError("eIDAS territory must be a two-letter code")
        if self.service_type.strip().upper() != "TSA/QTST":
            raise Rfc3161TimestampConfigurationError("eIDAS service type must be TSA/QTST")
        if self.service_status.strip().upper() != "GRANTED":
            raise Rfc3161TimestampConfigurationError("eIDAS qualified timestamp service must have GRANTED status")
        _hex_sha256(self.service_certificate_sha256, label="service certificate")
        _hex_sha256(self.trusted_list_sha256, label="trusted list")
        _aware(self.service_valid_from, label="service_valid_from")
        if self.service_valid_until is not None:
            _aware(self.service_valid_until, label="service_valid_until")
        _aware(self.verified_at, label="verified_at")
        if not self.trusted_list_sequence.strip():
            raise Rfc3161TimestampConfigurationError("trusted list sequence is required")

    def covers(self, *, certificate: x509.Certificate, gen_time: datetime) -> bool:
        if not self.trusted_list_signature_verified:
            return False
        cert_fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
        if cert_fingerprint != self.service_certificate_sha256.strip().lower():
            return False
        instant = gen_time.astimezone(timezone.utc) if gen_time.tzinfo else gen_time.replace(tzinfo=timezone.utc)
        if instant < _aware(self.service_valid_from, label="service_valid_from"):
            return False
        if self.service_valid_until is not None and instant > _aware(self.service_valid_until, label="service_valid_until"):
            return False
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "service_uri": self.service_uri,
            "territory": self.territory.strip().upper(),
            "service_type": "TSA/QTST",
            "service_status": "GRANTED",
            "service_certificate_sha256": self.service_certificate_sha256.strip().lower(),
            "service_valid_from": self.service_valid_from,
            "service_valid_until": self.service_valid_until,
            "trusted_list_sequence": self.trusted_list_sequence,
            "trusted_list_sha256": self.trusted_list_sha256.strip().lower(),
            "trusted_list_signature_verified": self.trusted_list_signature_verified,
            "verified_at": self.verified_at,
        }


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
        self.qualification_evidence = qualification_evidence
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
        validation_material = {
            "response_sha256": response_sha256,
            "request_nonce": timestamp_request.nonce,
            "token_policy_oid": timestamp_response.tst_info.policy.dotted_string,
            "token_serial_number": str(timestamp_response.tst_info.serial_number),
            "token_gen_time": gen_time.isoformat(),
            "rfc3161_signature_and_chain_verified": True,
            "exact_payload_verified": True,
            "timestamp_response_base64": token_b64,
        }
        validation_ref = "rfc3161-validation:" + _sha256(canonical_json_bytes(validation_material))

        qualified = False
        qualification = None
        if self.qualification_evidence is not None:
            qualification = self.qualification_evidence.as_dict()
            qualified = self.qualification_evidence.covers(certificate=self.tsa_certificate, gen_time=gen_time)
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
                "eidas_qualification_evidence": qualification,
                "qualified_trusted_list_gate_satisfied": qualified,
                "cryptographically_valid_does_not_imply_eidas_qualified": True,
            },
        )
