from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from vertical_apps.industrial_claims.proof_extensions import dual_digest


@dataclass(frozen=True)
class OriginalObjectReceipt:
    provider: str
    object_ref: str
    version_ref: str
    sha256: str
    sha512: str
    byte_length: int
    retention_mode: str
    retention_until: str | None
    legal_hold: bool
    provider_receipt_ref: str
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.provider or not self.object_ref or not self.version_ref or not self.provider_receipt_ref:
            raise ValueError("immutable original receipt requires provider/object/version/receipt identity")
        if len(self.sha256) != 64 or len(self.sha512) != 128:
            raise ValueError("immutable original receipt digests are invalid")
        if self.byte_length < 0:
            raise ValueError("immutable original receipt byte length is invalid")
        if self.retention_mode not in {"COMPLIANCE", "GOVERNANCE", "LEGAL_HOLD"}:
            raise ValueError("immutable original receipt retention mode is invalid")
        if self.retention_mode == "COMPLIANCE" and not self.retention_until:
            raise ValueError("compliance retention requires retention_until")


class OriginalEvidenceStore(Protocol):
    name: str

    def put_immutable(
        self,
        *,
        tenant_id: str,
        evidence_id: str,
        content: bytes,
        content_type: str,
        retention_until: str | None,
        legal_hold: bool,
        metadata: Mapping[str, Any],
    ) -> OriginalObjectReceipt:
        ...

    def read_immutable_version(
        self,
        *,
        tenant_id: str,
        evidence_id: str,
        object_ref: str,
        version_ref: str,
    ) -> bytes:
        """Return the exact stored bytes for the immutable version named by the receipt."""
        ...


class UnavailableOriginalEvidenceStore:
    name = "UNCONFIGURED"

    def put_immutable(
        self,
        *,
        tenant_id: str,
        evidence_id: str,
        content: bytes,
        content_type: str,
        retention_until: str | None,
        legal_hold: bool,
        metadata: Mapping[str, Any],
    ) -> OriginalObjectReceipt:
        raise RuntimeError("secure immutable original-evidence storage is not configured")

    def read_immutable_version(
        self,
        *,
        tenant_id: str,
        evidence_id: str,
        object_ref: str,
        version_ref: str,
    ) -> bytes:
        raise RuntimeError("secure immutable original-evidence storage is not configured")


def verify_original_receipt(content: bytes | bytearray | memoryview, receipt: OriginalObjectReceipt) -> dict[str, Any]:
    digests = dual_digest(bytes(content))
    errors: list[str] = []
    if digests["sha256"] != receipt.sha256:
        errors.append("ORIGINAL_SHA256_MISMATCH")
    if digests["sha512"] != receipt.sha512:
        errors.append("ORIGINAL_SHA512_MISMATCH")
    if digests["byte_length"] != receipt.byte_length:
        errors.append("ORIGINAL_BYTE_LENGTH_MISMATCH")
    return {
        "valid": not errors,
        "errors": errors,
        "provider": receipt.provider,
        "object_ref": receipt.object_ref,
        "version_ref": receipt.version_ref,
        "provider_receipt_ref": receipt.provider_receipt_ref,
    }
