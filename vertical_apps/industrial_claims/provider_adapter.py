from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping

from vertical_apps.industrial_claims.proof import ExternalAttestation
from vertical_apps.industrial_claims.proof_providers import ProofRequest


_VERIFIED_STATES = {"VALID", "VERIFIED"}
_ALLOWED_ALGORITHMS = {"SHA-256": 64, "SHA-512": 128}


class ProviderReceiptError(RuntimeError):
    pass


def _required(value: object, *, label: str, max_chars: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_chars:
        raise ProviderReceiptError(f"invalid provider receipt {label}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise ProviderReceiptError(f"invalid provider receipt {label}")
    return text


def _digest(value: object, algorithm: str) -> str:
    digest = _required(value, label="digest", max_chars=256).lower()
    expected = _ALLOWED_ALGORITHMS.get(algorithm)
    if expected is None:
        raise ProviderReceiptError("unsupported provider receipt digest algorithm")
    if len(digest) != expected or any(ch not in "0123456789abcdef" for ch in digest):
        raise ProviderReceiptError("invalid provider receipt digest")
    return digest


def _aware_timestamp(value: object, *, label: str) -> str:
    text = _required(value, label=label, max_chars=128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderReceiptError(f"invalid provider receipt {label}") from exc
    if parsed.tzinfo is None:
        raise ProviderReceiptError(f"provider receipt {label} must include timezone")
    return parsed.isoformat()


@dataclass(frozen=True)
class ProviderReceiptPolicy:
    kind: str
    provider: str
    require_validation_ref: bool = True
    require_issued_at: bool = True

    def __post_init__(self) -> None:
        _required(self.kind, label="kind", max_chars=128)
        _required(self.provider, label="provider", max_chars=256)


class ReceiptBoundProofProvider:
    """Adapt an external trust provider without trusting its response blindly.

    ``transport`` performs the provider-specific network/API operation and returns
    a mapping. This adapter accepts a verified attestation only when the response
    is cryptographically bound to the exact request digest, algorithm, proof kind,
    tenant/subject context and purpose. Any ambiguity fails closed.
    """

    def __init__(
        self,
        *,
        policy: ProviderReceiptPolicy,
        transport: Callable[[ProofRequest], Mapping[str, Any]],
    ) -> None:
        self.kind = policy.kind
        self.name = policy.provider
        self.policy = policy
        self.transport = transport

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        algorithm = _required(request.digest_algorithm, label="request digest algorithm", max_chars=32).upper()
        expected_digest = _digest(request.digest, algorithm)
        tenant = _required(request.tenant_id, label="request tenant", max_chars=128)
        subject = _required(request.subject_ref, label="request subject")
        purpose = _required(request.purpose, label="request purpose", max_chars=256)

        try:
            response = self.transport(request)
        except Exception as exc:  # provider outage is not proof success
            return ExternalAttestation(
                kind=self.kind,
                provider=self.name,
                state="UNAVAILABLE",
                digest_algorithm=algorithm,
                digest=expected_digest,
                provider_ref=None,
                details={
                    "tenant_id": tenant,
                    "subject_ref": subject,
                    "purpose": purpose,
                    "fail_closed": True,
                    "provider_error_type": type(exc).__name__,
                },
            )
        if not isinstance(response, Mapping):
            raise ProviderReceiptError("provider receipt must be an object")

        response_kind = _required(response.get("kind"), label="kind", max_chars=128)
        response_provider = _required(response.get("provider"), label="provider", max_chars=256)
        response_state = _required(response.get("state"), label="state", max_chars=64).upper()
        response_algorithm = _required(response.get("digest_algorithm"), label="digest algorithm", max_chars=32).upper()
        response_digest = _digest(response.get("digest"), response_algorithm)
        response_tenant = _required(response.get("tenant_id"), label="tenant", max_chars=128)
        response_subject = _required(response.get("subject_ref"), label="subject")
        response_purpose = _required(response.get("purpose"), label="purpose", max_chars=256)

        if response_kind != self.kind:
            raise ProviderReceiptError("provider receipt kind does not match request")
        if response_provider != self.name:
            raise ProviderReceiptError("provider receipt provider identity does not match configured provider")
        if response_algorithm != algorithm or response_digest != expected_digest:
            raise ProviderReceiptError("provider receipt digest does not match request")
        if response_tenant != tenant or response_subject != subject or response_purpose != purpose:
            raise ProviderReceiptError("provider receipt context does not match request")

        provider_ref = str(response.get("provider_ref") or "").strip() or None
        validation_ref = str(response.get("validation_ref") or "").strip() or None
        issued_at_raw = response.get("issued_at")
        issued_at = _aware_timestamp(issued_at_raw, label="issued_at") if issued_at_raw else None

        if response_state in _VERIFIED_STATES:
            if not provider_ref:
                raise ProviderReceiptError("verified provider receipt requires provider_ref")
            if self.policy.require_validation_ref and not validation_ref:
                raise ProviderReceiptError("verified provider receipt requires validation_ref")
            if self.policy.require_issued_at and not issued_at:
                raise ProviderReceiptError("verified provider receipt requires issued_at")

        receipt_id = str(response.get("receipt_id") or "").strip() or None
        details = {
            "tenant_id": tenant,
            "subject_ref": subject,
            "purpose": purpose,
            "receipt_id": receipt_id,
            "request_metadata": dict(request.metadata),
            "provider_details": dict(response.get("details") or {}),
            "binding_verified": response_state in _VERIFIED_STATES,
        }
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state=response_state,
            digest_algorithm=algorithm,
            digest=expected_digest,
            provider_ref=provider_ref,
            issued_at=issued_at,
            validation_ref=validation_ref,
            details=details,
        )
