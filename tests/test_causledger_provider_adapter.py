from __future__ import annotations

import pytest

from vertical_apps.industrial_claims.provider_adapter import (
    ProviderReceiptError,
    ProviderReceiptPolicy,
    ReceiptBoundProofProvider,
)
from vertical_apps.industrial_claims.proof_providers import ProofRequest


def _request() -> ProofRequest:
    return ProofRequest(
        tenant_id="tenant-a",
        subject_ref="finding-a",
        digest_algorithm="SHA-256",
        digest="a" * 64,
        purpose="CAUSLEDGER_PROOF_ATTESTATION_TARGET",
        metadata={"revision": 1},
    )


def _valid_response(**overrides):
    response = {
        "kind": "QUALIFIED_TIMESTAMP",
        "provider": "qualified-provider",
        "state": "VERIFIED",
        "digest_algorithm": "SHA-256",
        "digest": "a" * 64,
        "tenant_id": "tenant-a",
        "subject_ref": "finding-a",
        "purpose": "CAUSLEDGER_PROOF_ATTESTATION_TARGET",
        "provider_ref": "provider:receipt:1",
        "validation_ref": "provider:validation:1",
        "issued_at": "2026-08-31T23:00:00+00:00",
        "receipt_id": "receipt-1",
        "details": {"policy": "qualified"},
    }
    response.update(overrides)
    return response


def _provider(response):
    return ReceiptBoundProofProvider(
        policy=ProviderReceiptPolicy(
            kind="QUALIFIED_TIMESTAMP",
            provider="qualified-provider",
        ),
        transport=lambda _request: response,
    )


def test_verified_external_receipt_is_bound_to_exact_request():
    attestation = _provider(_valid_response()).attest(_request())
    assert attestation.verified is True
    assert attestation.digest == "a" * 64
    assert attestation.provider_ref == "provider:receipt:1"
    assert attestation.validation_ref == "provider:validation:1"
    assert attestation.details["binding_verified"] is True


@pytest.mark.parametrize(
    "override,match",
    [
        ({"digest": "b" * 64}, "digest does not match"),
        ({"digest_algorithm": "SHA-512", "digest": "b" * 128}, "digest does not match"),
        ({"kind": "QUALIFIED_SEAL"}, "kind does not match"),
        ({"provider": "lookalike-provider"}, "provider identity"),
        ({"tenant_id": "tenant-b"}, "context does not match"),
        ({"subject_ref": "finding-b"}, "context does not match"),
        ({"purpose": "OTHER_PURPOSE"}, "context does not match"),
    ],
)
def test_external_receipt_substitution_or_misbinding_is_rejected(override, match):
    with pytest.raises(ProviderReceiptError, match=match):
        _provider(_valid_response(**override)).attest(_request())


def test_verified_receipt_requires_validation_identity_and_time():
    for response in (
        _valid_response(provider_ref=None),
        _valid_response(validation_ref=None),
        _valid_response(issued_at=None),
    ):
        with pytest.raises(ProviderReceiptError):
            _provider(response).attest(_request())


def test_provider_outage_returns_unavailable_not_fake_verified():
    def broken(_request):
        raise TimeoutError("provider timeout")

    provider = ReceiptBoundProofProvider(
        policy=ProviderReceiptPolicy(kind="QUALIFIED_TIMESTAMP", provider="qualified-provider"),
        transport=broken,
    )
    attestation = provider.attest(_request())
    assert attestation.verified is False
    assert attestation.state == "UNAVAILABLE"
    assert attestation.provider_ref is None
    assert attestation.details["fail_closed"] is True
