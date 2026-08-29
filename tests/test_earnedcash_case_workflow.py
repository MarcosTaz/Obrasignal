from decimal import Decimal

import pytest

from earnedcash.case_workflow import CaseState, transition_case


def test_open_case_requires_customer_approval_before_action():
    with pytest.raises(ValueError, match="customer approval required"):
        transition_case(
            current=CaseState.OPEN,
            target=CaseState.ACTION_APPROVED,
            amount=Decimal("1000"),
        )
    transition = transition_case(
        current=CaseState.OPEN,
        target=CaseState.ACTION_APPROVED,
        amount=Decimal("1000"),
        customer_approved=True,
    )
    assert transition.to_state == CaseState.ACTION_APPROVED


def test_recovery_request_requires_customer_approval():
    with pytest.raises(ValueError, match="customer approval required"):
        transition_case(
            current=CaseState.ACTION_APPROVED,
            target=CaseState.RECOVERY_REQUESTED,
            amount=Decimal("1000"),
        )


def test_settlement_requires_verified_settlement_evidence():
    with pytest.raises(ValueError, match="settlement evidence required"):
        transition_case(
            current=CaseState.RECOVERY_REQUESTED,
            target=CaseState.SETTLED,
            amount=Decimal("1000"),
        )


def test_paid_requires_verified_cash_evidence():
    with pytest.raises(ValueError, match="verified cash evidence required"):
        transition_case(
            current=CaseState.RECOVERY_REQUESTED,
            target=CaseState.PAID,
            amount=Decimal("1000"),
        )
    assert transition_case(
        current=CaseState.RECOVERY_REQUESTED,
        target=CaseState.PAID,
        amount=Decimal("1000"),
        cash_evidence_verified=True,
    ).to_state == CaseState.PAID


def test_nonzero_case_cannot_be_closed_as_zero():
    with pytest.raises(ValueError, match="non-zero"):
        transition_case(
            current=CaseState.OPEN,
            target=CaseState.CLOSED_ZERO,
            amount=Decimal("1"),
        )


def test_zero_case_can_close_zero():
    assert transition_case(
        current=CaseState.OPEN,
        target=CaseState.CLOSED_ZERO,
        amount=Decimal("0"),
    ).to_state == CaseState.CLOSED_ZERO


def test_terminal_paid_case_cannot_reopen():
    with pytest.raises(ValueError, match="invalid transition"):
        transition_case(
            current=CaseState.PAID,
            target=CaseState.OPEN,
            amount=Decimal("1000"),
        )
