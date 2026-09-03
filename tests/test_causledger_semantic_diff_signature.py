from __future__ import annotations

import pytest

from vertical_apps.industrial_claims.proof import ExternalAttestation
from vertical_apps.industrial_claims.semantic_diff_signature import (
    SemanticDiffSignatureError,
    build_signed_semantic_diff,
)


class RecordingSignatureProvider:
    kind = "QUALIFIED_SIGNATURE"
    name = "signature-provider"

    def __init__(self, *, state="VERIFIED", wrong_digest=False):
        self.state = state
        self.wrong_digest = wrong_digest
        self.request = None

    def attest(self, request):
        self.request = request
        return ExternalAttestation(
            kind=self.kind,
            provider=self.name,
            state=self.state,
            digest_algorithm="SHA-256",
            digest=("f" * 64 if self.wrong_digest else request.digest),
            provider_ref="signature-1" if self.state == "VERIFIED" else None,
            issued_at="2026-09-01T17:30:00+00:00" if self.state == "VERIFIED" else None,
            validation_ref="signature-validation-1" if self.state == "VERIFIED" else None,
            details={
                "subject_ref": request.subject_ref,
                "purpose": request.purpose,
            },
        )


def test_signed_semantic_diff_binds_exact_a_to_b_bytes():
    provider = RecordingSignatureProvider()
    result = build_signed_semantic_diff(
        tenant_id="tenant-a",
        finding_id="finding-a",
        before_ref="drawing-A",
        after_ref="drawing-B",
        before_text="hole=10mm\nmaterial=steel",
        after_text="hole=12mm\nmaterial=steel\nfinish=zinc",
        signature_provider=provider,
    )

    diff = result["semantic_diff"]
    assert diff["before_ref"] == "drawing-A"
    assert diff["after_ref"] == "drawing-B"
    assert diff["before_hashes"]["sha256"] != diff["after_hashes"]["sha256"]
    assert any("-hole=10mm" in line for line in diff["unified_diff"])
    assert any("+hole=12mm" in line for line in diff["unified_diff"])
    assert provider.request.payload is not None
    assert provider.request.digest == result["signing_target_sha256"]
    assert provider.request.purpose == "SIGNED_SEMANTIC_REVISION_DIFF"
    assert result["signature_verified"] is True
    assert result["truth_boundary"]["proves_exact_diff_signing_target"] is True
    assert result["truth_boundary"]["does_not_establish_commercial_meaning"] is True


def test_signature_over_another_digest_is_rejected():
    provider = RecordingSignatureProvider(wrong_digest=True)
    with pytest.raises(SemanticDiffSignatureError, match="exact signing target"):
        build_signed_semantic_diff(
            tenant_id="tenant-a",
            finding_id="finding-a",
            before_ref="A",
            after_ref="B",
            before_text="old",
            after_text="new",
            signature_provider=provider,
        )


def test_unavailable_signature_provider_never_claims_signed_diff():
    provider = RecordingSignatureProvider(state="UNAVAILABLE")
    result = build_signed_semantic_diff(
        tenant_id="tenant-a",
        finding_id="finding-a",
        before_ref="A",
        after_ref="B",
        before_text="old",
        after_text="new",
        signature_provider=provider,
    )
    assert result["signature_verified"] is False
    assert result["truth_boundary"]["proves_exact_diff_signing_target"] is False
