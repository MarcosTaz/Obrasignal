from __future__ import annotations

from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import OriginalObjectReceipt
from vertical_apps.industrial_claims.secure_capture import (
    CaptureIdentity,
    SourceAuthenticationReceipt,
    capture_original_evidence,
)


class RetentionStore:
    name = "retention-test"

    def __init__(self, mode: str, *, legal_hold: bool = False):
        self.mode = mode
        self.legal_hold = legal_hold
        self._stored: dict[tuple[str, str], bytes] = {}

    def put_immutable(self, *, tenant_id, evidence_id, content, content_type, retention_until, legal_hold, metadata):
        digests = dual_digest(content)
        object_ref = f"{tenant_id}/{evidence_id}"
        self._stored[(object_ref, "v1")] = content
        return OriginalObjectReceipt(
            provider=self.name,
            object_ref=object_ref,
            version_ref="v1",
            sha256=digests["sha256"],
            sha512=digests["sha512"],
            byte_length=digests["byte_length"],
            retention_mode=self.mode,
            retention_until=(retention_until or "2036-09-01T00:00:00Z") if self.mode == "COMPLIANCE" else retention_until,
            legal_hold=self.legal_hold,
            provider_receipt_ref=f"receipt-{self.mode.lower()}",
            metadata=dict(metadata),
        )

    def read_immutable_version(self, *, tenant_id, evidence_id, object_ref, version_ref):
        return self._stored[(object_ref, version_ref)]


def _capture(store):
    return capture_original_evidence(
        original_store=store,
        evidence_id="tenant-a:e1",
        identity=CaptureIdentity(
            tenant_id="tenant-a",
            actor_id="actor-a",
            subject="subject-a",
            amr=("webauthn",),
        ),
        source_type="document",
        source_ref="customer-change-17.pdf",
        content=b"customer-directed change evidence",
        content_type="application/pdf",
        source_authentication=SourceAuthenticationReceipt(
            state="UNVERIFIED",
            scheme="UPLOAD",
            provider="causledger-intake",
        ),
        retention_until="2036-09-01T00:00:00Z",
    )


def test_compliance_retention_is_the_only_ordinary_mode_exposed_as_worm_locked():
    captured = _capture(RetentionStore("COMPLIANCE"))
    assert captured.evidence.metadata["original_version_readback_verified"] is True
    assert captured.evidence.metadata["immutability"] == "WORM_LOCKED"
    assert captured.evidence.metadata["worm_lock_verified"] is True


def test_governance_retention_never_claims_worm_lock():
    captured = _capture(RetentionStore("GOVERNANCE"))
    assert captured.evidence.metadata["original_version_readback_verified"] is True
    assert captured.evidence.metadata["immutability"] == "GOVERNANCE_RETENTION"
    assert captured.evidence.metadata["worm_lock_verified"] is False


def test_legal_hold_is_reported_separately_from_worm_lock():
    captured = _capture(RetentionStore("LEGAL_HOLD", legal_hold=True))
    assert captured.evidence.metadata["original_version_readback_verified"] is True
    assert captured.evidence.metadata["immutability"] == "LEGAL_HOLD"
    assert captured.evidence.metadata["worm_lock_verified"] is False
    assert captured.evidence.metadata["original_legal_hold"] is True
