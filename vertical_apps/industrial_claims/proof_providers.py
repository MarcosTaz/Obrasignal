from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from vertical_apps.industrial_claims.proof import ExternalAttestation


@dataclass(frozen=True)
class ProofRequest:
    tenant_id: str
    subject_ref: str
    digest_algorithm: str
    digest: str
    purpose: str
    metadata: Mapping[str, Any]


class ProofProvider(Protocol):
    kind: str
    name: str

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        ...


class UnavailableProofProvider:
    """Fail-closed provider used until a real external trust service is configured."""

    def __init__(self, *, kind: str, name: str = "UNCONFIGURED") -> None:
        self.kind = kind
        self.name = name

    def attest(self, request: ProofRequest) -> ExternalAttestation:
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state="UNAVAILABLE",
            digest_algorithm=request.digest_algorithm,
            digest=request.digest,
            provider_ref=None,
            details={
                "tenant_id": request.tenant_id,
                "subject_ref": request.subject_ref,
                "purpose": request.purpose,
                "fail_closed": True,
                **dict(request.metadata),
            },
        )


@dataclass(frozen=True)
class ProofProviderBundle:
    qualified_timestamp: ProofProvider
    qualified_seal: ProofProvider
    qualified_signature: ProofProvider
    worm_lock: ProofProvider
    public_anchor: ProofProvider
    evidence_escrow: ProofProvider

    @classmethod
    def fail_closed(cls) -> "ProofProviderBundle":
        return cls(
            qualified_timestamp=UnavailableProofProvider(kind="QUALIFIED_TIMESTAMP"),
            qualified_seal=UnavailableProofProvider(kind="QUALIFIED_SEAL"),
            qualified_signature=UnavailableProofProvider(kind="QUALIFIED_SIGNATURE"),
            worm_lock=UnavailableProofProvider(kind="WORM_LOCK"),
            public_anchor=UnavailableProofProvider(kind="PUBLIC_ANCHOR"),
            evidence_escrow=UnavailableProofProvider(kind="EVIDENCE_ESCROW"),
        )
