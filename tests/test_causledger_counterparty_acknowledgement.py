from __future__ import annotations

import pytest

from vertical_apps.industrial_claims.counterparty_acknowledgement import (
    CounterpartyAcknowledgementError,
    build_fact_acknowledgement_request,
    verify_counterparty_fact_acknowledgement,
)


def _request():
    return build_fact_acknowledgement_request(
        tenant_id="tenant-a",
        finding_id="finding-a",
        evidence_id="evidence-a",
        evidence_sha256="a" * 64,
        fact_id="fact-request-r17",
        fact_type="CHANGE_INSTRUCTION",
        fact_value="Change R17 was requested on drawing revision B.",
    )


def _receipt(request, *, decision="CONFIRMED"):
    return {
        "request_sha256": request["request_sha256"],
        "counterparty_ref": "customer-legal-entity-a",
        "signer_ref": "customer-user-42",
        "decision": decision,
        "signed_at": "2026-09-01T17:15:00+00:00",
        "validation_ref": "identity-validation-42",
        "signature_algorithm": "TEST-SIGNATURE",
        "signature": "signed-receipt-token",
    }


def test_confirmed_fact_is_signed_without_admitting_liability_or_debt():
    request = _request()
    seen = {}

    def verifier(payload, signature, signer_ref):
        seen["payload"] = payload
        seen["signature"] = signature
        seen["signer_ref"] = signer_ref
        return True

    attestation = verify_counterparty_fact_acknowledgement(
        request_payload=request,
        receipt=_receipt(request),
        signature_verifier=verifier,
    )

    assert attestation.state == "VERIFIED"
    assert attestation.kind == "COUNTERPARTY_ACKNOWLEDGEMENT"
    assert attestation.digest == "a" * 64
    assert attestation.details["evidence_id"] == "evidence-a"
    assert attestation.details["fact_confirmation_only"] is True
    assert attestation.details["does_not_admit_liability"] is True
    assert attestation.details["does_not_admit_debt"] is True
    assert attestation.details["does_not_accept_recovery_amount"] is True
    assert attestation.details["does_not_waive_rights_or_defences"] is True
    assert attestation.details["acknowledgement_does_not_itself_establish_legal_recoverability"] is True
    assert seen["signature"] == "signed-receipt-token"
    assert seen["signer_ref"] == "customer-user-42"


def test_disputed_fact_is_preserved_but_never_becomes_verified_acknowledgement():
    request = _request()
    attestation = verify_counterparty_fact_acknowledgement(
        request_payload=request,
        receipt=_receipt(request, decision="DISPUTED"),
        signature_verifier=lambda *_args: True,
    )
    assert attestation.state == "DISPUTED"
    assert attestation.verified is False
    assert attestation.provider_ref is None
    assert attestation.details["decision"] == "DISPUTED"


def test_receipt_for_another_request_fails_closed():
    request = _request()
    receipt = _receipt(request)
    receipt["request_sha256"] = "b" * 64
    with pytest.raises(CounterpartyAcknowledgementError, match="another request"):
        verify_counterparty_fact_acknowledgement(
            request_payload=request,
            receipt=receipt,
            signature_verifier=lambda *_args: True,
        )


def test_invalid_counterparty_signature_fails_closed():
    request = _request()
    with pytest.raises(CounterpartyAcknowledgementError, match="signature is invalid"):
        verify_counterparty_fact_acknowledgement(
            request_payload=request,
            receipt=_receipt(request),
            signature_verifier=lambda *_args: False,
        )


def test_removing_no_liability_boundary_invalidates_the_request():
    request = _request()
    request["legal_effect_boundary"]["does_not_admit_liability"] = False
    # Recompute neither digest: mutation must be detected before any signature can
    # turn the altered semantics into an apparently valid acknowledgement.
    with pytest.raises(CounterpartyAcknowledgementError, match="SHA-256 mismatch"):
        verify_counterparty_fact_acknowledgement(
            request_payload=request,
            receipt=_receipt(request),
            signature_verifier=lambda *_args: True,
        )
