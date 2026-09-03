from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from vertical_apps.industrial_claims.proof import ExternalAttestation, canonical_json_bytes
from vertical_apps.industrial_claims.proof_providers import ProofProvider, ProofRequest


class HardwareSealConfigurationError(ValueError):
    pass


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _required(value: object, *, label: str, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise HardwareSealConfigurationError(f"invalid {label}")
    return text


def _digest(value: object) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise HardwareSealConfigurationError("seal digest must be SHA-256 hex")
    return text


def _aware(value: object, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or "").strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise HardwareSealConfigurationError(f"invalid {label}") from exc
    if parsed.tzinfo is None:
        raise HardwareSealConfigurationError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class HardwareSignatureResult:
    signature: bytes
    key_version: str
    provider_ref: str
    signed_at: str
    key_attestation: bytes | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.signature, bytes) or not self.signature:
            raise HardwareSealConfigurationError("hardware signature bytes are required")
        _required(self.key_version, label="hardware key version", maximum=512)
        _required(self.provider_ref, label="hardware signature provider reference", maximum=4096)
        _aware(self.signed_at, label="hardware signed_at")
        if self.key_attestation is not None and (not isinstance(self.key_attestation, bytes) or not self.key_attestation):
            raise HardwareSealConfigurationError("hardware key attestation must be non-empty bytes")


@dataclass(frozen=True)
class HardwareKeyEvidence:
    verified: bool
    verifier: str
    validation_ref: str
    key_id: str
    key_version: str
    certificate_sha256: str
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        _required(self.verifier, label="hardware verifier", maximum=256)
        _required(self.validation_ref, label="hardware validation reference", maximum=4096)
        _required(self.key_id, label="hardware key id", maximum=2048)
        _required(self.key_version, label="hardware key version", maximum=512)
        _digest(self.certificate_sha256)


@dataclass(frozen=True)
class QualifiedSealEvidence:
    verified: bool
    verifier: str
    validation_ref: str
    certificate_sha256: str
    valid_from: str
    valid_until: str | None
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        _required(self.verifier, label="qualified-seal verifier", maximum=256)
        _required(self.validation_ref, label="qualified-seal validation reference", maximum=4096)
        _digest(self.certificate_sha256)
        _aware(self.valid_from, label="qualified-seal valid_from")
        if self.valid_until is not None:
            _aware(self.valid_until, label="qualified-seal valid_until")

    def covers(self, *, certificate: x509.Certificate, signing_time: datetime) -> bool:
        if not self.verified:
            return False
        if certificate.fingerprint(hashes.SHA256()).hex() != self.certificate_sha256.lower():
            return False
        instant = signing_time.astimezone(timezone.utc)
        if instant < _aware(self.valid_from, label="qualified-seal valid_from"):
            return False
        if self.valid_until is not None and instant >= _aware(self.valid_until, label="qualified-seal valid_until"):
            return False
        return True


class HardwareSigningBackend(Protocol):
    name: str

    def sign(self, *, key_id: str, algorithm: str, payload: bytes) -> HardwareSignatureResult:
        ...


class HardwareKeyAttestationVerifier(Protocol):
    def verify(
        self,
        *,
        backend_name: str,
        key_id: str,
        result: HardwareSignatureResult,
        certificate: x509.Certificate,
    ) -> HardwareKeyEvidence:
        ...


class QualifiedSealCertificateVerifier(Protocol):
    def verify(
        self,
        *,
        certificate: x509.Certificate,
        signing_time: datetime,
    ) -> QualifiedSealEvidence:
        ...


class HardwareQualifiedSealProvider(ProofProvider):
    """Seal exact proof bytes with a pinned certificate and independently gated HSM/eIDAS evidence."""

    kind = "QUALIFIED_SEAL"

    def __init__(
        self,
        *,
        backend: HardwareSigningBackend,
        key_id: str,
        signing_certificate_pem: bytes,
        hardware_verifier: HardwareKeyAttestationVerifier | None = None,
        qualification_verifier: QualifiedSealCertificateVerifier | None = None,
    ) -> None:
        self.name = _required(getattr(backend, "name", ""), label="hardware backend name", maximum=128)
        self.backend = backend
        self.key_id = _required(key_id, label="hardware key id", maximum=2048)
        if not isinstance(signing_certificate_pem, bytes) or not signing_certificate_pem.strip():
            raise HardwareSealConfigurationError("signing certificate PEM is required")
        try:
            certificates = x509.load_pem_x509_certificates(signing_certificate_pem)
        except ValueError as exc:
            raise HardwareSealConfigurationError("signing certificate PEM is invalid") from exc
        if len(certificates) != 1:
            raise HardwareSealConfigurationError("exactly one pinned signing certificate is required")
        self.certificate = certificates[0]
        self.hardware_verifier = hardware_verifier
        self.qualification_verifier = qualification_verifier
        public_key = self.certificate.public_key()
        if isinstance(public_key, rsa.RSAPublicKey):
            self.algorithm = "RSA_PSS_SHA256"
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            self.algorithm = "ECDSA_SHA256"
        else:
            raise HardwareSealConfigurationError("unsupported qualified-seal public key type")

    def _nonverified(
        self,
        request: ProofRequest,
        *,
        state: str,
        error_code: str,
        provider_ref: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> ExternalAttestation:
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state=state,
            digest_algorithm="SHA-256",
            digest=request.digest,
            provider_ref=provider_ref,
            details={
                "error_code": error_code,
                "cryptographic_signature_is_not_hardware_proof": True,
                "hardware_proof_is_not_qualified_seal_proof": True,
                "qualified_seal_claim_is_fail_closed": True,
                **dict(extra or {}),
            },
        )

    def _verify_signature(self, *, payload: bytes, signature: bytes) -> None:
        key = self.certificate.public_key()
        if isinstance(key, rsa.RSAPublicKey):
            key.verify(
                signature,
                payload,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=hashes.SHA256().digest_size),
                hashes.SHA256(),
            )
            return
        if isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
            return
        raise HardwareSealConfigurationError("unsupported seal verification key type")

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        if request.digest_algorithm.upper() != "SHA-256":
            return self._nonverified(request, state="INVALID_REQUEST", error_code="SHA256_REQUIRED")
        try:
            digest = _digest(request.digest)
        except HardwareSealConfigurationError:
            raise
        payload = request.payload
        if not isinstance(payload, bytes) or not payload:
            return self._nonverified(request, state="INVALID_REQUEST", error_code="EXACT_PAYLOAD_REQUIRED")
        if _sha256(payload) != digest:
            return self._nonverified(request, state="INVALID_REQUEST", error_code="PAYLOAD_DIGEST_MISMATCH")

        try:
            result = self.backend.sign(key_id=self.key_id, algorithm=self.algorithm, payload=payload)
        except Exception as exc:
            return self._nonverified(
                request,
                state="UNAVAILABLE",
                error_code="HARDWARE_SIGNING_FAILED",
                extra={"error_type": type(exc).__name__},
            )
        signing_time = _aware(result.signed_at, label="hardware signed_at")
        cert_not_before = self.certificate.not_valid_before_utc
        cert_not_after = self.certificate.not_valid_after_utc
        if signing_time < cert_not_before or signing_time >= cert_not_after:
            return self._nonverified(
                request,
                state="INVALID",
                error_code="SIGNING_CERTIFICATE_NOT_VALID_AT_SIGNING_TIME",
                provider_ref=result.provider_ref,
            )
        try:
            self._verify_signature(payload=payload, signature=result.signature)
        except Exception as exc:
            return self._nonverified(
                request,
                state="INVALID",
                error_code="SIGNATURE_VERIFICATION_FAILED",
                provider_ref=result.provider_ref,
                extra={"error_type": type(exc).__name__},
            )

        cert_sha256 = self.certificate.fingerprint(hashes.SHA256()).hex()
        signature_material: dict[str, Any] = {
            "algorithm": self.algorithm,
            "payload_sha256": digest,
            "signature_sha256": _sha256(result.signature),
            "signature_base64": base64.b64encode(result.signature).decode("ascii"),
            "certificate_sha256": cert_sha256,
            "certificate_subject": self.certificate.subject.rfc4514_string(),
            "key_id_sha256": hashlib.sha256(self.key_id.encode("utf-8")).hexdigest(),
            "key_version": result.key_version,
            "signed_at": signing_time.isoformat(),
            "cryptographic_signature_verified": True,
        }

        hardware: HardwareKeyEvidence | None = None
        hardware_error: str | None = None
        if self.hardware_verifier is not None:
            try:
                candidate = self.hardware_verifier.verify(
                    backend_name=self.name,
                    key_id=self.key_id,
                    result=result,
                    certificate=self.certificate,
                )
                if candidate.key_id != self.key_id or candidate.key_version != result.key_version:
                    raise HardwareSealConfigurationError("hardware evidence is bound to another key identity")
                if candidate.certificate_sha256.lower() != cert_sha256:
                    raise HardwareSealConfigurationError("hardware evidence is bound to another certificate")
                hardware = candidate if candidate.verified else None
                if not candidate.verified:
                    hardware_error = "HARDWARE_ATTESTATION_NOT_VERIFIED"
            except Exception as exc:
                hardware_error = f"HARDWARE_ATTESTATION_FAILED:{type(exc).__name__}"
        else:
            hardware_error = "HARDWARE_ATTESTATION_VERIFIER_NOT_CONFIGURED"

        qualification: QualifiedSealEvidence | None = None
        qualification_error: str | None = None
        if hardware is not None and self.qualification_verifier is not None:
            try:
                candidate = self.qualification_verifier.verify(
                    certificate=self.certificate,
                    signing_time=signing_time,
                )
                if candidate.certificate_sha256.lower() != cert_sha256:
                    raise HardwareSealConfigurationError("qualified seal evidence is bound to another certificate")
                qualification = candidate if candidate.covers(certificate=self.certificate, signing_time=signing_time) else None
                if qualification is None:
                    qualification_error = "QUALIFIED_SEAL_EVIDENCE_DOES_NOT_COVER_SIGNING_TIME"
            except Exception as exc:
                qualification_error = f"QUALIFIED_SEAL_VERIFICATION_FAILED:{type(exc).__name__}"
        elif hardware is None:
            qualification_error = "QUALIFICATION_BLOCKED_UNTIL_HARDWARE_KEY_IS_VERIFIED"
        else:
            qualification_error = "QUALIFIED_SEAL_VERIFIER_NOT_CONFIGURED"

        validation_material = {
            **signature_material,
            "hardware_key_evidence": None if hardware is None else {
                "verifier": hardware.verifier,
                "validation_ref": hardware.validation_ref,
                "key_id_sha256": hashlib.sha256(hardware.key_id.encode("utf-8")).hexdigest(),
                "key_version": hardware.key_version,
                "certificate_sha256": hardware.certificate_sha256,
                "details": dict(hardware.details),
            },
            "hardware_verification_error": hardware_error,
            "qualified_seal_evidence": None if qualification is None else {
                "verifier": qualification.verifier,
                "validation_ref": qualification.validation_ref,
                "certificate_sha256": qualification.certificate_sha256,
                "valid_from": qualification.valid_from,
                "valid_until": qualification.valid_until,
                "details": dict(qualification.details),
            },
            "qualified_seal_verification_error": qualification_error,
        }
        validation_ref = "seal-validation:" + _sha256(canonical_json_bytes(validation_material))
        if hardware is None:
            state = "CRYPTOGRAPHICALLY_VALID"
        elif qualification is None:
            state = "HSM_KEY_VERIFIED"
        else:
            state = "VERIFIED"
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state=state,
            digest_algorithm="SHA-256",
            digest=digest,
            provider_ref=result.provider_ref,
            issued_at=signing_time.isoformat(),
            validation_ref=validation_ref,
            details={
                **dict(request.metadata),
                **validation_material,
                "cryptographic_signature_is_not_hardware_proof": True,
                "hardware_proof_is_not_qualified_seal_proof": True,
                "qualified_seal_claim_is_fail_closed": True,
            },
        )
