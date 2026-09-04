from __future__ import annotations

import pytest

from vertical_apps.industrial_claims.release_preflight import (
    ReleaseEvidence,
    ReleasePreflightError,
    evaluate_release_preflight,
)


SHA = "b8acd4585eee6390040652794284c4222f08c32b"


def _public_ready(**overrides) -> ReleaseEvidence:
    values = {
        "canonical_domain": "vindorum.com",
        "domain_owned": True,
        "tls_ready": True,
        "canonical_url": "https://vindorum.com",
        "deployment_project": "vindorum",
        "deployment_dedicated": True,
        "deployment_revision_sha": SHA,
        "expected_release_sha": SHA,
    }
    values.update(overrides)
    return ReleaseEvidence(**values)


def _paid_ready(**overrides) -> ReleaseEvidence:
    values = {
        **_public_ready().__dict__,
        "merchant_account_label": "VINDORUM merchant account",
        "merchant_identity_approved_for_vindorum": True,
        "live_billing_verified": True,
        "signed_webhook_roundtrip_verified": True,
        "secure_intake_ready": True,
    }
    values.update(overrides)
    return ReleaseEvidence(**values)


def test_empty_evidence_fails_closed_at_every_release_layer():
    result = evaluate_release_preflight(ReleaseEvidence())
    assert result.metadata_site_release_ready is False
    assert result.paid_scan_backend_ready is False
    assert result.commercial_launch_ready is False
    assert result.paid_scan_cta_may_be_enabled is False
    assert "DOMAIN_OWNERSHIP_UNVERIFIED" in result.public_blockers
    assert "LIVE_BILLING_UNVERIFIED" in result.paid_scan_blockers
    assert "DEDICATED_SENDER_UNVERIFIED" in result.commercial_blockers


def test_metadata_site_can_be_release_ready_without_claiming_paid_scan_is_live():
    result = evaluate_release_preflight(_public_ready())
    assert result.metadata_site_release_ready is True
    assert result.paid_scan_backend_ready is False
    assert result.commercial_launch_ready is False
    assert result.paid_scan_cta_may_be_enabled is False
    assert result.public_blockers == ()
    assert "LIVE_BILLING_UNVERIFIED" in result.paid_scan_blockers
    assert "SECURE_INTAKE_NOT_READY" in result.paid_scan_blockers


def test_exact_deployed_revision_is_required_for_public_release():
    result = evaluate_release_preflight(
        _public_ready(deployment_revision_sha="0" * 40)
    )
    assert result.metadata_site_release_ready is False
    assert "DEPLOYED_RELEASE_SHA_MISMATCH" in result.public_blockers


def test_canonical_url_must_be_https_and_on_the_canonical_domain():
    http = evaluate_release_preflight(_public_ready(canonical_url="http://vindorum.com"))
    foreign = evaluate_release_preflight(_public_ready(canonical_url="https://obrasignal.com"))
    assert "CANONICAL_URL_UNVERIFIED" in http.public_blockers
    assert "CANONICAL_URL_UNVERIFIED" in foreign.public_blockers


def test_paid_scan_requires_approved_merchant_identity_live_billing_webhook_and_secure_intake():
    result = evaluate_release_preflight(
        _public_ready(
            merchant_account_label="Obrasignal",
            merchant_identity_approved_for_vindorum=False,
            live_billing_verified=True,
            signed_webhook_roundtrip_verified=True,
            secure_intake_ready=True,
        )
    )
    assert result.paid_scan_backend_ready is False
    assert "MERCHANT_IDENTITY_NOT_APPROVED_FOR_VINDORUM" in result.paid_scan_blockers


def test_paid_cta_must_remain_locked_until_backend_is_really_ready():
    result = evaluate_release_preflight(_public_ready(paid_scan_cta_enabled=True))
    assert result.paid_scan_backend_ready is False
    assert result.commercial_launch_ready is False
    assert result.safety_blockers == ("PAID_SCAN_CTA_PREMATURELY_ENABLED",)


def test_paid_backend_can_be_ready_before_sender_and_full_commercial_launch():
    result = evaluate_release_preflight(_paid_ready())
    assert result.metadata_site_release_ready is True
    assert result.paid_scan_backend_ready is True
    assert result.paid_scan_cta_may_be_enabled is True
    assert result.commercial_launch_ready is False
    assert "DEDICATED_SENDER_UNVERIFIED" in result.commercial_blockers


def test_full_commercial_launch_requires_verified_sender_on_canonical_domain():
    wrong = evaluate_release_preflight(
        _paid_ready(sender_ready=True, sender_mailbox="sales@obrasignal.com", paid_scan_cta_enabled=True)
    )
    assert wrong.commercial_launch_ready is False
    assert "SENDER_DOMAIN_MISMATCH" in wrong.commercial_blockers

    ready = evaluate_release_preflight(
        _paid_ready(sender_ready=True, sender_mailbox="recovery@vindorum.com", paid_scan_cta_enabled=True)
    )
    assert ready.metadata_site_release_ready is True
    assert ready.paid_scan_backend_ready is True
    assert ready.commercial_launch_ready is True
    assert ready.safety_blockers == ()


def test_invalid_domain_input_is_rejected_instead_of_normalized_into_readiness():
    with pytest.raises(ReleasePreflightError, match="canonical domain is invalid"):
        evaluate_release_preflight(ReleaseEvidence(canonical_domain="https://vindorum.com"))


def test_serialized_decision_keeps_truth_boundaries_explicit():
    result = evaluate_release_preflight(_public_ready()).as_dict()
    assert result["product"] == "VINDORUM"
    assert result["truth_boundary"]["public_site_live_does_not_mean_paid_scan_live"] is True
    assert result["truth_boundary"]["paid_scan_backend_ready_does_not_prove_customer_payment"] is True
    assert result["truth_boundary"]["commercial_launch_ready_does_not_prove_buyer_interest"] is True
