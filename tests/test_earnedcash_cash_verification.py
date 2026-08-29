from decimal import Decimal

import pytest

from earnedcash.cash_verification import (
    CashEvidence,
    CashEvidenceKind,
    CashVerificationState,
    verify_cash_evidence,
)


def evidence(**overrides):
    values = dict(
        evidence_ref="bank:tx-1",
        kind=CashEvidenceKind.BANK_RECEIPT,
        tenant_id="tenant-1",
        project_id="project-1",
        currency="GBP",
        amount=Decimal("1000"),
        independently_verified=True,
    )
    values.update(overrides)
    return CashEvidence(**values)


def verify(item, *, claimed_amount=Decimal("1000"), tenant_id="tenant-1",
           project_id="project-1", currency="GBP"):
    return verify_cash_evidence(
        tenant_id=tenant_id,
        project_id=project_id,
        currency=currency,
        claimed_amount=claimed_amount,
        evidence=item,
    )


def test_exact_scope_bank_receipt_match_is_verified():
    result = verify(evidence())
    assert result.state == CashVerificationState.VERIFIED
    assert result.verified_amount == Decimal("1000")
    assert result.evidence_ref == "bank:tx-1"
    assert result.reason == "EXACT_SCOPE_AMOUNT_MATCH"


def test_credit_note_never_counts_as_verified_cash():
    result = verify(
        evidence(kind=CashEvidenceKind.CREDIT_NOTE, evidence_ref="credit:cn-1")
    )
    assert result.state == CashVerificationState.MISMATCH
    assert result.verified_amount == Decimal("0")
    assert result.evidence_ref == "credit:cn-1"
    assert result.reason == "NON_CASH_EVIDENCE_KIND"


def test_self_attested_evidence_never_verifies_cash():
    result = verify(evidence(independently_verified=False))
    assert result.state == CashVerificationState.UNKNOWN
    assert result.verified_amount == Decimal("0")
    assert result.reason == "EVIDENCE_NOT_INDEPENDENTLY_VERIFIED"


@pytest.mark.parametrize(
    "item,kwargs",
    [
        (evidence(tenant_id="other"), {}),
        (evidence(project_id="other"), {}),
        (evidence(currency="EUR"), {}),
        (evidence(amount=Decimal("999.99")), {}),
        (evidence(), {"tenant_id": "other"}),
        (evidence(), {"project_id": "other"}),
        (evidence(), {"currency": "EUR"}),
        (evidence(), {"claimed_amount": Decimal("999.99")}),
    ],
)
def test_any_scope_or_amount_mismatch_fails_closed(item, kwargs):
    result = verify(item, **kwargs)
    assert result.state == CashVerificationState.MISMATCH
    assert result.verified_amount == Decimal("0")
    assert result.reason == "CASH_EVIDENCE_SCOPE_OR_AMOUNT_MISMATCH"


def test_blank_evidence_reference_is_unknown():
    result = verify(evidence(evidence_ref="   "))
    assert result.state == CashVerificationState.UNKNOWN
    assert result.verified_amount == Decimal("0")
    assert result.evidence_ref is None
    assert result.reason == "EVIDENCE_REFERENCE_MISSING"


def test_nonfinite_evidence_amount_is_unknown():
    result = verify(evidence(amount=Decimal("NaN")))
    assert result.state == CashVerificationState.UNKNOWN
    assert result.verified_amount == Decimal("0")
    assert result.reason == "INVALID_EVIDENCE_AMOUNT"


def test_invalid_claimed_amount_is_rejected():
    with pytest.raises(ValueError, match="invalid claimed amount"):
        verify(evidence(), claimed_amount=Decimal("NaN"))
    with pytest.raises(ValueError, match="invalid claimed amount"):
        verify(evidence(), claimed_amount=Decimal("-1"))
