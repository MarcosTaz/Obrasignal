from __future__ import annotations

import pytest

from vertical_apps.industrial_claims.proof_extensions import dual_digest
from vertical_apps.industrial_claims.proof_storage import (
    OriginalObjectReceipt,
    UnavailableOriginalEvidenceStore,
    verify_original_receipt,
)


def test_unconfigured_original_store_fails_closed():
    store = UnavailableOriginalEvidenceStore()
    with pytest.raises(RuntimeError, match="not configured"):
        store.put_immutable(
            tenant_id="tenant",
            evidence_id="e1",
            content=b"original",
            content_type="application/pdf",
            retention_until=None,
            legal_hold=False,
            metadata={},
        )


def test_original_receipt_detects_content_tampering():
    original = b"original bytes"
    digests = dual_digest(original)
    receipt = OriginalObjectReceipt(
        provider="object-store",
        object_ref="tenant/e1",
        version_ref="v1",
        sha256=digests["sha256"],
        sha512=digests["sha512"],
        byte_length=digests["byte_length"],
        retention_mode="COMPLIANCE",
        retention_until="2036-08-31T00:00:00Z",
        legal_hold=False,
        provider_receipt_ref="receipt-1",
        metadata={},
    )
    assert verify_original_receipt(original, receipt)["valid"] is True
    assert verify_original_receipt(original + b"x", receipt)["valid"] is False
