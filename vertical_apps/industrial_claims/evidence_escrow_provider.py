from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Mapping, Protocol

from vertical_apps.industrial_claims.proof import ExternalAttestation, sha256_hex
from vertical_apps.industrial_claims.proof_providers import ProofRequest


class EvidenceEscrowError(RuntimeError):
    pass


class EvidenceEscrowTransport(Protocol):
    """Provider-specific custody transport.

    Implementations may call an external escrow service, but this contract never
    treats an upload acknowledgement as proof of custody: the exact deposited
    object/version must also be read back and re-hashed by CausLedger.
    """

    def deposit(
        self,
        *,
        tenant_id: str,
        subject_ref: str,
        evidence_id: str,
        payload: bytes,
        sha256: str,
    ) -> Mapping[str, Any]:
        ...

    def read_back(
        self,
        *,
        provider_ref: str,
        object_ref: str,
        object_version: str,
    ) -> bytes:
        ...


def _required(value: object, *, label: str, max_chars: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_chars or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise EvidenceEscrowError(f"invalid escrow {label}")
    return text


def _timestamp(value: object) -> str:
    text = _required(value, label="issued_at", max_chars=128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceEscrowError("invalid escrow issued_at") from exc
    if parsed.tzinfo is None:
        raise EvidenceEscrowError("escrow issued_at must include timezone")
    return parsed.isoformat()


class IndependentEvidenceEscrowProvider:
    kind = "EVIDENCE_ESCROW"

    def __init__(self, *, name: str, transport: EvidenceEscrowTransport) -> None:
        self.name = _required(name, label="provider", max_chars=256)
        self.transport = transport

    def _result(
        self,
        request: ProofRequest,
        *,
        state: str,
        evidence_id: str | None,
        provider_ref: str | None = None,
        issued_at: str | None = None,
        validation_ref: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> ExternalAttestation:
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state=state,
            digest_algorithm="SHA-256",
            digest=str(request.digest or "").strip().lower(),
            provider_ref=provider_ref,
            issued_at=issued_at,
            validation_ref=validation_ref,
            details={
                "tenant_id": request.tenant_id,
                "subject_ref": request.subject_ref,
                "purpose": request.purpose,
                "evidence_id": evidence_id,
                "binding_verified": False,
                "original_bytes_escrowed": False,
                "read_back_verified": False,
                "escrow_is_not_immutability_proof": True,
                **dict(details or {}),
            },
        )

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        algorithm = str(request.digest_algorithm or "").strip().upper()
        digest = str(request.digest or "").strip().lower()
        evidence_id = str(request.metadata.get("evidence_id") or "").strip()
        if algorithm != "SHA-256" or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise EvidenceEscrowError("evidence escrow requires an exact SHA-256 request digest")
        if request.payload is None:
            return self._result(request, state="INVALID", evidence_id=evidence_id or None, details={"reason": "ORIGINAL_BYTES_REQUIRED"})
        payload = bytes(request.payload)
        if not payload or hashlib.sha256(payload).hexdigest() != digest:
            return self._result(request, state="INVALID", evidence_id=evidence_id or None, details={"reason": "PAYLOAD_DIGEST_MISMATCH"})
        if not evidence_id:
            return self._result(request, state="INVALID", evidence_id=None, details={"reason": "EVIDENCE_ID_REQUIRED"})

        tenant_id = _required(request.tenant_id, label="tenant", max_chars=128)
        subject_ref = _required(request.subject_ref, label="subject")
        _required(request.purpose, label="purpose", max_chars=256)
        try:
            receipt = self.transport.deposit(
                tenant_id=tenant_id,
                subject_ref=subject_ref,
                evidence_id=evidence_id,
                payload=payload,
                sha256=digest,
            )
        except Exception as exc:
            return self._result(
                request,
                state="UNAVAILABLE",
                evidence_id=evidence_id,
                details={"provider_error_type": type(exc).__name__, "fail_closed": True},
            )

        try:
            if not isinstance(receipt, Mapping):
                raise EvidenceEscrowError("escrow receipt must be an object")
            if _required(receipt.get("provider"), label="provider", max_chars=256) != self.name:
                raise EvidenceEscrowError("escrow provider identity mismatch")
            if _required(receipt.get("tenant_id"), label="tenant", max_chars=128) != tenant_id:
                raise EvidenceEscrowError("escrow tenant binding mismatch")
            if _required(receipt.get("subject_ref"), label="subject") != subject_ref:
                raise EvidenceEscrowError("escrow subject binding mismatch")
            if _required(receipt.get("evidence_id"), label="evidence id") != evidence_id:
                raise EvidenceEscrowError("escrow evidence binding mismatch")
            if _required(receipt.get("digest_algorithm"), label="digest algorithm", max_chars=32).upper() != "SHA-256":
                raise EvidenceEscrowError("escrow digest algorithm mismatch")
            if _required(receipt.get("digest"), label="digest", max_chars=128).lower() != digest:
                raise EvidenceEscrowError("escrow digest mismatch")

            provider_ref = _required(receipt.get("provider_ref"), label="provider ref")
            object_ref = _required(receipt.get("object_ref"), label="object ref")
            object_version = _required(receipt.get("object_version"), label="object version")
            validation_ref = _required(receipt.get("validation_ref"), label="validation ref")
            issued_at = _timestamp(receipt.get("issued_at"))
            read_back = self.transport.read_back(
                provider_ref=provider_ref,
                object_ref=object_ref,
                object_version=object_version,
            )
            if not isinstance(read_back, (bytes, bytearray, memoryview)):
                raise EvidenceEscrowError("escrow read-back must return bytes")
            read_back_sha256 = hashlib.sha256(bytes(read_back)).hexdigest()
            if read_back_sha256 != digest or bytes(read_back) != payload:
                raise EvidenceEscrowError("escrow read-back does not match deposited original")

            receipt_binding = {
                "provider": self.name,
                "provider_ref": provider_ref,
                "object_ref": object_ref,
                "object_version": object_version,
                "tenant_id": tenant_id,
                "subject_ref": subject_ref,
                "evidence_id": evidence_id,
                "sha256": digest,
                "validation_ref": validation_ref,
                "issued_at": issued_at,
            }
            return self._result(
                request,
                state="VERIFIED",
                evidence_id=evidence_id,
                provider_ref=provider_ref,
                issued_at=issued_at,
                validation_ref=validation_ref,
                details={
                    "binding_verified": True,
                    "original_bytes_escrowed": True,
                    "read_back_verified": True,
                    "object_ref": object_ref,
                    "object_version": object_version,
                    "read_back_sha256": read_back_sha256,
                    "receipt_binding_sha256": sha256_hex(receipt_binding),
                },
            )
        except (EvidenceEscrowError, TypeError, ValueError) as exc:
            return self._result(
                request,
                state="INVALID",
                evidence_id=evidence_id,
                details={"reason": type(exc).__name__, "fail_closed": True},
            )
